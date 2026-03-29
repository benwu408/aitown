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
from agents.cognition.drives import DriveSystem
from agents.cognition.working_memory import WorkingMemory, MAX_ITEMS
from agents.cognition.episodic_memory import encode_subjectively, Episode, EpisodicMemory
from agents.cognition.beliefs import BeliefSystem, Belief
from agents.cognition.identity import Identity
from agents.cognition.skills import SkillMemory
from agents.cognition.world_model import WorldModelMemory
from agents.cognition.emotions import EmotionalState
from agents.agent import Agent
from agents.profiles import AGENT_PROFILES
from simulation.world import World


class TestDrivesDecay(unittest.TestCase):
    def test_drives_decay(self):
        ds = DriveSystem()
        old_hunger = ds.hunger
        old_thirst = ds.thirst
        ds.tick_update(is_working=False, is_sleeping=False, is_alone=True,
                       is_socializing=False, wealth=100.0)
        self.assertGreater(ds.hunger, old_hunger)
        self.assertGreater(ds.thirst, old_thirst)

    def test_drives_urgency(self):
        ds = DriveSystem()
        # Set hunger well above its urgency_threshold of 0.7
        ds.hunger = 0.95
        urgency = ds.compute_urgency("hunger")
        self.assertGreater(urgency, 0.5)

        # Set thirst above its urgency_threshold of 0.65
        ds.thirst = 0.9
        name, score = ds.get_most_urgent()
        self.assertIn(name, ("hunger", "thirst"))
        self.assertGreater(score, 0.5)

    def test_drives_thirst_belonging(self):
        ds = DriveSystem()
        self.assertIsInstance(ds.thirst, float)
        self.assertIsInstance(ds.belonging, float)
        old_thirst = ds.thirst
        old_belonging = ds.belonging
        ds.tick_update(is_working=False, is_sleeping=False, is_alone=True,
                       is_socializing=False, wealth=100.0, num_friends=0)
        self.assertGreater(ds.thirst, old_thirst)
        self.assertGreater(ds.belonging, old_belonging)


class TestWorkingMemory(unittest.TestCase):
    def test_working_memory_push(self):
        wm = WorkingMemory()
        wm.push("low item", priority=0.2)
        wm.push("high item", priority=0.9)
        wm.push("mid item", priority=0.5)
        top = wm.get_top_items(3)
        self.assertEqual(top[0].content, "high item")
        self.assertEqual(top[0].priority, 0.9)

    def test_working_memory_eviction(self):
        wm = WorkingMemory()
        # Fill buffer with MAX_ITEMS low-priority items
        for i in range(MAX_ITEMS):
            wm.push(f"item_{i}", priority=0.3)
        self.assertEqual(len(wm.items), MAX_ITEMS)
        # Push a high priority item -- should evict the lowest
        wm.push("important", priority=0.95)
        self.assertEqual(len(wm.items), MAX_ITEMS)
        contents = [i.content for i in wm.items]
        self.assertIn("important", contents)

    def test_working_memory_decay(self):
        wm = WorkingMemory()
        wm.push("decaying", priority=0.5)
        old_priority = wm.items[0].priority
        wm.decay_priorities(amount=0.1)
        self.assertLess(wm.items[0].priority, old_priority)


class TestEpisodicMemorySubjective(unittest.TestCase):
    def test_episodic_memory_subjective(self):
        event = {
            "content": "A fight broke out in the clearing",
            "tick": 100, "day": 1, "time_of_day": "afternoon",
            "location": "clearing", "agents_involved": ["Bob"],
            "valence": -0.5, "intensity": 0.6,
        }

        class FakeEmotions:
            valence = 0.0
            anxiety = 0.0
            def get_dominant_emotion(self):
                return ("neutral", 0.0)

        # Calm personality
        calm_personality = {"neuroticism": 0.1, "agreeableness": 0.5, "extraversion": 0.5}
        ep_calm = encode_subjectively(event, calm_personality, FakeEmotions())

        # Neurotic personality
        neurotic_personality = {"neuroticism": 0.9, "agreeableness": 0.5, "extraversion": 0.5}
        ep_neurotic = encode_subjectively(event, neurotic_personality, FakeEmotions())

        # Neurotic agent should amplify negative valence more
        self.assertLess(ep_neurotic.emotional_valence, ep_calm.emotional_valence)
        self.assertGreater(ep_neurotic.emotional_intensity, ep_calm.emotional_intensity)


class TestBeliefs(unittest.TestCase):
    def test_beliefs_extract(self):
        bs = BeliefSystem()
        episodes = []
        # Create enough episodes with the same agent to form a belief
        for i in range(5):
            episodes.append(Episode(
                content=f"I talked with Alice at the clearing",
                tick=i * 10, day=0, time_of_day="morning",
                location="clearing", agents_involved=["Alice"],
                emotional_valence=0.3, emotional_intensity=0.5,
            ))
        new_beliefs = bs.extract_from_episodes(episodes)
        # Should form a positive belief about Alice
        self.assertGreater(len(new_beliefs), 0)
        # Check it was added to the system
        self.assertGreater(len(bs.beliefs), 0)

    def test_beliefs_nightly_reflection(self):
        bs = BeliefSystem()
        # Day with many negative events
        episodes = []
        for i in range(5):
            episodes.append(Episode(
                content=f"Bad thing happened #{i}",
                tick=100 + i, day=1, time_of_day="afternoon",
                location="clearing", emotional_valence=-0.5,
                emotional_intensity=0.6,
            ))
        changes = bs.nightly_reflection_update(episodes)
        self.assertGreater(len(changes), 0)
        # Should have a cautious belief
        self.assertTrue(any("not been going well" in c for c in changes))


