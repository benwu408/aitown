import unittest

from simulation.world import World


class WorldTests(unittest.TestCase):
    def test_fresh_world_has_zero_buildings(self):
        world = World()
        self.assertEqual(world.get_buildings_list(), [])

    def test_resource_location_ids_are_valid(self):
        world = World()
        location_ids = set(world.locations.keys())
        for resource in world.resources.values():
            for location in resource["locations"]:
                self.assertIn(location, location_ids)

    def test_norm_violation_updates_structured_norm(self):
        world = World()
        norm = world.add_norm("Respect claimed spaces", tick=5)
        world.add_norm_violation({
            "tick": 7,
            "agent": "Ava",
            "norm": "Respect claimed spaces",
            "location": "clearing",
            "description": "Ava ignored a claim.",
        })

        self.assertEqual(norm["violations"], 1)
        self.assertGreaterEqual(len(norm["history"]), 2)


if __name__ == "__main__":
    unittest.main()
