"""Full interaction system -- awareness, scoring, interaction types, conversations, overhearing, avoidance."""

import logging
import random
import math
import re
import uuid

logger = logging.getLogger("agentica.interactions")

VISUAL_RANGE = 8
INDOOR_RANGE = 4
CONVERSATION_RANGE = 3
OVERHEAR_RANGE = 4
BUILDING_ENTRANCE_RANGE = 2
MAX_ATTENTION_SLOTS = 4


def _contains_non_latin_dialogue(text: str) -> bool:
    if not text:
        return False
    if re.search(r"[\u0400-\u04FF]", text):
        return True
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return False
    non_ascii_letters = sum(1 for ch in letters if ord(ch) > 127)
    return (non_ascii_letters / max(len(letters), 1)) > 0.2


def _english_fallback_line(result: dict) -> str:
    actionable = result.get("actionable")
    if isinstance(actionable, dict) and actionable.get("description"):
        desc = str(actionable["description"]).strip()
        if desc:
            return f"Let me say it plainly: {desc}"

    tone = str(result.get("tone", "casual")).lower()
    if tone == "warm":
        return "I'm trying to say this clearly: I want us to understand each other."
    if tone == "tense":
        return "Let me be clear, because this matters to me."
    if tone == "hesitant":
        return "I'm not saying this well, but here's what I mean."
    return "Let me put that more clearly."


def _force_english_dialogue(result: dict, speaker_name: str) -> dict:
    speech = str(result.get("speech", "") or "")
    if _contains_non_latin_dialogue(speech):
        logger.warning("Normalized non-English dialogue for %s: %r", speaker_name, speech[:120])
        result["speech"] = _english_fallback_line(result)
    return result


def _is_inside_building(agent, world) -> bool:
    loc = world.locations.get(agent.current_location)
    return loc is not None and loc.get("type") == "built_structure"


def _near_entrance(agent, world) -> bool:
    loc = world.locations.get(agent.current_location)
    if not loc:
        return True
    entry = world.get_location_entry(agent.current_location)
    ax, ay = agent.position
    return abs(ax - entry[0]) + abs(ay - entry[1]) <= BUILDING_ENTRANCE_RANGE


class AwarenessSystem:
    """Determines which agents each agent can perceive."""

    def get_perceived(self, agent, all_agents: dict, world) -> list[dict]:
        perceived = []
        ax, ay = agent.position
        agent_indoors = _is_inside_building(agent, world)
        agent_near_entrance = _near_entrance(agent, world) if agent_indoors else True

        for other_id, other in all_agents.items():
            if other_id == agent.id:
                continue
            ox, oy = other.position
            dist = abs(ax - ox) + abs(ay - oy)
            same_loc = agent.current_location == other.current_location

            # Indoor/outdoor visibility
            other_indoors = _is_inside_building(other, world)
            if agent_indoors and not other_indoors:
                if not agent_near_entrance:
                    continue
                effective_range = BUILDING_ENTRANCE_RANGE
            elif not agent_indoors and other_indoors:
                if not _near_entrance(other, world):
                    continue
                effective_range = BUILDING_ENTRANCE_RANGE
            elif same_loc:
                effective_range = INDOOR_RANGE if agent_indoors else VISUAL_RANGE
            else:
                effective_range = VISUAL_RANGE

            if dist > effective_range:
                continue

            attention = self._attention_weight(agent, other, dist, same_loc)
            perceived.append({
                "agent": other,
                "distance": dist,
                "attention": attention,
                "can_talk": dist <= CONVERSATION_RANGE,
                "can_overhear": dist <= OVERHEAR_RANGE,
                "same_location": same_loc,
            })

        perceived.sort(key=lambda x: -x["attention"])
        # Attention competition: agents can only focus on a few things at once
        if len(perceived) > MAX_ATTENTION_SLOTS:
            cutoff = perceived[MAX_ATTENTION_SLOTS - 1]["attention"] * 0.5
            perceived = [p for p in perceived if p["attention"] >= cutoff][:MAX_ATTENTION_SLOTS + 2]
        return perceived

    def _attention_weight(self, agent, other, distance: int, same_loc: bool) -> float:
        weight = 0.0

        rel = agent.relationships.get(other.name)
        if rel:
            # Notice friends/enemies more (observer-specific weighting)
            sentiment_diff = abs(rel.get("sentiment", 0.5) - 0.5)
            familiarity = rel.get("familiarity", 0)
            weight += sentiment_diff * 0.4
            weight += familiarity * 0.2

        weight += (1.0 / (1.0 + distance * 0.3)) * 0.2

        dom_em, intensity = other.emotional_state.get_dominant_emotion()
        if dom_em in ("sad", "anxious", "angry") and intensity > 0.4:
            weight += agent.profile.personality.get("agreeableness", 0.5) * 0.3

        for goal in agent.active_goals:
            if other.name.lower() in goal.get("text", "").lower():
                weight += 0.4

        return max(0.0, weight)


class InteractionDecider:
    """Determines whether an agent should initiate interaction."""

    def should_interact(self, agent, perceived: list[dict]) -> tuple[bool, object | None, str]:
        if not perceived or getattr(agent, "is_in_conversation", False):
            return False, None, ""

        best_score = 0.0
        best_target = None
        best_reason = ""

        for p in perceived:
            other = p["agent"]
            if (
                not p["can_talk"]
                or getattr(other, "is_in_conversation", False)
                or getattr(other, "current_action", None).value == "sleeping"
            ):
                continue

            score, reason = self._score(agent, other, p)
            if score > best_score:
                best_score = score
                best_target = other
                best_reason = reason

        # Personality threshold — lower = more social
        threshold = 0.08 + (1.0 - agent.profile.personality.get("extraversion", 0.5)) * 0.12
        if agent.drives.social_need > 0.2:
            threshold -= 0.12
        if agent.emotional_state.anxiety > 0.5:
            threshold += 0.05

        if best_score > threshold:
            return True, best_target, best_reason
        return False, None, ""

    def _score(self, agent, other, perceived: dict) -> tuple[float, str]:
        score = 0.0
        reasons = []

        rel = agent.relationships.get(other.name, {})
        familiarity = rel.get("familiarity", 0)
        sentiment = rel.get("sentiment", 0.5)

        # Drive alignment: social need
        if agent.drives.social_need > 0.2:
            score += agent.drives.social_need * 0.55
            reasons.append("want to connect")

        # Drive alignment: hunger + other has food -> ask for help / trade
        if agent.drives.hunger > 0.5 and other.inventory:
            from systems.economy import FOOD_ITEMS
            if any(i.get("name") in FOOD_ITEMS for i in other.inventory):
                score += 0.35
                reasons.append("they might have food")

        # Drive alignment: shelter need + other has building skill
        if agent.drives.shelter_need > 0.4:
            other_build = getattr(other, "skill_memory", None)
            if other_build and other_build.activities.get("construction", {}).get("skill_level", 0) > 0.3:
                score += 0.25
                reasons.append("need building help")

        # Goal relevance: agent has active goals mentioning other
        for goal in agent.active_goals:
            if other.name.lower() in goal.get("text", "").lower():
                score += 0.4
                reasons.append("goal involves them")
                break

        # Curiosity about strangers
        if familiarity < 0.1:
            score += 0.3 * agent.profile.personality.get("openness", 0.5)
            reasons.append("haven't met yet")

        # Friends
        if sentiment > 0.5:
            score += 0.25
            reasons.append("friend nearby")

        # Both idle at same location
        if agent.current_action.value == "idle" and other.current_action.value == "idle":
            if perceived.get("same_location"):
                score += 0.5
                reasons.append("both idle together")
            else:
                score += 0.22
                reasons.append("both idle nearby")

        # Emotional triggers
        dom_em, intensity = other.emotional_state.get_dominant_emotion()
        if dom_em in ("sad", "anxious") and intensity > 0.4:
            score += agent.profile.personality.get("agreeableness", 0.5) * 0.3
            reasons.append("they seem upset")

        # Agent is angry at other -> confront
        agent_em, agent_intensity = agent.emotional_state.get_dominant_emotion()
        if agent_em == "angry" and agent_intensity > 0.4 and sentiment < 0.35:
            score += 0.3
            reasons.append("unresolved tension")

        # Unresolved conflicts
        if any(c.get("with") == other.name and c.get("status") == "active" for c in getattr(agent, "active_conflicts", [])):
            score += 0.2
            reasons.append("unresolved conflict")

        # Negative modifiers
        if sentiment < 0.2:
            score -= 0.2

        return max(0.0, score), reasons[0] if reasons else "proximity"


