"""Decision pipeline -- novelty detection, routine behavior, and LLM-gated decisions."""

import logging
import random

logger = logging.getLogger("agentica.decision")

NOVELTY_THRESHOLD = 0.3

DECISION_PROMPT = """You are {name}, a {age}-year-old {role} in a frontier settlement.

RIGHT NOW:
- Location: {location}
- Time: {time_of_day} (hour {hour})
- Currently doing: {current_action}
- Health: {health_desc}

WHAT CAUGHT YOUR ATTENTION:
{novel_stimuli}

YOUR INNER STATE:
- Emotions: {emotion_desc}
- Pressing needs: {drive_desc}
- Background worry: {worry}
- Recent thoughts: {recent_thoughts}

WHAT YOU KNOW:
- Working memory: {working_memory_items}
- Long-arc goals: {long_term_goals}
- Today's active goals: {active_goals}
- Immediate intentions: {active_intentions}
- Morning plan: {morning_plan}
- Beliefs relevant here: {beliefs}

NEARBY PEOPLE:
{nearby_agents}

YOUR SKILLS: {skills}

AVAILABLE LOCATIONS: {known_locations}

Given what just grabbed your attention, what do you want to do next? Describe a single concrete action in 1-2 sentences. Be specific about what you'll do and where. This is a frontier settlement with no modern technology. You can walk places, talk to people, gather resources, build things, eat, rest, trade, or anything else that makes physical sense.

Return ONLY the action description, nothing else."""


class NoveltyDetector:
    def __init__(self):
        self._last_attention_count: dict[str, int] = {}
        self._last_location: dict[str, str] = {}
        self._last_nearby: dict[str, set[str]] = {}
        self._last_action: dict[str, str] = {}

    def detect(self, agent, world_state: dict, tick: int) -> tuple[float, list[str]]:
        aid = agent.id
        score = 0.0
        stimuli = []

        # New items in working memory since last check
        current_wm_count = len(agent.working_memory.items)
        prev_count = self._last_attention_count.get(aid, current_wm_count)
        if current_wm_count > prev_count:
            new_items = current_wm_count - prev_count
            score += min(0.3, new_items * 0.15)
            top_item = agent.working_memory.items[0]
            stimuli.append(f"New thought: {top_item.content if hasattr(top_item, 'content') else top_item}")
        self._last_attention_count[aid] = current_wm_count

        # Drive crossing urgency threshold
        if agent.drives.dominant_drive_changed():
            score += 0.35
            stimuli.append(f"Urgent need shift: {agent.drives.get_prompt_description()[:80]}")

        # Location changed
        prev_loc = self._last_location.get(aid, agent.current_location)
        if agent.current_location != prev_loc:
            score += 0.25
            stimuli.append(f"Arrived at {agent.current_location.replace('_', ' ')}")
        self._last_location[aid] = agent.current_location

        # New agents nearby
        nearby_now = set()
        for other_id, other in world_state.get("agents", {}).items():
            if other_id == aid:
                continue
            if hasattr(other, "current_location") and other.current_location == agent.current_location:
                nearby_now.add(other.name)
        prev_nearby = self._last_nearby.get(aid, set())
        new_faces = nearby_now - prev_nearby
        if new_faces:
            score += min(0.3, len(new_faces) * 0.15)
            for name in list(new_faces)[:3]:
                model = agent.mental_models.models.get(name)
                if model and (model.trust > 0.7 or model.trust < 0.2 or model.unresolved_issues):
                    score += 0.15
                    stimuli.append(f"Someone significant is here: {name}")
                else:
                    stimuli.append(f"{name} is nearby")
        self._last_nearby[aid] = nearby_now

        # Active action completed or failed (went idle from non-idle)
        prev_action = self._last_action.get(aid, "idle")
        current = agent.current_action.value
        if prev_action not in ("idle", "walking") and current == "idle":
            score += 0.2
            stimuli.append(f"Finished {prev_action}")
        self._last_action[aid] = current

        # Incoming conversation
        if agent.is_in_conversation:
            score += 0.4
            stimuli.append("In a conversation")

        # Emotional threshold crossed
        if agent.emotional_state.just_crossed_threshold():
            score += 0.25
            emo, intensity = agent.emotional_state.get_dominant_emotion()
            stimuli.append(f"Strong feeling: {emo} ({intensity:.1f})")

        # Active event or observation
        if agent.working_memory.latest_observation:
            score += 0.1
            stimuli.append(f"Noticed: {agent.working_memory.latest_observation[:60]}")

        # Goal-relevant person nearby
        for goal in agent.active_goals:
            if goal.get("status") != "active":
                continue
            for name in nearby_now:
                if name.lower() in goal.get("text", "").lower():
                    score += 0.2
                    stimuli.append(f"Goal-relevant person nearby: {name}")
                    break

        # Random snap-out-of-autopilot
        if random.random() < 0.03:
            score += 0.35
            stimuli.append("Spontaneous awareness")

        return min(score, 1.0), stimuli


