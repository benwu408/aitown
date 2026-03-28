"""Daily cycle — morning planning and evening reflection with rich cognitive context."""

import logging
from llm.client import llm_client

logger = logging.getLogger("agentica.daily_cycle")


def _normalize_schedule(agent, raw_schedule) -> list[dict]:
    """Keep daily schedules valid and grounded in known world locations."""
    valid_locations = set(agent.world.get_all_location_ids())
    normalized = []

    for step in raw_schedule or []:
        if not isinstance(step, dict):
            continue
        try:
            hour = int(step.get("hour", 0))
        except (TypeError, ValueError):
            continue
        if hour < 0 or hour > 23:
            continue
        location = step.get("location") or agent.current_location
        if location not in valid_locations:
            location = agent.current_location
        activity = str(step.get("activity", "idle")).strip().lower() or "idle"
        normalized.append({
            "hour": hour,
            "location": location,
            "activity": activity,
            "label": f"{hour:02d}:00 {activity.replace('_', ' ')} at {location.replace('_', ' ')}",
        })

    if not normalized:
        home = agent._find_home() or agent.current_location
        normalized = [
            {"hour": 6, "location": agent.current_location, "activity": "wake and orient", "label": f"06:00 wake and orient at {agent.current_location.replace('_', ' ')}"},
            {"hour": 8, "location": "clearing", "activity": "explore for resources", "label": "08:00 explore for resources at clearing"},
            {"hour": 12, "location": agent.current_location, "activity": "eat if possible", "label": f"12:00 eat if possible at {agent.current_location.replace('_', ' ')}"},
            {"hour": 15, "location": "forest_edge" if "forest_edge" in valid_locations else agent.current_location, "activity": "gather wood", "label": "15:00 gather wood at forest edge"},
            {"hour": 20, "location": home, "activity": "rest", "label": f"20:00 rest at {home.replace('_', ' ')}"},
        ]

    normalized.sort(key=lambda item: item["hour"])
    return normalized


def _derive_long_term_goals(agent) -> list[dict]:
    goals = []
    if not agent._find_home():
        goals.append({
            "text": "Secure a reliable place to sleep",
            "why": "Safety and rest matter if I'm going to last here",
            "priority": 0.9,
            "category": "shelter",
        })
    if agent.drives.hunger > 0.45:
        goals.append({
            "text": "Find dependable food sources",
            "why": "I can't think clearly if hunger keeps pulling at me",
            "priority": 0.75,
            "category": "food",
        })
    goals.append({
        "text": "Figure out my place in this settlement",
        "why": "I need purpose and some direction here",
        "priority": 0.6,
        "category": "identity",
    })
    return goals[:4]


def _derive_intentions(agent, result: dict, schedule: list[dict]) -> list[dict]:
    intentions: list[dict] = []
    must_do = result.get("must_do", []) if isinstance(result.get("must_do"), list) else []
    want_to = result.get("want_to", []) if isinstance(result.get("want_to"), list) else []
    for idx, text in enumerate(must_do[:3]):
        step = schedule[min(idx, len(schedule) - 1)] if schedule else {"location": agent.current_location, "activity": text}
        intentions.append({
            "goal": text,
            "why": "This feels necessary today.",
            "urgency": round(0.85 - idx * 0.1, 2),
            "source": "morning_plan",
            "target_location": step.get("location", agent.current_location),
            "next_step": step.get("activity", text),
            "status": "active",
        })
    for idx, text in enumerate(want_to[:2]):
        step = schedule[min(idx + len(must_do), len(schedule) - 1)] if schedule else {"location": agent.current_location, "activity": text}
        intentions.append({
            "goal": text,
            "why": "If the day opens up, I want to make space for this.",
            "urgency": round(0.45 - idx * 0.05, 2),
            "source": "morning_plan",
            "target_location": step.get("location", agent.current_location),
            "next_step": step.get("activity", text),
            "status": "active",
        })
    if agent.working_memory.current_goal:
        intentions.append({
            "goal": agent.working_memory.current_goal,
            "why": "It keeps pulling at my attention.",
            "urgency": 0.55,
            "source": "working_memory",
            "target_location": agent.current_location,
            "next_step": "follow through on current focus",
            "status": "active",
        })
    return intentions[:6]


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
  "current_plan": {{
    "goal": "main thing you're trying to move forward today",
    "why": "why it matters to you",
    "prerequisites": ["what has to be true first"],
    "candidate_steps": ["concrete steps to try in order"],
    "fallback": "what you'll do if the first approach fails",
    "urgency": 0.0,
    "social_dependencies": ["people you may need"],
    "expected_location": "location id or null",
    "expected_resources": ["resource ids"]
  }},
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
    agent.daily_schedule = _normalize_schedule(agent, result.get("schedule", []))
    agent.current_plan_step = agent.daily_schedule[0] if agent.daily_schedule else None
    agent.long_term_goals = _derive_long_term_goals(agent)
    agent.active_intentions = _derive_intentions(agent, result, agent.daily_schedule)
    raw_plan = result.get("current_plan") if isinstance(result.get("current_plan"), dict) else {}
    agent.current_plan = {
        "goal": raw_plan.get("goal") or (agent.active_intentions[0]["goal"] if agent.active_intentions else "Get through the day"),
        "why": raw_plan.get("why") or "This feels like the best use of today.",
        "prerequisites": raw_plan.get("prerequisites") or [],
        "candidate_steps": raw_plan.get("candidate_steps") or [step.get("activity") for step in agent.daily_schedule[:3]],
        "fallback": raw_plan.get("fallback") or "If this stalls, look for a smaller useful task and regroup.",
        "urgency": raw_plan.get("urgency", agent.active_intentions[0]["urgency"] if agent.active_intentions else 0.5),
        "social_dependencies": raw_plan.get("social_dependencies") or [],
        "expected_location": raw_plan.get("expected_location") or (agent.daily_schedule[0].get("location") if agent.daily_schedule else agent.current_location),
        "expected_resources": raw_plan.get("expected_resources") or [],
        "step_index": 0,
        "status": "active",
    }
    agent.fallback_plan = {
        "goal": "Recover if the day goes sideways",
        "steps": [agent.current_plan["fallback"]],
        "status": "standby",
    }
    agent.blocked_reasons = []
    agent.decision_rationale = {}
    agent.plan_mode = "scheduled"
    agent.plan_deviation_reason = ""

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
        if hasattr(agent, "active_conflicts") and interacted_with:
            agent.note_conflict(next(iter(interacted_with)), tension, tick, severity=0.45, kind="tension")

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
        recent_roles = ", ".join(role.get("role", "") for role in getattr(agent, "current_institution_roles", [])[:2] if role.get("role"))
        narrative_parts = [
            summary,
            result.get("self_reflection", ""),
            f"My place lately: {recent_roles}." if recent_roles else "",
        ]
        agent.identity.self_narrative = " ".join(part for part in narrative_parts if part).strip()

    tomorrow = result.get("tomorrow_intention")
    if tomorrow and isinstance(tomorrow, str) and tomorrow != "null":
        agent.active_intentions.insert(0, {
            "goal": tomorrow,
            "why": "This is what keeps echoing at the end of the day.",
            "urgency": 0.58,
            "source": "evening_reflection",
            "target_location": agent.current_location,
            "next_step": tomorrow,
            "status": "candidate",
        })
        agent.active_intentions = agent.active_intentions[:8]

    return result