INTERACTION_TYPES = {
    "acknowledge": {"turns": (0, 0), "llm": False},
    "greeting": {"turns": (1, 2), "llm": False},
    "small_talk": {"turns": (2, 4), "llm": False},
    "info": {"turns": (3, 5), "llm": True},
    "request": {"turns": (2, 4), "llm": True},
    "negotiation": {"turns": (3, 8), "llm": True},
    "trade": {"turns": (2, 5), "llm": True},
    "deep": {"turns": (5, 12), "llm": True},
    "argument": {"turns": (3, 8), "llm": True},
    "comforting": {"turns": (3, 8), "llm": True},
    "planning": {"turns": (3, 8), "llm": True},
    "gossip": {"turns": (2, 6), "llm": True},
    "teach": {"turns": (3, 6), "llm": True},
    "ask_for_help": {"turns": (2, 5), "llm": True},
    "offer_help": {"turns": (2, 4), "llm": True},
    "confront": {"turns": (3, 8), "llm": True},
    "collaborate": {"turns": (3, 8), "llm": True},
    "propose": {"turns": (3, 6), "llm": True},
    "observe": {"turns": (0, 0), "llm": False},
    "avoid": {"turns": (0, 0), "llm": False},
}


def _agents_have_complementary_inventory(agent, other) -> bool:
    """Check if agents have items the other might want."""
    from systems.economy import FOOD_ITEMS, BUILDING_ITEMS
    agent_has_food = any(i.get("name") in FOOD_ITEMS for i in agent.inventory)
    agent_has_building = any(i.get("name") in BUILDING_ITEMS for i in agent.inventory)
    other_has_food = any(i.get("name") in FOOD_ITEMS for i in other.inventory)
    other_has_building = any(i.get("name") in BUILDING_ITEMS for i in other.inventory)

    # One has food surplus + needs building, the other has building surplus + needs food
    if agent_has_food and other_has_building and agent.drives.shelter_need > 0.3:
        return True
    if agent_has_building and other_has_food and agent.drives.hunger > 0.3:
        return True
    # Both have different items
    if agent_has_food != other_has_food or agent_has_building != other_has_building:
        return True
    return False


def select_interaction_type(agent, other, reason: str, rel: dict) -> str:
    familiarity = rel.get("familiarity", 0.1)
    sentiment = rel.get("sentiment", 0.5)

    if reason == "they seem upset":
        return "comforting"

    if reason == "unresolved tension" or reason == "unresolved conflict":
        return "confront" if sentiment < 0.3 else "argument"

    if reason == "they might have food":
        return "trade" if familiarity > 0.1 else "ask_for_help"

    if reason == "need building help":
        return "ask_for_help" if familiarity > 0.1 else "info"

    if reason == "goal involves them":
        return "collaborate" if familiarity > 0.2 else "propose"

    # Trade when one agent is in need and the other has what they want
    if familiarity > 0.05 and _agents_have_complementary_inventory(agent, other):
        if agent.drives.hunger > 0.4 or agent.drives.shelter_need > 0.4:
            return "trade"

    if reason == "haven't met yet":
        return "info"

    if reason == "both idle together":
        if familiarity < 0.15:
            return "info"
        elif familiarity < 0.4:
            return "small_talk"
        else:
            return "planning"

    if reason == "want to connect":
        if familiarity < 0.1:
            return "greeting"
        elif familiarity < 0.3:
            return "info"
        else:
            return "deep"

    if reason == "friend nearby" and sentiment > 0.5:
        return "deep" if familiarity > 0.3 else "small_talk"

    # Teach: agent has high skill and other is doing the same activity poorly
    if familiarity > 0.2:
        agent_skills = getattr(agent, "skill_memory", None)
        other_skills = getattr(other, "skill_memory", None)
        if agent_skills and other_skills:
            for activity, data in agent_skills.activities.items():
                if data.get("skill_level", 0) > 0.6:
                    other_level = other_skills.activities.get(activity, {}).get("skill_level", 0)
                    if other_level < 0.3 and random.random() < 0.2:
                        return "teach"

    # Offer help: high agreeableness + other is struggling
    if agent.profile.personality.get("agreeableness", 0.5) > 0.6:
        if other.drives.hunger > 0.6 or other.drives.rest > 0.7:
            if familiarity > 0.1 and random.random() < 0.3:
                return "offer_help"

    # Gossip: familiar agents who have memories about third parties
    if familiarity > 0.3:
        third_party_memories = [
            e for e in agent.episodic_memory.recent(15)
            if e.agents_involved
            and other.name not in e.agents_involved
            and agent.name not in e.agents_involved[:1]
        ]
        hearsay_beliefs = [b for b in agent.belief_system.beliefs if getattr(b, "source_type", "") == "hearsay"]
        if (third_party_memories or hearsay_beliefs):
            extraversion = agent.profile.personality.get("extraversion", 0.5)
            if random.random() < extraversion * 0.3:
                return "gossip"

    if familiarity < 0.05:
        return "greeting"

    return "info" if familiarity < 0.2 else "small_talk"


class LightweightInteraction:
    """Template-based greetings and small talk — no LLM needed."""

    GREETINGS_WARM = [
        "Hey {name}! Good to see you.",
        "{name}! How are things?",
        "Morning, {name}.",
    ]
    GREETINGS_NEUTRAL = [
        "Hello, {name}.",
        "Hey there.",
        "Hi.",
    ]
    GREETINGS_COLD = [
        "{name}.",
        "Oh. Hello.",
    ]
    SMALL_TALK = [
        "How's your day going?",
        "Found anything interesting around here?",
        "This place has potential, don't you think?",
        "Have you been to the river? Lots of fish there.",
        "The forest has good berries if you're hungry.",
        "I wonder if we should start building shelters soon.",
        "It's a beautiful spot, isn't it?",
    ]

    def generate_greeting(self, agent, other, rel: dict, time_of_day: str) -> str:
        sentiment = rel.get("sentiment", 0.5) if rel else 0.5
        name = other.name.split()[0]
        if sentiment > 0.5:
            return random.choice(self.GREETINGS_WARM).format(name=name)
        elif sentiment < 0.2:
            return random.choice(self.GREETINGS_COLD).format(name=name)
        return random.choice(self.GREETINGS_NEUTRAL).format(name=name)

    def generate_small_talk(self, agent) -> str:
        return random.choice(self.SMALL_TALK)


