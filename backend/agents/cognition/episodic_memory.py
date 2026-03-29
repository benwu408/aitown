"""Episodic memory -- personal events with emotional encoding and distortion over time."""

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
    emotional_valence: float = 0.0
    emotional_intensity: float = 0.5
    primary_emotion: str = "neutral"
    emotional_coloring: str = ""  # subjective emotional flavor

    # Subjective framing
    my_role: str = "observer"
    my_interpretation: str = ""
    sensory_detail: str = ""
    what_this_means: str = ""

    # Memory dynamics
    times_recalled: int = 0
    last_recalled: int = 0
    accuracy_drift: float = 0.0
    confidence: float = 0.8  # how certain the agent is about this memory

    # Retrieval
    category: str = "observation"

    def recall(self, current_tick: int) -> str:
        self.times_recalled += 1
        self.last_recalled = current_tick
        self.accuracy_drift = min(0.5, self.accuracy_drift + 0.02)
        # Confidence erodes slightly each recall for non-vivid memories
        if self.emotional_intensity < 0.6:
            self.confidence = max(0.2, self.confidence - 0.01)

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
            "emotional_coloring": self.emotional_coloring,
            "role": self.my_role, "interpretation": self.my_interpretation,
            "times_recalled": self.times_recalled,
            "confidence": round(self.confidence, 2),
            "category": self.category,
        }


def encode_subjectively(event_data: dict, agent_personality: dict, agent_emotions) -> Episode:
    """Create a witness-specific memory. Same event, different agents produce different episodes."""
    content = event_data.get("content", "")
    neuroticism = agent_personality.get("neuroticism", 0.5)
    agreeableness = agent_personality.get("agreeableness", 0.5)
    extraversion = agent_personality.get("extraversion", 0.5)

    # Get current emotional state influence
    current_valence = getattr(agent_emotions, "valence", 0.0)
    current_anxiety = getattr(agent_emotions, "anxiety", 0.0)
    dominant_emotion = "neutral"
    if hasattr(agent_emotions, "get_dominant_emotion"):
        dominant_emotion = agent_emotions.get_dominant_emotion()[0]

    base_valence = event_data.get("valence", 0.0)
    base_intensity = event_data.get("intensity", 0.5)

    # Neurotic agents amplify negative events, dampen positive ones
    if base_valence < 0:
        valence = base_valence * (1.0 + neuroticism * 0.4)
        intensity = min(1.0, base_intensity + neuroticism * 0.2)
    else:
        valence = base_valence * (1.0 - neuroticism * 0.2)
        intensity = base_intensity

    # Current mood colors the memory
    valence = max(-1.0, min(1.0, valence + current_valence * 0.15))

    # Agreeable agents remember social events more vividly
    if event_data.get("agents_involved"):
        intensity = min(1.0, intensity + agreeableness * 0.1)

    # Extraverts remember group events more positively
    if len(event_data.get("agents_involved", [])) > 1 and extraversion > 0.5:
        valence = min(1.0, valence + 0.05)

    # Emotional coloring based on personality + current state
    coloring_parts = []
    if current_anxiety > 0.3:
        coloring_parts.append("tinged with unease")
    if current_valence > 0.3:
        coloring_parts.append("seen through a hopeful lens")
    elif current_valence < -0.3:
        coloring_parts.append("colored by a dark mood")
    if neuroticism > 0.7:
        coloring_parts.append("remembered with worry about what could go wrong")
    emotional_coloring = "; ".join(coloring_parts) if coloring_parts else ""

    # Confidence: anxious agents are less certain, recent events are clearer
    confidence = 0.85 - current_anxiety * 0.15 - neuroticism * 0.1
    confidence = max(0.3, min(1.0, confidence))

    return Episode(
        content=content,
        tick=event_data.get("tick", 0),
        day=event_data.get("day", 0),
        time_of_day=event_data.get("time_of_day", ""),
        location=event_data.get("location", ""),
        agents_involved=event_data.get("agents_involved", []),
        emotional_valence=round(max(-1.0, min(1.0, valence)), 2),
        emotional_intensity=round(max(0.0, min(1.0, intensity)), 2),
        primary_emotion=dominant_emotion,
        emotional_coloring=emotional_coloring,
        my_role=event_data.get("role", "observer"),
        my_interpretation=event_data.get("interpretation", ""),
        sensory_detail=event_data.get("sensory_detail", ""),
        what_this_means=event_data.get("what_this_means", ""),
        confidence=round(confidence, 2),
        category=event_data.get("category", "observation"),
    )


class EpisodicMemory:
    def __init__(self, max_size: int = 300):
        self.episodes: list[Episode] = []
        self.max_size = max_size

    def add(self, episode):
        if not isinstance(episode, Episode):
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
            self.episodes.sort(key=lambda e: e.emotional_intensity, reverse=True)
            self.episodes = self.episodes[:self.max_size]
            self.episodes.sort(key=lambda e: e.tick)

    def add_subjective(self, event_data: dict, agent_personality: dict, agent_emotions):
        ep = encode_subjectively(event_data, agent_personality, agent_emotions)
        self.add(ep)

    def add_simple(self, content: str, tick: int, day: int, time_of_day: str, location: str,
                   category: str = "observation", valence: float = 0.0, intensity: float = 0.5,
                   emotion: str = "neutral", agents: list[str] | None = None,
                   confidence: float = 0.8):
        self.add(Episode(
            content=content, tick=tick, day=day, time_of_day=time_of_day, location=location,
            agents_involved=agents or [], emotional_valence=valence,
            emotional_intensity=intensity, primary_emotion=emotion, category=category,
            confidence=confidence,
        ))

    def retrieve(self, query: str, current_tick: int, k: int = 10) -> list[Episode]:
        scored = []
        for ep in self.episodes:
            recency = 1.0 / (1.0 + (current_tick - ep.last_recalled if ep.last_recalled else current_tick - ep.tick) * 0.005)
            emotional_weight = ep.emotional_intensity * 1.5
            rehearsal_boost = min(ep.times_recalled * 0.1, 0.5)
            relevance = 0.3 if any(w in ep.content.lower() for w in query.lower().split()[:5]) else 0.0
            confidence_boost = ep.confidence * 0.1

            score = 0.22 * recency + 0.28 * emotional_weight + 0.28 * relevance + 0.12 * rehearsal_boost + 0.10 * confidence_boost
            scored.append((score, ep))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [ep for _, ep in scored[:k]]

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
                emotional_coloring=d.get("emotional_coloring", ""),
                my_role=d.get("role", "observer"),
                my_interpretation=d.get("interpretation", ""),
                times_recalled=d.get("times_recalled", 0),
                confidence=d.get("confidence", 0.8),
                category=d.get("category", "observation"),
            ))

    @property
    def memories(self):
        return self.episodes

    def add_legacy(self, tick: int, content: str, importance: float = 5.0,
                   memory_type: str = "observation", related_agents: list[str] | None = None,
                   location: str = ""):
        intensity = min(1.0, importance / 10.0)
        self.add_simple(
            content=content, tick=tick, day=tick // 288, time_of_day="",
            location=location, category=memory_type,
            intensity=intensity, agents=related_agents,
        )

    def get_emotional_summary(self) -> str:
        recent = self.episodes[-20:]
        if not recent:
            return "No recent memories."
        avg_valence = sum(e.emotional_valence for e in recent) / len(recent)
        if avg_valence > 0.2:
            return "Recent days have been mostly positive."
        elif avg_valence < -0.2:
            return "Recent days have been difficult."
        return "Recent days have been a mix of ups and downs."
