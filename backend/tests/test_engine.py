import unittest
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

from simulation.engine import SimulationEngine


class EnginePlanningTests(unittest.TestCase):
    def setUp(self):
        self.engine = SimulationEngine()
        self.agent = next(iter(self.engine.agents.values()))

    def test_schedule_drives_action_when_needs_are_not_urgent(self):
        self.agent.current_location = "forest_edge"
        self.agent.position = self.engine.world.get_location_entry("forest_edge")
        self.agent.working_memory.background_worry = ""
        self.agent.working_memory.current_goal = ""
        self.agent.daily_schedule = [
            {"hour": 8, "location": "forest_edge", "activity": "gather wood", "label": "08:00 gather wood at forest edge"}
        ]
        self.engine.time_manager.tick_in_day = int((8 / 24) * self.engine.time_manager.ticks_per_day)

        routine, reason = self.engine._get_planned_action(self.agent, self.engine.time_manager.hour, self.engine.time_manager.time_of_day)

        self.assertEqual(reason, None)
        self.assertEqual(routine["action"], "gathering")
        self.assertEqual(routine["resource"], "wood")
        self.assertEqual(self.agent.plan_mode, "scheduled")

    def test_urgent_need_can_override_schedule(self):
        self.agent.current_location = "forest_edge"
        self.agent.position = self.engine.world.get_location_entry("forest_edge")
        self.agent.daily_schedule = [
            {"hour": 8, "location": "forest_edge", "activity": "gather wood", "label": "08:00 gather wood at forest edge"}
        ]
        self.agent.drives.hunger = 0.95
        self.engine.time_manager.tick_in_day = int((8 / 24) * self.engine.time_manager.ticks_per_day)

        routine, reason = self.engine._get_planned_action(self.agent, self.engine.time_manager.hour, self.engine.time_manager.time_of_day)

        self.assertIsNotNone(routine)
        self.assertIn("body", reason.lower())
        self.assertEqual(self.agent.plan_mode, "deviating")

    def test_strong_intention_can_outrank_schedule(self):
        self.agent.current_location = "clearing"
        self.agent.daily_schedule = [
            {"hour": 8, "location": "forest_edge", "activity": "gather wood", "label": "08:00 gather wood at forest edge"}
        ]
        self.agent.active_intentions = [{
            "goal": "Check on Eleanor",
            "why": "I promised I'd look for her.",
            "urgency": 0.92,
            "source": "commitment",
            "target_location": "clearing",
            "next_step": "meet and check in",
            "status": "active",
        }]
        self.engine.time_manager.tick_in_day = int((8 / 24) * self.engine.time_manager.ticks_per_day)

        routine, reason = self.engine._get_planned_action(self.agent, self.engine.time_manager.hour, self.engine.time_manager.time_of_day)

        self.assertEqual(self.agent.plan_mode, "commitment")
        self.assertIsNotNone(reason)
        self.assertIn("commitment", reason.lower())
        self.assertEqual(routine["target"], "clearing")

    def test_repeated_blocked_outcomes_create_recovery_intention(self):
        self.engine._note_plan_outcome(self.agent, False, "building", "Not enough wood.")
        self.engine._note_plan_outcome(self.agent, False, "building", "Still not enough wood.")

        self.assertTrue(any("Get unstuck" in intention.get("goal", "") for intention in self.agent.active_intentions))
        self.assertGreater(len(self.agent.blocked_reasons), 0)

    def test_agent_pauses_and_resumes_for_conversation(self):
        self.agent.path = [(1, 1), (2, 2), (3, 3)]
        self.agent.path_index = 1
        self.agent.move_target = "forest_edge"

        self.agent.pause_for_conversation(25)

        self.assertEqual(self.agent.current_action.value, "talking")
        self.assertEqual(self.agent.path, [])
        self.assertEqual(self.agent.paused_move_target, "forest_edge")

        self.agent.resume_after_conversation()

        self.assertEqual(self.agent.current_action.value, "walking")
        self.assertEqual(self.agent.path, [(1, 1), (2, 2), (3, 3)])
        self.assertEqual(self.agent.path_index, 1)
        self.assertEqual(self.agent.move_target, "forest_edge")

    def test_sleep_action_walks_home_before_sleeping(self):
        self.agent.current_location = "clearing"
        self.agent.world_model.known_claims["building_1"] = {"claimed_by": self.agent.name}

        routine = {"action": "sleeping", "target": "building_1", "thought": "Time to rest."}
        target = routine["target"]
        action = routine["action"]

        if action == "sleeping":
            if target != self.agent.current_location:
                self.agent.start_walking(target)
            else:
                self.agent.current_action = self.agent.current_action.SLEEPING

        self.assertEqual(self.agent.current_action.value, "walking")
        self.assertEqual(self.agent.move_target, "building_1")

    def test_sleep_lasts_until_morning(self):
        self.engine.tick = 100
        self.engine.time_manager.day = 1
        self.engine.time_manager.tick_in_day = int((23 / 24) * self.engine.time_manager.ticks_per_day)

        wake_tick = self.engine._next_morning_tick()
        self.agent.start_sleeping_until(wake_tick)

        self.assertEqual(self.agent.current_action.value, "sleeping")
        self.assertGreater(self.agent.sleep_until_tick, self.engine.tick)

        self.engine.tick = wake_tick - 1
        self.assertEqual(self.agent.current_action.value, "sleeping")

        self.engine.tick = wake_tick
        if self.agent.current_action.value == "sleeping":
            if not (self.agent.sleep_until_tick and self.engine.tick < self.agent.sleep_until_tick):
                self.agent.wake_up()
        self.assertEqual(self.agent.current_action.value, "idle")

    def test_no_new_conversations_start_overnight(self):
        agents = list(self.engine.agents.values())[:2]
        agents[0].position = (10, 10)
        agents[1].position = (11, 10)
        agents[0].current_location = "clearing"
        agents[1].current_location = "clearing"
        agents[0].current_action = agents[0].current_action.IDLE
        agents[1].current_action = agents[1].current_action.IDLE
        agents[0].conversation_cooldown = 0
        agents[1].conversation_cooldown = 0
        agents[0].is_in_conversation = False
        agents[1].is_in_conversation = False
        agents[0].drives.social_need = 1.0
        agents[1].drives.social_need = 1.0
        self.engine.time_manager.tick_in_day = int((1 / 24) * self.engine.time_manager.ticks_per_day)

        events = self.engine._process_interactions()

        self.assertEqual(events, [])
        self.assertEqual(agents[0].current_action.value, "idle")
        self.assertEqual(agents[1].current_action.value, "idle")

    def test_find_home_falls_back_to_world_claims(self):
        spot = self.engine.world.find_empty_space(2, 2)
        self.assertIsNotNone(spot)
        building_id = self.engine.world.build_structure(spot[0], spot[1], 2, 2, "Test Shelter", self.agent.name, "shelter")

        self.assertIsNotNone(building_id)
        self.agent.world_model.known_claims = {}

        home = self.agent._find_home()

        self.assertEqual(home, building_id)
        self.assertIn(building_id, self.agent.world_model.known_claims)

    def test_agents_have_varied_sleep_windows(self):
        sleep_windows = {
            (agent.sleep_start_hour, agent.wake_hour)
            for agent in self.engine.agents.values()
        }

        self.assertGreater(len(sleep_windows), 1)

    def test_supported_proposal_advances_to_project(self):
        agents = list(self.engine.agents.values())[:8]
        proposer = agents[0]
        for agent in agents:
            agent.current_location = "clearing"
            agent.position = self.engine.world.get_location_entry("clearing")
            if agent is not proposer:
                agent.relationships[proposer.name] = {"sentiment": 0.8, "trust": 0.9, "familiarity": 0.7}
                model = agent.mental_models.get_or_create(proposer.name)
                model.reliability = 0.9
                model.leadership_influence = 0.5

        proposal = self.engine._make_proposal(
            proposer,
            "We should build a communal fire in the clearing.",
            "clearing",
            participants=[a.name for a in agents],
            kind="project",
        )

        events = self.engine._process_active_proposals()

        stored = next(p for p in self.engine.world.active_proposals if p["id"] == proposal["id"])
        self.assertIn(stored["status"], {"active_discussion", "accepted"})
        self.assertTrue(any(event["eventType"] == "proposal_advanced" for event in events))

        stored["status"] = "active_discussion"
        stored["legitimacy"] = 0.75
        events = self.engine._process_active_proposals()

        self.assertEqual(stored["status"], "accepted")
        self.assertTrue(any(project["name"] == "Communal Fire" for project in self.engine.world.projects))
        self.assertTrue(any(event["eventType"] == "project_started" for event in events))

    def test_institution_upkeep_assigns_roles_and_schedules_meeting(self):
        agents = list(self.engine.agents.values())[:3]
        institution = {
            "id": "inst_1",
            "name": "Clearing Circle",
            "purpose": "daily coordination",
            "location": "clearing",
            "members": [agent.name for agent in agents],
            "roles": {agents[0].name: "convener"},
            "operating_norm_ids": [],
            "legitimacy": 0.6,
            "activity_level": 0.5,
            "formed_tick": 1,
            "recurring_actions": [{"kind": "meeting", "topic": "Daily coordination", "frequency_days": 1, "hour": 18, "next_day": self.engine.time_manager.day}],
            "status": "active",
        }
        self.engine.world.constitution.institutions.append(institution)

        events = self.engine._run_institution_upkeep()

        self.assertTrue(any(meeting.get("institution_id") == "inst_1" for meeting in self.engine.world.meetings))
        self.assertTrue(any(role.get("institution_name") == "Clearing Circle" for role in agents[0].current_institution_roles))
        self.assertTrue(any(event["eventType"] == "institution_meeting" for event in events))

    def test_missed_commitment_creates_conflict(self):
        agents = list(self.engine.agents.values())[:2]
        agent, other = agents
        self.engine.time_manager.day = 2
        self.engine.time_manager.tick_in_day = int((15 / 24) * self.engine.time_manager.ticks_per_day)
        agent.social_commitments.append({
            "kind": "meeting",
            "description": "Attend mediation",
            "participants": [agent.name, other.name],
            "location": "clearing",
            "scheduled_day": 2,
            "scheduled_hour": 10,
            "status": "planned",
        })

        events = self.engine._process_missed_obligations()

        self.assertTrue(any(conflict.get("with") == other.name for conflict in agent.active_conflicts))
        self.assertTrue(any(event["eventType"] == "commitment_missed" for event in events))

    def test_world_state_exposes_open_action_state(self):
        state = self.engine.get_world_state()

        self.assertIn("worldObjects", state)
        self.assertIn("innovations", state)
        self.assertIn("patterns", state)
        self.assertIn("timelineEvents", state)


if __name__ == "__main__":
    unittest.main()
