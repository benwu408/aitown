"""Episodic memory — personal events with emotional encoding and distortion over time."""

import math
import random
from dataclasses import dataclass, field


@dataclass
class Episode:
    content: str
    tick: int
    day: int
    time_of_day: str
    location: str
    agents_involved: list[str] = field(default_factory=list)

    # Emotional encoding
    emotional_valence: float = 0.0   # -1 painful to 1 wonderful
    emotional_intensity: float = 0.5  # 0 forgettable to 1 unforgettable
    primary_emotion: str = "neutral"

    # Subjective framing
    my_role: str = "observer"        # "caused", "experienced", "witnessed"
    my_interpretation: str = ""
    sensory_detail: str = ""         # Vivid detail from the moment
    what_this_means: str = ""        # Personal significance

    # Memory dynamics
    times_recalled: int = 0
    last_recalled: int = 0
    accuracy_drift: float = 0.0

    # Retrieval
    category: str = "observation"    # observation, conversation, action, reflection, emotion

    def recall(self, current_tick: int) -> str:
        """Recall this memory — may distort it slightly."""
        self.times_recalled += 1
        self.last_recalled = current_tick
        self.accuracy_drift = min(0.5, self.accuracy_drift + 0.02)

        # Emotional intensity amplifies for dramatic memories, decays for mundane
        if self.emotional_intensity > 0.6:
            self.emotional_intensity = min(1.0, self.emotional_intensity + 0.01)
        elif self.emotional_intensity < 0.3:
            self.emotional_intensity = max(0.0, self.emotional_intensity - 0.01)

        return self.content

    def to_dict(self) -> dict:
        return {
            "content": self.content, "tick": self.tick, "day": self.day,
            "time_of_day": self.time_of_day, "location": self.location,
            "agents_involved": self.agents_involved,
            "valence": round(self.emotional_valence, 2),
            "intensity": round(self.emotional_intensity, 2),
            "emotion": self.primary_emotion,
            "role": self.my_role, "interpretation": self.my_interpretation,
            "times_recalled": self.times_recalled,
            "category": self.category,
        }


class EpisodicMemory:
    def __init__(self, max_size: int = 300):
        self.episodes: list[Episode] = []
        self.max_size = max_size

    def add(self, episode):
        # Accept either Episode or legacy MemoryEntry
        if not isinstance(episode, Episode):
            # Legacy MemoryEntry compatibility
            ep = Episode(
                content=getattr(episode, "content", str(episode)),
                tick=getattr(episode, "tick", 0),
                day=getattr(episode, "tick", 0) // 288,
                time_of_day="",
                location=getattr(episode, "location", ""),
                agents_involved=getattr(episode, "related_agents", []),
                emotional_intensity=min(1.0, getattr(episode, "importance", 5.0) / 10.0),
                category=getattr(episode, "memory_type", "observation"),
            )
            episode = ep
        self.episodes.append(episode)
        if len(self.episodes) > self.max_size:
            # Drop oldest low-intensity episodes
            self.episodes.sort(key=lambda e: e.emotional_intensity, reverse=True)
            self.episodes = self.episodes[:self.max_size]
            self.episodes.sort(key=lambda e: e.tick)

    def add_simple(self, content: str, tick: int, day: int, time_of_day: str, location: str,
                   category: str = "observation", valence: float = 0.0, intensity: float = 0.5,
                   emotion: str = "neutral", agents: list[str] | None = None):
        self.add(Episode(
            content=content, tick=tick, day=day, time_of_day=time_of_day, location=location,
            agents_involved=agents or [], emotional_valence=valence,
            emotional_intensity=intensity, primary_emotion=emotion, category=category,
        ))

    def retrieve(self, query: str, current_tick: int, k: int = 10) -> list[Episode]:
        """Retrieve most relevant memories. Weighted by recency + emotion + rehearsal."""
        scored = []
        for ep in self.episodes:
            recency = 1.0 / (1.0 + (current_tick - ep.last_recalled if ep.last_recalled else current_tick - ep.tick) * 0.005)
            emotional_weight = ep.emotional_intensity * 1.5
            rehearsal_boost = min(ep.times_recalled * 0.1, 0.5)
            # Simple keyword relevance (no embeddings for now)
            relevance = 0.3 if any(w in ep.content.lower() for w in query.lower().split()[:5]) else 0.0

            score = 0.25 * recency + 0.30 * emotional_weight + 0.30 * relevance + 0.15 * rehearsal_boost
            scored.append((score, ep))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [ep for _, ep in scored[:k]]

        # Mark as recalled
        for ep in results:
            ep.recall(current_tick)

        return results

    def recent(self, n: int = 10) -> list[Episode]:
        return self.episodes[-n:]

    def recent_text(self, n: int = 10) -> list[str]:
        return [e.content for e in self.episodes[-n:]]

    def by_category(self, category: str, n: int = 10) -> list[Episode]:
        return [e for e in self.episodes if e.category == category][-n:]

    def reflections(self, n: int = 5) -> list[str]:
        return [e.content for e in self.by_category("reflection", n)]

    def conversations_with(self, agent_name: str, n: int = 5) -> list[Episode]:
        return [e for e in self.episodes if agent_name in e.agents_involved and e.category == "conversation"][-n:]

    def to_list(self, n: int = 50) -> list[dict]:
        return [e.to_dict() for e in self.episodes[-n:]]

    def load_from_list(self, data: list[dict]):
        self.episodes = []
        for d in data:
            self.episodes.append(Episode(
                content=d.get("content", ""),
                tick=d.get("tick", 0),
                day=d.get("day", 0),
                time_of_day=d.get("time_of_day", ""),
                location=d.get("location", ""),
                agents_involved=d.get("agents_involved", []),
                emotional_valence=d.get("valence", 0.0),
                emotional_intensity=d.get("intensity", 0.5),
                primary_emotion=d.get("emotion", "neutral"),
                my_role=d.get("role", "observer"),
                my_interpretation=d.get("interpretation", ""),
                times_recalled=d.get("times_recalled", 0),
                category=d.get("category", "observation"),
            ))

    # --- Legacy compatibility with old MemoryStream ---
    @property
    def memories(self):
        """Alias for old code that accesses .memories directly."""
        return self.episodes

    def add_legacy(self, tick: int, content: str, importance: float = 5.0,
                   memory_type: str = "observation", related_agents: list[str] | None = None,
                   location: str = ""):
        """Compatible with old MemoryEntry-style adds."""
        # Map importance to intensity (old: 1-10, new: 0-1)
        intensity = min(1.0, importance / 10.0)
        self.add_simple(
            content=content, tick=tick, day=tick // 288, time_of_day="",
            location=location, category=memory_type,
            intensity=intensity, agents=related_agents,
        )

    def get_emotional_summary(self) -> str:
        """Summarize recent emotional pattern."""
        recent = self.episodes[-20:]
        if not recent:
            return "No recent memories."
        avg_valence = sum(e.emotional_valence for e in recent) / len(recent)
        if avg_valence > 0.2:
            return "Recent days have been mostly positive."
        elif avg_valence < -0.2:
            return "Recent days have been difficult."
        return "Recent days have been a mix of ups and downs."
