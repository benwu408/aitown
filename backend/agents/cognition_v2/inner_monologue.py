"""Inner monologue — continuous stream of consciousness with typed thoughts."""

import logging
import random

logger = logging.getLogger("agentica.monologue")

THOUGHT_TYPES = [
    "observation", "worry", "memory_trigger", "self_talk", "daydream",
    "reaction", "question", "gratitude", "frustration", "realization",
    "physical", "nostalgia",
]

# Thoughts that get stored as episodic memories
MEMORABLE_TYPES = {"realization", "worry", "reaction", "frustration"}

THOUGHT_PROMPT = """You are {name}'s inner voice. Generate ONE brief {thought_type} thought (1-2 sentences).

Current situation: {location}, {time_of_day}
Currently doing: {activity}
Emotional state: {emotion_desc}
Dominant need: {drive_desc}
Background worry: {worry}
Physical sensation: {sensation}

Thought type guide:
- observation: noticing something about the environment or another person
- worry: anxiety about something unresolved
- memory_trigger: a sensory detail triggering a memory from before arriving here
- self_talk: talking to yourself about what you should do
- daydream: imagining a future possibility or wishing for something
- reaction: emotional response to something that just happened
- question: wondering about something you don't understand
- gratitude: appreciating something small
- frustration: annoyance at a situation or yourself
- realization: connecting two things you hadn't connected before
- physical: awareness of your body (tired, hungry, sore, comfortable)
- nostalgia: thinking about life before you came here

Keep it to 1-2 sentences. Make it feel like a real human inner voice.
Most thoughts are mundane, not dramatic.

Return ONLY the thought, nothing else."""


def select_thought_type(agent) -> str:
    """Select thought type weighted by agent's current state."""
    emotions = agent.emotional_state
    drives = agent.drives
    personality = agent.profile.personality

    weights = {
        "observation": 0.15,
        "worry": emotions.anxiety * 0.3 + 0.05,
        "memory_trigger": 0.08,
        "self_talk": 0.12,
        "daydream": max(0.02, 0.15 - emotions.anxiety * 0.1),
        "reaction": 0.1 if agent.working_memory.latest_observation else 0.02,
        "question": personality.get("openness", 0.5) * 0.12,
        "gratitude": max(0.02, emotions.joy * 0.15),
        "frustration": max(0.02, (emotions.anger + drives.competence_need) * 0.1),
        "realization": 0.05,
        "physical": max(0.02, (drives.hunger + drives.rest) * 0.15 - 0.1),
        "nostalgia": 0.06,
    }

    total = sum(weights.values())
    weights = {k: v / total for k, v in weights.items()}

    return random.choices(list(weights.keys()), weights=list(weights.values()))[0]


async def generate_thought(agent, location: str, time_of_day: str, activity: str) -> str | None:
    """Generate a typed inner monologue thought. Lightweight LLM call."""
    from llm.client import llm_client

    thought_type = select_thought_type(agent)

    prompt = THOUGHT_PROMPT.format(
        name=agent.name,
        thought_type=thought_type,
        location=location.replace("_", " "),
        time_of_day=time_of_day,
        activity=activity,
        emotion_desc=agent.emotional_state.get_prompt_description(),
        drive_desc=agent.drives.get_prompt_description(),
        worry=agent.working_memory.background_worry or "nothing specific",
        sensation=agent.working_memory.latest_sensation or "nothing notable",
    )

    result = await llm_client.generate(
        f"You are the inner voice of {agent.name}, a {agent.profile.age}-year-old {getattr(agent, 'self_concept', None) or 'newcomer to this settlement'}.",
        prompt,
        temperature=0.9,
        max_tokens=100,
    )

    if result:
        thought = result.strip().strip('"').strip("'")
        agent.inner_thought = thought
        agent.working_memory.push(thought)

        # Store important thoughts as episodic memories
        if thought_type in MEMORABLE_TYPES:
            agent.episodic_memory.add_simple(
                f"Thought to myself: {thought}",
                tick=0, day=0, time_of_day=time_of_day,
                location=location, category="inner_thought",
                intensity=0.3, emotion=agent.emotional_state.get_dominant_emotion()[0],
            )

        return thought
    return None
