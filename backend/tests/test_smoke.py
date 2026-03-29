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

import asyncio
import unittest
from unittest.mock import patch
from simulation.engine import SimulationEngine


WORLD_STATE_KEYS = {"tick", "time", "agents", "weather", "speed"}
TIME_KEYS = {"tick_in_day", "day", "hour", "minute", "time_string", "time_of_day", "season", "weather", "is_night"}
AGENT_KEYS = {"id", "name", "age", "job", "position", "currentLocation", "currentAction", "emotion", "innerThought", "colorIndex", "state"}


def _noop_create_task(coro, **kwargs):
    coro.close()
    return None


class SmokeTests(unittest.TestCase):
    def setUp(self):
        self.engine = SimulationEngine()

    def test_engine_boots(self):
        self.assertGreater(len(self.engine.agents), 0)
        self.assertEqual(self.engine.tick, 0)

    @patch("asyncio.create_task", side_effect=_noop_create_task)
    def test_process_tick_returns_list(self, _mock):
        self.engine.tick += 1
        self.engine.time_manager.advance()
        events = self.engine._process_tick()
        self.assertIsInstance(events, list)

    def test_world_state_shape(self):
        state = self.engine.get_world_state()
        missing = WORLD_STATE_KEYS - state.keys()
        self.assertEqual(missing, set(), f"Missing keys in world_state: {missing}")

    def test_time_dict_shape(self):
        state = self.engine.get_world_state()
        missing = TIME_KEYS - state["time"].keys()
        self.assertEqual(missing, set(), f"Missing keys in time: {missing}")

    def test_agent_dict_shape(self):
        state = self.engine.get_world_state()
        self.assertGreater(len(state["agents"]), 0)
        agent = state["agents"][0]
        missing = AGENT_KEYS - agent.keys()
        self.assertEqual(missing, set(), f"Missing keys in agent: {missing}")

    @patch("asyncio.create_task", side_effect=_noop_create_task)
    def test_several_ticks(self, _mock):
        for _ in range(5):
            self.engine.tick += 1
            self.engine.time_manager.advance()
            events = self.engine._process_tick()
            self.assertIsInstance(events, list)
        self.assertEqual(self.engine.tick, 5)


if __name__ == "__main__":
    unittest.main()
