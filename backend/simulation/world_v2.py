"""Open-ended world — zero-building wilderness with emergent settlement growth."""

import heapq
import logging
import random

logger = logging.getLogger("agentica.world")

MAP_SIZE = 40

LOCATIONS = {
    "clearing": {
        "type": "open_space",
        "label": "Clearing",
        "description": "A broad clearing where everyone arrived. It is the only obviously communal place.",
        "col": 17,
        "row": 17,
        "width": 6,
        "height": 5,
        "capacity": 30,
        "resources": [],
        "claimed_by": None,
        "designated_purpose": None,
    },
    "north_fields": {
        "type": "open_land",
        "label": "North Fields",
        "description": "Fertile ground with wild edible plants and tall grass.",
        "col": 10,
        "row": 4,
        "width": 8,
        "height": 5,
        "capacity": 12,
        "resources": ["wild_plants", "wild_grass", "soil"],
        "claimed_by": None,
        "designated_purpose": None,
    },
    "east_meadow": {
        "type": "open_land",
        "label": "East Meadow",
        "description": "A broad meadow full of flowers, shrubs, and scattered berry bushes.",
        "col": 28,
        "row": 12,
        "width": 7,
        "height": 6,
        "capacity": 12,
        "resources": ["wild_berries", "wild_plants"],
        "claimed_by": None,
        "designated_purpose": None,
    },
    "forest_edge": {
        "type": "natural",
        "label": "Forest Edge",
        "description": "Dense woodland packed with trees, berries, herbs, and fallen branches.",
        "col": 3,
        "row": 3,
        "width": 9,
        "height": 10,
        "capacity": 16,
        "resources": ["wood", "wild_berries", "wild_herbs", "stone"],
        "claimed_by": None,
        "designated_purpose": None,
    },
    "river": {
        "type": "water",
        "label": "River",
        "description": "A river on the western side with water, fish, and soft clay banks.",
        "col": 2,
        "row": 13,
        "width": 4,
        "height": 17,
        "capacity": 10,
        "resources": ["fresh_water", "fish", "clay"],
        "claimed_by": None,
        "designated_purpose": None,
    },
    "berry_grove": {
        "type": "natural",
        "label": "Berry Grove",
        "description": "A small grove thick with berry bushes and herbs.",
        "col": 22,
        "row": 24,
        "width": 5,
        "height": 4,
        "capacity": 8,
        "resources": ["wild_berries", "wild_herbs"],
        "claimed_by": None,
        "designated_purpose": None,
    },
    "south_field": {
        "type": "open_space",
        "label": "South Field",
        "description": "A wide southern grassland with room to gather or build later.",
        "col": 12,
        "row": 31,
        "width": 10,
        "height": 5,
        "capacity": 20,
        "resources": ["wild_grass"],
        "claimed_by": None,
        "designated_purpose": None,
    },
    "hill_overlook": {
        "type": "natural",
        "label": "Hill Overlook",
        "description": "A rocky northern hill with loose stone and mineral veins.",
        "col": 27,
        "row": 2,
        "width": 5,
        "height": 4,
        "capacity": 8,
        "resources": ["stone", "minerals"],
        "claimed_by": None,
        "designated_purpose": None,
    },
    "pond": {
        "type": "water",
        "label": "Pond",
        "description": "A small freshwater pond with reeds, fish, and muddy edges.",
        "col": 33,
        "row": 27,
        "width": 4,
        "height": 4,
        "capacity": 6,
        "resources": ["fresh_water", "fish"],
        "claimed_by": None,
        "designated_purpose": None,
    },
}

RESOURCES = {
    "wood": {"locations": ["forest_edge"], "quantity": 240, "renewable": True, "regen_rate": 2},
    "stone": {"locations": ["forest_edge", "hill_overlook"], "quantity": 180, "renewable": False, "regen_rate": 0},
    "wild_berries": {"locations": ["forest_edge", "east_meadow", "berry_grove"], "quantity": 140, "renewable": True, "regen_rate": 6},
    "wild_plants": {"locations": ["north_fields", "east_meadow"], "quantity": 120, "renewable": True, "regen_rate": 5},
    "fish": {"locations": ["river", "pond"], "quantity": 70, "renewable": True, "regen_rate": 3},
    "fresh_water": {"locations": ["river", "pond"], "quantity": 999, "renewable": True, "regen_rate": 999},
    "clay": {"locations": ["river"], "quantity": 120, "renewable": False, "regen_rate": 0},
    "wild_herbs": {"locations": ["forest_edge", "berry_grove"], "quantity": 50, "renewable": True, "regen_rate": 2},
    "wild_grass": {"locations": ["north_fields", "south_field"], "quantity": 200, "renewable": True, "regen_rate": 8},
    "minerals": {"locations": ["hill_overlook"], "quantity": 60, "renewable": False, "regen_rate": 0},
    "soil": {"locations": ["north_fields"], "quantity": 999, "renewable": True, "regen_rate": 999},
}


