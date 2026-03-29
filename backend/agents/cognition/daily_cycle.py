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
    for goal in getattr(agent.identity, "long_arc_goals", [])[:4]:
        text = str(goal.get("text", "")).strip()
        if not text:
            continue
        goals.append({
            "text": text,
            "why": goal.get("why") or "This feels tied to who I'm becoming.",
            "priority": round(float(goal.get("priority", 0.6)), 2),
            "category": goal.get("category", "identity"),
            "source": goal.get("source", "identity_tension"),
        })

    if not goals and not agent._find_home():
        goals.append({
            "text": "Secure a reliable place to sleep",
            "why": "Safety and rest matter if I'm going to last here.",
            "priority": 0.9,
            "category": "shelter",
            "source": "survival_fallback",
        })
    if not goals and agent.drives.hunger > 0.65:
        goals.append({
            "text": "Stabilize my access to food",
            "why": "Hunger keeps narrowing everything else.",
            "priority": 0.82,
            "category": "food",
            "source": "survival_fallback",
        })
    return goals[:4]


def _derive_active_goals(agent, result: dict, tick: int) -> list[dict]:
    goals: list[dict] = []
    current_plan = result.get("current_plan")
    if isinstance(current_plan, dict) and current_plan.get("goal"):
        goals.append({
            "text": current_plan["goal"],
            "status": "active",
            "source": "morning_plan",
            "priority": round(float(current_plan.get("urgency", 0.7)), 2),
            "created_tick": tick,
            "kind": "daily_focus",
        })
    for goal in agent.long_term_goals[:3]:
        goals.append({
            "text": goal.get("text", ""),
            "status": "active",
            "source": goal.get("source", "identity_tension"),
            "priority": goal.get("priority", 0.6),
            "created_tick": tick,
            "kind": "long_arc",
        })
    return goals[:6]


def _derive_intentions(agent, result: dict, schedule: list[dict], tick: int) -> list[dict]:
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
            "created_tick": tick,
            "expires_after_ticks": 200,
            "refresh_on_relevance": True,
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
            "created_tick": tick,
            "expires_after_ticks": 200,
            "refresh_on_relevance": True,
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
            "created_tick": tick,
            "expires_after_ticks": 180,
            "refresh_on_relevance": True,
        })
    return intentions[:6]


MORNING_PROMPT = """You are {name}. It's morning. You just woke up.

How you're feeling: {emotion_desc}
Your pressing needs: {drive_desc}
Background worry: {worry}

Your personality: {personality_desc}
Your job: {job}
What you're getting good at: {skill_summary}
What you find satisfying: {enjoyment_summary}

Recent reflections still on your mind:
{recent_reflections}

Active goals:
{goals}

People you know:
{social_context}

RULES: You live in a frontier settlement. NO phones, NO email, NO paperwork. You can only walk places, talk to people face-to-face, gather resources, build, trade, eat, and rest.

What does your day look like? Be realistic about who you are right now. If you're exhausted, your plan might just be "get through the day."

Available locations: {locations}

Return JSON:
{{
  "mood_on_waking": "1-2 sentence description of how the morning feels",
  "priorities": ["ranked list of what matters most today (max 3)"],
  "must_do": ["essential tasks (max 3)"],
  "want_to": ["things you'd like to do if there's time (max 2)"],
  "avoiding": ["things you should do but are dreading (max 1)"],
  "social_goals": ["people to talk to or relationships to tend (max 2)"],
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
    {{"hour": 9, "location": "clearing", "activity": "gather resources"}},
    {{"hour": 12, "location": "clearing", "activity": "eating"}},
    {{"hour": 14, "location": "forest_edge", "activity": "gather wood"}},
    {{"hour": 18, "location": "clearing", "activity": "rest and socialize"}},
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

Your skills and what you've been doing:
{skill_context}

Your sense of self right now:
{identity_context}

Reflect honestly. This is private. Think about:
- How did today make you feel overall?
- Did anything change how you see someone?
- Did you learn something about yourself or the world?
- What's weighing on you as you try to sleep?
- Who are you becoming in this settlement?

Return JSON:
{{
  "evening_mood": "how you feel as the day ends",
  "day_summary": "1-2 sentences -- how would you describe today?",
  "new_beliefs": [
    {{"content": "belief text", "category": "person_model or world_knowledge or self_belief", "confidence": 0.5}}
  ],
  "updated_mental_models": [
    {{"agent": "name", "perception": "updated understanding", "trust_change": 0.0}}
  ],
  "self_reflection": "something you realized about yourself, or null",
  "identity_update": "how you see your role/place in this settlement now, or null",
  "world_lessons": ["things you learned about how this place works (max 2)"],
  "unresolved_tension": "what's going to keep you up tonight, or null",
  "tomorrow_intention": "one thing to do tomorrow, or null",
  "tomorrow_avoid": "one thing to avoid or be careful about tomorrow, or null"
}}"""


