"""Belief system — generalized knowledge extracted from patterns across episodes."""

from dataclasses import dataclass, field


@dataclass
class Belief:
    content: str
    category: str  # person_model, world_knowledge, social_norm, self_belief
    confidence: float = 0.5
    emotional_charge: float = 0.0
    source_type: str = "personal_experience"
    source_agent: str = ""
    supporting_count: int = 1
    contradicting_count: int = 0
    first_formed: int = 0
    last_reinforced: int = 0
    is_actively_questioned: bool = False

    def reinforce(self, tick: int):
        self.confidence = min(1.0, self.confidence + 0.05)
        self.supporting_count += 1
        self.last_reinforced = tick
        self.is_actively_questioned = False

    def challenge(self, tick: int):
        resistance = self.confidence * 0.5 + self.emotional_charge * 0.3
        change = 0.1 * (1.0 - resistance)
        self.confidence = max(0.0, self.confidence - change)
        self.contradicting_count += 1
        if self.confidence < 0.4:
            self.is_actively_questioned = True

    def to_dict(self) -> dict:
        return {
            "content": self.content, "category": self.category,
            "confidence": round(self.confidence, 2),
            "charge": round(self.emotional_charge, 2),
            "source": self.source_type, "questioned": self.is_actively_questioned,
        }


class BeliefSystem:
    def __init__(self):
        self.beliefs: list[Belief] = []

    def add(self, content: str, category: str = "world_knowledge", confidence: float = 0.5,
            source: str = "personal_experience", source_agent: str = "", tick: int = 0,
            emotional_charge: float = 0.0):
        # Check if similar belief exists
        for b in self.beliefs:
            if self._similar(b.content, content):
                b.reinforce(tick)
                return
        self.beliefs.append(Belief(
            content=content, category=category, confidence=confidence,
            source_type=source, source_agent=source_agent, first_formed=tick,
            last_reinforced=tick, emotional_charge=emotional_charge,
        ))
        # Keep max 30 beliefs
        if len(self.beliefs) > 30:
            self.beliefs.sort(key=lambda b: b.confidence, reverse=True)
            self.beliefs = self.beliefs[:30]

    def challenge(self, content: str, tick: int):
        for b in self.beliefs:
            if self._similar(b.content, content):
                b.challenge(tick)
                return

    def get_by_category(self, category: str) -> list[Belief]:
        return [b for b in self.beliefs if b.category == category]

    def get_about_person(self, name: str) -> list[Belief]:
        return [b for b in self.beliefs if name.lower() in b.content.lower()]

    def get_self_beliefs(self) -> list[Belief]:
        return self.get_by_category("self_belief")

    def get_questioned(self) -> list[Belief]:
        return [b for b in self.beliefs if b.is_actively_questioned]

    def get_prompt_context(self, relevant_to: str = "", max_beliefs: int = 5) -> str:
        if relevant_to:
            relevant = [b for b in self.beliefs if any(
                w in b.content.lower() for w in relevant_to.lower().split()[:3]
            )]
            relevant.sort(key=lambda b: b.confidence, reverse=True)
            selected = relevant[:max_beliefs]
        else:
            selected = sorted(self.beliefs, key=lambda b: b.confidence, reverse=True)[:max_beliefs]

        if not selected:
            return ""
        return "Your beliefs:\n" + "\n".join(
            f"- {b.content} (confidence: {b.confidence:.0%}{'—questioning this' if b.is_actively_questioned else ''})"
            for b in selected
        )

    def to_list(self) -> list[dict]:
        return [b.to_dict() for b in self.beliefs]

    def load_from_list(self, data: list[dict]):
        self.beliefs = []
        for d in data:
            self.beliefs.append(Belief(
                content=d.get("content", ""), category=d.get("category", "world_knowledge"),
                confidence=d.get("confidence", 0.5), emotional_charge=d.get("charge", 0.0),
                source_type=d.get("source", "personal_experience"),
            ))

    @staticmethod
    def _similar(a: str, b: str) -> bool:
        """Very rough similarity check — share enough words."""
        a_words = set(a.lower().split())
        b_words = set(b.lower().split())
        if not a_words or not b_words:
            return False
        overlap = len(a_words & b_words)
        return overlap / min(len(a_words), len(b_words)) > 0.5