class WorldConstitution:
    """Living rules of the simulation. Starts blank."""

    def __init__(self):
        self.economic_rules = {"currency": None, "trade_rules": [], "property_rules": [], "taxation": None}
        self.governance_rules = {"system": None, "leaders": [], "laws": [], "enforcement_mechanism": None}
        self.social_norms: list[dict] = []
        self.institutions: list[dict] = []
        self.change_history: list[dict] = []

    def summary(self) -> str:
        parts = []
        if self.economic_rules["currency"]:
            parts.append(f"Currency: {self.economic_rules['currency']}")
        if self.governance_rules.get("informal_leader"):
            parts.append(f"Leader: {self.governance_rules['informal_leader']}")
        elif self.governance_rules["leaders"]:
            parts.append(f"Leaders: {', '.join(self.governance_rules['leaders'])}")
        if self.governance_rules["laws"]:
            parts.append(f"Laws: {'; '.join(self.governance_rules['laws'][:3])}")
        if self.social_norms:
            norm_labels = [n["text"] if isinstance(n, dict) else str(n) for n in self.social_norms[:3]]
            parts.append(f"Norms: {'; '.join(norm_labels)}")
        if self.institutions:
            parts.append(f"Institutions: {', '.join(i['name'] for i in self.institutions[:3])}")
        return "\n".join(parts) if parts else "No rules established yet. This place is still completely unsettled."

    def to_dict(self) -> dict:
        return {
            "economic": self.economic_rules,
            "governance": self.governance_rules,
            "norms": self.social_norms,
            "institutions": self.institutions,
            "history": self.change_history[-40:],
        }

    def load_from_dict(self, data: dict):
        if data.get("economic"):
            self.economic_rules = data["economic"]
        if data.get("governance"):
            self.governance_rules = data["governance"]
        if data.get("norms"):
            self.social_norms = data["norms"]
        if data.get("institutions"):
            self.institutions = data["institutions"]
        if data.get("history"):
            self.change_history = data["history"]


