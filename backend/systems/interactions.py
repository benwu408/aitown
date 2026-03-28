"""Full interaction system — awareness, scoring, interaction types, conversations, overhearing, avoidance."""

import logging
import random
import math
import re

logger = logging.getLogger("agentica.interactions")

VISUAL_RANGE = 8
INDOOR_RANGE = 4
CONVERSATION_RANGE = 3
OVERHEAR_RANGE = 4


class AwarenessSystem:
    """Determines which agents each agent can perceive."""

    def get_perceived(self, agent, all_agents: dict, world) -> list[dict]:
        perceived = []
        ax, ay = agent.position

        for other_id, other in all_agents.items():
            if other_id == agent.id:
                continue
            ox, oy = other.position
            dist = abs(ax - ox) + abs(ay - oy)
            same_loc = agent.current_location == other.current_location

            visible = dist <= (INDOOR_RANGE if same_loc else VISUAL_RANGE)
            if not visible:
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
        return perceived

    def _attention_weight(self, agent, other, distance: int, same_loc: bool) -> float:
        weight = 0.0

        # Relationship strength
        rel = agent.relationships.get(other.name)
        if rel:
            weight += abs(rel.get("sentiment", 0.5) - 0.5) * 0.4

        # Proximity
        weight += (1.0 / (1.0 + distance * 0.3)) * 0.2

        # Emotional distress
        dom_em, intensity = other.emotional_state.get_dominant_emotion()
        if dom_em in ("sad", "anxious", "angry") and intensity > 0.4:
            weight += agent.profile.personality.get("agreeableness", 0.5) * 0.3

        # Goal relevance
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

        # Social need
        if agent.drives.social_need > 0.2:
            score += agent.drives.social_need * 0.55
            reasons.append("want to connect")

        # Never talked to this person → curiosity
        familiarity = rel.get("familiarity", 0)
        if familiarity < 0.1:
            score += 0.3 * agent.profile.personality.get("openness", 0.5)
            reasons.append("haven't met yet")

        # Friends
        sentiment = rel.get("sentiment", 0.5)
        if sentiment > 0.5:
            score += 0.25
            reasons.append("friend nearby")

        # Both idle at same location — strong signal
        if agent.current_action.value == "idle" and other.current_action.value == "idle":
            if perceived.get("same_location"):
                score += 0.5
                reasons.append("both idle together")
            else:
                score += 0.22
                reasons.append("both idle nearby")

        # They seem upset
        dom_em, intensity = other.emotional_state.get_dominant_emotion()
        if dom_em in ("sad", "anxious") and intensity > 0.4:
            score += agent.profile.personality.get("agreeableness", 0.5) * 0.3
            reasons.append("they seem upset")

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

    # Trade when one agent is in need and the other has what they want
    if familiarity > 0.05 and _agents_have_complementary_inventory(agent, other):
        # Higher chance of trade when driven by need
        if agent.drives.hunger > 0.4 or agent.drives.shelter_need > 0.4:
            return "trade"

    # New settlement — people need to figure things out together
    if reason == "haven't met yet":
        return "info"  # Exchange information about what they've found

    if reason == "both idle together":
        if familiarity < 0.15:
            return "info"  # First real conversation — share what you know
        elif familiarity < 0.4:
            return "small_talk"
        else:
            return "planning"  # Know each other well enough to plan together

    if reason == "want to connect":
        if familiarity < 0.1:
            return "greeting"
        elif familiarity < 0.3:
            return "info"
        else:
            return "deep"

    if reason == "friend nearby" and sentiment > 0.5:
        return "deep" if familiarity > 0.3 else "small_talk"

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

        # Check if observer's name is mentioned
        mentioned = observer.name.lower() in speech.lower() or observer.name.split()[0].lower() in speech.lower()
        if mentioned:
            observer.emotional_state.apply_event("gossip_about_self", 0.5)
            observer.working_memory.push(f"I think {speakers[0]} and {speakers[1]} are talking about me")

        return {
            "fragment": fragment,
            "speakers": speakers,
            "mentioned_self": mentioned,
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
            prompt = f"""You are {speaker.name}. You've decided to talk to {listener.name}.
Why: {self.reason}. Type: {self.interaction_type}.

Your emotional state: {speaker.emotional_state.get_prompt_description()}
Your drives: {speaker.drives.get_prompt_description()}
Your relationship with {listener.name}: sentiment={rel.get('sentiment',0.5):.1f}, trust={rel.get('trust',0.5):.1f}
{mental_model}
What's on your mind: {speaker.working_memory.get_prompt_context()}
{trade_ctx}
Context: {self.location}. You're all new settlers who just arrived at this place.

Start with something SPECIFIC: what you've noticed about this place, what you need help with, what you're curious about, something you discovered, or ask them about themselves. Don't just say "hello" or "how are you" — say something with substance. 1-2 sentences.

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

Return JSON:
{{"speech": "your response", "inner_thought": "what you're thinking", "tone": "warm/casual/tense", "emotion_shift": "how this makes you feel or null", "wants_to_continue": true, "trust_shift": "up/down/same", "actionable": {{"kind": "decision_to_meet/decision_to_gather/decision_to_build/decision_to_visit/proposal/request/offer/promise/agreement/meeting_invitation/barter_offer/support_signal/opposition_signal/alliance_signal/request_help or null", "description": "clear actionable statement or null", "location": "location id or null", "time_hint": "morning/noon/evening/tomorrow/number or null", "participants": ["names involved"], "required_resources": ["wood"], "recurring": false}}}}"""

        result = await llm_client.generate_json(
            f"You are {speaker.name}, a {speaker.profile.age}-year-old in a new settlement.",
            prompt,
            default={"speech": "...", "inner_thought": "", "tone": "casual", "actionable": None},
        )
        actionable = normalize_actionable_payload(result.get("actionable"), speaker, listener, self.location)
        if actionable:
            result["actionable"] = actionable
            if actionable["kind"] == "proposal":
                self.structured_proposals.append(actionable)
            else:
                self.structured_commitments.append(actionable)
        self.turns.append({"speaker": speaker.name, **result})
        return result


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


def normalize_actionable_payload(payload, speaker, listener, location: str) -> dict | None:
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
    participants = payload.get("participants") or [speaker.name, listener.name]
    if speaker.name not in participants:
        participants.append(speaker.name)
    if listener.name not in participants:
        participants.append(listener.name)
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


def process_conversation_consequences(agent, other_name: str, conversation: Conversation, tick: int = 0, day: int = 0):
    """Apply all consequences of a completed conversation."""
    # Update relationship
    if other_name not in agent.relationships:
        agent.relationships[other_name] = {"sentiment": 0.5, "trust": 0.5, "familiarity": 0.1}
    rel = agent.relationships[other_name]
    rel["familiarity"] = min(1.0, rel.get("familiarity", 0.1) + 0.03)

    # Process turns for trust/emotion shifts
    for turn in conversation.turns:
        if turn.get("speaker") != agent.name:
            trust_shift = turn.get("trust_shift", "same")
            if trust_shift == "up":
                rel["trust"] = min(1.0, rel.get("trust", 0.5) + 0.03)
                rel["sentiment"] = min(1.0, rel.get("sentiment", 0.5) + 0.02)
            elif trust_shift == "down":
                rel["trust"] = max(0.0, rel.get("trust", 0.5) - 0.03)
                rel["sentiment"] = max(-1.0, rel.get("sentiment", 0.5) - 0.02)

    # Satisfy social need
    if conversation.interaction_type != "argument":
        agent.drives.satisfy_social()
        agent.emotional_state.apply_event("positive_conversation", 0.3)
    else:
        agent.emotional_state.apply_event("negative_conversation", 0.5)

    # Store memory
    summary = f"Talked with {other_name}: " + "; ".join(
        t.get("speech", "...")[:40] for t in conversation.turns[:3]
    )
    agent.episodic_memory.add_simple(
        summary, tick=tick, day=day, time_of_day="", location=conversation.location,
        category="conversation", intensity=0.5, agents=[other_name],
    )

    # Update mental model
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

    for commitment in conversation.structured_commitments:
        if agent.name in commitment.get("participants", []):
            _add_commitment(agent, commitment, other_name, tick, day)

        kind = commitment.get("kind")
        description = commitment.get("description", "")
        if kind in {"barter_offer", "offer"}:
            agent.active_intentions.insert(0, {
                "goal": f"Complete trade with {other_name}",
                "why": f"{other_name} floated a concrete exchange: {description}",
                "urgency": 0.68,
                "source": "trade",
                "target_location": commitment.get("location") or conversation.location,
                "next_step": description,
                "status": "active",
                "trade_details": {
                    "partner": other_name,
                    "description": description,
                    "required_resources": commitment.get("required_resources", []),
                },
            })
            agent.note_reciprocity(other_name)
            agent.mental_models.update_from_interaction(
                other_name,
                tick=tick,
                generosity_delta=0.03,
                reliability_delta=0.02,
                alliance_delta=0.02,
            )
        elif kind == "support_signal":
            agent.active_intentions.insert(0, {
                "goal": f"Build support with {other_name}",
                "why": f"{other_name} signaled support: {description}",
                "urgency": 0.56,
                "source": "support",
                "target_location": commitment.get("location") or conversation.location,
                "next_step": "Keep the coalition together",
                "status": "active",
            })
            agent.mental_models.update_from_interaction(
                other_name,
                tick=tick,
                trust_delta=0.03,
                alliance_delta=0.08,
                leadership_delta=0.02,
            )
        elif kind == "opposition_signal":
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
            agent.add_life_event(f"{other_name} opposed me about: {description}", tick, category="conflict", impact=0.45)
        elif kind == "alliance_signal":
            agent.active_intentions.insert(0, {
                "goal": f"Coordinate more closely with {other_name}",
                "why": f"We signaled we're on the same side: {description}",
                "urgency": 0.54,
                "source": "alliance",
                "target_location": commitment.get("location") or conversation.location,
                "next_step": "Stay in touch and act together",
                "status": "active",
            })
            agent.mental_models.update_from_interaction(
                other_name,
                tick=tick,
                trust_delta=0.03,
                alliance_delta=0.1,
                emotional_safety_delta=0.02,
            )
        elif kind == "request":
            agent.active_intentions.insert(0, {
                "goal": f"Decide whether to help {other_name}",
                "why": f"{other_name} asked for help: {description}",
                "urgency": 0.48,
                "source": "request",
                "target_location": commitment.get("location") or conversation.location,
                "next_step": description,
                "status": "candidate",
            })
        agent.active_intentions = agent.active_intentions[:8]

    for proposal in conversation.structured_proposals:
        if agent.name not in proposal.get("participants", []):
            continue
        agent.active_goals.append({
            "text": f"Follow through on proposal: {proposal['description']}",
            "status": "active",
            "source": "conversation",
            "priority": 0.75,
            "created_tick": tick,
            "kind": "proposal",
            "location": proposal.get("location"),
        })
        agent.active_intentions.insert(0, {
            "goal": proposal["description"],
            "why": f"{other_name} and I talked seriously about making this happen.",
            "urgency": 0.68,
            "source": "proposal",
            "target_location": proposal.get("location") or conversation.location,
            "next_step": "build support for the proposal",
            "status": "active",
        })
        agent.active_intentions = agent.active_intentions[:8]
        agent.episodic_memory.add_simple(
            f"Discussed a proposal with {other_name}: {proposal['description']}",
            tick=tick,
            day=day,
            time_of_day="",
            location=proposal.get("location", conversation.location),
            category="reflection",
            intensity=0.6,
            emotion="curious",
            agents=[other_name],
        )


class ObservationSystem:
    """Template-based observations — agents notice what others are doing (no LLM needed)."""

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

    def generate_observation(self, observer, other, distance: int) -> str | None:
        if distance > VISUAL_RANGE:
            return None
        if random.random() > 0.3:
            return None  # Don't always notice

        name = other.name.split()[0]

        # Check emotion
        dom_em, intensity = other.emotional_state.get_dominant_emotion()
        if intensity > 0.4 and dom_em != "neutral":
            template = random.choice(self.TEMPLATES["emotion"])
            return template.format(name=name, emotion=dom_em)

        # Check action
        action = other.current_action.value
        if action not in ("idle",):
            template = random.choice(self.TEMPLATES["action"])
            return template.format(name=name, action=action)

        # Check inventory
        if other.inventory:
            item = other.inventory[0].get("name", "something")
            template = random.choice(self.TEMPLATES["item"])
            return template.format(name=name, item=item.replace("_", " "))

        return None


class AvoidanceSystem:
    """Determines if an agent should avoid another person."""

    def should_avoid(self, agent, other) -> bool:
        rel = agent.relationships.get(other.name, {})
        if rel.get("sentiment", 0.5) < 0.2:
            return True
        if rel.get("trust", 0.5) < 0.15:
            return True
        return False

    def get_agents_to_avoid(self, agent, nearby_agents: list) -> list:
        return [other for other in nearby_agents if self.should_avoid(agent, other)]


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


# Singletons
awareness_system = AwarenessSystem()
interaction_decider = InteractionDecider()
lightweight = LightweightInteraction()
overhearing_system = OverhearingSystem()
observation_system = ObservationSystem()
avoidance_system = AvoidanceSystem()