class RoutineBehavior:
    @staticmethod
    def get_action(agent, hour: float, time_of_day: str) -> dict | None:
        # Continue current action if busy
        if agent.current_action.value not in ("idle",) or agent.path:
            return None

        # Follow daily schedule if available
        if agent.daily_schedule:
            best_step = None
            for step in agent.daily_schedule:
                if step["hour"] <= hour:
                    best_step = step
            if best_step:
                activity = best_step.get("activity", "idle")
                location = best_step.get("location", agent.current_location)
                if location != agent.current_location:
                    return {"action": "walking", "target": location, "thought": f"Time for: {activity}"}
                action_map = {
                    "eating": "eating", "eat": "eating", "eat if possible": "eating",
                    "sleeping": "sleeping", "sleep": "sleeping", "rest": "sleeping",
                    "working": "working", "work": "working",
                    "gathering": "gathering", "gather wood": "gathering_wood",
                    "explore": "walking_explore", "explore for resources": "walking_explore",
                }
                mapped = None
                for key, val in action_map.items():
                    if key in activity.lower():
                        mapped = val
                        break
                if mapped:
                    return {"action": mapped, "target": location, "thought": None}

        # Fall back to the agent's drive-based routine
        return agent.get_routine_action(hour, time_of_day)


class DecisionPromptConstructor:
    @staticmethod
    def build(agent, world_state: dict, stimuli: list[str], tick: int) -> tuple[str, str]:
        agent.prune_expired_intentions(tick)

        nearby_parts = []
        for other_id, other in world_state.get("agents", {}).items():
            if other_id == agent.id:
                continue
            if hasattr(other, "current_location") and other.current_location == agent.current_location:
                model = agent.mental_models.models.get(other.name)
                if model:
                    bits = [
                        f"trust={model.trust:.1f}",
                        f"reliability={model.reliability:.1f}",
                        f"gut={model.gut_feeling:+.1f}",
                        f"safety={model.emotional_safety:.1f}",
                    ]
                    if model.what_i_think_they_think_of_me:
                        bits.append(f"they likely see me as {model.what_i_think_they_think_of_me}")
                    if model.predicted_behaviors:
                        bits.append(f"I expect: {model.predicted_behaviors[-1]}")
                    if model.unresolved_issues:
                        bits.append(f"unresolved: {model.unresolved_issues[-1]}")
                    nearby_parts.append(
                        f"- {other.name}: {model.perceived_personality[:60]} ({'; '.join(bits)})"
                    )
                else:
                    nearby_parts.append(f"- {other.name}: don't know them well")

        long_term_goals_text = "\n".join(
            f"- {g['text']} (priority {float(g.get('priority', 0.5)):.2f}, source {g.get('source', 'unknown')})"
            for g in agent.long_term_goals[:4]
            if g.get("text")
        ) or "None"

        active_goals_text = "\n".join(
            f"- {g['text']} (priority {float(g.get('priority', 0.5)):.2f}, kind {g.get('kind', 'general')})"
            for g in agent.active_goals
            if g.get("status") == "active" and g.get("text")
        ) or "None"

        active_intentions_text = "\n".join(
            f"- {i.get('goal', '')} | urgency {float(i.get('urgency', 0.5)):.2f} | "
            f"time_left {max(0, int(i.get('expires_after_ticks', 200)) - max(0, tick - int(i.get('created_tick', tick))))} ticks | "
            f"next: {i.get('next_step', i.get('goal', ''))}"
            for i in agent.active_intentions[:6]
            if i.get("goal")
        ) or "None"

        recent_thoughts = []
        if hasattr(agent, '_recent_inner_thoughts'):
            recent_thoughts = agent._recent_inner_thoughts[-5:]
        thoughts_text = "\n".join(f"- {t}" for t in recent_thoughts) or "Mind is quiet"

        beliefs_text = agent.belief_system.get_prompt_context(max_beliefs=5)
        known_locs = ", ".join(agent.world_model.known_locations.keys()) or "just the clearing"

        health_desc = "healthy"
        if agent.is_sick:
            health_desc = "sick and feverish"
        elif agent.health < 0.5:
            health_desc = "injured"

        role = agent.self_concept or "newcomer"

        system = f"You are {agent.name}, a {agent.profile.age}-year-old {role} in a frontier settlement."
        prompt = DECISION_PROMPT.format(
            name=agent.name,
            age=agent.profile.age,
            role=role,
            location=agent.current_location.replace("_", " "),
            time_of_day=world_state.get("time_of_day", "day"),
            hour=world_state.get("hour", 12),
            current_action=agent.current_action.value,
            health_desc=health_desc,
            novel_stimuli="\n".join(f"- {s}" for s in stimuli) or "General awareness",
            emotion_desc=agent.emotional_state.get_prompt_description(),
            drive_desc=agent.drives.get_prompt_description(),
            worry=agent.working_memory.background_worry or "nothing specific",
            recent_thoughts=thoughts_text,
            working_memory_items=", ".join(i.content if hasattr(i, 'content') else str(i) for i in agent.working_memory.items[:5]) or "mind is clear",
            long_term_goals=long_term_goals_text,
            active_goals=active_goals_text,
            active_intentions=active_intentions_text,
            morning_plan=agent.daily_plan or "No plan yet",
            beliefs=beliefs_text,
            nearby_agents="\n".join(nearby_parts) or "Nobody around",
            skills=agent.skill_memory.get_prompt_summary(),
            known_locations=known_locs,
        )
        return system, prompt