async def morning_plan(agent, day: int, tick: int, locations: str) -> dict:
    """Generate morning plan with rich cognitive context."""
    personality_desc = ", ".join(f"{k}:{v:.1f}" for k, v in agent.profile.personality.items())
    goals_text = "\n".join(f"- {g['text']}" for g in agent.long_term_goals[:4])
    reflections_text = "\n".join(f"- {r}" for r in agent.episodic_memory.reflections(5))

    skill_summary = agent.skill_memory.get_prompt_summary()
    enjoyment_summary = agent.skill_memory.get_enjoyment_summary()

    social_parts = []
    for name_key, model in list(agent.mental_models.models.items())[:6]:
        social_parts.append(
            f"- {name_key}: trust={model.trust:.1f}, gut={model.gut_feeling:+.1f}, "
            f"they likely see me as {model.what_i_think_they_think_of_me or 'unclear'}"
        )
    social_context = "\n".join(social_parts) or "Haven't gotten to know anyone yet"

    prompt = MORNING_PROMPT.format(
        name=agent.name,
        emotion_desc=agent.emotional_state.get_prompt_description(),
        drive_desc=agent.drives.get_prompt_description(),
        worry=agent.working_memory.background_worry or "nothing specific",
        personality_desc=personality_desc,
        job=getattr(agent.profile, 'job', None) or agent.self_concept or 'newcomer',
        skill_summary=skill_summary,
        enjoyment_summary=enjoyment_summary,
        recent_reflections=reflections_text or "None",
        goals=goals_text or "No specific goals",
        social_context=social_context,
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
    agent.active_goals = _derive_active_goals(agent, result, tick)
    agent.active_intentions = _derive_intentions(agent, result, agent.daily_schedule, tick)
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

    # Store structured priorities for routine behavior selection
    priorities = result.get("priorities", [])
    if priorities and isinstance(priorities, list):
        agent.daily_priorities = priorities[:3]
    else:
        agent.daily_priorities = []

    # Social goals feed into intention system
    social_goals = result.get("social_goals", [])
    if social_goals and isinstance(social_goals, list):
        for sg in social_goals[:2]:
            if sg and isinstance(sg, str):
                agent.active_intentions.append({
                    "goal": sg,
                    "why": "Social connection matters to me.",
                    "urgency": 0.4,
                    "source": "morning_plan_social",
                    "target_location": "clearing",
                    "next_step": sg,
                    "status": "candidate",
                    "created_tick": tick,
                    "expires_after_ticks": 180,
                    "refresh_on_relevance": True,
                })
        agent.active_intentions = agent.active_intentions[:8]

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

    skill_context = agent.skill_memory.get_prompt_summary()
    identity_context = agent.identity.self_narrative or "Still figuring out who I am here."

    prompt = EVENING_PROMPT.format(
        name=agent.name,
        todays_episodes=episodes_text or "Nothing notable happened today.",
        emotion_desc=agent.emotional_state.get_prompt_description(),
        relevant_beliefs=agent.belief_system.get_prompt_context(max_beliefs=5),
        interaction_summary="\n".join(interaction_parts) or "Didn't interact with anyone today.",
        skill_context=skill_context,
        identity_context=identity_context,
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

    significant_names = []
    for name in interacted_with:
        relevant_eps = [e for e in todays if name in getattr(e, "agents_involved", [])]
        if any(getattr(e, "emotional_intensity", 0.0) >= 0.55 for e in relevant_eps):
            significant_names.append(name)
            summary = "; ".join(getattr(e, "content", "")[:120] for e in relevant_eps[-4:])
            other_stub = type("OtherAgent", (), {"name": name})()
            await agent.mental_models.synthesize_after_interaction(
                agent,
                other_stub,
                interaction_summary=summary,
                llm_client=llm_client,
            )

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

    # Identity crystallization
    identity_update = result.get("identity_update")
    if identity_update and isinstance(identity_update, str) and identity_update != "null":
        if not agent.self_concept:
            agent.bump_identity(identity_update)
    relationships = getattr(agent, "relationships", {})
    num_friends = sum(1 for rel in relationships.values() if rel.get("trust", 0.0) > 0.62)
    has_home = bool(agent._find_home())
    competence = min(1.0, max(
        (entry.get("skill_level", 0.0) for entry in agent.skill_memory.activities.values()),
        default=0.0,
    ))
    agent.identity.update_belonging(has_home, num_friends, day + 1)
    agent.identity.update_purpose(
        has_role=bool(agent.self_concept or agent.identity.role_in_community),
        has_goals=bool(agent.active_goals or agent.long_term_goals),
        competence_satisfaction=competence,
    )
    agent.identity.satisfaction_with_role = round(min(1.0, 0.4 + competence * 0.4), 2)
    agent.identity.satisfaction_with_relationships = round(min(1.0, 0.3 + num_friends * 0.15), 2)
    agent.identity.satisfaction_with_community = round((agent.identity.sense_of_belonging + agent.identity.satisfaction_with_relationships) / 2, 2)
    agent.identity.life_satisfaction = round(
        (
            agent.identity.sense_of_belonging
            + agent.identity.sense_of_purpose
            + agent.identity.satisfaction_with_role
            + agent.identity.satisfaction_with_relationships
        ) / 4,
        2,
    )
    agent.identity.detect_tensions(agent.belief_system.beliefs, relationships, todays)
    agent.identity.generate_goals_from_tensions()
    agent.identity.update_self_narrative(todays, agent.belief_system.beliefs)
    if identity_update and isinstance(identity_update, str) and identity_update != "null":
        agent.identity.self_narrative = f"{agent.identity.self_narrative} {identity_update}".strip()[:320]
    agent.long_term_goals = _derive_long_term_goals(agent)
    agent.active_goals = [
        goal for goal in agent.active_goals
        if goal.get("status") == "active" and goal.get("kind") == "daily_focus"
    ]
    for goal in agent.long_term_goals[:3]:
        if not any(existing.get("text") == goal.get("text") for existing in agent.active_goals):
            agent.active_goals.append({
                "text": goal.get("text", ""),
                "status": "active",
                "source": goal.get("source", "identity_tension"),
                "priority": goal.get("priority", 0.6),
                "created_tick": tick,
                "kind": "long_arc",
            })
    agent.active_goals = agent.active_goals[:6]

    tomorrow = result.get("tomorrow_intention")
    if tomorrow and isinstance(tomorrow, str) and tomorrow != "null":
        agent.add_intention(
            tomorrow,
            "This is what keeps echoing at the end of the day.",
            0.58,
            "evening_reflection",
            target_location=agent.current_location,
            next_step=tomorrow,
            status="candidate",
            created_tick=tick,
            expires_after_ticks=220,
            refresh_on_relevance=True,
        )
    elif agent.long_term_goals:
        top_goal = agent.long_term_goals[0]
        agent.add_intention(
            f"Make progress on {top_goal.get('text', 'what matters to me')}",
            top_goal.get("why", "I want tomorrow to move me forward."),
            min(0.75, float(top_goal.get("priority", 0.6))),
            "long_term_goal_followthrough",
            target_location=agent.current_location,
            next_step=top_goal.get("text", ""),
            status="candidate",
            created_tick=tick,
            expires_after_ticks=220,
            refresh_on_relevance=True,
        )

    # World lessons become beliefs
    for lesson in result.get("world_lessons", []):
        if lesson and isinstance(lesson, str):
            agent.belief_system.add(
                lesson, "world_knowledge", 0.6, tick=tick,
            )

    # Tomorrow's caution becomes background worry
    tomorrow_avoid = result.get("tomorrow_avoid")
    if tomorrow_avoid and isinstance(tomorrow_avoid, str) and tomorrow_avoid != "null":
        if not agent.working_memory.background_worry:
            agent.working_memory.set_worry(tomorrow_avoid)

    agent.prune_expired_intentions(tick)

    return result