class OverhearingSystem:
    """Agents near conversations catch fragments."""

    DISTORTIONS = [
        lambda w: w.replace("might", "will"),
        lambda w: w.replace("some", "a lot of"),
        lambda w: w.replace("maybe", "definitely"),
        lambda w: w.replace("think", "know"),
        lambda w: w.replace("could", "should"),
    ]

    def process(self, observer, speakers: list[str], speech: str, distance: int, is_argument: bool = False) -> dict | None:
        catch_prob = max(0.2, 1.0 - distance * 0.25)
        if is_argument:
            catch_prob = min(1.0, catch_prob + 0.3)

        if random.random() > catch_prob:
            return None

        # Extract fragment
        words = speech.split()
        if len(words) <= 4:
            fragment = speech
        else:
            chunk = random.randint(3, min(6, len(words)))
            start = random.randint(0, len(words) - chunk)
            fragment = "..." + " ".join(words[start:start + chunk]) + "..."

        # Distortion: overheard info sometimes wrong/incomplete
        confidence = round(random.uniform(0.2, 0.4), 2)
        if random.random() < 0.3:
            distortion = random.choice(self.DISTORTIONS)
            fragment = distortion(fragment)
            confidence = round(confidence * 0.7, 2)

        # Check if observer's name is mentioned -- name-triggered anxiety
        mentioned = observer.name.lower() in speech.lower() or observer.name.split()[0].lower() in speech.lower()
        if mentioned:
            observer.emotional_state.apply_event("gossip_about_self", 0.5)
            observer.emotional_state.apply_event("anxiety", 0.3)
            observer.working_memory.push(
                f"I think {' and '.join(speakers[:2])} are talking about me",
                priority=0.8,
            )

        # Store overheard info in belief system with low confidence
        if hasattr(observer, "belief_system"):
            observer.belief_system.add(
                f"Overheard {' and '.join(speakers[:2])}: {fragment}",
                category="hearsay",
                confidence=confidence,
                source="overheard",
                source_agent=speakers[0] if speakers else "someone",
            )

        # Store in episodic memory
        if hasattr(observer, "episodic_memory"):
            observer.episodic_memory.add_simple(
                f"Overheard {' and '.join(speakers[:2])} say: {fragment}",
                tick=0, day=0, time_of_day="",
                location="", category="observation",
                intensity=0.3 if not mentioned else 0.6,
                emotion="curious" if not mentioned else "anxious",
                agents=speakers[:2],
            )

        return {
            "fragment": fragment,
            "speakers": speakers,
            "mentioned_self": mentioned,
            "confidence": confidence,
        }


class Conversation:
    """LLM-powered conversation with cognitive context."""

    def __init__(self, initiator, target, interaction_type: str, reason: str, location: str):
        self.participants = [initiator.name, target.name]
        self.interaction_type = interaction_type
        self.location = location
        self.reason = reason
        self.turns: list[dict] = []
        self.is_active = True
        self.structured_commitments: list[dict] = []
        self.structured_proposals: list[dict] = []
        type_info = INTERACTION_TYPES.get(interaction_type, {"turns": (2, 4)})
        self.max_turns = random.randint(*type_info["turns"])

    def _inventory_summary(self, agent) -> str:
        if not agent.inventory:
            return "nothing"
        counts: dict[str, int] = {}
        for item in agent.inventory:
            name = item.get("name", "unknown")
            counts[name] = counts.get(name, 0) + int(item.get("quantity", 1))
        return ", ".join(f"{qty} {name.replace('_', ' ')}" for name, qty in counts.items())

    def _gossip_context(self, speaker, listener) -> str:
        if self.interaction_type != "gossip":
            return ""
        pieces = []
        # Recent memories involving third parties
        for ep in speaker.episodic_memory.recent(20):
            for name in ep.agents_involved:
                if name != speaker.name and name != listener.name:
                    pieces.append(f"- About {name}: {ep.content[:80]} (felt {ep.primary_emotion or 'neutral'})")
                    break
            if len(pieces) >= 3:
                break
        # Hearsay beliefs
        for b in speaker.belief_system.beliefs:
            if getattr(b, "source_type", "") == "hearsay" and listener.name.lower() not in b.content.lower():
                pieces.append(f"- Heard from {getattr(b, 'source_agent', 'someone')}: {b.content[:80]}")
            if len(pieces) >= 5:
                break
        if not pieces:
            return ""
        return (
            "\nGOSSIP CONTEXT:\nYou have things you could share about other people:\n"
            + "\n".join(pieces)
            + "\nShare what you know, but filtered through YOUR personality and opinions. "
            "You might exaggerate, downplay, or misremember details."
        )

    def _trade_context(self, speaker, listener) -> str:
        if self.interaction_type != "trade":
            return ""
        return f"""
TRADE CONTEXT:
Your inventory: {self._inventory_summary(speaker)}
{listener.name}'s visible inventory: {self._inventory_summary(listener)}
Your needs: hunger={speaker.drives.hunger:.1f}, shelter_need={speaker.drives.shelter_need:.1f}

You can propose a concrete exchange using the barter_offer actionable kind. Specify exact items and quantities.
Be practical — offer what you have surplus of for what you actually need."""

    async def generate_turn(self, speaker, listener, previous_speech: str = "") -> dict:
        from llm.client import llm_client

        rel = speaker.relationships.get(listener.name, {})
        mental_model = speaker.mental_models.get_prompt_for(listener.name)

        if not previous_speech:
            # Opening line
            trade_ctx = self._trade_context(speaker, listener)
            gossip_ctx = self._gossip_context(speaker, listener)
            prompt = f"""You are {speaker.name}. You've decided to talk to {listener.name}.
Why: {self.reason}. Type: {self.interaction_type}.

Your emotional state: {speaker.emotional_state.get_prompt_description()}
Your drives: {speaker.drives.get_prompt_description()}
Your relationship with {listener.name}: sentiment={rel.get('sentiment',0.5):.1f}, trust={rel.get('trust',0.5):.1f}
{mental_model}
What's on your mind: {speaker.working_memory.get_prompt_context()}
{trade_ctx}{gossip_ctx}
Context: {self.location}. You're all new settlers who just arrived at this place.

Start with something SPECIFIC: what you've noticed about this place, what you need help with, what you're curious about, something you discovered, or ask them about themselves. Don't just say "hello" or "how are you" — say something with substance. 1-2 sentences.
All speech must be in plain natural English. Do not use Russian, any other language, transliteration, or code-switching.

Return JSON:
{{"speech": "what you say", "inner_thought": "what you're thinking", "tone": "warm/casual/tense/hesitant", "emotion_shift": "how this makes you feel or null", "actionable": {{"kind": "decision_to_meet/decision_to_gather/decision_to_build/decision_to_visit/proposal/request/offer/promise/agreement/meeting_invitation/barter_offer/support_signal/opposition_signal/alliance_signal/request_help or null", "description": "clear actionable statement or null", "location": "location id or null", "time_hint": "morning/noon/evening/tomorrow/number or null", "participants": ["names involved"], "required_resources": ["wood"], "recurring": false}}}}"""
        else:
            trade_ctx = self._trade_context(speaker, listener)
            prompt = f"""You are {speaker.name} in conversation with {listener.name}.

They said: "{previous_speech}"

Your emotional state: {speaker.emotional_state.get_prompt_description()}
Your relationship: sentiment={rel.get('sentiment',0.5):.1f}, trust={rel.get('trust',0.5):.1f}
{mental_model}
{trade_ctx}
RULES:
- Do NOT repeat or rephrase what they just said
- Do NOT echo their words back. Add something NEW.
- Share a personal opinion, ask a question, offer information, or change the subject
- If the conversation feels like it's going in circles, end it naturally
- Be specific to who YOU are — your personality, your experiences, your needs
- 1-2 sentences max. Real people don't give speeches.
- All speech must be in plain natural English. Do not use Russian, any other language, transliteration, or code-switching.

Return JSON:
{{"speech": "your response", "inner_thought": "what you're thinking", "tone": "warm/casual/tense", "emotion_shift": "how this makes you feel or null", "wants_to_continue": true, "trust_shift": "up/down/same", "actionable": {{"kind": "decision_to_meet/decision_to_gather/decision_to_build/decision_to_visit/proposal/request/offer/promise/agreement/meeting_invitation/barter_offer/support_signal/opposition_signal/alliance_signal/request_help or null", "description": "clear actionable statement or null", "location": "location id or null", "time_hint": "morning/noon/evening/tomorrow/number or null", "participants": ["names involved"], "required_resources": ["wood"], "recurring": false}}}}"""

        result = await llm_client.generate_json(
            f"You are {speaker.name}, a {speaker.profile.age}-year-old in a new settlement.",
            prompt,
            default={"speech": "...", "inner_thought": "", "tone": "casual", "actionable": None},
        )
        result = _force_english_dialogue(result, speaker.name)
        actionable = normalize_actionable_payload(result.get("actionable"), speaker, listener, self.location)
        if actionable:
            result["actionable"] = actionable
            if actionable["kind"] == "proposal":
                self.structured_proposals.append(actionable)
            else:
                self.structured_commitments.append(actionable)
        self.turns.append({"speaker": speaker.name, **result})
        return result


