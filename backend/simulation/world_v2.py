"""Open-ended world — abandoned settlement with resources, claimable buildings, blank constitution."""

import heapq
import json
import logging
import random

logger = logging.getLogger("agentica.world")

MAP_SIZE = 40

# Location definitions — the abandoned settlement
LOCATIONS = {
    # Starting point — just an open clearing
    "clearing": {
        "type": "open_space", "label": "Clearing",
        "description": "An open grassy clearing. This is where everyone arrived.",
        "col": 18, "row": 18, "width": 4, "height": 4,
        "capacity": 30, "resources": [],
        "claimed_by": None, "designated_purpose": None,
    },
    # Natural resource areas — no buildings, just nature
    "north_fields": {
        "type": "open_land", "label": "North Fields",
        "description": "Fertile soil with wild plants growing. Could be farmed.",
        "col": 10, "row": 4, "width": 6, "height": 4,
        "resources": ["wild_plants", "soil"],
        "claimed_by": None, "designated_purpose": None, "capacity": 10,
    },
    "east_meadow": {
        "type": "open_land", "label": "East Meadow",
        "description": "A grassy meadow with berry bushes scattered around.",
        "col": 30, "row": 14, "width": 5, "height": 4,
        "resources": ["wild_berries", "wild_plants"],
        "claimed_by": None, "designated_purpose": None, "capacity": 10,
    },
    "forest": {
        "type": "natural", "label": "Forest",
        "description": "Dense woods. Source of wood, berries, herbs, and stone.",
        "col": 2, "row": 2, "width": 6, "height": 8,
        "resources": ["wood", "wild_berries", "wild_herbs", "stone"],
        "claimed_by": None, "designated_purpose": None, "capacity": 15,
    },
    "river": {
        "type": "natural", "label": "River",
        "description": "A river running along the west side. Fresh water and fish.",
        "col": 2, "row": 12, "width": 3, "height": 18,
        "resources": ["fresh_water", "fish", "clay"],
        "claimed_by": None, "designated_purpose": None, "capacity": 10,
    },
    "south_field": {
        "type": "open_space", "label": "South Field",
        "description": "A wide open area with tall grass.",
        "col": 12, "row": 32, "width": 8, "height": 4,
        "resources": ["wild_grass"],
        "claimed_by": None, "designated_purpose": None, "capacity": 20,
    },
    "hilltop": {
        "type": "natural", "label": "Hilltop",
        "description": "A rocky hill with a view of the whole area. Stone and minerals.",
        "col": 28, "row": 2, "width": 4, "height": 3,
        "resources": ["stone", "minerals"],
        "claimed_by": None, "designated_purpose": None, "capacity": 8,
    },
    "berry_grove": {
        "type": "natural", "label": "Berry Grove",
        "description": "A small grove thick with berry bushes. Easy food source.",
        "col": 24, "row": 24, "width": 3, "height": 3,
        "resources": ["wild_berries", "wild_herbs"],
        "claimed_by": None, "designated_purpose": None, "capacity": 8,
    },
    "pond": {
        "type": "natural", "label": "Pond",
        "description": "A small freshwater pond. Fish and clean water.",
        "col": 34, "row": 28, "width": 3, "height": 3,
        "resources": ["fresh_water", "fish"],
        "claimed_by": None, "designated_purpose": None, "capacity": 6,
    },
}

# Gatherable resources
RESOURCES = {
    "wood": {"locations": ["forest_edge"], "quantity": 500, "renewable": True, "regen_rate": 5},
    "stone": {"locations": ["forest_edge", "hill_overlook"], "quantity": 300, "renewable": False, "regen_rate": 0},
    "wild_berries": {"locations": ["forest_edge"], "quantity": 100, "renewable": True, "regen_rate": 10},
    "wild_plants": {"locations": ["farmable_land_north", "farmable_land_east"], "quantity": 80, "renewable": True, "regen_rate": 8},
    "fish": {"locations": ["river"], "quantity": 50, "renewable": True, "regen_rate": 5},
    "fresh_water": {"locations": ["river"], "quantity": 999, "renewable": True, "regen_rate": 999},
    "clay": {"locations": ["river"], "quantity": 200, "renewable": False, "regen_rate": 0},
    "wild_herbs": {"locations": ["forest_edge"], "quantity": 40, "renewable": True, "regen_rate": 3},
    "wild_grass": {"locations": ["open_field_south"], "quantity": 200, "renewable": True, "regen_rate": 10},
}


