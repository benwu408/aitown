import sys
import types

fake_settings_module = types.ModuleType("pydantic_settings")


class BaseSettings:
    def __init__(self, **kwargs):
        for name, value in self.__class__.__dict__.items():
            if name.startswith("_") or callable(value):
                continue
            setattr(self, name, kwargs.get(name, value))


fake_settings_module.BaseSettings = BaseSettings
sys.modules.setdefault("pydantic_settings", fake_settings_module)
fake_aiosqlite = types.ModuleType("aiosqlite")
fake_aiosqlite.connect = None
sys.modules.setdefault("aiosqlite", fake_aiosqlite)

import unittest
from systems.open_action_models import (
    ActionIntent, ActionEvaluation, ActionResult,
    SuccessOutcome, FailureOutcome, ObjectSpec,
    WorldObject, Observability, WorldChange,
)
from systems.consequence_engine import ConsequenceEngine
from systems.pattern_detector import PatternDetector
from systems.innovation import InnovationTracker
from agents.cognition.drives import DriveSystem
from agents.cognition.working_memory import WorkingMemory
from agents.cognition.episodic_memory import EpisodicMemory
from agents.cognition.skills import SkillMemory
from agents.cognition.world_model import WorldModelMemory
from agents.cognition.emotions import EmotionalState
from simulation.world import World


class _StubAgent:
    """Minimal agent for consequence engine tests."""
    def __init__(self, name, location="clearing"):
        self.id = f"agent_{name.lower()}"
        self.name = name
        self.current_location = location
        self.health = 1.0
        self.inventory = []
        self.drives = DriveSystem()
        self.working_memory = WorkingMemory()
        self.episodic_memory = EpisodicMemory()
        self.skill_memory = SkillMemory()
        self.world_model = WorldModelMemory()
        self.emotional_state = EmotionalState()
        self.is_sick = False

    def consume_inventory(self, resource, amount):
        for item in self.inventory:
            if item.get("name") == resource:
                if item.get("quantity", 0) >= amount:
                    item["quantity"] -= amount
                    return True
        return False


class TestActionModels(unittest.TestCase):
    def test_action_models(self):
        intent = ActionIntent(
            agent_name="Alice",
            description="Chop wood at the forest edge",
            tick_started=100,
            context={"location": "forest_edge"},
        )
        self.assertEqual(intent.agent_name, "Alice")
        self.assertEqual(intent.tick_started, 100)

        evaluation = ActionEvaluation(
            feasible=True,
            success_chance=0.8,
            time_ticks=3,
            energy_cost=0.2,
            materials_consumed={"stone": 1.0},
        )
        self.assertTrue(evaluation.feasible)
        self.assertAlmostEqual(evaluation.success_chance, 0.8)

        result = ActionResult(
            intent=intent,
            evaluation=evaluation,
            success=True,
            outcome=SuccessOutcome(description="Chopped wood"),
            tick_completed=103,
        )
        self.assertTrue(result.success)
        self.assertEqual(result.tick_completed, 103)


class TestConsequenceEngineSuccess(unittest.TestCase):
    def test_consequence_engine_success(self):
        engine = ConsequenceEngine()
        world = World()
        agent = _StubAgent("Alice")

        obj_spec = ObjectSpec(
            name="Wooden Spear",
            description="A sharpened wooden spear",
            category="tool",
            portable=True,
        )
        intent = ActionIntent(agent_name="Alice", description="Craft a spear", tick_started=50)
        evaluation = ActionEvaluation(
            feasible=True, success_chance=0.9, time_ticks=2,
            energy_cost=0.1, materials_consumed={},
        )
        outcome = SuccessOutcome(
            description="Crafted a wooden spear",
            objects_created=[obj_spec],
            skill_practiced="crafting",
            skill_difficulty=0.5,
        )
        result = ActionResult(
            intent=intent, evaluation=evaluation,
            success=True, outcome=outcome, tick_completed=52,
        )

        observations = engine.apply(result, agent, world, {}, tick=52, day=1)

        # Object should appear in world
        self.assertGreater(len(world.world_objects), 0)
        # Agent should have it in inventory (portable)
        self.assertTrue(any(i["name"] == "Wooden Spear" for i in agent.inventory))
        # Skill should be recorded
        self.assertGreater(agent.skill_memory.get_skill_level("crafting"), 0.0)


