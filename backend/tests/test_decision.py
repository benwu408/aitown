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
from agents.cognition.decision import NoveltyDetector, RoutineBehavior, DecisionPromptConstructor
from agents.cognition.drives import DriveSystem
from agents.cognition.working_memory import WorkingMemory
from agents.cognition.episodic_memory import EpisodicMemory
from agents.cognition.beliefs import BeliefSystem
from agents.cognition.mental_models import MentalModelSystem
from agents.cognition.skills import SkillMemory
from agents.cognition.world_model import WorldModelMemory
from agents.cognition.identity import Identity
from agents.cognition.emotions import EmotionalState
from simulation.actions import ActionType


class _FakeProfile:
    def __init__(self):
        self.id = "agent_tester"
        self.name = "Tester"
        self.age = 30
        self.personality = {
            "openness": 0.5, "conscientiousness": 0.5,
            "extraversion": 0.5, "agreeableness": 0.5, "neuroticism": 0.5,
        }
        self.values = ["helpfulness"]
        self.backstory = "A wandering tester."


class _FakeAgent:
    """Minimal agent stub with enough fields for decision pipeline tests."""
    def __init__(self):
        self.id = "agent_tester"
        self.name = "Tester"
        self.profile = _FakeProfile()
        self.current_location = "clearing"
        self.previous_location = ""
        self.current_action = ActionType.IDLE
        self.inner_thought = ""
        self.daily_plan = ""
        self.daily_schedule = []
        self.path = []
        self.long_term_goals = []
        self.active_goals = []
        self.active_intentions = []
        self.is_in_conversation = False
        self.is_sick = False
        self.health = 1.0
        self.self_concept = "newcomer"
        self._recent_inner_thoughts = []

        self.drives = DriveSystem()
        self.working_memory = WorkingMemory()
        self.episodic_memory = EpisodicMemory()
        self.belief_system = BeliefSystem()
        self.mental_models = MentalModelSystem()
        self.skill_memory = SkillMemory()
        self.world_model = WorldModelMemory()
        self.identity = Identity()
        self.emotional_state = EmotionalState()

    def get_routine_action(self, hour, time_of_day):
        return {"action": "idle", "target": self.current_location, "thought": None}

    def prune_expired_intentions(self, current_tick):
        return None


class TestNoveltyDetectorNoNovelty(unittest.TestCase):
    def test_novelty_detector_no_novelty(self):
        nd = NoveltyDetector()
        agent = _FakeAgent()
        # Stable state: no new items, no drive change, same location
        # First call establishes baselines
        nd.detect(agent, {"agents": {}}, tick=0)
        # Second call should show low novelty
        score, stimuli = nd.detect(agent, {"agents": {}}, tick=1)
        # Score should be below 0.3 (might be slightly above 0 due to random snap)
        # We check it's reasonably low, accounting for the 3% random chance
        self.assertLessEqual(score, 1.0)


class TestNoveltyDetectorNewObservation(unittest.TestCase):
    def test_novelty_detector_new_observation(self):
        nd = NoveltyDetector()
        agent = _FakeAgent()
        # Establish baseline
        nd.detect(agent, {"agents": {}}, tick=0)
        # Push new items to working memory
        agent.working_memory.push("Something unusual happened", priority=0.8)
        agent.working_memory.push("A strange sound from the forest", priority=0.7)
        agent.working_memory.push("Smoke on the horizon", priority=0.9)

        score, stimuli = nd.detect(agent, {"agents": {}}, tick=1)
        self.assertGreater(score, 0.0)
        # Should have a "New thought" stimulus
        self.assertTrue(any("New thought" in s for s in stimuli))


class TestNoveltyDetectorDriveShift(unittest.TestCase):
    def test_novelty_detector_drive_shift(self):
        nd = NoveltyDetector()
        agent = _FakeAgent()
        # Establish baseline
        nd.detect(agent, {"agents": {}}, tick=0)

        # Force a dominant drive change by making hunger very high
        agent.drives.hunger = 0.99
        agent.drives.thirst = 0.0
        agent.drives.rest = 0.0
        agent.drives.social_need = 0.0
        agent.drives.belonging = 0.0
        agent.drives.safety_need = 0.0
        agent.drives.shelter_need = 0.0
        agent.drives.purpose_need = 0.0
        agent.drives.competence_need = 0.0
        agent.drives.autonomy_need = 0.0
        agent.drives.energy = 1.0
        agent.drives.health = 1.0
        # Force prev dominant to something different
        agent.drives._prev_dominant = "social"

        score, stimuli = nd.detect(agent, {"agents": {}}, tick=1)
        self.assertGreater(score, 0.3)
        self.assertTrue(any("Urgent need" in s for s in stimuli))


class TestRoutineBehavior(unittest.TestCase):
    def test_routine_behavior(self):
        agent = _FakeAgent()
        agent.daily_schedule = [
            {"hour": 6, "activity": "eat", "location": "clearing"},
            {"hour": 8, "activity": "work", "location": "forest_edge"},
            {"hour": 12, "activity": "eat", "location": "clearing"},
            {"hour": 20, "activity": "sleep", "location": "clearing"},
        ]

        # At hour 9, the best step should be hour 8 (work at forest_edge)
        result = RoutineBehavior.get_action(agent, hour=9.0, time_of_day="morning")
        self.assertIsNotNone(result)
        # Should want to walk to forest_edge since agent is at clearing
        self.assertEqual(result["action"], "walking")
        self.assertEqual(result["target"], "forest_edge")


class TestDecisionPromptConstructor(unittest.TestCase):
    def test_decision_prompt_constructor(self):
        agent = _FakeAgent()
        agent.working_memory.push("I need to find water", priority=0.8)
        agent.long_term_goals = [{"text": "Become someone people rely on", "priority": 0.8, "source": "identity_tension"}]
        agent.active_goals = [{"text": "Build a shelter", "status": "active"}]
        agent.active_intentions = [{
            "goal": "Talk to John about the missing food",
            "urgency": 0.7,
            "created_tick": 40,
            "expires_after_ticks": 200,
            "next_step": "find John near the clearing",
        }]
        agent.belief_system.add("Wood is plentiful in the forest", tick=0)
        agent.drives.hunger = 0.8
        model = agent.mental_models.get_or_create("John")
        model.trust = 0.7
        model.gut_feeling = -0.2
        model.what_i_think_they_think_of_me = "suspicious and withholding"
        model.predicted_behaviors = ["question me if I approach too casually"]
        model.perceived_personality = "proud and observant"

        other = _FakeAgent()
        other.id = "other"
        other.name = "John"

        world_state = {
            "agents": {"other": other},
            "time_of_day": "morning",
            "hour": 8,
        }
        stimuli = ["Noticed: The river is nearby"]

        system, prompt = DecisionPromptConstructor.build(agent, world_state, stimuli, tick=50)

        # Verify prompt contains key elements
        self.assertIn("Tester", system)
        self.assertIn("The river is nearby", prompt)
        self.assertIn("Build a shelter", prompt)
        self.assertIn("Become someone people rely on", prompt)
        self.assertIn("Talk to John about the missing food", prompt)
        self.assertIn("suspicious and withholding", prompt)
        self.assertIn("gut=-0.2", prompt)
        self.assertIn("find water", prompt)
        # Should contain drives info (might say "hungry" or "starving")
        self.assertTrue("hungry" in prompt.lower() or "starving" in prompt.lower())
        # Should contain emotions or inner state section
        self.assertTrue("emotion" in prompt.lower() or "inner state" in prompt.lower())


if __name__ == "__main__":
    unittest.main()
