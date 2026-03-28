"""Mutable world grid — the single source of truth for the town map."""

import heapq
import json
import logging
from dataclasses import dataclass, field

logger = logging.getLogger("agentica.world")

MAP_SIZE = 40

# Structure costs
STRUCTURE_COSTS = {
    "house": {"coins": 150, "tools": 5},
    "bakery": {"coins": 200, "tools": 8},
    "workshop": {"coins": 300, "tools": 10},
    "general_store": {"coins": 250, "tools": 8},
    "tavern": {"coins": 250, "tools": 8},
    "clinic": {"coins": 400, "tools": 15},
    "school": {"coins": 300, "tools": 10},
    "church": {"coins": 350, "tools": 12},
    "barn": {"coins": 100, "tools": 5},
    "market_stall": {"coins": 80, "tools": 3},
}

DECORATION_COSTS = {
    "tree": 5, "flower": 2, "bench": 10, "fence": 3, "rock": 0, "lantern": 8,
}


@dataclass
class BuildingDef:
    id: str
    label: str
    col: int
    row: int
    width: int
    height: int
    entry_col: int = 0
    entry_row: int = 0
    owner: str = ""
    building_type: str = ""

    def __post_init__(self):
        if self.entry_col == 0 and self.entry_row == 0:
            self.entry_col = self.col + self.width // 2
            self.entry_row = self.row + self.height


# Default buildings (seed layout for fresh starts)
DEFAULT_BUILDINGS = [
    BuildingDef("town_hall", "Town Hall", 18, 18, 3, 3, building_type="town_hall"),
    BuildingDef("general_store", "General Store", 22, 22, 3, 2, building_type="general_store"),
    BuildingDef("farm", "Farm", 6, 6, 4, 4, entry_col=8, entry_row=10, building_type="farm"),
    BuildingDef("barn", "Barn", 11, 8, 2, 2, building_type="barn"),
    BuildingDef("bakery", "Bakery", 25, 20, 2, 2, building_type="bakery"),
    BuildingDef("workshop", "Workshop", 14, 24, 3, 2, building_type="workshop"),
    BuildingDef("tavern", "Tavern", 22, 26, 3, 2, building_type="tavern"),
    BuildingDef("school", "School", 28, 24, 2, 2, building_type="school"),
    BuildingDef("church", "Church", 26, 16, 2, 3, building_type="church"),
    BuildingDef("house_1", "Eleanor's House", 14, 14, 2, 2, owner="eleanor", building_type="house"),
    BuildingDef("house_2", "John's House", 10, 12, 2, 2, owner="john", building_type="house"),
    BuildingDef("house_3", "Kowalski House", 16, 28, 2, 2, owner="tom", building_type="house"),
    BuildingDef("house_4", "Reeves House", 30, 20, 2, 2, owner="marcus", building_type="house"),
    BuildingDef("house_5", "Brennan House", 12, 20, 2, 2, owner="henry", building_type="house"),
    BuildingDef("house_6", "Others House", 30, 28, 2, 2, building_type="house"),
    BuildingDef("park", "Park", 18, 12, 3, 2, entry_col=19, entry_row=14, building_type="park"),
    BuildingDef("pond", "Pond", 8, 32, 3, 3, entry_col=9, entry_row=31, building_type="pond"),
]

BUILDING_MAP = {b.id: b for b in DEFAULT_BUILDINGS}


