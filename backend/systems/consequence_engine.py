"""Consequence Engine -- applies ActionResults to the world state."""

import logging
import random

from systems.open_action_models import (
    ActionResult, SuccessOutcome, FailureOutcome,
    WorldObject, ObservationRecord, ObjectSpec,
)

logger = logging.getLogger("agentica.consequences")


class ConsequenceEngine:
    def __init__(self):
        pass

    def apply(self, result: ActionResult, agent, world, agents: dict, tick: int, day: int = 0) -> list[ObservationRecord]:
        observations: list[ObservationRecord] = []

        # Consume materials
        for resource, amount in result.evaluation.materials_consumed.items():
            self._consume_material(agent, world, resource, amount)

        # Drain energy
        agent.drives.rest = min(1.0, agent.drives.rest + result.evaluation.energy_cost * 0.5)

        if result.success and isinstance(result.outcome, SuccessOutcome):
            observations += self._apply_success(result, agent, world, agents, tick, day)
        else:
            observations += self._apply_failure(result, agent, world, tick)

        # Notify observers
        observations += self._notify_observers(result, agent, world, agents, tick)

        return observations

    def _apply_success(self, result: ActionResult, agent, world, agents: dict, tick: int, day: int) -> list[ObservationRecord]:
        outcome: SuccessOutcome = result.outcome
        observations = []

        # Create objects
        for obj_spec in outcome.objects_created:
            obj = WorldObject(
                id=WorldObject.generate_id(),
                name=obj_spec.name,
                description=obj_spec.description,
                category=obj_spec.category,
                effects=obj_spec.effects,
                durability=obj_spec.durability,
                size=obj_spec.size,
                portable=obj_spec.portable,
                visual_description=obj_spec.visual_description,
                created_by=agent.name,
                created_on=day,
                location=agent.current_location if not obj_spec.portable else None,
                owner=agent.name,
            )

            if obj.portable:
                agent.inventory.append({
                    "name": obj.name,
                    "quantity": 1,
                    "object_id": obj.id,
                    "category": obj.category,
                    "description": obj.description,
                })
            else:
                world.add_object_to_location(obj, agent.current_location)

            world.world_objects[obj.id] = obj

            if obj.category not in world.known_object_types:
                world.known_object_types.add(obj.category)

        # Produce resources
        for resource, amount in outcome.resources_produced.items():
            agent.inventory.append({"name": resource, "quantity": amount})

        # Apply world changes
        for change in outcome.world_changes:
            world.apply_environmental_change(change)

        # Update skills
        skill = outcome.skill_practiced
        if skill:
            agent.skill_memory.record_attempt(skill, True, outcome.skill_difficulty)

        # Record knowledge
        if outcome.knowledge_gained:
            agent.world_model.learn_norm(f"Learned: {outcome.knowledge_gained[:100]}")

        # Register unlocks
        for unlock in result.evaluation.unlocks:
            if unlock and unlock not in world.latent_possibilities:
                world.latent_possibilities.append(unlock)

        return observations

    def _apply_failure(self, result: ActionResult, agent, world, tick: int) -> list[ObservationRecord]:
        outcome: FailureOutcome = result.outcome

        # Waste materials
        for resource, amount in outcome.materials_wasted.items():
            self._consume_material(agent, world, resource, amount)

        # Injury risk
        if outcome.injury_risk > 0 and random.random() < outcome.injury_risk:
            damage = random.uniform(0.05, 0.2)
            agent.health = max(0.1, agent.health - damage)
            agent.episodic_memory.add_simple(
                f"I hurt myself: {outcome.injury_description or 'minor injury'}",
                tick=tick, day=0, time_of_day="", location=agent.current_location,
                category="event", intensity=0.6, emotion="pain",
            )
            logger.info("%s injured (-%s health): %s", agent.name, round(damage, 2), outcome.injury_description)

        # Emotional impact of failure
        if hasattr(agent, "emotional_state"):
            agent.emotional_state.apply_event("frustration", 0.15)

        # Record skill failure
        skill = result.evaluation.on_success.skill_practiced
        if skill:
            agent.skill_memory.record_attempt(skill, False, 0.3)

        # Partial result handling
        if outcome.partial_result:
            agent.world_model.learn_norm(f"Partial result: {outcome.partial_result[:80]}")

        return []

    def _consume_material(self, agent, world, resource: str, amount: float):
        int_amount = max(1, int(amount))
        if agent.consume_inventory(resource, int_amount):
            return
        world.gather_resource(resource, int_amount, agent.current_location)

    def _notify_observers(self, result: ActionResult, agent, world, agents: dict, tick: int) -> list[ObservationRecord]:
        obs = result.evaluation.observability
        who_sees = obs.who_can_see.lower()
        noise = obs.noise_level.lower()

        observer_agents = world.get_agents_who_can_observe(
            agent.current_location, who_sees, noise, agents,
        )

        records = []
        for observer in observer_agents:
            if observer.id == agent.id:
                continue

            what_seen = obs.what_they_see or f"{agent.name} is doing something"
            result_visible = obs.duration_visible.lower() not in ("brief moment",)

            visible_objects = []
            if result.success and isinstance(result.outcome, SuccessOutcome):
                visible_objects = [o.name for o in result.outcome.objects_created]

            record = ObservationRecord(
                observer=observer.name,
                actor=agent.name,
                what_seen=what_seen,
                result_visible=result_visible,
                objects_visible=visible_objects,
                location=agent.current_location,
                tick=tick,
            )
            records.append(record)

            # Push into observer's attention and memory
            observer.working_memory.push(f"I saw {agent.name}: {what_seen[:80]}")
            observer.episodic_memory.add_simple(
                f"Saw {agent.name}: {what_seen[:100]}",
                tick=tick, day=0, time_of_day="", location=agent.current_location,
                category="observation", intensity=0.4, emotion="curious",
            )

        return records


consequence_engine = ConsequenceEngine()