class LiveConversation:
    """Dynamic multi-party conversation where agents can join and leave."""

    MAX_PARTICIPANTS = 5

    def __init__(self, initiator, target, interaction_type: str, reason: str, location: str):
        self.id = str(uuid.uuid4())[:8]
        self.participants = [initiator, target]
        self.participant_names = [initiator.name, target.name]  # kept in sync
        self.interaction_type = interaction_type
        self.location = location
        self.reason = reason
        self.transcript: list[dict] = []
        self.turns = self.transcript
        self.is_active = True
        self.structured_commitments: list[dict] = []
        self.structured_proposals: list[dict] = []
        type_info = INTERACTION_TYPES.get(interaction_type, {"turns": (2, 4)})
        self.max_turns = random.randint(*type_info["turns"])
        self.turn_count = 0
        self._last_speaker_name: str | None = None

    def add_participant(self, agent):
        if len(self.participants) >= self.MAX_PARTICIPANTS:
            return
        if any(p.id == agent.id for p in self.participants):
            return
        self.participants.append(agent)
        self.participant_names.append(agent.name)
        self.transcript.append({"speaker": "narrator", "speech": f"{agent.name} joins the conversation."})
        # Extend conversation a bit when someone joins
        self.max_turns += 2

    def remove_participant(self, agent):
        self.participants = [p for p in self.participants if p.id != agent.id]
        self.participant_names = [p.name for p in self.participants]
        self.transcript.append({"speaker": "narrator", "speech": f"{agent.name} leaves the conversation."})
        if len(self.participants) < 2:
            self.is_active = False

    def select_next_speaker(self):
        """Weighted random speaker selection -- not round-robin."""
        candidates = self.participants
        if not candidates:
            return None

        weights = []
        last_speech = self.transcript[-1] if self.transcript else {}
        last_speech_text = last_speech.get("speech", "")

        for p in candidates:
            w = 1.0
            # Don't pick the same speaker twice in a row
            if p.name == self._last_speaker_name:
                w = 0.0
            else:
                # Recency bonus: how many turns since they last spoke
                turns_since = 0
                for t in reversed(self.transcript):
                    if t.get("speaker") == p.name:
                        break
                    if t.get("speaker") != "narrator":
                        turns_since += 1
                w += turns_since * 0.4

                # Addressed bonus: last speaker mentioned their name
                if p.name.split()[0].lower() in last_speech_text.lower():
                    w += 1.5

                # Just joined bonus
                if self.transcript and self.transcript[-1].get("speaker") == "narrator" and p.name in self.transcript[-1].get("speech", ""):
                    w += 1.0

            weights.append(max(0.0, w))

        total = sum(weights)
        if total == 0:
            # Fallback: pick anyone except last speaker
            eligible = [p for p in candidates if p.name != self._last_speaker_name]
            return random.choice(eligible) if eligible else random.choice(candidates)

        r = random.random() * total
        cumulative = 0.0
        for p, w in zip(candidates, weights):
            cumulative += w
            if r <= cumulative:
                return p
        return candidates[-1]

    def _inventory_summary(self, agent) -> str:
        if not agent.inventory:
            return "nothing"
        counts: dict[str, int] = {}
        for item in agent.inventory:
            name = item.get("name", "unknown")
            counts[name] = counts.get(name, 0) + int(item.get("quantity", 1))
        return ", ".join(f"{qty} {name.replace('_', ' ')}" for name, qty in counts.items())

    def _gossip_context(self, speaker, others) -> str:
        if self.interaction_type != "gossip":
            return ""
        other_names = {o.name for o in others}
        pieces = []
        for ep in speaker.episodic_memory.recent(20):
            for name in ep.agents_involved:
                if name != speaker.name and name not in other_names:
                    pieces.append(f"- About {name}: {ep.content[:80]} (felt {ep.primary_emotion or 'neutral'})")
                    break
            if len(pieces) >= 3:
                break
        for b in speaker.belief_system.beliefs:
            if getattr(b, "source_type", "") == "hearsay":
                if not any(n.lower() in b.content.lower() for n in other_names):
                    pieces.append(f"- Heard from {getattr(b, 'source_agent', 'someone')}: {b.content[:80]}")
            if len(pieces) >= 5:
                break
        if not pieces:
            return ""
        return (
            "\nGOSSIP CONTEXT:\nYou have things you could share about other people:\n"
            + "\n".join(pieces)
            + "\nShare what you know, but filtered through YOUR personality and opinions. "
            "You might exaggerate, downplay, or misremember details."
        )

    def _trade_context(self, speaker, others) -> str:
        if self.interaction_type != "trade":
            return ""
        other_inv = "\n".join(f"{o.name}'s visible inventory: {self._inventory_summary(o)}" for o in others[:2])
        return f"""
TRADE CONTEXT:
Your inventory: {self._inventory_summary(speaker)}
{other_inv}
Your needs: hunger={speaker.drives.hunger:.1f}, shelter_need={speaker.drives.shelter_need:.1f}

You can propose a concrete exchange using the barter_offer actionable kind. Specify exact items and quantities.
Be practical -- offer what you have surplus of for what you actually need."""

    def _format_transcript(self, limit: int = 6) -> str:
        recent = [t for t in self.transcript[-limit:] if t.get("speech")]
        if not recent:
            return ""
        lines = []
        for t in recent:
            speaker = t["speaker"]
            speech = t["speech"]
            if speaker == "narrator":
                lines.append(f"[{speech}]")
            else:
                lines.append(f"{speaker}: \"{speech}\"")
        return "\n".join(lines)

    def _relationships_summary(self, speaker, others) -> str:
        parts = []
        for o in others:
            rel = speaker.relationships.get(o.name, {})
            parts.append(f"  {o.name}: sentiment={rel.get('sentiment',0.5):.1f}, trust={rel.get('trust',0.5):.1f}")
        return "\n".join(parts)

    async def generate_turn(self, speaker) -> dict:
        from llm.client import llm_client

        others = [p for p in self.participants if p.id != speaker.id]
        others_str = ", ".join(o.name for o in others)
        transcript_str = self._format_transcript()
        trade_ctx = self._trade_context(speaker, others)
        gossip_ctx = self._gossip_context(speaker, others)
        rel_summary = self._relationships_summary(speaker, others)

        if not self.transcript or all(t.get("speaker") == "narrator" for t in self.transcript):
            # Opening line
            prompt = f"""You are {speaker.name}. You've decided to talk to {others_str}.
Why: {self.reason}. Type: {self.interaction_type}.

Your emotional state: {speaker.emotional_state.get_prompt_description()}
Your drives: {speaker.drives.get_prompt_description()}
Your relationships:
{rel_summary}
What's on your mind: {speaker.working_memory.get_prompt_context()}
{trade_ctx}{gossip_ctx}
Context: {self.location}. You're all settlers in this place.

Start with something SPECIFIC: what you've noticed, what you need help with, what you're curious about, something you discovered. Don't just say "hello" or "how are you" -- say something with substance. 1-2 sentences.
All speech must be in plain natural English. Do not use Russian, any other language, transliteration, or code-switching.

Return JSON:
{{"speech": "what you say", "inner_thought": "what you're thinking", "tone": "warm/casual/tense/hesitant", "emotion_shift": "how this makes you feel or null", "actionable": {{"kind": "decision_to_meet/decision_to_gather/decision_to_build/decision_to_visit/proposal/request/offer/promise/agreement/meeting_invitation/barter_offer/support_signal/opposition_signal/alliance_signal/request_help or null", "description": "clear actionable statement or null", "location": "location id or null", "time_hint": "morning/noon/evening/tomorrow/number or null", "participants": ["names involved"], "required_resources": ["wood"], "recurring": false}}}}"""
        else:
            prompt = f"""You are {speaker.name} in a conversation at {self.location}.
Present: {others_str}

Recent conversation:
{transcript_str}

Your emotional state: {speaker.emotional_state.get_prompt_description()}
Your relationships:
{rel_summary}
{trade_ctx}{gossip_ctx}
RULES:
- You can respond to anyone present, or address the group
- Do NOT repeat what was just said. Add something NEW.
- Share a personal opinion, ask a question, offer information, or change the subject
- If you want to leave the conversation, set wants_to_leave to true and say a brief goodbye
- If the conversation feels like it's going in circles, end it naturally
- Be specific to who YOU are -- your personality, your experiences, your needs
- 1-2 sentences max. Real people don't give speeches.
- All speech must be in plain natural English. Do not use Russian, any other language, transliteration, or code-switching.

Return JSON:
{{"speech": "your response", "inner_thought": "what you're thinking", "tone": "warm/casual/tense", "emotion_shift": "how this makes you feel or null", "wants_to_continue": true, "wants_to_leave": false, "trust_shift": "up/down/same", "actionable": {{"kind": "decision_to_meet/decision_to_gather/decision_to_build/decision_to_visit/proposal/request/offer/promise/agreement/meeting_invitation/barter_offer/support_signal/opposition_signal/alliance_signal/request_help or null", "description": "clear actionable statement or null", "location": "location id or null", "time_hint": "morning/noon/evening/tomorrow/number or null", "participants": ["names involved"], "required_resources": ["wood"], "recurring": false}}}}"""

        result = await llm_client.generate_json(
            f"You are {speaker.name}, a {speaker.profile.age}-year-old settler.",
            prompt,
            default={"speech": "...", "inner_thought": "", "tone": "casual", "actionable": None},
        )
        result = _force_english_dialogue(result, speaker.name)
        actionable = normalize_actionable_payload(result.get("actionable"), speaker, others, self.location)
        if actionable:
            result["actionable"] = actionable
            if actionable["kind"] == "proposal":
                self.structured_proposals.append(actionable)
            else:
                self.structured_commitments.append(actionable)
        turn = {"speaker": speaker.name, **result}
        self.transcript.append(turn)
        self.turn_count += 1
        self._last_speaker_name = speaker.name
        return result


