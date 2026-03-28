"""Coherence checker — validates world state consistency."""

import logging

logger = logging.getLogger("agentica.coherence")


class CoherenceChecker:
    def check(self, agents: dict, world) -> list[str]:
        """Run all coherence checks. Returns list of issues found and fixed."""
        issues = []

        # Resource conservation: no negative quantities
        for res_name, res in world.resources.items():
            if res["quantity"] < 0:
                res["quantity"] = 0
                issues.append(f"Fixed: {res_name} had negative quantity")

        # Agent positions should be within map bounds
        for agent in agents.values():
            col, row = agent.position
            if col < 0 or col >= world.width or row < 0 or row >= world.height:
                # Reset to clearing
                entry = world.get_location_entry("clearing")
                agent.position = entry
                agent.current_location = "clearing"
                issues.append(f"Fixed: {agent.name} was out of bounds, moved to clearing")

        # Institutions should have purpose
        for inst in world.constitution.institutions[:]:
            if not inst.get("name") or not inst.get("purpose"):
                world.constitution.institutions.remove(inst)
                issues.append(f"Removed empty institution")

        # Claimed locations should have valid claimants
        for loc_id, loc in world.locations.items():
            claimer = loc.get("claimed_by")
            if claimer and claimer not in [a.name for a in agents.values()]:
                loc["claimed_by"] = None
                issues.append(f"Fixed: {loc_id} claimed by non-existent agent {claimer}")

        if issues:
            logger.info(f"Coherence check: {len(issues)} issues fixed")

        return issues


coherence_checker = CoherenceChecker()
