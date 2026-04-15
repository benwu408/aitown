"""Consequence Engine -- applies ActionResults to the world state."""

import logging
import random

from systems.open_action_models import (
    ActionResult, SuccessOutcome, FailureOutcome,
    WorldObject, ObservationRecord, ObjectSpec, ObjectMutation,
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
        created_objects: list[WorldObject] = []

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
                material_form=obj_spec.material_form,
                object_memory=obj_spec.object_memory or f"This is a new {obj_spec.name.lower()}.",
                contents=list(obj_spec.contents),
                placement=obj_spec.placement,
                relationships=dict(obj_spec.relationships),
                visual_archetype=obj_spec.visual_archetype,
                pixel_spec=obj_spec.pixel_spec,
                created_by=agent.name,
                created_on=day,
                location=(obj_spec.placement or {}).get("location") or (agent.current_location if not obj_spec.portable else None),
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
                if obj.category in {"tool", "mechanism", "container", "art", "marker"}:
                    agent.set_held_object(obj.id)
            else:
                world.add_object_to_location(obj, obj.location or agent.current_location)

            world.world_objects[obj.id] = obj
            created_objects.append(obj)

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

        self._apply_object_mutations(outcome.object_mutations, created_objects, agent, world)

        held = agent.get_held_object() if hasattr(agent, "get_held_object") else None
        if held and held.category in {"tool", "mechanism", "container", "marker"}:
            held.durability = max(0.0, held.durability - min(0.08, 0.01 + outcome.skill_difficulty * 0.03))
            if held.durability <= 0.0:
                world.remove_object(held.id)
                agent.inventory = [item for item in agent.inventory if item.get("object_id") != held.id]
                agent.reconcile_held_object()

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

        self._apply_object_mutations(outcome.object_mutations, [], agent, world)

        held = agent.get_held_object() if hasattr(agent, "get_held_object") else None
        if held and held.category in {"tool", "mechanism", "container", "marker"}:
            held.durability = max(0.0, held.durability - 0.01)
            if held.durability <= 0.0:
                world.remove_object(held.id)
                agent.inventory = [item for item in agent.inventory if item.get("object_id") != held.id]
                agent.reconcile_held_object()

        return []

    def _consume_material(self, agent, world, resource: str, amount: float):
        int_amount = max(1, int(amount))
        if agent.consume_inventory(resource, int_amount):
            return
        world.gather_resource(resource, int_amount, agent.current_location)

    def _resolve_mutation_target(self, selector: str, created_objects: list[WorldObject], agent, world):
        selector = (selector or "").strip()
        if not selector:
            return None
        if selector == "held_object":
            return agent.get_held_object() if hasattr(agent, "get_held_object") else None
        if selector.startswith("created:"):
            name = selector.split(":", 1)[1].strip().lower()
            return next((obj for obj in created_objects if obj.name.lower() == name), None)
        if selector.startswith("owned:"):
            name = selector.split(":", 1)[1].strip().lower()
            return next((obj for obj in world.get_objects_by_owner(agent.name) if obj.name.lower() == name), None)
        if selector.startswith("nearby:"):
            name = selector.split(":", 1)[1].strip().lower()
            return next((obj for obj in world.get_objects_at(agent.current_location) if obj.name.lower() == name), None)
        return next((obj for obj in world.world_objects.values() if obj.name.lower() == selector.lower()), None)

    def _transfer_to_contents(self, agent, obj: WorldObject, payload: dict):
        name = str(payload.get("name", "")).strip()
        qty = float(payload.get("quantity", 1.0) or 1.0)
        source = payload.get("source", "agent_inventory")
        if not name:
            return
        if source == "agent_inventory":
            if not hasattr(agent, "remove_inventory_amount") or not agent.remove_inventory_amount(name, qty):
                return
        entry = next((item for item in obj.contents if item.get("name") == name and not item.get("object_id")), None)
        if entry:
            entry["quantity"] = round(float(entry.get("quantity", 0.0)) + qty, 2)
        else:
            obj.contents.append({"name": name, "quantity": round(qty, 2)})

    def _transfer_from_contents(self, agent, obj: WorldObject, payload: dict):
        name = str(payload.get("name", "")).strip()
        qty = float(payload.get("quantity", 1.0) or 1.0)
        destination = payload.get("destination", "agent_inventory")
        if not name:
            return
        for item in list(obj.contents):
            if item.get("name") != name:
                continue
            available = float(item.get("quantity", 0.0) or 0.0)
            taken = min(available, qty)
            left = round(available - taken, 2)
            if left > 0:
                item["quantity"] = left
            else:
                obj.contents.remove(item)
            if destination == "agent_inventory" and taken > 0:
                if hasattr(agent, "add_inventory_item"):
                    agent.add_inventory_item(name, taken)
                else:
                    agent.inventory.append({"name": name, "quantity": taken})
            break

    def _apply_object_mutations(self, mutations: list[ObjectMutation], created_objects: list[WorldObject], agent, world):
        for mutation in mutations or []:
            obj = self._resolve_mutation_target(mutation.selector, created_objects, agent, world)
            if not obj:
                continue
            if mutation.usage_note:
                obj.usage_history.append(mutation.usage_note)
                obj.usage_history = obj.usage_history[-12:]
            if mutation.new_memory:
                obj.object_memory = mutation.new_memory
            elif mutation.usage_note:
                existing = obj.object_memory.strip()
                addition = mutation.usage_note.strip()
                obj.object_memory = f"{existing} {addition}".strip()[:320]
            for payload in mutation.contents_add:
                if isinstance(payload, dict):
                    self._transfer_to_contents(agent, obj, payload)
            for payload in mutation.contents_remove:
                if isinstance(payload, dict):
                    self._transfer_from_contents(agent, obj, payload)
            if mutation.location is not None:
                obj.location = mutation.location
            if mutation.holder is not None:
                obj.owner = mutation.holder or None
                if mutation.holder in {agent.name, agent.id}:
                    if not any(item.get("object_id") == obj.id for item in agent.inventory):
                        agent.inventory.append({
                            "name": obj.name,
                            "quantity": 1,
                            "object_id": obj.id,
                            "category": obj.category,
                            "description": obj.description,
                        })
                    agent.set_held_object(obj.id)
            if mutation.placement:
                obj.placement = mutation.placement
                obj.location = mutation.placement.get("location") or obj.location or agent.current_location
                obj.portable = False
                agent.inventory = [item for item in agent.inventory if item.get("object_id") != obj.id]
                if getattr(agent, "held_object_id", None) == obj.id:
                    agent.reconcile_held_object()
            if mutation.durability_delta:
                obj.durability = max(0.0, min(1.0, obj.durability + mutation.durability_delta))
            if mutation.relationships:
                obj.relationships.update(mutation.relationships)

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