def should_join_conversation(agent, conversation, distance: int) -> bool:
    """Heuristic: should a nearby agent join an active conversation? No LLM."""
    if len(conversation.participants) >= LiveConversation.MAX_PARTICIPANTS:
        return False
    if getattr(agent, "is_in_conversation", False):
        return False
    if getattr(agent, "conversation_cooldown", 0) > 0:
        return False
    if distance > CONVERSATION_RANGE:
        return False
    if getattr(agent, "current_action", None) and agent.current_action.value == "sleeping":
        return False

    score = 0.0

    # Relationships with participants
    for p in conversation.participants:
        rel = agent.relationships.get(p.name, {})
        score += rel.get("sentiment", 0.5) * 0.15
        if rel.get("familiarity", 0) > 0.3:
            score += 0.1

    # Social need
    score += agent.drives.social_need * 0.3

    # Name mentioned in recent transcript
    recent_text = " ".join(t.get("speech", "") for t in conversation.transcript[-3:])
    if agent.name in recent_text or agent.name.split()[0] in recent_text:
        score += 0.4

    # Personality: extraverts join more readily
    threshold = 0.35 + (1.0 - agent.profile.personality.get("extraversion", 0.5)) * 0.2
    return score > threshold


def should_leave_conversation(agent, conversation) -> bool:
    """Heuristic: should a participant leave a multi-party conversation? No LLM."""
    if len(conversation.participants) <= 2:
        return False  # 2-person convos end normally, not by leaving

    # Social need fully satisfied -- might drift away
    if agent.drives.social_need < 0.05 and random.random() < 0.25:
        return True

    # Hungry or exhausted and convo has gone on
    if conversation.turn_count > 4:
        if agent.drives.hunger > 0.65 or agent.drives.rest > 0.7:
            return True

    return False


