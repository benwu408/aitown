"""Agent memory system — stores observations, conversations, reflections."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MemoryEntry:
    tick: int
    content: str
    importance: float = 5.0  # 1-10
    memory_type: str = "observation"  # observation, conversation, reflection, action, emotion
    related_agents: list[str] = field(default_factory=list)
    location: str = ""

    def to_dict(self) -> dict:
        return {
            "tick": self.tick,
            "content": self.content,
            "importance": self.importance,
            "type": self.memory_type,
            "relatedAgents": self.related_agents,
            "location": self.location,
        }


class MemoryStream:
    def __init__(self, max_size: int = 500):
        self.memories: list[MemoryEntry] = []
        self.max_size = max_size

    def add(self, entry: MemoryEntry):
        self.memories.append(entry)
        if len(self.memories) > self.max_size:
            # Remove oldest low-importance memories
            self.memories.sort(key=lambda m: m.importance, reverse=True)
            self.memories = self.memories[: self.max_size]
            self.memories.sort(key=lambda m: m.tick)

    def recent(self, n: int = 10) -> list[MemoryEntry]:
        return self.memories[-n:]

    def recent_text(self, n: int = 10) -> list[str]:
        return [m.content for m in self.memories[-n:]]

    def about_agent(self, agent_name: str, n: int = 5) -> list[MemoryEntry]:
        relevant = [m for m in self.memories if agent_name in m.related_agents]
        return relevant[-n:]

    def by_type(self, memory_type: str, n: int = 10) -> list[MemoryEntry]:
        relevant = [m for m in self.memories if m.memory_type == memory_type]
        return relevant[-n:]

    def reflections(self, n: int = 5) -> list[str]:
        return [m.content for m in self.by_type("reflection", n)]

    def to_list(self, n: int = 50) -> list[dict]:
        return [m.to_dict() for m in self.memories[-n:]]
