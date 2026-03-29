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
from simulation.world import World, WEATHER_ACTION_MODIFIERS, SEASON_RESOURCE_MODIFIERS
from systems.open_action_models import WorldObject, WorldChange


class _FakeAgent:
    """Minimal agent stub for observer tests."""
    def __init__(self, agent_id, name, location):
        self.id = agent_id
        self.name = name
        self.current_location = location


class TestWorldObjects(unittest.TestCase):
    def test_world_objects(self):
        world = World()
        obj = WorldObject(
            id="obj_test1", name="Stone Axe", description="A crude axe",
            category="tool", location="clearing", owner="Alice",
        )
        world.world_objects[obj.id] = obj

        at_clearing = world.get_objects_at("clearing")
        self.assertEqual(len(at_clearing), 1)
        self.assertEqual(at_clearing[0].name, "Stone Axe")

        by_alice = world.get_objects_by_owner("Alice")
        self.assertEqual(len(by_alice), 1)
        self.assertEqual(by_alice[0].id, "obj_test1")

        by_bob = world.get_objects_by_owner("Bob")
        self.assertEqual(len(by_bob), 0)

    def test_world_object_decay(self):
        world = World()
        obj = WorldObject(
            id="obj_decay", name="Wooden Shield", description="A shield",
            category="tool", durability=1.0, location="clearing",
        )
        world.world_objects[obj.id] = obj
        old_dur = obj.durability
        world.decay_all_objects(weather="clear")
        self.assertLess(obj.durability, old_dur)

        # Storm weather should decay faster
        obj2 = WorldObject(
            id="obj_decay2", name="Basket", description="A basket",
            category="container", durability=1.0, location="clearing",
        )
        world.world_objects[obj2.id] = obj2
        world.decay_all_objects(weather="storm")
        # Storm decay_rate = 0.002 * 1.5 = 0.003
        self.assertLess(obj2.durability, 1.0)


class TestEnvironmentalChange(unittest.TestCase):
    def test_environmental_change(self):
        world = World()
        change = WorldChange(
            type="terrain_modification",
            description="Ground was cleared",
            location="clearing",
            visual_change="The ground is now flat and packed",
        )
        # Should not raise
        world.apply_environmental_change(change)
        # Verify the location description was modified
        loc = world.locations["clearing"]
        self.assertIn("flat and packed", loc["description"])


class TestObserverDetection(unittest.TestCase):
    def test_observer_detection(self):
        world = World()
        agents = {
            "a1": _FakeAgent("a1", "Alice", "clearing"),
            "a2": _FakeAgent("a2", "Bob", "clearing"),
            "a3": _FakeAgent("a3", "Charlie", "forest_edge"),
        }

        # Normal noise, anyone at location
        observers = world.get_agents_who_can_observe(
            "clearing", "anyone at this location", "normal", agents
        )
        names = [a.name for a in observers]
        self.assertIn("Alice", names)
        self.assertIn("Bob", names)
        self.assertNotIn("Charlie", names)

        # Silent noise, nobody
        observers_silent = world.get_agents_who_can_observe(
            "clearing", "nobody", "silent", agents
        )
        self.assertEqual(len(observers_silent), 0)


class TestPathfindingAvoidance(unittest.TestCase):
    def test_pathfinding_avoidance(self):
        world = World()
        start = world.get_location_entry("clearing")
        end = world.get_location_entry("north_fields")

        # Normal path
        normal_path = world.find_path(start, end)
        self.assertGreater(len(normal_path), 1)

        # Path with avoidance -- should still find a path but may differ
        avoid = [(start[0] + 1, start[1] + 1)]
        avoid_path = world.find_path(start, end, avoidance_targets=avoid)
        self.assertGreater(len(avoid_path), 1)


class TestLatentPossibilities(unittest.TestCase):
    def test_latent_possibilities(self):
        world = World()
        self.assertEqual(len(world.latent_possibilities), 0)
        world.latent_possibilities.append("pottery_wheel")
        world.latent_possibilities.append("loom")
        self.assertEqual(len(world.latent_possibilities), 2)
        self.assertIn("pottery_wheel", world.latent_possibilities)


class TestResourceScarcity(unittest.TestCase):
    def test_resource_scarcity(self):
        world = World()
        # Consume some resources at forest_edge
        gathered = world.gather_resource("wild_berries", 50, "forest_edge")
        self.assertGreater(gathered, 0)

        scarcity = world.get_location_scarcity("forest_edge")
        # wild_berries should have some scarcity now
        self.assertIn("wild_berries", scarcity)
        self.assertGreater(scarcity["wild_berries"], 0.0)


class TestWeatherModifiers(unittest.TestCase):
    def test_weather_modifiers(self):
        world = World()
        world.update_weather_season("clear", "spring")
        self.assertAlmostEqual(world.get_weather_modifier("gathering"), 1.0)

        world.update_weather_season("storm", "spring")
        self.assertLess(world.get_weather_modifier("gathering"), 1.0)
        self.assertLess(world.get_weather_modifier("building"), 1.0)


class TestSeasonResourceModifier(unittest.TestCase):
    def test_season_resource_modifier(self):
        world = World()
        world.update_weather_season("clear", "spring")
        spring_mod = world.get_season_resource_modifier("wild_plants")
        self.assertGreater(spring_mod, 1.0)  # Spring boosts wild_plants

        world.update_weather_season("clear", "winter")
        winter_mod = world.get_season_resource_modifier("wild_plants")
        self.assertLess(winter_mod, 1.0)  # Winter reduces wild_plants


if __name__ == "__main__":
    unittest.main()
