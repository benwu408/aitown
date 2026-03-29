"""InnovationTracker -- records novel actions and tracks adoption."""

import logging

logger = logging.getLogger("agentica.innovation")


class InnovationTracker:
    def __init__(self):
        self._innovations: dict[str, dict] = {}
        self._known_action_types: set[str] = set()
        self._next_id = 1

    def record_new_action(self, agent, action_result: dict, world_state) -> dict | None:
        action_type = action_result.get("action_type", "")
        action_desc = action_result.get("description", action_type)
        key = f"{action_type}:{action_desc[:60]}"

        if key in self._known_action_types:
            existing = self._innovations.get(key)
            if existing and agent.name != existing["inventor"] and agent.name not in existing["adopters"]:
                self.record_adoption(key, agent.name)
            return None

        self._known_action_types.add(key)
        innovation_id = f"innov_{self._next_id}"
        self._next_id += 1

        innovation = {
            "id": innovation_id,
            "key": key,
            "name": action_desc[:80],
            "description": action_result.get("description", action_desc),
            "inventor": agent.name,
            "invented_on": action_result.get("tick", 0),
            "action_type": action_type,
            "observers": [],
            "adopters": [],
            "adoption_rate": 0.0,
            "parent_id": action_result.get("parent_innovation_id"),
            "reactions": [],
        }
        self._innovations[key] = innovation
        logger.info("New innovation: %s by %s", innovation["name"], agent.name)
        return innovation

    def record_observation(self, innovation_id: str, observer: str, reaction: str = "curious"):
        for innov in self._innovations.values():
            if innov["id"] == innovation_id or innov["key"] == innovation_id:
                if observer not in innov["observers"] and observer != innov["inventor"]:
                    innov["observers"].append(observer)
                    innov["reactions"].append({"observer": observer, "reaction": reaction})
                    innov["reactions"] = innov["reactions"][-20:]
                return

    def record_adoption(self, innovation_id: str, adopter: str):
        for innov in self._innovations.values():
            if innov["id"] == innovation_id or innov["key"] == innovation_id:
                if adopter not in innov["adopters"] and adopter != innov["inventor"]:
                    innov["adopters"].append(adopter)
                    total_agents = max(1, len(innov["observers"]) + len(innov["adopters"]) + 1)
                    innov["adoption_rate"] = len(innov["adopters"]) / total_agents
                return

    def update_adoption_rates(self, total_agents: int):
        for innov in self._innovations.values():
            if total_agents > 0:
                innov["adoption_rate"] = round(len(innov["adopters"]) / total_agents, 3)

    def get_innovations_summary(self) -> list[dict]:
        return [
            {
                "id": innov["id"],
                "name": innov["name"],
                "inventor": innov["inventor"],
                "invented_on": innov["invented_on"],
                "observers": len(innov["observers"]),
                "adopters": len(innov["adopters"]),
                "adoption_rate": innov["adoption_rate"],
                "is_common": innov["adoption_rate"] > 0.3,
            }
            for innov in self._innovations.values()
        ]

    def get_innovation_tree(self) -> dict:
        roots = []
        children_map: dict[str, list] = {}

        for innov in self._innovations.values():
            node = {
                "id": innov["id"],
                "name": innov["name"],
                "inventor": innov["inventor"],
                "adoption_rate": innov["adoption_rate"],
                "children": [],
            }
            parent = innov.get("parent_id")
            if parent:
                children_map.setdefault(parent, []).append(node)
            else:
                roots.append(node)

        def attach_children(node):
            node["children"] = children_map.get(node["id"], [])
            for child in node["children"]:
                attach_children(child)

        for root in roots:
            attach_children(root)

        return {"roots": roots, "total": len(self._innovations)}

    def get_common_practices(self) -> list[dict]:
        return [innov for innov in self._innovations.values() if innov["adoption_rate"] > 0.3]


innovation_tracker = InnovationTracker()
