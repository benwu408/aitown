"""Meta-simulation -- stub for future PatternDetector.

All hardcoded governance cycles, leadership emergence, norm detection,
currency detection, and institution creation have been removed.
These must emerge from: open-ended actions -> pattern detection -> consequences.

The PatternDetector (Phase 2) will populate world.constitution data structures
by observing actual agent behavior, not by running hardcoded heuristics.
"""

import logging

logger = logging.getLogger("agentica.meta")


class MetaSimulation:
    """Placeholder -- returns no events until PatternDetector is wired in."""

    def __init__(self):
        pass

    def check(self, agents: dict, world, tick: int, day: int) -> list[dict]:
        """No-op. Will be replaced by PatternDetector in Phase 2."""
        return []

    async def process_proposal(self, agent, proposal_text: str, agents: dict, world) -> dict | None:
        """No-op. Proposal evaluation will go through ActionInterpreter."""
        return None


meta_simulation = MetaSimulation()
