"""LLM prompt templates for agent cognition."""


def get_location_list() -> str:
    """Get dynamic list of all current buildings from the world."""
    try:
        from simulation.world import World
        # Access the singleton world if available, otherwise fall back to defaults
        from simulation.world import BUILDING_MAP
        locations = [f"{b.id} ({b.label})" for b in BUILDING_MAP.values()]
        return ", ".join(locations)
    except Exception:
        return "tavern, bakery, park, farm, workshop, church, school, general_store, town_hall, pond, house_1, house_2, house_3, house_4, house_5, house_6"


LOCATION_CONSTRAINT = "IMPORTANT: Only reference locations that actually exist in town. There is NO café, NO library, NO community center. Use building IDs from the available locations list."


def conversation_system_prompt(agent_name: str, agent_profile: dict) -> str:
    personality_desc = ", ".join(
        f"{k}: {v:.1f}" for k, v in agent_profile.get("personality", {}).items()
    )
    values = ", ".join(agent_profile.get("values", []))

    # Secret awareness
    secret_str = ""
    secrets = agent_profile.get("secrets", [])
    if secrets:
        secret_text = secrets[0].get("content", "")
        secret_str = f"\n\nYou have a deep secret: \"{secret_text}\". You NEVER share this openly. Only if you trust someone deeply and feel emotionally vulnerable might you hint at it — but even then, you are cautious."

    return f"""You are {agent_name}, a {agent_profile.get('age', '?')}-year-old {agent_profile.get('job', '?')} in the small town of Agentica.

Your personality traits (0-1 scale): {personality_desc}
Your values: {values}
Your backstory: {agent_profile.get('backstory', '')}{secret_str}

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
    trust_level: float = 0.5,
    opinions: dict | None = None,
    active_goals: list[str] | None = None,
) -> str:
    memories_str = "\n".join(f"- {m}" for m in recent_memories[-5:]) if recent_memories else "None"
    goals_str = ", ".join(active_goals[:3]) if active_goals else ""
    goals_line = f"\nYour current goals: {goals_str}" if goals_str else ""

    # Opinions context
    opinion_str = ""
    if opinions:
        relevant = [f"{k}: {'pro' if v.get('stance', 0) > 0.2 else 'anti' if v.get('stance', 0) < -0.2 else 'neutral'}"
                    for k, v in opinions.items() if abs(v.get('stance', 0)) > 0.2]
        if relevant:
            opinion_str = f"\nYour opinions on town issues: {', '.join(relevant)}"

    return f"""You are at {location}. It is {time_of_day}. Your current mood: {mood}.
Your relationship with {other_name}: {relationship_notes} (trust: {trust_level:.1f}){goals_line}{opinion_str}

Your recent memories:
{memories_str}

{other_name} says to you: "{other_message}"

Respond naturally as {agent_name} would. You live in a real town where your actions have consequences. During this conversation you can:
- Propose meeting up again (lunch, drinks, walks, any activity at any location)
- Ask for help or offer to help (fix something, visit someone, lend money)
- Suggest a group activity or invite others to join next time
- Offer to teach or learn something from the other person
- Propose checking on someone who's struggling or sick
- Share gossip, opinions, or personal secrets if trust is high enough

If you propose an activity, be specific about where and when. Available locations: {get_location_list()}.

