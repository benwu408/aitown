"""Action Interpreter -- evaluates any proposed action for feasibility and consequences."""

import logging
import random

from systems.open_action_models import (
    ActionIntent, ActionEvaluation, ActionResult,
    SuccessOutcome, FailureOutcome, ObjectSpec, WorldChange,
    Observability, SocialImplications,
)

logger = logging.getLogger("agentica.actions")

ROUTINE_ACTIONS = {"walking", "idle", "sleeping", "eating", "drinking", "gathering", "resting"}


def _safe_float(val, default=0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _safe_int(val, default=1) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _parse_object_spec(d: dict) -> ObjectSpec:
    return ObjectSpec(
        name=d.get("name", "unknown"),
        description=d.get("description", ""),
        category=d.get("category", "other"),
        effects=d.get("effects", {}),
        durability=_safe_float(d.get("durability"), 1.0),
        size=d.get("size", "small"),
        portable=bool(d.get("portable", True)),
        visual_description=d.get("visual_description", ""),
    )


def _parse_world_change(d: dict) -> WorldChange:
    return WorldChange(
        type=d.get("type", "other"),
        description=d.get("description", ""),
        location=d.get("location", ""),
        permanent=bool(d.get("permanent", False)),
        visual_change=d.get("visual_change", ""),
    )


def _parse_success(d: dict) -> SuccessOutcome:
    return SuccessOutcome(
        description=d.get("description", ""),
        objects_created=[_parse_object_spec(o) for o in d.get("objects_created", []) if isinstance(o, dict)],
        resources_produced={k: _safe_float(v) for k, v in d.get("resources_produced", {}).items()},
        world_changes=[_parse_world_change(w) for w in d.get("world_changes", []) if isinstance(w, dict)],
        skill_practiced=d.get("skill_practiced", ""),
        skill_difficulty=_safe_float(d.get("skill_difficulty"), 0.5),
        knowledge_gained=d.get("knowledge_gained", ""),
    )


def _parse_failure(d: dict) -> FailureOutcome:
    return FailureOutcome(
        description=d.get("description", ""),
        materials_wasted={k: _safe_float(v) for k, v in d.get("materials_wasted", {}).items()},
        partial_result=d.get("partial_result"),
        injury_risk=_safe_float(d.get("injury_risk"), 0.0),
        injury_description=d.get("injury_description", ""),
    )


def _parse_observability(d: dict) -> Observability:
    return Observability(
        who_can_see=d.get("who_can_see", "anyone at this location"),
        what_they_see=d.get("what_they_see", ""),
        noise_level=d.get("noise_level", "normal"),
        duration_visible=d.get("duration_visible", "brief moment"),
    )


def _parse_social(d: dict) -> SocialImplications:
    rules = d.get("rules_violated", [])
    if isinstance(rules, str):
        rules = [rules] if rules else []
    return SocialImplications(
        rules_violated=rules,
        precedent=d.get("precedent", ""),
        likely_reactions=d.get("likely_reactions", ""),
    )


def _parse_evaluation(data: dict) -> ActionEvaluation:
    return ActionEvaluation(
        feasible=bool(data.get("feasible", False)),
        why_not=data.get("why_not", ""),
        success_chance=_safe_float(data.get("success_chance"), 0.0),
        time_ticks=_safe_int(data.get("time_ticks"), 1),
        energy_cost=_safe_float(data.get("energy_cost"), 0.1),
        materials_consumed={k: _safe_float(v) for k, v in data.get("materials_consumed", {}).items()},
        on_success=_parse_success(data.get("on_success", {})),
        on_failure=_parse_failure(data.get("on_failure", {})),
        observability=_parse_observability(data.get("observability", {})),
        social_implications=_parse_social(data.get("social_implications", {})),
        unlocks=data.get("unlocks", []) if isinstance(data.get("unlocks"), list) else [],
    )


class ActionInterpreter:
    def __init__(self):
        self.registered_action_types: dict[str, dict] = {}

    async def evaluate_action(self, agent, action_description: str, world) -> ActionResult:
        from llm.client import llm_client

        intent = ActionIntent(
            agent_name=agent.name,
            description=action_description,
            tick_started=0,
            context={
                "location": agent.current_location,
                "nearby_agents": self._get_nearby_names(agent, world),
            },
        )

        inventory_str = ", ".join(
            f"{i.get('name', str(i))} x{i.get('quantity', 1)}" for i in agent.inventory[:10]
        ) or "nothing"
        skills_str = agent.skill_memory.get_prompt_summary()
        resources_str = ", ".join(world.get_resources_at(agent.current_location)) or "none"
        nearby_agents = self._get_nearby_names(agent, world)

        objects_here = []
        if hasattr(world, "get_objects_at"):
            objects_here = [f"{o.name} ({o.category})" for o in world.get_objects_at(agent.current_location)]
        objects_str = ", ".join(objects_here[:10]) or "none"

        time_mgr = getattr(world, "_time_manager", None)
        weather = "clear"
        time_of_day = "day"
        if time_mgr:
            weather = getattr(time_mgr, "weather", "clear")
            time_of_day = getattr(time_mgr, "time_of_day", "day")

        strength = agent.profile.physical_traits.get("strength", 0.5)
        endurance = agent.profile.physical_traits.get("endurance", 0.5)
        dexterity = agent.profile.physical_traits.get("dexterity", 0.5)
        energy = round(1.0 - agent.drives.rest, 2)

        prompt = f"""You are the reality engine for a small settlement survival simulation.
Your job is to determine what happens when someone tries to do something.
Be realistic but generous. Think like a physics simulation crossed with common sense.

WHO IS DOING THIS
Name: {agent.name}, Age: {agent.profile.age}
Strength: {strength}/1.0, Endurance: {endurance}/1.0, Dexterity: {dexterity}/1.0
Health: {round(agent.health, 2)}/1.0, Energy: {energy}/1.0
{skills_str}
Carrying: {inventory_str}

WHAT THEY WANT TO DO
"{action_description}"

WHERE THEY ARE
Location: {agent.current_location}
Resources here: {resources_str}
Objects/structures here: {objects_str}
Other agents present: {', '.join(nearby_agents) or 'nobody'}

WORLD CONTEXT
Weather: {weather}
Time of day: {time_of_day}
Community rules: {world.constitution.summary()}

INSTRUCTIONS
A first attempt at something should be possible but might produce a crude result. Mastery comes with practice.
Inexperienced attempts have lower success chance, not impossibility.

Return JSON:
{{
    "feasible": true/false,
    "why_not": "if infeasible, the specific reason",
    "success_chance": 0.0-1.0,
    "time_ticks": integer,
    "energy_cost": 0.0-1.0,
    "materials_consumed": {{"resource_name": amount}},
    "on_success": {{
        "description": "what happens if it works",
        "objects_created": [
            {{
                "name": "descriptive name",
                "description": "what it is",
                "category": "tool/structure/container/food/medicine/art/clothing/document/marker/furniture/mechanism/other",
                "effects": {{}},
                "durability": 0.0-1.0,
                "size": "tiny/small/medium/large/structure",
                "portable": true/false,
                "visual_description": "brief visual for rendering"
            }}
        ],
        "resources_produced": {{}},
        "world_changes": [
            {{
                "type": "terrain_modification/new_path/building_modification/resource_change/boundary_marker/other",
                "description": "what changed",
                "location": "where",
                "permanent": true/false,
                "visual_change": "how it looks now"
            }}
        ],
        "skill_practiced": "skill name",
        "skill_difficulty": 0.0-1.0,
        "knowledge_gained": "what the agent learns"
    }},
    "on_failure": {{
        "description": "what happens if it fails",
        "materials_wasted": {{}},
        "partial_result": "anything produced even in failure, or null",
        "injury_risk": 0.0-1.0,
        "injury_description": "what kind of injury if unlucky"
    }},
    "observability": {{
        "who_can_see": "anyone at this location / nearby / nobody",
        "what_they_see": "what an observer would perceive",
        "noise_level": "silent/quiet/normal/loud",
        "duration_visible": "brief moment / ongoing process / permanent result"
    }},
    "social_implications": {{
        "rules_violated": [],
        "precedent": "social expectation this sets",
        "likely_reactions": "how others might feel"
    }},
    "unlocks": ["things now possible that weren't before"]
}}"""

        data = await llm_client.generate_json(
            "You are the physics engine for a settlement simulation. Be realistic but permissive. Return valid JSON only.",
            prompt,
            default=None,
            temperature=0.7,
            max_tokens=800,
        )

        if data is None:
            evaluation = ActionEvaluation(feasible=False, why_not="Failed to evaluate action (LLM error)")
            return ActionResult(
                intent=intent, evaluation=evaluation,
                success=False, outcome=FailureOutcome(description="Evaluation failed"),
            )

        evaluation = _parse_evaluation(data)

        if not evaluation.feasible:
            return ActionResult(
                intent=intent, evaluation=evaluation,
                success=False, outcome=FailureOutcome(description=evaluation.why_not),
            )

        # Skill-aware success rolling
        skill_name = evaluation.on_success.skill_practiced or "general"
        skill_entry = agent.skill_memory.activities.get(skill_name, {})
        skill_level = skill_entry.get("skill_level", 0.0)
        adjusted_chance = evaluation.success_chance * (0.5 + skill_level * 0.5)
        succeeded = random.random() < adjusted_chance

        outcome = evaluation.on_success if succeeded else evaluation.on_failure

        return ActionResult(
            intent=intent,
            evaluation=evaluation,
            success=succeeded,
            outcome=outcome,
        )

    def _get_nearby_names(self, agent, world) -> list[str]:
        names = []
        if hasattr(self, "_agents"):
            for a in self._agents.values():
                if a.id != agent.id and a.current_location == agent.current_location:
                    names.append(a.name)
        return names

action_interpreter = ActionInterpreter()