class TestConsequenceEngineFailure(unittest.TestCase):
    def test_consequence_engine_failure(self):
        engine = ConsequenceEngine()
        world = World()
        agent = _StubAgent("Bob")
        agent.inventory.append({"name": "stone", "quantity": 5})

        intent = ActionIntent(agent_name="Bob", description="Build a wall", tick_started=60)
        evaluation = ActionEvaluation(
            feasible=True, success_chance=0.3, time_ticks=5,
            energy_cost=0.3, materials_consumed={"stone": 2.0},
            on_success=SuccessOutcome(skill_practiced="building", skill_difficulty=0.7),
        )
        outcome = FailureOutcome(
            description="The wall collapsed",
            materials_wasted={"stone": 1.0},
        )
        result = ActionResult(
            intent=intent, evaluation=evaluation,
            success=False, outcome=outcome, tick_completed=65,
        )

        engine.apply(result, agent, world, {}, tick=65)

        # Skill failure should be recorded
        entry = agent.skill_memory.activities.get("building")
        self.assertIsNotNone(entry)
        self.assertGreater(entry["failures"], 0)


class TestConsequenceEngineObservers(unittest.TestCase):
    def test_consequence_engine_observers(self):
        engine = ConsequenceEngine()
        world = World()
        actor = _StubAgent("Alice", location="clearing")
        observer = _StubAgent("Bob", location="clearing")

        agents = {
            actor.id: actor,
            observer.id: observer,
        }

        intent = ActionIntent(agent_name="Alice", description="Dance wildly", tick_started=70)
        evaluation = ActionEvaluation(
            feasible=True, success_chance=1.0,
            observability=Observability(
                who_can_see="anyone at this location",
                what_they_see="Alice is dancing wildly",
                noise_level="loud",
            ),
        )
        outcome = SuccessOutcome(description="Danced")
        result = ActionResult(
            intent=intent, evaluation=evaluation,
            success=True, outcome=outcome, tick_completed=71,
        )

        observations = engine.apply(result, actor, world, agents, tick=71)

        # Bob should have an observation record
        self.assertTrue(any(o.observer == "Bob" for o in observations))
        # Bob's working memory should have the observation
        bob_wm_contents = [i.content for i in observer.working_memory.items]
        self.assertTrue(any("Alice" in c for c in bob_wm_contents))


class TestPatternDetector(unittest.TestCase):
    def test_pattern_detector(self):
        pd = PatternDetector()
        for i in range(12):
            pd.record_action(f"agent_{i % 4}", {
                "type": "gathering",
                "location": "clearing",
                "resource": "wood",
            }, tick=i * 10)

        self.assertGreater(pd._gathering_counts["clearing"]["gathering"], 0)


class TestInnovationTracker(unittest.TestCase):
    def test_innovation_tracker(self):
        tracker = InnovationTracker()

        class FakeAgent:
            name = "Alice"

        agent = FakeAgent()
        action_result = {
            "action_type": "craft",
            "description": "Made a fishing net from vines",
            "tick": 100,
        }

        innovation = tracker.record_new_action(agent, action_result, None)
        self.assertIsNotNone(innovation)
        self.assertEqual(innovation["inventor"], "Alice")

        # Record observation
        tracker.record_observation(innovation["id"], "Bob", "impressed")
        innov_data = list(tracker._innovations.values())[0]
        self.assertIn("Bob", innov_data["observers"])

        # Same action again from same agent should return None (not new)
        dup = tracker.record_new_action(agent, action_result, None)
        self.assertIsNone(dup)


if __name__ == "__main__":
    unittest.main()
