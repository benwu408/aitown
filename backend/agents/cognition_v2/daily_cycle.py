"""Daily cycle — morning planning and evening reflection with rich cognitive context."""

import logging
from llm.client import llm_client

logger = logging.getLogger("agentica.daily_cycle")


MORNING_PROMPT = """You are {name}. It's morning. You just woke up.

How you're feeling: {emotion_desc}
Your pressing needs: {drive_desc}
Background worry: {worry}

Your personality: {personality_desc}
Your job: {job}

Recent reflections still on your mind:
{recent_reflections}

Active goals:
{goals}

RULES: You live in a small rural town. NO phones, NO email, NO paperwork. You can only walk places, talk to people face-to-face, buy/sell goods, work, eat, and rest.

What does your day look like? Be realistic about who you are right now. If you're exhausted, your plan might just be "get through the day."

Available locations: {locations}

Return JSON:
{{
  "mood_on_waking": "1-2 sentence description of how the morning feels",
  "must_do": ["essential tasks (max 3)"],
  "want_to": ["things you'd like to do if there's time (max 2)"],
  "avoiding": ["things you should do but are dreading (max 1)"],
  "schedule": [
    {{"hour": 7, "location": "home_id", "activity": "eating"}},
    {{"hour": 8, "location": "workplace_id", "activity": "working"}},
    {{"hour": 12, "location": "tavern", "activity": "eating"}},
    {{"hour": 14, "location": "somewhere", "activity": "working or idle"}},
    {{"hour": 18, "location": "tavern", "activity": "eating"}},
    {{"hour": 21, "location": "home_id", "activity": "sleeping"}}
  ]
}}"""


EVENING_PROMPT = """You are {name}. The day is ending. You're alone with your thoughts.

What happened today:
{todays_episodes}

Your emotional state: {emotion_desc}

Your beliefs that might be affected:
{relevant_beliefs}

People you interacted with today:
{interaction_summary}

Reflect honestly. This is private.
- How did today make you feel overall?
- Did anything change how you see someone?
- Did you learn something about yourself?
- What's weighing on you as you try to sleep?

Return JSON:
{{
  "evening_mood": "how you feel as the day ends",
  "day_summary": "1-2 sentences — how would you describe today?",
  "new_beliefs": [
    {{"content": "belief text", "category": "person_model or world_knowledge or self_belief", "confidence": 0.5}}
  ],
  "updated_mental_models": [
    {{"agent": "name", "perception": "updated understanding", "trust_change": 0.0}}
  ],
  "self_reflection": "something you realized about yourself, or null",
  "unresolved_tension": "what's going to keep you up tonight, or null",
  "tomorrow_intention": "one thing to do tomorrow, or null"
}}"""


async def morning_plan(agent, day: int, tick: int, locations: str) -> dict:
    """Generate morning plan with rich cognitive context."""
    personality_desc = ", ".join(f"{k}:{v:.1f}" for k, v in agent.profile.personality.items())
    goals_text = "\n".join(f"- {g['text']}" for g in agent.active_goals if g.get("status") == "active")
    reflections_text = "\n".join(f"- {r}" for r in agent.episodic_memory.reflections(5))

    prompt = MORNING_PROMPT.format(
        name=agent.name,
        emotion_desc=agent.emotional_state.get_prompt_description(),
        drive_desc=agent.drives.get_prompt_description(),
        worry=agent.working_memory.background_worry or "nothing specific",
        personality_desc=personality_desc,
        job=getattr(agent.profile, 'job', None) or agent.self_concept or 'newcomer',
        recent_reflections=reflections_text or "None",
        goals=goals_text or "No specific goals",
        locations=locations,
    )

    job = getattr(agent.profile, 'job', None) or agent.self_concept or 'newcomer'
    sys = f"You are {agent.name}, a {agent.profile.age}-year-old {job} in a frontier settlement."
    result = await llm_client.generate_json(sys, prompt, default={"schedule": [], "mood_on_waking": "okay"})

    # Process morning mood into working memory
    mood = result.get("mood_on_waking", "")
    if mood:
        agent.working_memory.push(mood)
        agent.inner_thought = mood

    # Set background worry from "avoiding" or "dreading"
    avoiding = result.get("avoiding", [])
    if avoiding and isinstance(avoiding, list) and avoiding[0]:
        agent.working_memory.set_worry(avoiding[0])

    # Store plan
    plan_text = f"Must do: {', '.join(result.get('must_do', []))}"
    if result.get("want_to"):
        plan_text += f". Want to: {', '.join(result['want_to'])}"
    agent.daily_plan = plan_text

    return result


async def evening_reflection(agent, day: int, tick: int) -> dict:
    """Evening reflection — update beliefs, mental models, emotional processing."""
    # Gather today's episodes
    todays = [e for e in agent.episodic_memory.episodes if e.day == day]
    episodes_text = "\n".join(f"- [{e.primary_emotion}] {e.content}" for e in todays[-15:])

    # Interaction summary
    interacted_with = set()
    for e in todays:
        for name in e.agents_involved:
            interacted_with.add(name)
    interaction_parts = []
    for name in interacted_with:
        model = agent.mental_models.models.get(name)
        if model:
            interaction_parts.append(f"- {name}: {model.perceived_personality[:60]}")
        else:
            interaction_parts.append(f"- {name}: don't know them well")

    prompt = EVENING_PROMPT.format(
        name=agent.name,
        todays_episodes=episodes_text or "Nothing notable happened today.",
        emotion_desc=agent.emotional_state.get_prompt_description(),
        relevant_beliefs=agent.belief_system.get_prompt_context(max_beliefs=5),
        interaction_summary="\n".join(interaction_parts) or "Didn't interact with anyone today.",
    )

    sys = f"You are {agent.name}, reflecting privately at the end of the day."
    result = await llm_client.generate_json(sys, prompt, default={"evening_mood": "tired", "day_summary": "another day"})

    # Process new beliefs
    for b in result.get("new_beliefs", []):
        if isinstance(b, dict) and b.get("content"):
            agent.belief_system.add(
                b["content"], b.get("category", "world_knowledge"),
                b.get("confidence", 0.5), tick=tick,
            )

    # Update mental models
    for update in result.get("updated_mental_models", []):
        if isinstance(update, dict) and update.get("agent"):
            model = agent.mental_models.get_or_create(update["agent"])
            if update.get("perception"):
                model.perceived_personality = update["perception"]
            model.trust = max(0.0, min(1.0, model.trust + update.get("trust_change", 0)))
            model.last_updated = tick

    # Set tomorrow's worry
    tension = result.get("unresolved_tension")
    if tension and isinstance(tension, str) and tension != "null":
        agent.working_memory.set_worry(tension)

    # Self-reflection goes into episodic memory
    self_ref = result.get("self_reflection")
    if self_ref and isinstance(self_ref, str) and self_ref != "null":
        agent.episodic_memory.add_simple(
            self_ref, tick, day, "night", agent.current_location,
            category="reflection", intensity=0.7, emotion="reflective",
        )

    # Store day summary
    summary = result.get("day_summary", "")
    if summary:
        agent.episodic_memory.add_simple(
            f"Day {day}: {summary}", tick, day, "night", agent.current_location,
            category="reflection", intensity=0.5,
        )

    return result