class WorldV2:
    _next_building_id: int = 1

    def __init__(self):
        self.width = MAP_SIZE
        self.height = MAP_SIZE
        self.locations = {k: dict(v) for k, v in LOCATIONS.items()}
        self.resources = {k: dict(v) for k, v in RESOURCES.items()}
        self.constitution = WorldConstitution()
        self.created_objects: list[dict] = []
        self.trades: list[dict] = []
        self.active_proposals: list[dict] = []
        self.meetings: list[dict] = []
        self.coalitions: list[dict] = []
        self.norm_violations: list[dict] = []
        self.projects: list[dict] = []
        self.tile_resource_state: dict[str, dict[str, int]] = {}
        self.tiles: list[list[dict]] = []
        self._path_cache: dict = {}
        self._generate_world()

    def _generate_world(self):
        self.tiles = []
        self.tile_resource_state = {}

        loc_tiles: dict[str, str] = {}
        for loc_id, loc in self.locations.items():
            for dc in range(loc["width"]):
                for dr in range(loc["height"]):
                    loc_tiles[f"{loc['col'] + dc},{loc['row'] + dr}"] = loc_id

        for row in range(MAP_SIZE):
            tile_row = []
            for col in range(MAP_SIZE):
                key = f"{col},{row}"
                loc_id = loc_tiles.get(key)
                tile = {
                    "col": col,
                    "row": row,
                    "type": "grass",
                    "structure": None,
                    "decoration": None,
                    "walkable": True,
                    "resourceHints": [],
                    "resourceState": {},
                }

                if loc_id:
                    loc = self.locations[loc_id]
                    ltype = loc["type"]
                    if ltype == "water":
                        tile["type"] = "water"
                        tile["walkable"] = col in (loc["col"], loc["col"] + loc["width"] - 1)
                        tile["decoration"] = "reed" if random.random() < 0.15 else None
                    elif ltype == "open_land":
                        tile["type"] = "dirt"
                        if random.random() < 0.18:
                            tile["decoration"] = "flower"
                    elif ltype == "open_space":
                        tile["type"] = "grass"
                        if random.random() < 0.08:
                            tile["decoration"] = "flower"
                    else:
                        tile["type"] = "dark_grass"
                        if random.random() < 0.45:
                            tile["decoration"] = "tree"
                            tile["walkable"] = False
                        elif random.random() < 0.18:
                            tile["decoration"] = "flower"

                    tile["resourceHints"] = list(loc.get("resources", []))
                else:
                    roll = random.random()
                    if roll < 0.03:
                        tile["decoration"] = "tree"
                        tile["walkable"] = False
                    elif roll < 0.045:
                        tile["decoration"] = "flower"
                    elif roll < 0.06:
                        tile["type"] = "dark_grass"

                tile_row.append(tile)
            self.tiles.append(tile_row)

        self._rebuild_tile_resource_state()
        self._apply_structures_to_tiles()
        self._path_cache.clear()

    def _rebuild_tile_resource_state(self):
        self.tile_resource_state = {}
        for loc_id, loc in self.locations.items():
            if loc.get("type") not in ("natural", "open_land", "open_space"):
                continue
            resources = loc.get("resources", [])
            for dc in range(loc["width"]):
                for dr in range(loc["height"]):
                    col = loc["col"] + dc
                    row = loc["row"] + dr
                    tile = self.tiles[row][col]
                    tile_key = f"{col},{row}"
                    tile_state: dict[str, int] = {}
                    if "wood" in resources and tile.get("decoration") == "tree":
                        tile_state["wood"] = 3
                    if "wild_berries" in resources and (tile.get("decoration") == "flower" or random.random() < 0.25):
                        tile_state["wild_berries"] = 2
                    if "wild_herbs" in resources and random.random() < 0.2:
                        tile_state["wild_herbs"] = 1
                    if "wild_plants" in resources and tile["type"] in ("dirt", "grass") and random.random() < 0.35:
                        tile_state["wild_plants"] = 1
                    if tile_state:
                        self.tile_resource_state[tile_key] = tile_state
        self._sync_tile_resource_visuals()

    def _sync_tile_resource_visuals(self):
        for row in self.tiles:
            for tile in row:
                tile["resourceState"] = {}
                if tile.get("decoration") == "stump":
                    tile["decoration"] = None
        for key, state in self.tile_resource_state.items():
            col, row = map(int, key.split(","))
            if not (0 <= row < self.height and 0 <= col < self.width):
                continue
            tile = self.tiles[row][col]
            tile["resourceState"] = dict(state)
            if state.get("wood", 0) > 0:
                tile["decoration"] = "tree"
                tile["walkable"] = False
            elif "wood" in tile.get("resourceHints", []):
                tile["decoration"] = "stump"
                tile["walkable"] = True

    def _apply_structures_to_tiles(self):
        for loc_id, loc in self.locations.items():
            if loc.get("type") != "built_structure":
                continue
            for dc in range(loc["width"]):
                for dr in range(loc["height"]):
                    col = loc["col"] + dc
                    row = loc["row"] + dr
                    tile = self.tiles[row][col]
                    tile["structure"] = {
                        "building_id": loc_id,
                        "type": "built_structure",
                        "label": loc.get("label", loc_id),
                        "owner": loc.get("claimed_by", ""),
                    }
                    tile["walkable"] = False
                    tile["decoration"] = None
                    tile["resourceState"] = {}
                    tile["type"] = "dirt"
                    self.tile_resource_state.pop(f"{col},{row}", None)

    def _update_tile_after_resource_gather(self, location: str, resource: str):
        if resource != "wood":
            return
        loc = self.locations.get(location)
        if not loc:
            return
        tree_tiles = []
        for dc in range(loc["width"]):
            for dr in range(loc["height"]):
                col = loc["col"] + dc
                row = loc["row"] + dr
                state = self.tile_resource_state.get(f"{col},{row}", {})
                if state.get("wood", 0) > 0:
                    tree_tiles.append((col, row, state["wood"]))
        if not tree_tiles:
            return
        col, row, remaining = random.choice(tree_tiles)
        state = self.tile_resource_state[f"{col},{row}"]
        state["wood"] = max(0, remaining - 1)
        tile = self.tiles[row][col]
        if state["wood"] == 0:
            del state["wood"]
            tile["decoration"] = "stump"
            tile["walkable"] = True
        tile["resourceState"] = dict(state)
        if not state:
            self.tile_resource_state.pop(f"{col},{row}", None)
            tile["resourceState"] = {}
            if "wood" in tile.get("resourceHints", []):
                tile["decoration"] = "stump"

    def _regen_tile_resources(self):
        for loc_id, loc in self.locations.items():
            if "wood" not in loc.get("resources", []):
                continue
            if self.resources["wood"]["quantity"] >= RESOURCES["wood"]["quantity"]:
                break
            for dc in range(loc["width"]):
                for dr in range(loc["height"]):
                    if random.random() > 0.01:
                        continue
                    col = loc["col"] + dc
                    row = loc["row"] + dr
                    tile = self.tiles[row][col]
                    tile_key = f"{col},{row}"
                    if tile["structure"] or tile["decoration"] == "tree":
                        continue
                    if tile["type"] == "dark_grass":
                        tile["decoration"] = "tree"
                        tile["walkable"] = False
                        self.tile_resource_state.setdefault(tile_key, {})["wood"] = 2
                        tile["resourceState"] = dict(self.tile_resource_state[tile_key])
                        return

    def get_location(self, loc_id: str) -> dict | None:
        return self.locations.get(loc_id)

    def add_proposal(self, proposal: dict) -> dict:
        self.active_proposals = [p for p in self.active_proposals if p.get("id") != proposal.get("id")]
        self.active_proposals.append(proposal)
        return proposal

    def upsert_meeting(self, meeting: dict) -> dict:
        self.meetings = [m for m in self.meetings if m.get("id") != meeting.get("id")]
        self.meetings.append(meeting)
        return meeting

    def upsert_project(self, project: dict) -> dict:
        self.projects = [p for p in self.projects if p.get("id") != project.get("id")]
        self.projects.append(project)
        return project

    def record_trade(self, trade: dict):
        self.trades.append(trade)
        self.trades = self.trades[-120:]

    def add_norm_violation(self, violation: dict):
        self.norm_violations.append(violation)
        self.norm_violations = self.norm_violations[-80:]
        norm_text = violation.get("norm")
        if not norm_text:
            return
        for norm in self.constitution.social_norms:
            if (norm["text"] if isinstance(norm, dict) else str(norm)) != norm_text:
                continue
            if isinstance(norm, dict):
                norm["violations"] = int(norm.get("violations", 0)) + 1
                history = norm.setdefault("history", [])
                history.append({
                    "tick": violation.get("tick", 0),
                    "type": "violation",
                    "description": violation.get("description", ""),
                })
                norm["history"] = history[-10:]
                norm["strength"] = round(max(0.1, float(norm.get("strength", 0.55)) - 0.03), 2)
            break

    def add_norm(self, text: str, tick: int, category: str = "social", origin: str = "emergent", scope: str = "settlement") -> dict:
        existing = next((n for n in self.constitution.social_norms if (n["text"] if isinstance(n, dict) else n) == text), None)
        if existing:
            if isinstance(existing, dict):
                existing["strength"] = round(min(1.0, existing.get("strength", 0.5) + 0.05), 2)
                history = existing.setdefault("history", [])
                history.append({"tick": tick, "type": "reaffirmed", "description": text})
                existing["history"] = history[-10:]
            return existing if isinstance(existing, dict) else {"text": existing}
        norm = {
            "id": f"norm_{len(self.constitution.social_norms) + 1}",
            "text": text,
            "category": category,
            "origin": origin,
            "strength": 0.55,
            "scope": scope,
            "recognized_by": [],
            "violations": 0,
            "created_tick": tick,
            "status": "active",
            "history": [{"tick": tick, "type": "created", "description": text}],
        }
        self.constitution.social_norms.append(norm)
        return norm

    def recognize_norm(self, text: str, agent_name: str, amount: float = 0.02):
        for norm in self.constitution.social_norms:
            if (norm["text"] if isinstance(norm, dict) else str(norm)) != text:
                continue
            if isinstance(norm, dict):
                if agent_name and agent_name not in norm["recognized_by"]:
                    norm["recognized_by"].append(agent_name)
                norm["strength"] = round(min(1.0, float(norm.get("strength", 0.55)) + amount), 2)
            return

    def get_location_entry(self, loc_id: str) -> tuple[int, int]:
        loc = self.locations.get(loc_id)
        if not loc:
            return (20, 20)
        if loc["type"] == "water":
            return (loc["col"] + loc["width"], loc["row"] + loc["height"] // 2)
        return (loc["col"] + loc["width"] // 2, min(self.height - 1, loc["row"] + loc["height"]))

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
        available = []
        for resource in loc.get("resources", []):
            if self.resources.get(resource, {}).get("quantity", 0) > 0:
                available.append(resource)
        return available

    def get_all_location_ids(self) -> list[str]:
        return list(self.locations.keys())

    def get_unclaimed_buildings(self) -> list[str]:
        return [
            loc_id
            for loc_id, loc in self.locations.items()
            if loc.get("type") == "built_structure" and not loc.get("claimed_by")
        ]

    def claim_location(self, loc_id: str, agent_name: str, purpose: str = "") -> bool:
        loc = self.locations.get(loc_id)
        if not loc or loc.get("claimed_by"):
            return False
        loc["claimed_by"] = agent_name
        loc["designated_purpose"] = purpose
        logger.info("%s claimed %s for %s", agent_name, loc_id, purpose or "personal use")
        return True

    def gather_resource(self, resource: str, amount: int, location: str) -> int:
        res = self.resources.get(resource)
        if not res:
            return 0
        locs = res["locations"] if isinstance(res["locations"], list) else [res["locations"]]
        if location not in locs:
            return 0
        gathered = min(amount, res["quantity"])
        if gathered <= 0:
            return 0
        res["quantity"] -= gathered
        self._update_tile_after_resource_gather(location, resource)
        return gathered

    def regenerate_resources(self):
        for resource, state in self.resources.items():
            if state["renewable"] and state["quantity"] < RESOURCES[resource]["quantity"]:
                state["quantity"] = min(RESOURCES[resource]["quantity"], state["quantity"] + state["regen_rate"])
        self._regen_tile_resources()
        self._sync_tile_resource_visuals()

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
        neighbors = [(0, 1), (0, -1), (1, 0), (-1, 0)]
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
                nb = (current[0] + dc, current[1] + dr)
                if not self.is_walkable(nb[0], nb[1]) and nb != end:
                    continue
                tg = g_score[current] + 1
                if tg < g_score.get(nb, float("inf")):
                    came_from[nb] = current
                    g_score[nb] = tg
                    h = abs(nb[0] - end[0]) + abs(nb[1] - end[1])
                    heapq.heappush(open_set, (tg + h, nb))
        return [start]

    def get_distance(self, loc_a: str, loc_b: str) -> float:
        ea = self.get_location_entry(loc_a)
        eb = self.get_location_entry(loc_b)
        return abs(ea[0] - eb[0]) + abs(ea[1] - eb[1])

    def get_tile_grid(self):
        return self.tiles

    def build_structure(self, col: int, row: int, width: int, height: int, label: str, builder: str = "", purpose: str = "") -> str | None:
        for dc in range(width):
            for dr in range(height):
                if not (0 <= col + dc < self.width and 0 <= row + dr < self.height):
                    return None
                tile = self.tiles[row + dr][col + dc]
                if tile.get("structure") or tile["type"] == "water" or tile.get("decoration") == "tree":
                    return None

        bid = f"building_{self._next_building_id}"
        self._next_building_id += 1
        self.locations[bid] = {
            "type": "built_structure",
            "label": label,
            "description": f"{label}, built by {builder or 'the settlers'}",
            "col": col,
            "row": row,
            "width": width,
            "height": height,
            "capacity": width * height * 2,
            "resources": [],
            "claimed_by": builder or None,
            "designated_purpose": purpose,
        }
        self.created_objects.append({
            "id": bid,
            "label": label,
            "builder": builder,
            "purpose": purpose,
            "tick_hint": len(self.created_objects) + 1,
        })
        self._apply_structures_to_tiles()
        self._sync_tile_resource_visuals()
        self._path_cache.clear()
        logger.info("Built '%s' at (%s,%s) by %s, id=%s", label, col, row, builder, bid)
        return bid

    def find_empty_space(self, width: int, height: int) -> tuple[int, int] | None:
        center_col, center_row = 20, 20
        for radius in range(2, 18):
            row_start = max(2, center_row - radius)
            row_end = min(self.height - height - 2, center_row + radius)
            col_start = max(2, center_col - radius)
            col_end = min(self.width - width - 2, center_col + radius)
            for row in range(row_start, row_end + 1):
                for col in range(col_start, col_end + 1):
                    can_build = True
                    for dc in range(width):
                        for dr in range(height):
                            tile = self.tiles[row + dr][col + dc]
                            if tile.get("structure") or tile["type"] in ("water",) or tile.get("decoration") == "tree":
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
            if loc.get("type") != "built_structure":
                continue
            buildings.append({
                "id": loc_id,
                "label": loc.get("label", loc_id.replace("_", " ").title()),
                "type": loc["type"],
                "col": loc["col"],
                "row": loc["row"],
                "width": loc["width"],
                "height": loc["height"],
                "owner": loc.get("claimed_by", ""),
                "purpose": loc.get("designated_purpose", ""),
            })
        for project in self.projects:
            if project.get("status") != "completed":
                continue
            if not project.get("render_as_structure"):
                continue
            buildings.append({
                "id": project["id"],
                "label": project.get("name", project["id"]),
                "type": "project",
                "col": project.get("col", 0),
                "row": project.get("row", 0),
                "width": project.get("width", 2),
                "height": project.get("height", 2),
                "owner": project.get("sponsor", ""),
                "purpose": project.get("kind", ""),
            })
        return buildings

    def get_world_summary(self) -> str:
        built = sum(1 for loc in self.locations.values() if loc.get("type") == "built_structure")
        claimed = sum(1 for loc in self.locations.values() if loc.get("claimed_by"))
        return (
            f"Untouched wilderness around a central clearing. {built} structures built so far, "
            f"{claimed} claimed spaces. {len(self.active_proposals)} active proposals, "
            f"{len(self.projects)} projects, {len(self.trades)} trades. Constitution: {self.constitution.summary()}"
        )

    def to_save_dict(self) -> dict:
        return {
            "version": 2,
            "locations": self.locations,
            "resources": self.resources,
            "constitution": self.constitution.to_dict(),
            "created_objects": self.created_objects[-50:],
            "trades": self.trades[-50:],
            "active_proposals": self.active_proposals[-50:],
            "meetings": self.meetings[-50:],
            "coalitions": self.coalitions[-50:],
            "norm_violations": self.norm_violations[-80:],
            "projects": self.projects[-50:],
            "next_building_id": self._next_building_id,
            "tile_resource_state": self.tile_resource_state,
        }

    def load_from_save(self, data: dict):
        if data.get("locations"):
            self.locations = data["locations"]
        if data.get("resources"):
            self.resources = data["resources"]
        if data.get("constitution"):
            self.constitution.load_from_dict(data["constitution"])
        if data.get("created_objects"):
            self.created_objects = data["created_objects"]
        if data.get("trades"):
            self.trades = data["trades"]
        if data.get("active_proposals"):
            self.active_proposals = data["active_proposals"]
        if data.get("meetings"):
            self.meetings = data["meetings"]
        if data.get("coalitions"):
            self.coalitions = data["coalitions"]
        if data.get("norm_violations"):
            self.norm_violations = data["norm_violations"]
        if data.get("projects"):
            self.projects = data["projects"]
        self._next_building_id = data.get("next_building_id", self._next_building_id)
        self._generate_world()
        if data.get("tile_resource_state"):
            self.tile_resource_state = data["tile_resource_state"]
            for key, state in self.tile_resource_state.items():
                col, row = map(int, key.split(","))
                tile = self.tiles[row][col]
                if state.get("wood", 0) > 0:
                    tile["decoration"] = "tree"
                    tile["walkable"] = False
                elif tile.get("structure") is None and tile.get("decoration") == "tree":
                    tile["decoration"] = None
                    tile["walkable"] = True
        self._sync_tile_resource_visuals()
        self._apply_structures_to_tiles()
        self._path_cache.clear()