def _normalize_time_hint(raw_hint: str | None) -> tuple[str, int]:
    hint = (raw_hint or "soon").strip().lower()
    if any(word in hint for word in ("morning", "breakfast")):
        return ("morning", 8)
    if any(word in hint for word in ("noon", "midday", "lunch")):
        return ("noon", 12)
    if "afternoon" in hint:
        return ("afternoon", 15)
    if any(word in hint for word in ("evening", "sunset", "dinner")):
        return ("evening", 18)
    if "night" in hint:
        return ("night", 20)
    match = re.search(r"(\\d{1,2})", hint)
    if match:
        hour = max(0, min(23, int(match.group(1))))
        return (hint, hour)
    return (hint, 12)


def normalize_actionable_payload(payload, speaker, others, location: str) -> dict | None:
    """Normalize an actionable payload from an LLM response.

    others: a single agent or list of agents participating in the conversation.
    """
    if not isinstance(payload, dict):
        return None
    kind = payload.get("kind")
    description = payload.get("description")
    if not kind or not description:
        return None
    kind_map = {
        "meeting_invitation": "meeting",
        "request_help": "request",
    }
    kind = kind_map.get(kind, kind)
    # Normalize others to a list
    if not isinstance(others, list):
        others = [others]
    other_names = [o.name if hasattr(o, "name") else str(o) for o in others]
    all_names = [speaker.name] + other_names
    participants = payload.get("participants") or list(all_names)
    for name in all_names:
        if name not in participants:
            participants.append(name)
    time_hint, scheduled_hour = _normalize_time_hint(payload.get("time_hint"))
    return {
        "kind": kind,
        "description": description.strip(),
        "participants": participants,
        "location": payload.get("location") or location,
        "time_hint": time_hint,
        "scheduled_hour": scheduled_hour,
        "required_resources": payload.get("required_resources") or [],
        "recurring": bool(payload.get("recurring", False)),
        "status": "planned",
    }


def _add_commitment(agent, commitment: dict, other_name: str, tick: int, day: int):
    scheduled_day = day + 1 if "tomorrow" in commitment.get("time_hint", "") or tick > 0 else max(day, 1)
    full_commitment = {
        **commitment,
        "scheduled_day": scheduled_day,
        "source_conversation_tick": tick,
        "with": [name for name in commitment["participants"] if name != agent.name],
    }
    duplicate = any(
        existing.get("kind") == full_commitment["kind"]
        and existing.get("description") == full_commitment["description"]
        and existing.get("location") == full_commitment["location"]
        and existing.get("scheduled_day") == full_commitment["scheduled_day"]
        and existing.get("scheduled_hour") == full_commitment["scheduled_hour"]
        for existing in agent.social_commitments
    )
    if not duplicate:
        agent.social_commitments.append(full_commitment)
        agent.active_intentions.insert(0, {
            "goal": full_commitment["description"],
            "why": f"I made this plan with {other_name}.",
            "urgency": 0.72,
            "source": "commitment",
            "target_location": full_commitment["location"],
            "next_step": full_commitment["description"],
            "status": "active",
        })
        agent.active_intentions = agent.active_intentions[:8]
        agent.working_memory.unfinished_business = full_commitment["description"]
        agent.episodic_memory.add_simple(
            f"Made plans with {other_name}: {full_commitment['description']}",
            tick=tick,
            day=day,
            time_of_day="",
            location=full_commitment["location"],
            category="action",
            intensity=0.7,
            emotion="hopeful",
            agents=[other_name],
        )