class World:
    def __init__(self):
        self.width = MAP_SIZE
        self.height = MAP_SIZE
        self.buildings: list[BuildingDef] = list(DEFAULT_BUILDINGS)
        self.building_map: dict[str, BuildingDef] = dict(BUILDING_MAP)
        self._next_building_id = 100

        # Mutable tile grid — each tile is a dict
        self.tiles: list[list[dict]] = self._generate_default_grid()
        self._path_cache: dict = {}
        self._pending_changes: list[dict] = []

    def _generate_default_grid(self) -> list[list[dict]]:
        """Generate the default town layout."""
        grid = []
        # Pre-compute building tiles
        building_tiles: dict[str, str] = {}
        for b in self.buildings:
            for dc in range(b.width):
                for dr in range(b.height):
                    building_tiles[f"{b.col + dc},{b.row + dr}"] = b.id

        # Generate paths
        paths = self._generate_default_paths()

        # Tree and flower spots (from original)
        tree_spots = {f"{c},{r}" for c, r in [
            (3,3),(5,15),(7,28),(13,5),(16,10),(24,8),(32,10),(35,15),(33,25),
            (36,30),(4,35),(15,35),(25,5),(30,5),(35,8),(2,20),(37,20),(10,30),
            (22,10),(28,12),(32,16),(6,25),(34,22),(17,7),(26,32),(12,34),(33,33),
            (3,10),(38,12),(5,38),
        ]}
        flower_spots = {f"{c},{r}" for c, r in [
            (17,12),(19,12),(21,12),(19,20),(21,20),(15,16),(16,16),(27,15),(28,15),
        ]}

        for row in range(MAP_SIZE):
            tile_row = []
            for col in range(MAP_SIZE):
                key = f"{col},{row}"
                bid = building_tiles.get(key)
                is_path = key in paths
                is_tree = key in tree_spots
                is_flower = key in flower_spots

                tile: dict = {"col": col, "row": row, "type": "grass", "structure": None, "decoration": None, "walkable": True}

                if bid:
                    b = self.building_map.get(bid)
                    if b:
                        if b.building_type == "pond":
                            tile["type"] = "water"
                            tile["walkable"] = False
                        elif b.building_type == "farm":
                            tile["type"] = "dirt"
                        elif b.building_type == "park":
                            tile["type"] = "dark_grass"
                        else:
                            tile["walkable"] = False
                        tile["structure"] = {
                            "building_id": bid,
                            "type": b.building_type,
                            "label": b.label,
                            "owner": b.owner,
                        }
                elif is_path:
                    tile["type"] = "path"
                elif is_tree and not bid:
                    tile["decoration"] = "tree"
                    tile["walkable"] = False
                elif is_flower and not bid:
                    tile["type"] = "flowers"
                    tile["decoration"] = "flower"
                elif ((col * 7 + row * 13) % 100) < 5:
                    tile["type"] = "dark_grass"

                tile_row.append(tile)
            grid.append(tile_row)
        return grid

    def _generate_default_paths(self) -> set[str]:
        paths = set()
        def add_path(fc, fr, tc, tr):
            c, r = fc, fr
            while c != tc:
                paths.add(f"{c},{r}")
                c += 1 if c < tc else -1
            while r != tr:
                paths.add(f"{c},{r}")
                r += 1 if r < tr else -1
            paths.add(f"{tc},{tr}")

        for c in range(4, 35):
            paths.add(f"{c},21")
        for r in range(4, 35):
            paths.add(f"20,{r}")

        add_path(19,19,20,21); add_path(23,22,23,21); add_path(8,10,8,21)
        add_path(12,9,12,21); add_path(26,21,26,21); add_path(15,25,15,21)
        add_path(23,27,23,21); add_path(29,25,29,21); add_path(27,18,27,21)
        add_path(15,15,15,21); add_path(11,13,11,21); add_path(17,29,20,29)
        add_path(31,21,31,21); add_path(13,21,13,21); add_path(31,29,31,21)
        add_path(19,13,20,13); add_path(9,33,9,21); add_path(15,21,15,15)
        add_path(23,21,23,27); add_path(20,13,20,8)
        return paths

    # --- Tile access ---
    def get_tile(self, col: int, row: int) -> dict | None:
        if 0 <= col < self.width and 0 <= row < self.height:
            return self.tiles[row][col]
        return None

    def is_walkable(self, col: int, row: int) -> bool:
        if 0 <= col < self.width and 0 <= row < self.height:
            return self.tiles[row][col]["walkable"]
        return False

    # --- Mutations ---
    def set_tile_type(self, col: int, row: int, tile_type: str) -> bool:
        tile = self.get_tile(col, row)
        if not tile:
            return False
        tile["type"] = tile_type
        tile["walkable"] = tile_type != "water"
        if tile["structure"]:
            tile["walkable"] = False
        self._invalidate(col, row)
        self._pending_changes.append({"col": col, "row": row, "tile": dict(tile)})
        return True

    def add_structure(self, col: int, row: int, width: int, height: int,
                      structure_type: str, label: str, owner: str = "") -> str | None:
        """Place a building. Returns building_id or None if can't place."""
        # Check all tiles are available
        for dc in range(width):
            for dr in range(height):
                t = self.get_tile(col + dc, row + dr)
                if not t or t.get("structure") or t["type"] == "water":
                    return None

        bid = f"{structure_type}_{self._next_building_id}"
        self._next_building_id += 1

        # Create BuildingDef
        bdef = BuildingDef(
            id=bid, label=label, col=col, row=row, width=width, height=height,
            owner=owner, building_type=structure_type,
        )
        self.buildings.append(bdef)
        self.building_map[bid] = bdef

        # Update tiles
        for dc in range(width):
            for dr in range(height):
                t = self.tiles[row + dr][col + dc]
                t["structure"] = {"building_id": bid, "type": structure_type, "label": label, "owner": owner}
                t["walkable"] = False
                self._pending_changes.append({"col": col + dc, "row": row + dr, "tile": dict(t)})

        self._path_cache.clear()
        logger.info(f"Built {structure_type} '{label}' at ({col},{row}) id={bid}")
        return bid

    def remove_structure(self, building_id: str) -> bool:
        """Remove a building, revert tiles to grass."""
        bdef = self.building_map.get(building_id)
        if not bdef:
            return False

        for dc in range(bdef.width):
            for dr in range(bdef.height):
                t = self.tiles[bdef.row + dr][bdef.col + dc]
                t["structure"] = None
                t["type"] = "grass"
                t["walkable"] = True
                self._pending_changes.append({"col": bdef.col + dc, "row": bdef.row + dr, "tile": dict(t)})

        self.buildings.remove(bdef)
        del self.building_map[building_id]
        self._path_cache.clear()
        logger.info(f"Removed building {building_id}")
        return True

    def set_decoration(self, col: int, row: int, decoration: str | None) -> bool:
        tile = self.get_tile(col, row)
        if not tile or tile.get("structure"):
            return False
        tile["decoration"] = decoration
        if decoration == "tree":
            tile["walkable"] = False
        elif decoration is None:
            tile["walkable"] = True
        self._invalidate(col, row)
        self._pending_changes.append({"col": col, "row": row, "tile": dict(tile)})
        return True

    def flush_changes(self) -> list[dict]:
        """Get and clear pending tile changes for broadcast."""
        changes = self._pending_changes[:]
        self._pending_changes.clear()
        return changes

    def _invalidate(self, col: int, row: int):
        self._path_cache.clear()

    # --- Pathfinding ---
    def get_building_entry(self, building_id: str) -> tuple[int, int]:
        b = self.building_map.get(building_id)
        if not b:
            return (20, 20)
        return (b.entry_col, b.entry_row)

    def find_path(self, start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
        if start == end:
            return [start]
        cache_key = (start, end)
        if cache_key in self._path_cache:
            return self._path_cache[cache_key]
        path = self._a_star(start, end)
        self._path_cache[cache_key] = path
        return path

    def _a_star(self, start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
        def heuristic(a, b):
            return abs(a[0] - b[0]) + abs(a[1] - b[1])

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
                neighbor = (current[0] + dc, current[1] + dr)
                if not self.is_walkable(neighbor[0], neighbor[1]):
                    if neighbor != end:
                        continue
                tentative_g = g_score[current] + 1
                if tentative_g < g_score.get(neighbor, float("inf")):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    heapq.heappush(open_set, (tentative_g + heuristic(neighbor, end), neighbor))

        return [start, end]

    # --- Serialization ---
    def get_tile_grid(self) -> list[list[dict]]:
        """Full grid for frontend sync."""
        return self.tiles

    def get_buildings_list(self) -> list[dict]:
        """Serialized buildings for frontend."""
        return [
            {
                "id": b.id, "label": b.label, "type": b.building_type,
                "col": b.col, "row": b.row, "width": b.width, "height": b.height,
                "owner": b.owner,
            }
            for b in self.buildings
        ]

    def to_save_dict(self) -> dict:
        """Serialize for database persistence."""
        return {
            "tiles": [[t for t in row] for row in self.tiles],
            "buildings": [
                {"id": b.id, "label": b.label, "col": b.col, "row": b.row,
                 "width": b.width, "height": b.height, "entry_col": b.entry_col,
                 "entry_row": b.entry_row, "owner": b.owner, "building_type": b.building_type}
                for b in self.buildings
            ],
            "next_building_id": self._next_building_id,
        }

    def load_from_save(self, data: dict):
        """Restore from saved state."""
        if data.get("tiles"):
            self.tiles = data["tiles"]
        if data.get("buildings"):
            self.buildings = []
            self.building_map = {}
            for bd in data["buildings"]:
                bdef = BuildingDef(**bd)
                self.buildings.append(bdef)
                self.building_map[bdef.id] = bdef
        if data.get("next_building_id"):
            self._next_building_id = data["next_building_id"]
        self._path_cache.clear()
        logger.info(f"Loaded world: {len(self.buildings)} buildings")

    def find_empty_space(self, width: int, height: int) -> tuple[int, int] | None:
        """Find an empty area near existing paths for building."""
        for row in range(5, MAP_SIZE - height - 5):
            for col in range(5, MAP_SIZE - width - 5):
                can_build = True
                for dc in range(width):
                    for dr in range(height):
                        t = self.get_tile(col + dc, row + dr)
                        if not t or t.get("structure") or t.get("decoration") == "tree" or t["type"] in ("water", "path"):
                            can_build = False
                            break
                    if not can_build:
                        break
                if can_build:
                    # Check proximity to a path
                    near_path = False
                    for dc in range(-2, width + 2):
                        for dr in range(-2, height + 2):
                            t = self.get_tile(col + dc, row + dr)
                            if t and t["type"] == "path":
                                near_path = True
                                break
                        if near_path:
                            break
                    if near_path:
                        return (col, row)
        return None
