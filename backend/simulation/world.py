"""World state: map, buildings, locations, pathfinding grid."""

from dataclasses import dataclass, field

MAP_SIZE = 40


@dataclass
class BuildingDef:
    id: str
    label: str
    col: int
    row: int
    width: int
    height: int
    # Entry point for pathfinding (where agents stand when "at" this building)
    entry_col: int = 0
    entry_row: int = 0

    def __post_init__(self):
        if self.entry_col == 0 and self.entry_row == 0:
            # Default entry: front-center of building
            self.entry_col = self.col + self.width // 2
            self.entry_row = self.row + self.height


BUILDINGS = [
    BuildingDef("town_hall", "Town Hall", 18, 18, 3, 3),
    BuildingDef("general_store", "General Store", 22, 22, 3, 2),
    BuildingDef("farm", "Farm", 6, 6, 4, 4, entry_col=8, entry_row=10),
    BuildingDef("barn", "Barn", 11, 8, 2, 2),
    BuildingDef("bakery", "Bakery", 25, 20, 2, 2),
    BuildingDef("workshop", "Workshop", 14, 24, 3, 2),
    BuildingDef("tavern", "Tavern", 22, 26, 3, 2),
    BuildingDef("school", "School", 28, 24, 2, 2),
    BuildingDef("church", "Church", 26, 16, 2, 3),
    BuildingDef("house_1", "Eleanor's House", 14, 14, 2, 2),
    BuildingDef("house_2", "John's House", 10, 12, 2, 2),
    BuildingDef("house_3", "Kowalski House", 16, 28, 2, 2),
    BuildingDef("house_4", "Reeves House", 30, 20, 2, 2),
    BuildingDef("house_5", "Brennan House", 12, 20, 2, 2),
    BuildingDef("house_6", "Others House", 30, 28, 2, 2),
    BuildingDef("park", "Park", 18, 12, 3, 2, entry_col=19, entry_row=14),
    BuildingDef("pond", "Pond", 8, 32, 3, 3, entry_col=9, entry_row=31),
]

# Building lookup by id
BUILDING_MAP = {b.id: b for b in BUILDINGS}


class World:
    def __init__(self):
        self.width = MAP_SIZE
        self.height = MAP_SIZE
        self.buildings = BUILDINGS
        self.building_map = BUILDING_MAP
        self._walkable = self._build_walkable_grid()
        self._path_cache: dict[tuple[tuple[int, int], tuple[int, int]], list[tuple[int, int]]] = {}

    def _build_walkable_grid(self) -> list[list[bool]]:
        """Build a grid of walkable tiles."""
        grid = [[True] * self.width for _ in range(self.height)]

        # Mark building tiles as non-walkable (except farm, park)
        for b in self.buildings:
            if b.id in ("farm", "park"):
                continue
            if b.id == "pond":
                for dc in range(b.width):
                    for dr in range(b.height):
                        c, r = b.col + dc, b.row + dr
                        if 0 <= c < self.width and 0 <= r < self.height:
                            grid[r][c] = False
                continue
            for dc in range(b.width):
                for dr in range(b.height):
                    c, r = b.col + dc, b.row + dr
                    if 0 <= c < self.width and 0 <= r < self.height:
                        grid[r][c] = False

        return grid

    def is_walkable(self, col: int, row: int) -> bool:
        if 0 <= col < self.width and 0 <= row < self.height:
            return self._walkable[row][col]
        return False

    def get_building_entry(self, building_id: str) -> tuple[int, int]:
        """Get the entry point for a building."""
        b = self.building_map.get(building_id)
        if not b:
            return (20, 20)  # fallback to center
        return (b.entry_col, b.entry_row)

    def find_path(self, start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
        """A* pathfinding with caching."""
        if start == end:
            return [start]

        cache_key = (start, end)
        if cache_key in self._path_cache:
            return self._path_cache[cache_key]

        path = self._a_star(start, end)
        self._path_cache[cache_key] = path
        return path

    def _a_star(self, start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
        """A* pathfinding on the tile grid."""
        import heapq

        def heuristic(a: tuple[int, int], b: tuple[int, int]) -> float:
            return abs(a[0] - b[0]) + abs(a[1] - b[1])

        open_set: list[tuple[float, tuple[int, int]]] = [(0, start)]
        came_from: dict[tuple[int, int], tuple[int, int]] = {}
        g_score: dict[tuple[int, int], float] = {start: 0}

        neighbors = [(0, 1), (0, -1), (1, 0), (-1, 0)]

        while open_set:
            _, current = heapq.heappop(open_set)

            if current == end:
                # Reconstruct path
                path = [current]
                while current in came_from:
                    current = came_from[current]
                    path.append(current)
                path.reverse()
                return path

            for dc, dr in neighbors:
                neighbor = (current[0] + dc, current[1] + dr)
                if not self.is_walkable(neighbor[0], neighbor[1]):
                    # Allow walking to the end tile even if not walkable
                    if neighbor != end:
                        continue

                tentative_g = g_score[current] + 1
                if tentative_g < g_score.get(neighbor, float("inf")):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f = tentative_g + heuristic(neighbor, end)
                    heapq.heappush(open_set, (f, neighbor))

        # No path found — return direct line as fallback
        return [start, end]

    def get_nearby_agents(
        self, col: int, row: int, radius: int, agents: dict
    ) -> list[str]:
        """Get agent IDs within radius of a position."""
        nearby = []
        for aid, agent in agents.items():
            dx = abs(agent.position[0] - col)
            dy = abs(agent.position[1] - row)
            if dx + dy <= radius:
                nearby.append(aid)
        return nearby