def process_conversation_consequences(agent, other_names, conversation, tick: int = 0, day: int = 0, all_agent_names: list[str] | None = None):
    """Apply all consequences of a completed conversation.

    other_names: str or list[str] of the other participants.
    """
    if isinstance(other_names, str):
        other_names = [other_names]

    # Per-pair relationship updates
    for other_name in other_names:
        if other_name not in agent.relationships:
            agent.relationships[other_name] = {"sentiment": 0.5, "trust": 0.5, "familiarity": 0.1}
        rel = agent.relationships[other_name]
        rel["familiarity"] = min(1.0, rel.get("familiarity", 0.1) + 0.03)

        # Process turns for trust/emotion shifts
        for turn in conversation.turns:
            if turn.get("speaker") == other_name:
                trust_shift = turn.get("trust_shift", "same")
                if trust_shift == "up":
                    rel["trust"] = min(1.0, rel.get("trust", 0.5) + 0.03)
                    rel["sentiment"] = min(1.0, rel.get("sentiment", 0.5) + 0.02)
                elif trust_shift == "down":
                    rel["trust"] = max(0.0, rel.get("trust", 0.5) - 0.03)
                    rel["sentiment"] = max(-1.0, rel.get("sentiment", 0.5) - 0.02)

        # Update mental model per person
        if conversation.interaction_type != "argument":
            agent.mental_models.update_from_interaction(
                other_name,
                tick=tick,
                trust_delta=0.02,
                comfort_delta=0.02,
                emotional_safety_delta=0.03,
                alliance_delta=0.01,
            )
        else:
            model = agent.mental_models.get_or_create(other_name)
            model.unresolved_issues.append(f"Argument on day {day}")
            model.unresolved_issues = model.unresolved_issues[-4:]
            agent.mental_models.update_from_interaction(
                other_name,
                tick=tick,
                trust_delta=-0.03,
                emotional_safety_delta=-0.06,
                alliance_delta=-0.05,
            )

        # Gossip propagation per speaker
        if conversation.interaction_type == "gossip" and all_agent_names:
            for turn in conversation.turns:
                if turn.get("speaker") == other_name:
                    speech = turn.get("speech", "")
                    for third_name in all_agent_names:
                        if (
                            third_name in speech
                            and third_name != agent.name
                            and third_name != other_name
                        ):
                            agent.belief_system.add(
                                f"Heard from {other_name}: {speech[:100]}",
                                category="person_model",
                                confidence=0.35,
                                tick=tick,
                                source="hearsay",
                                source_agent=other_name,
                            )
                            break

    # Satisfy social need (once, not per-pair)
    if conversation.interaction_type != "argument":
        agent.drives.satisfy_social()
        agent.emotional_state.apply_event("positive_conversation", 0.3)
    else:
        agent.emotional_state.apply_event("negative_conversation", 0.5)

    # Emotion shifts from conversation turns
    for turn in conversation.turns:
        emotion_shift = turn.get("emotion_shift")
        if emotion_shift and turn.get("speaker") != agent.name:
            if emotion_shift in ("happy", "hopeful", "relieved", "grateful"):
                agent.emotional_state.apply_event("positive_conversation", 0.15)
            elif emotion_shift in ("sad", "anxious", "frustrated", "angry"):
                agent.emotional_state.apply_event("negative_conversation", 0.15)

    # Store memory mentioning all participants
    others_str = ", ".join(other_names)
    summary = f"Talked with {others_str}: " + "; ".join(
        t.get("speech", "...")[:40] for t in conversation.turns[:3] if t.get("speaker") != "narrator"
    )
    agent.episodic_memory.add_simple(
        summary, tick=tick, day=day, time_of_day="", location=conversation.location,
        category="conversation", intensity=0.5, agents=list(other_names),
    )

    # Information exchange: update beliefs from conversation content
    for turn in conversation.turns:
        speaker = turn.get("speaker", "")
        speech = turn.get("speech", "")
        if speaker == agent.name or not speech:
            continue
        # Learn facts mentioned in conversation
        if hasattr(agent, "belief_system") and len(speech) > 15:
            trust = agent.relationships.get(speaker, {}).get("trust", 0.5)
            confidence = min(0.8, 0.3 + trust * 0.4)
            agent.belief_system.add(
                f"{speaker} said: {speech[:100]}",
                category="conversation_info",
                confidence=confidence,
                tick=tick,
                source="conversation",
                source_agent=speaker,
            )
        # Update world understanding from conversation
        if hasattr(agent, "world_model"):
            agent.world_model.learn_from_conversation(speaker, speech[:100],
                trust_in_source=agent.relationships.get(speaker, {}).get("trust", 0.5))

    # Process commitments (uses first other_name for backward-compat in intention text)
    primary_other = other_names[0] if other_names else "someone"
    for commitment in conversation.structured_commitments:
        if agent.name in commitment.get("participants", []):
            _add_commitment(agent, commitment, primary_other, tick, day)

        kind = commitment.get("kind")
        description = commitment.get("description", "")
        if kind in {"barter_offer", "offer"}:
            agent.add_intention(
                f"Follow up with {primary_other} about the proposed exchange",
                f"{primary_other} floated a concrete exchange: {description}",
                0.68,
                "trade",
                target_location=commitment.get("location") or conversation.location,
                next_step=description,
                status="active",
                created_tick=tick,
                expires_after_ticks=200,
                refresh_on_relevance=True,
                extra={
                    "trade_details": {
                        "partner": primary_other,
                        "description": description,
                        "required_resources": commitment.get("required_resources", []),
                    },
                },
            )
            for other_name in other_names:
                agent.note_reciprocity(other_name)
                agent.mental_models.update_from_interaction(
                    other_name,
                    tick=tick,
                    generosity_delta=0.03,
                    reliability_delta=0.02,
                    alliance_delta=0.02,
                )
                agent.mental_models.apply_emotional_residue(other_name, tick, emotional_valence=0.08, emotional_intensity=0.45, source="offer")
        elif kind == "support_signal":
            agent.add_intention(
                f"Keep in contact with {primary_other} about shared support",
                f"{primary_other} signaled support: {description}",
                0.56,
                "support",
                target_location=commitment.get("location") or conversation.location,
                next_step="Keep the coalition together",
                status="active",
                created_tick=tick,
                expires_after_ticks=200,
                refresh_on_relevance=True,
            )
            for other_name in other_names:
                agent.mental_models.update_from_interaction(
                    other_name,
                    tick=tick,
                    trust_delta=0.03,
                    alliance_delta=0.08,
                    leadership_delta=0.02,
                )
                agent.mental_models.apply_emotional_residue(other_name, tick, emotional_valence=0.12, emotional_intensity=0.5, source="support")
        elif kind == "opposition_signal":
            for other_name in other_names:
                model = agent.mental_models.get_or_create(other_name)
                model.unresolved_issues.append(f"Opposed: {description}")
                model.unresolved_issues = model.unresolved_issues[-4:]
                agent.mental_models.update_from_interaction(
                    other_name,
                    tick=tick,
                    trust_delta=-0.03,
                    emotional_safety_delta=-0.04,
                    alliance_delta=-0.06,
                )
                agent.mental_models.apply_emotional_residue(other_name, tick, emotional_valence=-0.18, emotional_intensity=0.65, source="argument")
            agent.add_life_event(f"{primary_other} opposed me about: {description}", tick, category="conflict", impact=0.45)
        elif kind == "alliance_signal":
            agent.add_intention(
                f"Stay coordinated with {primary_other}",
                f"We signaled we're on the same side: {description}",
                0.54,
                "alliance",
                target_location=commitment.get("location") or conversation.location,
                next_step="Stay in touch and act together",
                status="active",
                created_tick=tick,
                expires_after_ticks=220,
                refresh_on_relevance=True,
            )
            for other_name in other_names:
                agent.mental_models.update_from_interaction(
                    other_name,
                    tick=tick,
                    trust_delta=0.03,
                    alliance_delta=0.1,
                    emotional_safety_delta=0.02,
                )
                agent.mental_models.apply_emotional_residue(other_name, tick, emotional_valence=0.14, emotional_intensity=0.55, source="alliance")
        elif kind == "request":
            agent.add_intention(
                f"Decide whether to help {primary_other}",
                f"{primary_other} asked for help: {description}",
                0.48,
                "request",
                target_location=commitment.get("location") or conversation.location,
                next_step=description,
                status="candidate",
                created_tick=tick,
                expires_after_ticks=180,
                refresh_on_relevance=True,
            )

    for proposal in conversation.structured_proposals:
        if agent.name not in proposal.get("participants", []):
            continue
        agent.add_intention(
            f"Seriously consider proposal with {primary_other}",
            f"{others_str} and I talked seriously about: {proposal['description']}",
            0.72,
            "proposal_consideration",
            target_location=proposal.get("location") or conversation.location,
            next_step=proposal["description"],
            status="active",
            created_tick=tick,
            expires_after_ticks=220,
            refresh_on_relevance=True,
        )
        agent.add_intention(
            f"Follow up on proposal details with {primary_other}",
            f"I need to decide whether and how to move this forward: {proposal['description']}",
            0.64,
            "proposal_followup",
            target_location=proposal.get("location") or conversation.location,
            next_step="bring it up again or test support carefully",
            status="candidate",
            created_tick=tick,
            expires_after_ticks=220,
            refresh_on_relevance=True,
        )
        agent.episodic_memory.add_simple(
            f"Discussed a proposal with {others_str}: {proposal['description']}",
            tick=tick,
            day=day,
            time_of_day="",
            location=proposal.get("location", conversation.location),
            category="reflection",
            intensity=0.6,
            emotion="curious",
            agents=list(other_names),
        )


class ObservationRecord:
    """Structured record of an observation."""
    __slots__ = ("observer", "subject", "action", "location", "emotion",
                 "detail", "tick", "novelty", "priority")

    def __init__(self, observer: str, subject: str, action: str, location: str,
                 emotion: str = "", detail: str = "", tick: int = 0,
                 novelty: float = 0.0, priority: float = 0.5):
        self.observer = observer
        self.subject = subject
        self.action = action
        self.location = location
        self.emotion = emotion
        self.detail = detail
        self.tick = tick
        self.novelty = novelty
        self.priority = priority

    def to_text(self) -> str:
        parts = [f"{self.subject} is {self.action}"]
        if self.emotion:
            parts.append(f"looking {self.emotion}")
        if self.detail:
            parts.append(self.detail)
        return ", ".join(parts) + "."


