import unittest
from types import SimpleNamespace

from systems.interactions import normalize_actionable_payload, process_conversation_consequences
from agents.agent import Agent
from agents.profiles import AGENT_PROFILES
from simulation.world import World


class InteractionNormalizationTests(unittest.TestCase):
    def test_normalizes_explicit_build_commitment(self):
        speaker = SimpleNamespace(name="Ava")
        listener = SimpleNamespace(name="Ben")
        payload = {
            "kind": "decision_to_build",
            "description": "Let's build a shelter by the clearing.",
            "location": "clearing",
            "time_hint": "tomorrow morning",
            "required_resources": ["wood"],
            "participants": ["Ava", "Ben"],
        }
        result = normalize_actionable_payload(payload, speaker, listener, "clearing")
        self.assertIsNotNone(result)
        self.assertEqual(result["kind"], "decision_to_build")
        self.assertEqual(result["location"], "clearing")
        self.assertEqual(result["scheduled_hour"], 8)
        self.assertEqual(result["required_resources"], ["wood"])

    def test_meeting_invitation_normalizes_to_meeting(self):
        speaker = SimpleNamespace(name="Ava")
        listener = SimpleNamespace(name="Ben")
        payload = {
            "kind": "meeting_invitation",
            "description": "Let's gather everyone to talk by the fire tomorrow evening.",
            "location": "clearing",
            "time_hint": "tomorrow evening",
        }
        result = normalize_actionable_payload(payload, speaker, listener, "clearing")
        self.assertIsNotNone(result)
        self.assertEqual(result["kind"], "meeting")
        self.assertEqual(result["scheduled_hour"], 18)

    def test_conversation_updates_social_model_and_intention(self):
        world = World()
        speaker = Agent(AGENT_PROFILES[0], world)
        convo = SimpleNamespace(
            interaction_type="planning",
            location="clearing",
            turns=[{"speaker": "John Harlow", "speech": "I'll help tomorrow.", "trust_shift": "up"}],
            structured_commitments=[{
                "kind": "decision_to_gather",
                "description": "Gather wood together tomorrow morning",
                "participants": [speaker.name, "John Harlow"],
                "location": "forest_edge",
                "time_hint": "tomorrow morning",
                "scheduled_hour": 8,
                "required_resources": ["wood"],
                "recurring": False,
                "status": "planned",
            }],
            structured_proposals=[],
        )

        process_conversation_consequences(speaker, "John Harlow", convo, tick=10, day=1)

        model = speaker.mental_models.models["John Harlow"]
        self.assertGreater(model.trust, 0.5)
        self.assertGreater(model.emotional_safety, 0.5)
        self.assertTrue(any(intent.get("source") == "commitment" for intent in speaker.active_intentions))

    def test_support_signal_updates_alliance_and_creates_intention(self):
        world = World()
        speaker = Agent(AGENT_PROFILES[0], world)
        convo = SimpleNamespace(
            interaction_type="planning",
            location="clearing",
            turns=[{"speaker": "John Harlow", "speech": "I'm with you on this.", "trust_shift": "up"}],
            structured_commitments=[{
                "kind": "support_signal",
                "description": "I support building a shared fire in the clearing.",
                "participants": [speaker.name, "John Harlow"],
                "location": "clearing",
                "time_hint": "soon",
                "scheduled_hour": 12,
                "required_resources": [],
                "recurring": False,
                "status": "planned",
            }],
            structured_proposals=[],
        )

        process_conversation_consequences(speaker, "John Harlow", convo, tick=10, day=1)

        model = speaker.mental_models.models["John Harlow"]
        self.assertGreater(model.alliance_lean, 0.0)
        self.assertTrue(any(intent.get("source") == "support" for intent in speaker.active_intentions))


if __name__ == "__main__":
    unittest.main()
