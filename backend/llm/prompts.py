"""LLM prompt templates for agent cognition."""


def conversation_system_prompt(agent_name: str, agent_profile: dict) -> str:
    personality_desc = ", ".join(
        f"{k}: {v:.1f}" for k, v in agent_profile.get("personality", {}).items()
    )
    values = ", ".join(agent_profile.get("values", []))
    return f"""You are {agent_name}, a {agent_profile.get('age', '?')}-year-old {agent_profile.get('job', '?')} in the small town of Agentica.

Your personality traits (0-1 scale): {personality_desc}
Your values: {values}
Your backstory: {agent_profile.get('backstory', '')}

Stay in character at all times. Speak naturally as {agent_name} would — use their vocabulary level, emotional tendencies, and communication style. Keep responses to 1-3 sentences."""


def conversation_user_prompt(
    agent_name: str,
    other_name: str,
    other_message: str,
    location: str,
    time_of_day: str,
    mood: str,
    relationship_notes: str,
    recent_memories: list[str],
) -> str:
    memories_str = "\n".join(f"- {m}" for m in recent_memories[-5:]) if recent_memories else "None"

    return f"""You are at {location}. It is {time_of_day}. Your current mood: {mood}.
Your relationship with {other_name}: {relationship_notes}

Your recent memories:
{memories_str}

{other_name} says to you: "{other_message}"

Respond naturally as {agent_name} would. Return JSON:
{{
  "speech": "your spoken response (1-3 sentences)",
  "inner_thought": "what you're actually thinking but not saying",
  "emotion": "your current emotion (one word)",
  "relationship_change": "slightly_positive, slightly_negative, or neutral",
  "wants_to_end_conversation": false,
  "gossip_to_share": "information about a third party you might mention, or null"
}}"""


def conversation_opener_prompt(
    agent_name: str,
    other_name: str,
    location: str,
    time_of_day: str,
    mood: str,
    relationship_notes: str,
    recent_memories: list[str],
    goals: list[str],
) -> str:
    memories_str = "\n".join(f"- {m}" for m in recent_memories[-5:]) if recent_memories else "None"
    goals_str = ", ".join(goals[:3]) if goals else "None"

    return f"""You are at {location}. It is {time_of_day}. Your current mood: {mood}.
Your relationship with {other_name}: {relationship_notes}
Your current goals: {goals_str}

Your recent memories:
{memories_str}

You see {other_name} nearby. Start a conversation with them. Choose a topic based on your personality, goals, recent memories, or just small talk.

Return JSON:
{{
  "speech": "your opening line to {other_name} (1-2 sentences)",
  "inner_thought": "what motivated you to start this conversation",
  "emotion": "your current emotion (one word)",
  "topic": "brief description of what you want to talk about"
}}"""


def reflection_prompt(
    agent_name: str,
    recent_memories: list[str],
) -> str:
    memories_str = "\n".join(f"- {m}" for m in recent_memories[-20:])

    return f"""You are {agent_name}. Here are your recent experiences:

{memories_str}

Based on these experiences, generate 2-3 higher-level reflections or insights. These should be beliefs, patterns, or conclusions you've drawn from your experiences.

Return JSON:
{{
  "reflections": [
    "First reflection or insight",
    "Second reflection or insight",
    "Third reflection or insight (optional)"
  ]
}}"""


def daily_plan_prompt(
    agent_name: str,
    agent_profile: dict,
    recent_reflections: list[str],
    current_goals: list[str],
    day_number: int,
) -> str:
    reflections_str = "\n".join(f"- {r}" for r in recent_reflections[-5:]) if recent_reflections else "None"
    goals_str = "\n".join(f"- {g}" for g in current_goals) if current_goals else "None"

    return f"""You are {agent_name}, {agent_profile.get('job', '?')} in Agentica. It is Day {day_number}.

Your current goals:
{goals_str}

Your recent reflections:
{reflections_str}

Create a simple plan for today. What do you want to accomplish? Who do you want to talk to? Any problems to address?

Return JSON:
{{
  "plan": "Brief description of today's plan (2-3 sentences)",
  "priority_goal": "The most important thing to do today",
  "people_to_see": ["name1", "name2"]
}}"""


def decision_prompt(
    agent_name: str,
    agent_profile: dict,
    current_plan: str,
    mood: str,
    observations: list[str],
    relevant_memories: list[str],
    location: str,
    time_of_day: str,
) -> str:
    personality_desc = ", ".join(
        f"{k}: {v:.1f}" for k, v in agent_profile.get("personality", {}).items()
    )
    goals_str = ", ".join(agent_profile.get("goals", [])[:3])
    obs_str = "\n".join(f"- {o}" for o in observations) if observations else "Nothing notable"
    mem_str = "\n".join(f"- {m}" for m in relevant_memories[-10:]) if relevant_memories else "None"

    return f"""You are {agent_name}, a {agent_profile.get('age', '?')}-year-old {agent_profile.get('job', '?')}.
Personality: {personality_desc}
Goals: {goals_str}
Current mood: {mood}
Today's plan: {current_plan or "No specific plan"}

You are at {location}. It is {time_of_day}.

What you observe:
{obs_str}

Relevant memories:
{mem_str}

What do you do next?

Return JSON:
{{
  "action_type": "one of: walking, talking, buying, selling, delivering, giving, working, eating, reflecting, idle, attending_event, arguing, celebrating, announcing",
  "target_location": "where you're going (building name), or null",
  "target_agent": "who you're interacting with, or null",
  "item": "item involved, or null",
  "speech": "what you say out loud, or null",
  "inner_thought": "what you're thinking (1-2 sentences)",
  "emotion": "your current emotion",
  "new_goal": "a new goal if one emerged, or null"
}}"""