class WorldConstitution:
    """Living rules of the simulation. Starts blank."""
    def __init__(self):
        self.economic_rules = {"currency": None, "trade_rules": [], "property_rules": [], "taxation": None}
        self.governance_rules = {"system": None, "leaders": [], "laws": [], "enforcement_mechanism": None}
        self.social_norms: list[str] = []
        self.institutions: list[dict] = []
        self.change_history: list[dict] = []

    def summary(self) -> str:
        parts = []
        if self.economic_rules["currency"]:
            parts.append(f"Currency: {self.economic_rules['currency']}")
        if self.governance_rules["leaders"]:
            parts.append(f"Leaders: {', '.join(self.governance_rules['leaders'])}")
        if self.governance_rules["laws"]:
            parts.append(f"Laws: {'; '.join(self.governance_rules['laws'][:3])}")
        if self.social_norms:
            parts.append(f"Norms: {'; '.join(self.social_norms[:3])}")
        if self.institutions:
            parts.append(f"Institutions: {', '.join(i['name'] for i in self.institutions)}")
        return "\n".join(parts) if parts else "No rules established yet. This is a blank slate."

    def to_dict(self) -> dict:
        return {
            "economic": self.economic_rules,
            "governance": self.governance_rules,
            "norms": self.social_norms,
            "institutions": self.institutions,
            "history": self.change_history[-20:],
        }

    def load_from_dict(self, d: dict):
        if d.get("economic"): self.economic_rules = d["economic"]
        if d.get("governance"): self.governance_rules = d["governance"]
        if d.get("norms"): self.social_norms = d["norms"]
        if d.get("institutions"): self.institutions = d["institutions"]
        if d.get("history"): self.change_history = d["history"]