class TestIdentity(unittest.TestCase):
    def test_identity_tensions(self):
        identity = Identity()
        identity.self_narrative = "This is home"
        identity.sense_of_belonging = 0.1  # Low belonging but narrative says "home"

        beliefs = [Belief(content="I value kindness", category="self_belief", confidence=0.7)]
        relationships = {}
        episodes = []  # No episodes of actually helping

        tensions = identity.detect_tensions(beliefs, relationships, episodes)
        self.assertGreater(len(tensions), 0)
        types_found = [t["type"] for t in tensions]
        # Should detect narrative_feeling_gap and/or value_action_gap
        self.assertTrue(
            "narrative_feeling_gap" in types_found or "value_action_gap" in types_found
        )

    def test_identity_goals(self):
        identity = Identity()
        identity.self_narrative = "This is home"
        identity.sense_of_belonging = 0.1

        beliefs = [Belief(content="I value helping others", category="self_belief", confidence=0.7)]
        identity.detect_tensions(beliefs, {}, [])
        self.assertGreater(len(identity.identity_tensions), 0)

        goals = identity.generate_goals_from_tensions()
        self.assertGreater(len(goals), 0)
        self.assertTrue(all("text" in g for g in goals))


class TestIntentionLifecycle(unittest.TestCase):
    def test_expired_intentions_are_pruned(self):
        agent = Agent(AGENT_PROFILES[0], World())
        agent.add_intention(
            "Talk to John",
            "Need to follow up on something awkward.",
            0.5,
            "conversation",
            created_tick=10,
            expires_after_ticks=20,
        )
        agent.prune_expired_intentions(40)
        self.assertEqual(agent.active_intentions, [])

    def test_refreshable_intention_reduces_urgency_instead_of_disappearing(self):
        agent = Agent(AGENT_PROFILES[0], World())
        agent.add_intention(
            "Check back with Eleanor",
            "This still matters if she is nearby again.",
            0.8,
            "conversation",
            created_tick=10,
            expires_after_ticks=20,
            refresh_on_relevance=True,
        )
        agent.prune_expired_intentions(40)
        self.assertEqual(len(agent.active_intentions), 1)
        self.assertEqual(agent.active_intentions[0]["created_tick"], 40)
        self.assertLess(agent.active_intentions[0]["urgency"], 0.8)


class TestSkills(unittest.TestCase):
    def test_skills_record(self):
        sm = SkillMemory()
        # Record successes
        sm.record_success("woodcutting", difficulty=0.5, tick=10)
        sm.record_success("woodcutting", difficulty=0.5, tick=20)
        sm.record_failure("woodcutting", tick=30)

        entry = sm.activities["woodcutting"]
        self.assertEqual(entry["attempts"], 3)
        self.assertEqual(entry["successes"], 2)
        self.assertEqual(entry["failures"], 1)
        self.assertGreater(entry["skill_level"], 0.0)


class TestWorldModel(unittest.TestCase):
    def test_world_model_confidence(self):
        wm = WorldModelMemory()
        wm.learn("The river has fish", confidence=0.8, tick=10)
        self.assertEqual(len(wm.knowledge), 1)
        self.assertAlmostEqual(wm.knowledge[0]["confidence"], 0.8)

        wm.challenge("The river has fish")
        self.assertLess(wm.knowledge[0]["confidence"], 0.8)


class TestEmotions(unittest.TestCase):
    def test_emotions_event_mappings(self):
        es = EmotionalState()

        # action_success
        old_pride = es.pride
        es.apply_event("action_success")
        self.assertGreater(es.pride, old_pride)

        # action_failure
        es2 = EmotionalState()
        old_shame = es2.shame
        es2.apply_event("action_failure")
        self.assertGreater(es2.shame, old_shame)

        # social_rejection
        es3 = EmotionalState()
        old_loneliness = es3.loneliness
        es3.apply_event("social_rejection")
        self.assertGreater(es3.loneliness, old_loneliness)

        # social_acceptance
        es4 = EmotionalState()
        old_joy = es4.joy
        es4.apply_event("social_acceptance")
        self.assertGreater(es4.joy, old_joy)

        # betrayed
        es5 = EmotionalState()
        old_resentment = es5.resentment
        es5.apply_event("betrayed", target="Alice")
        self.assertGreater(es5.resentment, old_resentment)
        self.assertEqual(es5.resentment_target, "Alice")

        # helped_someone
        es6 = EmotionalState()
        old_pride6 = es6.pride
        es6.apply_event("helped_someone")
        self.assertGreater(es6.pride, old_pride6)


if __name__ == "__main__":
    unittest.main()