_novelty_detector = NoveltyDetector()


async def decide(agent, world_state: dict, tick: int) -> str | None:
    """Main entry point. Called every tick per agent.
    Returns action description string if novelty triggered deliberation,
    or None to continue current behavior."""
    # Skip agents that are busy
    if agent.is_in_conversation or agent.current_action.value == "sleeping":
        return None
    if agent.path and agent.current_action.value == "walking":
        return None

    novelty_score, stimuli = _novelty_detector.detect(agent, world_state, tick)

    if novelty_score < NOVELTY_THRESHOLD:
        # Routine behavior -- no LLM call
        hour = world_state.get("hour", 12)
        time_of_day = world_state.get("time_of_day", "day")
        routine = RoutineBehavior.get_action(agent, hour, time_of_day)
        if routine:
            agent._last_routine_action = routine
        return None

    # Novelty detected -- engage full decision pipeline
    from llm.client import llm_client

    system, prompt = DecisionPromptConstructor.build(agent, world_state, stimuli, tick)

    result = await llm_client.generate(
        system, prompt,
        temperature=0.8,
        max_tokens=150,
    )

    if result:
        action_desc = result.strip().strip('"').strip("'")
        agent.inner_thought = action_desc[:120]
        agent.working_memory.push(action_desc[:100])
        logger.info("Novelty decision for %s (score=%.2f): %s", agent.name, novelty_score, action_desc[:80])
        return action_desc

    return None


def detect_novelty(agent, observations: dict) -> bool:
    """Legacy compatibility wrapper. Returns bool like the old interface."""
    # Build a minimal world_state from old-style observations
    score, _ = _novelty_detector.detect(agent, {"agents": {}}, 0)
    if score >= NOVELTY_THRESHOLD:
        return True

    # Also check the old observation-based triggers
    for other_name in observations.get("agents_nearby", []):
        model = agent.mental_models.models.get(other_name)
        if model and (model.trust > 0.7 or model.trust < 0.2 or model.unresolved_issues):
            return True
    if observations.get("incoming_conversation"):
        return True
    if observations.get("active_event"):
        return True
    return False


def get_routine_action(agent, time_of_day: str, hour: float) -> dict:
    """Legacy compatibility wrapper."""
    return agent.get_routine_action(hour, time_of_day)


def build_observations(agent, agents_dict: dict, world) -> dict:
    """Build observation context for the agent."""
    nearby = []
    for other_id, other in agents_dict.items():
        if other_id == agent.id:
            continue
        if other.current_location == agent.current_location:
            nearby.append(other.name)
    return {
        "agents_nearby": nearby,
        "incoming_conversation": False,
        "unexpected_location": False,
        "active_event": False,
    }
