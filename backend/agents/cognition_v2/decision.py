"""Decision pipeline — novelty detection, routine behavior, and LLM-gated decisions."""

import logging
import random
from simulation.actions import ActionType

logger = logging.getLogger("agentica.decision")


def detect_novelty(agent, observations: dict) -> bool:
    """Should this tick trigger an LLM decision call? Most ticks: no."""
    # Someone I have strong feelings about is nearby
    for other_name in observations.get("agents_nearby", []):
        model = agent.mental_models.models.get(other_name)
        if model and (model.trust > 0.7 or model.trust < 0.2 or model.unresolved_issues):
            return True

    # Incoming conversation
    if observations.get("incoming_conversation"):
        return True

    # Unexpected location (I'm somewhere I don't usually go at this time)
    if observations.get("unexpected_location"):
        return True

    # An event was announced
    if observations.get("active_event"):
        return True

    # A drive crossed a critical threshold
    if agent.drives.dominant_drive_changed():
        return True

    # Emotional threshold crossed
    if agent.emotional_state.just_crossed_threshold():
        return True

    # A goal is actionable right now
    for goal in agent.active_goals:
        if goal.get("status") == "active":
            # If goal mentions a person who's nearby
            for other_name in observations.get("agents_nearby", []):
                if other_name.lower() in goal.get("text", "").lower():
                    return True

    # Random chance — snap out of autopilot
    if random.random() < 0.03:
        return True

    return False


def get_routine_action(agent, time_of_day: str, hour: float) -> dict:
    """Simple rule-based behavior for non-novel ticks. No LLM call."""
    personality = agent.profile.personality
    is_social = personality.get("extraversion", 0.5) > 0.5

    # Drive interrupts
    should_interrupt, interrupt_type = agent.drives.should_interrupt_plan()
    if should_interrupt:
        if interrupt_type == "find_food":
            return {"action": "walking", "target": "bakery", "thought": "I need to eat."}
        elif interrupt_type == "go_sleep":
            return {"action": "walking", "target": agent.profile.home, "thought": "I can barely keep my eyes open."}
        elif interrupt_type == "seek_company":
            return {"action": "walking", "target": "tavern", "thought": "I need to be around people."}
        elif interrupt_type == "seek_safety":
            return {"action": "walking", "target": agent.profile.home, "thought": "I need to go home."}

    # Normal routine based on time of day
    if time_of_day == "night" or hour >= 22 or hour < 5:
        return {"action": "sleeping", "target": agent.profile.home, "thought": None}

    if time_of_day in ("dawn", "morning") and hour < 8:
        if agent.current_location == agent.profile.home:
            return {"action": "eating", "target": agent.profile.home, "thought": None}

    if time_of_day in ("morning", "midday", "afternoon") and 8 <= hour < 17:
        if agent.current_location != agent.profile.workplace:
            return {"action": "walking", "target": agent.profile.workplace, "thought": "Time for work."}
        return {"action": "working", "target": agent.profile.workplace, "thought": None}

    if time_of_day == "midday" and agent.drives.hunger > 0.5:
        if is_social:
            return {"action": "walking", "target": "tavern", "thought": "Lunch at the tavern."}
        return {"action": "eating", "target": agent.profile.home, "thought": None}

    if time_of_day == "evening":
        if is_social and agent.drives.social_need > 0.3:
            return {"action": "walking", "target": "tavern", "thought": None}
        elif personality.get("openness", 0.5) > 0.6:
            return {"action": "walking", "target": "park", "thought": None}
        return {"action": "walking", "target": agent.profile.home, "thought": None}

    return {"action": "idle", "target": agent.current_location, "thought": None}


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