class ObservationSystem:
    """Template-based observations -- agents notice what others are doing (no LLM needed)."""

    TEMPLATES = {
        "emotion": [
            "{name} looks {emotion}.",
            "{name} seems {emotion} today.",
        ],
        "action": [
            "{name} is {action}.",
            "{name} appears to be {action}.",
        ],
        "item": [
            "{name} is carrying some {item}.",
        ],
    }

    def __init__(self):
        self._recent_observations: dict[str, set] = {}

    def generate_observation(self, observer, other, distance: int, tick: int = 0) -> str | None:
        if distance > VISUAL_RANGE:
            return None
        if random.random() > 0.3:
            return None

        name = other.name.split()[0]
        action = other.current_action.value
        dom_em, intensity = other.emotional_state.get_dominant_emotion()
        text = None
        novelty = 0.0

        if intensity > 0.4 and dom_em != "neutral":
            template = random.choice(self.TEMPLATES["emotion"])
            text = template.format(name=name, emotion=dom_em)
        elif action not in ("idle",):
            template = random.choice(self.TEMPLATES["action"])
            text = template.format(name=name, action=action)
        elif other.inventory:
            item = other.inventory[0].get("name", "something")
            template = random.choice(self.TEMPLATES["item"])
            text = template.format(name=name, item=item.replace("_", " "))

        if not text:
            return None

        # Novelty detection: is this observation new/surprising?
        obs_key = f"{other.name}:{action}:{dom_em if intensity > 0.4 else ''}"
        recent = self._recent_observations.setdefault(observer.name, set())
        if obs_key not in recent:
            novelty = 0.5
            recent.add(obs_key)
            if len(recent) > 30:
                recent.pop()

        # Create structured record
        record = ObservationRecord(
            observer=observer.name,
            subject=other.name,
            action=action,
            location=getattr(other, "current_location", ""),
            emotion=dom_em if intensity > 0.4 else "",
            detail=text,
            tick=tick,
            novelty=novelty,
            priority=0.3 + novelty * 0.4,
        )

        # Push to working memory with priority
        if hasattr(observer, "working_memory"):
            observer.working_memory.push(text, priority=record.priority)

        # Store novel observations in episodic memory
        if novelty > 0.3 and hasattr(observer, "episodic_memory"):
            observer.episodic_memory.add_simple(
                text, tick=tick, day=0, time_of_day="",
                location=record.location, category="observation",
                intensity=0.3 + novelty * 0.3,
                emotion="curious" if novelty > 0.4 else "neutral",
                agents=[other.name],
            )

        return text


class AvoidanceSystem:
    """Determines if an agent should avoid another person."""

    def should_avoid(self, agent, other) -> bool:
        rel = agent.relationships.get(other.name, {})
        if rel.get("sentiment", 0.5) < 0.2:
            return True
        if rel.get("trust", 0.5) < 0.15:
            return True
        # Active unresolved conflicts
        for conflict in getattr(agent, "active_conflicts", []):
            if conflict.get("with") == other.name and conflict.get("status") == "active":
                if conflict.get("severity", 0) > 0.6:
                    return True
        # High anxiety + negative mental model
        if hasattr(agent, "emotional_state") and agent.emotional_state.anxiety > 0.6:
            model = agent.mental_models.models.get(other.name)
            if model and model.emotional_safety < 0.3:
                return True
        return False

    def get_agents_to_avoid(self, agent, nearby_agents: list) -> list:
        return [other for other in nearby_agents if self.should_avoid(agent, other)]

    def get_avoidance_targets(self, agent, all_agents: dict) -> list[str]:
        """Return list of agent names that this agent is currently avoiding."""
        targets = []
        for other_id, other in all_agents.items():
            if other_id == agent.id:
                continue
            if self.should_avoid(agent, other):
                targets.append(other.name)
        return targets

    def get_avoidance_positions(self, agent, all_agents: dict) -> list[tuple[int, int]]:
        """Return positions of agents that this agent should avoid, for pathfinding."""
        positions = []
        for other_id, other in all_agents.items():
            if other_id == agent.id:
                continue
            if self.should_avoid(agent, other):
                positions.append(other.position)
        return positions


# Location social modifiers — some places encourage/discourage socializing
SOCIAL_SPACE_MODIFIERS = {
    "clearing": 0.2,       # Gathering spot
    "berry_grove": 0.0,
    "forest": -0.1,        # People here to work
    "river": -0.1,
    "north_fields": -0.05,
    "east_meadow": 0.0,
    "south_field": -0.05,
    "hilltop": 0.05,
    "pond": 0.0,
}

def get_social_modifier(location: str) -> float:
    """Get social interaction modifier for a location. Built structures with social purposes get bonuses."""
    base = SOCIAL_SPACE_MODIFIERS.get(location, 0.0)
    # Built structures with social purposes get a bonus
    if "tavern" in location or "meeting" in location or "hall" in location:
        base += 0.3
    return base


class GroupConversation:
    """Multi-agent meeting where participants take turns speaking."""

    def __init__(self, participants: list, topic: str, location: str, max_rounds: int = 2):
        self.participants = participants
        self.topic = topic
        self.location = location
        self.max_rounds = max_rounds
        self.turns: list[dict] = []
        self.structured_commitments: list[dict] = []
        self.structured_proposals: list[dict] = []

    async def run(self) -> list[dict]:
        from llm.client import llm_client

        # Cap participants to avoid LLM cost explosion
        active = self.participants[:6]
        transcript: list[dict] = []

        for _round in range(self.max_rounds):
            for speaker in active:
                others = [p for p in active if p.id != speaker.id]
                others_str = ", ".join(o.name for o in others)
                prev_speech = "; ".join(
                    f"{t['speaker']}: {t['speech']}" for t in transcript[-4:]
                )

                prompt = f"""You are {speaker.name} at a group meeting about: {self.topic}

Present: {others_str}
Previous discussion: {prev_speech or 'Meeting just started.'}

Your emotional state: {speaker.emotional_state.get_prompt_description()}
Your drives: {speaker.drives.get_prompt_description()}

Respond with 1-2 sentences. You can agree, disagree, propose something, or ask a question.
All speech must be in plain natural English. Do not use Russian, any other language, transliteration, or code-switching.

Return JSON:
{{"speech": "what you say", "inner_thought": "what you're thinking", "actionable": {{"kind": "proposal/support_signal/opposition_signal or null", "description": "clear statement or null", "participants": ["names"]}}}}"""

                result = await llm_client.generate_json(
                    f"You are {speaker.name}, a {speaker.profile.age}-year-old in a settlement meeting.",
                    prompt,
                    default={"speech": "...", "inner_thought": ""},
                )
                result = _force_english_dialogue(result, speaker.name)
                turn = {"speaker": speaker.name, **result}
                transcript.append(turn)
                self.turns.append(turn)

                # Process actionable payloads
                actionable = result.get("actionable")
                if isinstance(actionable, dict) and actionable.get("kind") and actionable.get("description"):
                    actionable.setdefault("participants", [p.name for p in active])
                    actionable["location"] = self.location
                    if actionable["kind"] == "proposal":
                        self.structured_proposals.append(actionable)
                    else:
                        self.structured_commitments.append(actionable)

        return transcript


# Singletons
awareness_system = AwarenessSystem()
interaction_decider = InteractionDecider()
lightweight = LightweightInteraction()
overhearing_system = OverhearingSystem()
observation_system = ObservationSystem()
avoidance_system = AvoidanceSystem()


def get_avoidance_targets_for(agent, all_agents: dict) -> list[str]:
    """Convenience wrapper for avoidance system."""
    return avoidance_system.get_avoidance_targets(agent, all_agents)