class WorldV2:
    def __init__(self):
        self.width = MAP_SIZE
        self.height = MAP_SIZE
        self.locations = {k: dict(v) for k, v in LOCATIONS.items()}
        self.resources = {k: dict(v) for k, v in RESOURCES.items()}
        self.constitution = WorldConstitution()
        self.created_objects: list[dict] = []
        self.trades: list[dict] = []

        # Build tile grid
        self.tiles = self._generate_grid()
        self._path_cache: dict = {}

    def _generate_grid(self) -> list[list[dict]]:
        grid = []
        # Map location tiles
        loc_tiles = {}
        for loc_id, loc in self.locations.items():
            for dc in range(loc["width"]):
                for dr in range(loc["height"]):
                    loc_tiles[f"{loc['col']+dc},{loc['row']+dr}"] = loc_id

        # Paths connecting locations
        paths = set()
        # Central cross paths
        for c in range(4, 36): paths.add(f"{c},20")
        for r in range(4, 36): paths.add(f"20,{r}")
        # Connect to edges
        for c in range(2, 10): paths.add(f"{c},15")
        for r in range(2, 10): paths.add(f"5,{r}")
        for c in range(26, 34): paths.add(f"{c},15")

        for row in range(MAP_SIZE):
            tile_row = []
            for col in range(MAP_SIZE):
                key = f"{col},{row}"
                loc_id = loc_tiles.get(key)
                is_path = key in paths

                tile = {"col": col, "row": row, "type": "grass", "structure": None, "decoration": None, "walkable": True}

                if loc_id:
                    loc = self.locations[loc_id]
                    if loc["type"] == "natural" and "river" in loc_id or "pond" in loc_id:
                        tile["type"] = "water"
                        # River edge is walkable
                        tile["walkable"] = (col == loc["col"] + loc["width"] - 1 or col == loc["col"])
                    elif loc["type"] == "natural":
                        tile["type"] = "dark_grass"
                        tile["decoration"] = "tree" if random.random() < 0.35 else ("flower" if random.random() < 0.15 else None)
                        tile["walkable"] = tile["decoration"] != "tree"
                    elif loc["type"] == "open_land":
                        tile["type"] = "dirt"
                        if random.random() < 0.2:
                            tile["decoration"] = "flower"
                    elif loc["type"] == "open_space":
                        tile["type"] = "grass"
                        if random.random() < 0.1:
                            tile["decoration"] = "flower"
                elif is_path:
                    tile["type"] = "path"
                elif random.random() < 0.03:
                    tile["decoration"] = "tree"
                    tile["walkable"] = False

                tile_row.append(tile)
            grid.append(tile_row)
        return grid

    # --- Location access ---
    def get_location(self, loc_id: str) -> dict | None:
        return self.locations.get(loc_id)

    def get_location_entry(self, loc_id: str) -> tuple[int, int]:
        loc = self.locations.get(loc_id)
        if not loc:
            return (20, 20)
        # Entry point: center-bottom of the location
        return (loc["col"] + loc["width"] // 2, loc["row"] + loc["height"])

    def get_locations_with_resource(self, resource: str) -> list[str]:
        res = self.resources.get(resource)
        if not res:
            return []
        locs = res["locations"]
        return locs if isinstance(locs, list) else [locs]

    def get_resources_at(self, loc_id: str) -> list[str]:
        loc = self.locations.get(loc_id)
        if not loc:
            return []
        return loc.get("resources", [])

    def get_all_location_ids(self) -> list[str]:
        return list(self.locations.keys())

    def get_unclaimed_buildings(self) -> list[str]:
        return [lid for lid, loc in self.locations.items()
                if loc["type"] in ("empty_building", "built_structure") and not loc.get("claimed_by")]

    # --- Claiming ---
    def claim_location(self, loc_id: str, agent_name: str, purpose: str = "") -> bool:
        loc = self.locations.get(loc_id)
        if not loc or loc.get("claimed_by"):
            return False
        loc["claimed_by"] = agent_name
        loc["designated_purpose"] = purpose
        logger.info(f"{agent_name} claimed {loc_id} for {purpose or 'personal use'}")
        return True

    # --- Resources ---
    def gather_resource(self, resource: str, amount: int, location: str) -> int:
        res = self.resources.get(resource)
        if not res:
            return 0
        locs = res["locations"] if isinstance(res["locations"], list) else [res["locations"]]
        if location not in locs:
            return 0
        gathered = min(amount, res["quantity"])
        res["quantity"] -= gathered
        return gathered

    def regenerate_resources(self):
        for res_name, res in self.resources.items():
            if res["renewable"] and res["quantity"] < 999:
                res["quantity"] = min(999, res["quantity"] + res["regen_rate"])

    # --- Pathfinding ---
    def is_walkable(self, col: int, row: int) -> bool:
        if 0 <= col < self.width and 0 <= row < self.height:
            return self.tiles[row][col]["walkable"]
        return False

    def find_path(self, start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
        if start == end:
            return [start]
        key = (start, end)
        if key in self._path_cache:
            return self._path_cache[key]
        path = self._a_star(start, end)
        self._path_cache[key] = path
        return path

    def _a_star(self, start, end):
        open_set = [(0, start)]
        came_from = {}
        g_score = {start: 0}
        neighbors = [(0,1),(0,-1),(1,0),(-1,0)]
        while open_set:
            _, current = heapq.heappop(open_set)
            if current == end:
                path = [current]
                while current in came_from:
                    current = came_from[current]
                    path.append(current)
                path.reverse()
                return path
            for dc, dr in neighbors:
                nb = (current[0]+dc, current[1]+dr)
                if not self.is_walkable(nb[0], nb[1]) and nb != end:
                    continue
                tg = g_score[current] + 1
                if tg < g_score.get(nb, float("inf")):
                    came_from[nb] = current
                    g_score[nb] = tg
                    h = abs(nb[0]-end[0]) + abs(nb[1]-end[1])
                    heapq.heappush(open_set, (tg+h, nb))
        return [start]  # No valid path — stay put instead of walking through obstacles

    def get_distance(self, loc_a: str, loc_b: str) -> float:
        ea = self.get_location_entry(loc_a)
        eb = self.get_location_entry(loc_b)
        return abs(ea[0]-eb[0]) + abs(ea[1]-eb[1])

    # --- Serialization ---
    def get_tile_grid(self):
        return self.tiles

    # --- Building construction ---
    _next_building_id: int = 1

    def build_structure(self, col: int, row: int, width: int, height: int,
                        label: str, builder: str = "", purpose: str = "") -> str | None:
        """Build a new structure on the map. Returns building ID or None."""
        # Check tiles are available
        for dc in range(width):
            for dr in range(height):
                if not (0 <= col+dc < self.width and 0 <= row+dr < self.height):
                    return None
                t = self.tiles[row+dr][col+dc]
                if t.get("structure") or t["type"] == "water" or t.get("decoration") == "tree":
                    return None

        bid = f"building_{self._next_building_id}"
        self._next_building_id += 1

        # Register as location
        self.locations[bid] = {
            "type": "built_structure", "label": label,
            "description": f"{label}, built by {builder}",
            "col": col, "row": row, "width": width, "height": height,
            "capacity": width * height * 2,
            "resources": [], "claimed_by": builder,
            "designated_purpose": purpose,
        }

        # Update tiles
        for dc in range(width):
            for dr in range(height):
                t = self.tiles[row+dr][col+dc]
                t["structure"] = {"building_id": bid, "type": "built_structure", "label": label, "owner": builder}
                t["walkable"] = False
                t["decoration"] = None

        self._path_cache.clear()
        logger.info(f"Built '{label}' at ({col},{row}) by {builder}, id={bid}")
        return bid

    def find_empty_space(self, width: int, height: int) -> tuple[int, int] | None:
        """Find buildable space near the center clearing."""
        # Search outward from center
        center_col, center_row = 20, 20
        for radius in range(3, 18):
            for row in range(max(2, center_row - radius), min(self.height - height - 2, center_row + radius)):
                for col in range(max(2, center_col - radius), min(self.width - width - 2, center_col + radius)):
                    can_build = True
                    for dc in range(width):
                        for dr in range(height):
                            t = self.tiles[row+dr][col+dc]
                            if t.get("structure") or t["type"] in ("water", "path") or t.get("decoration") == "tree":
                                can_build = False
                                break
                        if not can_build:
                            break
                    if can_build:
                        return (col, row)
        return None

    def get_buildings_list(self) -> list[dict]:
        buildings = []
        for loc_id, loc in self.locations.items():
            if loc["type"] in ("empty_building", "built_structure"):
                label = loc.get("label", loc_id.replace("_", " ").title())
                buildings.append({
                    "id": loc_id, "label": label,
                    "type": loc["type"], "col": loc["col"], "row": loc["row"],
                    "width": loc["width"], "height": loc["height"],
                    "owner": loc.get("claimed_by", ""),
                    "purpose": loc.get("designated_purpose", ""),
                })
        return buildings

    def get_world_summary(self) -> str:
        built = sum(1 for loc in self.locations.values() if loc["type"] == "built_structure")
        return f"Open landscape with {len(self.locations)} known areas. {built} structures built. Constitution: {self.constitution.summary()}"

    def to_save_dict(self) -> dict:
        return {
            "locations": self.locations,
            "resources": self.resources,
            "constitution": self.constitution.to_dict(),
            "created_objects": self.created_objects[-50:],
            "trades": self.trades[-50:],
        }

    def load_from_save(self, data: dict):
        if data.get("locations"): self.locations = data["locations"]
        if data.get("resources"): self.resources = data["resources"]
        if data.get("constitution"): self.constitution.load_from_dict(data["constitution"])
        if data.get("created_objects"): self.created_objects = data["created_objects"]
        if data.get("trades"): self.trades = data["trades"]
        self._path_cache.clear()
