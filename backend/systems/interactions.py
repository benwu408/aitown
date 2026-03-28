"""Full interaction system — awareness, scoring, interaction types, conversations, overhearing, avoidance."""

import logging
import random
import math

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
            if not p["can_talk"] or getattr(other, "is_in_conversation", False):
                continue

            score, reason = self._score(agent, other, p)
            if score > best_score:
                best_score = score
                best_target = other
                best_reason = reason

        # Personality threshold — lower = more social
        threshold = 0.15 + (1.0 - agent.profile.personality.get("extraversion", 0.5)) * 0.2
        if agent.drives.social_need > 0.3:
            threshold -= 0.1
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
            score += agent.drives.social_need * 0.4
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
                score += 0.35
                reasons.append("both idle together")
            else:
                score += 0.15
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
    "deep": {"turns": (5, 12), "llm": True},
    "argument": {"turns": (3, 8), "llm": True},
    "comforting": {"turns": (3, 8), "llm": True},
    "planning": {"turns": (3, 8), "llm": True},
    "gossip": {"turns": (2, 6), "llm": True},
}


def select_interaction_type(agent, other, reason: str, rel: dict) -> str:
    familiarity = rel.get("familiarity", 0.1)
    sentiment = rel.get("sentiment", 0.5)

    if reason == "they seem upset":
        return "comforting"

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


class ConversationV2:
    """LLM-powered conversation with V2 cognitive context."""

    def __init__(self, initiator, target, interaction_type: str, reason: str, location: str):
        self.participants = [initiator.name, target.name]
        self.interaction_type = interaction_type
        self.location = location
        self.reason = reason
        self.turns: list[dict] = []
        self.is_active = True
        type_info = INTERACTION_TYPES.get(interaction_type, {"turns": (2, 4)})
        self.max_turns = random.randint(*type_info["turns"])

    async def generate_turn(self, speaker, listener, previous_speech: str = "") -> dict:
        from llm.client import llm_client

        rel = speaker.relationships.get(listener.name, {})
        mental_model = speaker.mental_models.get_prompt_for(listener.name)

        if not previous_speech:
            # Opening line
            prompt = f"""You are {speaker.name}. You've decided to talk to {listener.name}.
Why: {self.reason}. Type: {self.interaction_type}.

Your emotional state: {speaker.emotional_state.get_prompt_description()}
Your drives: {speaker.drives.get_prompt_description()}
Your relationship with {listener.name}: sentiment={rel.get('sentiment',0.5):.1f}, trust={rel.get('trust',0.5):.1f}
{mental_model}
What's on your mind: {speaker.working_memory.get_prompt_context()}

Context: {self.location}. You're all new settlers who just arrived at this place.

Start with something SPECIFIC: what you've noticed about this place, what you need help with, what you're curious about, something you discovered, or ask them about themselves. Don't just say "hello" or "how are you" — say something with substance. 1-2 sentences.

Return JSON:
{{"speech": "what you say", "inner_thought": "what you're thinking", "tone": "warm/casual/tense/hesitant", "emotion_shift": "how this makes you feel or null"}}"""
        else:
            prompt = f"""You are {speaker.name} in conversation with {listener.name}.

They said: "{previous_speech}"

Your emotional state: {speaker.emotional_state.get_prompt_description()}
Your relationship: sentiment={rel.get('sentiment',0.5):.1f}, trust={rel.get('trust',0.5):.1f}
{mental_model}

RULES:
- Do NOT repeat or rephrase what they just said
- Do NOT echo their words back. Add something NEW.
- Share a personal opinion, ask a question, offer information, or change the subject
- If the conversation feels like it's going in circles, end it naturally
- Be specific to who YOU are — your personality, your experiences, your needs
- 1-2 sentences max. Real people don't give speeches.

Return JSON:
{{"speech": "your response", "inner_thought": "what you're thinking", "tone": "warm/casual/tense", "emotion_shift": "how this makes you feel or null", "wants_to_continue": true, "trust_shift": "up/down/same"}}"""

        result = await llm_client.generate_json(
            f"You are {speaker.name}, a {speaker.profile.age}-year-old in a new settlement.",
            prompt,
            default={"speech": "...", "inner_thought": "", "tone": "casual"},
        )
        self.turns.append({"speaker": speaker.name, **result})
        return result


def process_conversation_consequences(agent, other_name: str, conversation: ConversationV2):
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
        summary, tick=0, day=0, time_of_day="", location=conversation.location,
        category="conversation", intensity=0.5, agents=[other_name],
    )

    # Update mental model
    agent.mental_models.update_from_interaction(other_name, tick=0)


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