Return JSON:
{{
  "speech": "your spoken response (1-3 sentences)",
  "inner_thought": "what you're actually thinking but not saying",
  "emotion": "your current emotion (one word)",
  "relationship_change": "slightly_positive, slightly_negative, or neutral",
  "wants_to_end_conversation": false,
  "gossip_to_share": "information about a third party you might mention, or null",
  "shared_secret": "if you hinted at or revealed a personal secret, describe what you shared. Otherwise null",
  "opinion_expressed": "if you expressed a stance on a town issue (taxes, clinic, modernization, etc), state the topic and your position. Otherwise null",
  "proposed_activity": {{
    "description": "what you proposed (e.g. 'Let's have lunch and discuss the school budget')",
    "location": "building_id where it happens (e.g. bakery, tavern, park)",
    "time": "morning, noon, afternoon, evening, or a specific hour like 14",
    "involves": ["names of anyone else who should join, or empty list"],
    "recurring": false
  }}
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
    opinions: dict | None = None,
) -> str:
    memories_str = "\n".join(f"- {m}" for m in recent_memories[-5:]) if recent_memories else "None"
    goals_str = ", ".join(goals[:3]) if goals else "None"

    opinion_str = ""
    if opinions:
        relevant = [f"{k}: {'pro' if v.get('stance', 0) > 0.2 else 'anti' if v.get('stance', 0) < -0.2 else 'neutral'}"
                    for k, v in opinions.items() if abs(v.get('stance', 0)) > 0.2]
        if relevant:
            opinion_str = f"\nYour opinions: {', '.join(relevant)}"

    return f"""You are at {location}. It is {time_of_day}. Your current mood: {mood}.
Your relationship with {other_name}: {relationship_notes}
Your current goals: {goals_str}{opinion_str}

Your recent memories:
{memories_str}

You see {other_name} nearby. Start a conversation with them. Choose a topic based on your personality, goals, recent memories, opinions on town issues, or just small talk. Your goals and concerns should drive what you talk about.

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
    active_goals: list[dict] | None = None,
    opinions: dict | None = None,
    social_context: str = "",
    town_needs: str = "",
) -> str:
    memories_str = "\n".join(f"- {m}" for m in recent_memories[-20:])

    goals_str = ""
    if active_goals:
        goals_lines = [f"- {g['text']} (status: {g['status']}, source: {g['source']})" for g in active_goals if g['status'] == 'active']
        if goals_lines:
            goals_str = f"\n\nYour current active goals:\n" + "\n".join(goals_lines)

    social_str = f"\n\nPeople around town:\n{social_context}" if social_context else ""
    town_str = f"\n\nTown needs: {town_needs}" if town_needs else ""

    return f"""You are {agent_name}. Here are your recent experiences:

{memories_str}{goals_str}{social_str}{town_str}

SIMULATION RULES — what you CAN and CANNOT do:
- You live in a small rural town with NO phones, NO texting, NO email, NO clerks, NO official forms, NO paperwork, NO stamps.
- You can ONLY: walk to places, talk to people face-to-face, buy/sell goods at shops, eat, work your job, rest, and think.
- To communicate you MUST walk to someone and talk to them in person.

Reflect on your experiences. Consider:
1. What patterns have you noticed? Keep insights short and personal.
2. Have any goals been completed or should be abandoned?
3. Any NEW goals? Must be simple physical actions: "Visit [person] at [place]", "Buy [item]", "Talk to [person] about [topic]", "Sell crafts at the store", "Have dinner with [person] at the tavern", "Help [person] with [task]". NO paperwork, NO forms, NO official processes.
4. Have your opinions on town issues shifted?
5. Would you like to post something on the town bulletin board? A thought, announcement, or opinion that everyone in town can read.

Available locations: {get_location_list()}. {LOCATION_CONSTRAINT}

Return JSON:
{{
  "reflections": ["insight 1", "insight 2", "insight 3 (optional)"],
  "new_goal": "a new goal that emerged from your experiences, or null",
  "completed_goal": "text of a goal you've achieved, or null",
  "abandoned_goal": "text of a goal you're giving up on, or null",
  "goal_progress": "brief note on progress toward your most important active goal, or null",
  "opinion_shifts": {{"topic_name": "new_stance_description"}} or {{}},
  "planned_action": {{
    "description": "what you want to do (e.g. 'Visit John and check on him')",
    "location": "building_id (e.g. house_2, park, tavern)",
    "time": "morning, noon, afternoon, or evening"
  }},
  "bulletin_post": "a short message to post on the town bulletin board for everyone to read, or null"
}}"""


def daily_plan_prompt(
    agent_name: str,
    agent_profile: dict,
    recent_reflections: list[str],
    active_goals: list[dict],
    day_number: int,
    opinions: dict | None = None,
) -> str:
    reflections_str = "\n".join(f"- {r}" for r in recent_reflections[-5:]) if recent_reflections else "None"
    goals_str = "\n".join(f"- {g['text']} (priority: {g['priority']:.1f})" for g in active_goals if g['status'] == 'active') if active_goals else "None"

    opinion_str = ""
    if opinions:
        strong = [f"{k}: {'strongly for' if v['stance'] > 0.3 else 'strongly against' if v['stance'] < -0.3 else 'mixed'}"
                  for k, v in opinions.items() if v.get('confidence', 0) > 0.3]
        if strong:
            opinion_str = f"\nYour strong opinions: {', '.join(strong)}"

    default_schedule = agent_profile.get("default_schedule", "Work at your workplace during the day, eat meals, socialize in the evening.")

    return f"""You are {agent_name}, {agent_profile.get('job', '?')} in Agentica. It is Day {day_number}.

Your active goals (these should drive your day):
{goals_str}

Your recent reflections:
{reflections_str}{opinion_str}

Your usual routine: {default_schedule}

Available locations: {get_location_list()}. {LOCATION_CONSTRAINT}

Create a plan for today. REMEMBER: you can only walk places, talk to people face-to-face, buy/sell goods, work, eat, and rest. NO phones, NO texting, NO paperwork, NO forms. If you want to talk to someone, walk to where they work or live. Keep it simple and realistic for a small rural town.

Return JSON:
{{
  "plan": "Brief description of today's plan (2-3 sentences)",
  "priority_goal": "The most important thing to do today",
  "people_to_see": ["name1", "name2"],
  "schedule": [
    {{"hour": 7, "location": "your_home_id", "activity": "eating"}},
    {{"hour": 8, "location": "workplace_id", "activity": "working"}},
    {{"hour": 12, "location": "bakery", "activity": "eating"}},
    {{"hour": 13, "location": "some_location", "activity": "working or idle or reflecting"}},
    {{"hour": 17, "location": "tavern", "activity": "eating"}},
    {{"hour": 21, "location": "your_home_id", "activity": "sleeping"}}
  ]
}}

The schedule should have 5-8 entries covering the full day. Activities can be: working, eating, sleeping, reflecting, buying, selling, idle. Use real location IDs from the list above."""


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
  "action_type": "one of: walking, talking, buying, selling, delivering, giving, working, eating, reflecting, idle, attending_event, arguing, celebrating, announcing, building",
  "target_location": "where you're going (building name), or null",
  "target_agent": "who you're interacting with, or null",
  "item": "item involved, or null",
  "speech": "what you say out loud, or null",
  "inner_thought": "what you're thinking (1-2 sentences)",
  "emotion": "your current emotion",
  "new_goal": "a new goal if one emerged, or null"
}}"""
