"""Social system — relationship management, gossip propagation."""

import logging
import random
from dataclasses import dataclass, field

logger = logging.getLogger("agentica.social")


@dataclass
class Relationship:
    sentiment: float = 0.5  # -1.0 to 1.0
    trust: float = 0.5  # 0.0 to 1.0
    familiarity: float = 0.1  # 0.0 to 1.0
    interaction_count: int = 0
    last_interaction_tick: int = 0
    notes: str = "Acquaintance"


class SocialSystem:
    def __init__(self):
        self.gossip_queue: list[dict] = []

    def update_relationship(
        self,
        agent,
        other_name: str,
        sentiment_delta: float = 0,
        trust_delta: float = 0,
        tick: int = 0,
        note: str | None = None,
    ):
        """Update relationship between two agents."""
        if other_name not in agent.relationships:
            agent.relationships[other_name] = {
                "sentiment": 0.5,
                "trust": 0.5,
                "familiarity": 0.1,
                "interaction_count": 0,
                "notes": "New acquaintance",
            }

        rel = agent.relationships[other_name]
        rel["sentiment"] = max(-1.0, min(1.0, rel.get("sentiment", 0.5) + sentiment_delta))
        rel["trust"] = max(0.0, min(1.0, rel.get("trust", 0.5) + trust_delta))
        rel["familiarity"] = min(1.0, rel.get("familiarity", 0.1) + 0.02)
        rel["interaction_count"] = rel.get("interaction_count", 0) + 1
        rel["last_interaction_tick"] = tick
        if note:
            rel["notes"] = note

    def add_gossip(self, source: str, about: str, content: str, importance: float = 5.0):
        """Add gossip to the propagation queue."""
        self.gossip_queue.append({
            "source": source,
            "about": about,
            "content": content,
            "importance": importance,
            "spread_count": 0,
        })

    def propagate_gossip(self, agents: dict, tick: int) -> list[dict]:
        """Spread gossip through conversations. Called periodically."""
        events = []

        for gossip in self.gossip_queue[:]:
            if gossip["spread_count"] >= 5:
                self.gossip_queue.remove(gossip)
                continue

            # Find agents who might spread this gossip
            for agent in agents.values():
                if agent.name == gossip["source"] or agent.name == gossip["about"]:
                    continue

                # Chance to learn gossip based on extroversion
                extroversion = agent.profile.personality.get("extraversion", 0.5)
                if random.random() < extroversion * 0.05:
                    # Agent learns the gossip
                    from agents.memory import MemoryEntry
                    agent.memory.add(MemoryEntry(
                        tick=tick,
                        content=f"Heard that {gossip['content']}",
                        importance=gossip["importance"] * 0.8,
                        memory_type="observation",
                        related_agents=[gossip["about"]],
                    ))
                    gossip["spread_count"] += 1

                    # Gossip affects relationships with the subject
                    about_name = gossip["about"]
                    if about_name not in agent.relationships:
                        agent.relationships[about_name] = {"sentiment": 0.5, "trust": 0.5, "familiarity": 0.1, "notes": "Acquaintance"}
                    # Negative gossip (high importance) hurts reputation
                    if gossip["importance"] >= 7:
                        agent.relationships[about_name]["sentiment"] = max(-1.0, agent.relationships[about_name].get("sentiment", 0.5) - 0.05)
                        agent.relationships[about_name]["trust"] = max(0.0, agent.relationships[about_name].get("trust", 0.5) - 0.03)
                    else:
                        # Neutral/positive gossip slightly positive
                        agent.relationships[about_name]["sentiment"] = min(1.0, agent.relationships[about_name].get("sentiment", 0.5) + 0.03)

                    events.append({
                        "type": "gossip",
                        "agentId": agent.id,
                        "about": gossip["about"],
                        "content": f"Heard gossip about {gossip['about']}",
                    })

        return events


social_system = SocialSystem()
