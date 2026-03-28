"""Action Interpreter — evaluates any proposed action for feasibility and consequences."""

import logging
import random

logger = logging.getLogger("agentica.actions")

ROUTINE_ACTIONS = {"walking", "idle", "sleeping", "eating", "drinking", "gathering", "resting"}


class ActionInterpreter:
    def __init__(self):
        self.registered_action_types: dict[str, dict] = {}

    async def evaluate_action(self, agent, action_description: str, world) -> dict:
        """Evaluate whether an action is possible and what happens."""
        from llm.client import llm_client

        # Build context
        inventory_str = ", ".join(i.get("name", str(i)) for i in agent.inventory[:5]) or "nothing"
        skills_str = agent.skill_memory.get_prompt_summary()
        resources_str = ", ".join(world.get_resources_at(agent.current_location)) or "none"
        nearby_agents = [a.name for a in self._get_nearby(agent, world)] if hasattr(self, '_agents') else []

        prompt = f"""You are the physics/logic engine for a small settlement simulation. Evaluate this action.

AGENT: {agent.name} (Age: {agent.profile.age})
Physical: strength={agent.profile.physical_traits.get('strength',0.5)}, endurance={agent.profile.physical_traits.get('endurance',0.5)}, dexterity={agent.profile.physical_traits.get('dexterity',0.5)}
Inventory: {inventory_str}
Location: {agent.current_location}
Skills: {skills_str}

PROPOSED ACTION: {action_description}

RESOURCES AT LOCATION: {resources_str}
NEARBY AGENTS: {', '.join(nearby_agents) or 'nobody'}
WEATHER: {world.time_info.get('weather', 'clear') if hasattr(world, 'time_info') else 'clear'}

WORLD RULES: {world.constitution.summary()}

Evaluate realistically. Be open to creative actions but physically grounded.

Return JSON:
{{
    "is_possible": true/false,
    "reason": "why or why not",
    "success_probability": 0.0-1.0,
    "time_ticks": 5,
    "resources_consumed": {{}},
    "resources_produced": {{}},
    "skill_used": "skill name",
    "objects_created": [],
    "world_changes": [],
    "social_visibility": "nearby/everyone/private"
}}"""

        result = await llm_client.generate_json(
            "You are the physics engine for a settlement simulation. Be realistic but permissive.",
            prompt,
            default={"is_possible": False, "reason": "evaluation failed"},
        )
        return result

    def apply_consequences(self, agent, result: dict, world):
        """Apply the consequences of a successful action."""
        events = []

        # Consume resources
        for resource, amount in result.get("resources_consumed", {}).items():
            # Try inventory first
            removed = False
            for item in agent.inventory[:]:
                if item.get("name") == resource:
                    item["quantity"] = item.get("quantity", 1) - amount
                    if item["quantity"] <= 0:
                        agent.inventory.remove(item)
                    removed = True
                    break
            if not removed:
                world.gather_resource(resource, amount, agent.current_location)

        # Produce resources → add to inventory
        for resource, amount in result.get("resources_produced", {}).items():
            agent.inventory.append({"name": resource, "quantity": amount})

        # Create objects
        for obj in result.get("objects_created", []):
            if isinstance(obj, dict):
                obj_type = obj.get("type", "other")
                if obj_type == "structure":
                    # Build a structure on the map
                    spot = world.find_empty_space(2, 2)
                    if spot:
                        bid = world.build_structure(
                            spot[0], spot[1], 2, 2,
                            obj.get("name", "Structure"),
                            agent.name,
                            obj.get("description", ""),
                        )
                        if bid:
                            events.append({
                                "type": "system_event",
                                "eventType": "building_constructed",
                                "label": "Construction!",
                                "description": f"{agent.name} built {obj.get('name', 'something')}",
                            })
                else:
                    world.created_objects.append({
                        "name": obj.get("name", "unknown"),
                        "type": obj_type,
                        "created_by": agent.name,
                        "location": agent.current_location,
                    })

        # Track skill
        skill = result.get("skill_used", "")
        if skill:
            success = random.random() < result.get("success_probability", 0.5)
            agent.skill_memory.record_attempt(skill, success, 0.5)

        return events


action_interpreter = ActionInterpreter()
