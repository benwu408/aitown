"""Belief system -- generalized knowledge extracted from patterns across episodes."""

from dataclasses import dataclass, field


@dataclass
class Belief:
    content: str
    category: str  # person_model, world_knowledge, social_norm, self_belief
    confidence: float = 0.5
    emotional_charge: float = 0.0
    source_type: str = "personal_experience"
    source_agent: str = ""
    evidence_count: int = 1
    contradicting_count: int = 0
    first_formed: int = 0
    last_updated_tick: int = 0
    is_actively_questioned: bool = False

    # Legacy alias
    @property
    def supporting_count(self) -> int:
        return self.evidence_count

    @property
    def last_reinforced(self) -> int:
        return self.last_updated_tick

    def reinforce(self, tick: int):
        self.confidence = min(1.0, self.confidence + 0.05)
        self.evidence_count += 1
        self.last_updated_tick = tick
        self.is_actively_questioned = False

    def challenge(self, tick: int):
        resistance = self.confidence * 0.5 + self.emotional_charge * 0.3
        change = 0.1 * (1.0 - resistance)
        self.confidence = max(0.0, self.confidence - change)
        self.contradicting_count += 1
        self.last_updated_tick = tick
        if self.confidence < 0.4:
            self.is_actively_questioned = True

    def to_dict(self) -> dict:
        return {
            "content": self.content, "category": self.category,
            "confidence": round(self.confidence, 2),
            "charge": round(self.emotional_charge, 2),
            "source": self.source_type, "questioned": self.is_actively_questioned,
            "evidence_count": self.evidence_count,
            "last_updated_tick": self.last_updated_tick,
        }


class BeliefSystem:
    def __init__(self):
        self.beliefs: list[Belief] = []

    def add(self, content: str, category: str = "world_knowledge", confidence: float = 0.5,
            source: str = "personal_experience", source_agent: str = "", tick: int = 0,
            emotional_charge: float = 0.0):
        for b in self.beliefs:
            if self._similar(b.content, content):
                b.reinforce(tick)
                return
        self.beliefs.append(Belief(
            content=content, category=category, confidence=confidence,
            source_type=source, source_agent=source_agent, first_formed=tick,
            last_updated_tick=tick, emotional_charge=emotional_charge,
        ))
        if len(self.beliefs) > 30:
            self.beliefs.sort(key=lambda b: b.confidence, reverse=True)
            self.beliefs = self.beliefs[:30]

    def challenge(self, content: str, tick: int):
        for b in self.beliefs:
            if self._similar(b.content, content):
                b.challenge(tick)
                # Remove beliefs that have been contradicted and have low confidence
                if b.confidence < 0.15 and b.contradicting_count >= 2:
                    self.beliefs.remove(b)
                return

    def extract_from_episodes(self, recent_episodes: list) -> list[Belief]:
        """Look for patterns in recent memories and form/update beliefs."""
        new_beliefs = []
        if not recent_episodes:
            return new_beliefs

        # Count agent co-occurrences to form social beliefs
        agent_sentiment: dict[str, list[float]] = {}
        location_counts: dict[str, int] = {}
        action_outcomes: dict[str, list[bool]] = {}

        for ep in recent_episodes:
            # Track location frequency
            if hasattr(ep, "location") and ep.location:
                location_counts[ep.location] = location_counts.get(ep.location, 0) + 1

            # Track sentiments about people
            for agent_name in getattr(ep, "agents_involved", []):
                agent_sentiment.setdefault(agent_name, []).append(
                    getattr(ep, "emotional_valence", 0.0)
                )

            # Track action category outcomes
            cat = getattr(ep, "category", "")
            valence = getattr(ep, "emotional_valence", 0.0)
            if cat and cat not in ("observation", "reflection"):
                action_outcomes.setdefault(cat, []).append(valence > 0)

        tick = recent_episodes[-1].tick if hasattr(recent_episodes[-1], "tick") else 0

        # Form beliefs about people from repeated interactions
        for name, sentiments in agent_sentiment.items():
            if len(sentiments) >= 3:
                avg = sum(sentiments) / len(sentiments)
                if avg > 0.15:
                    belief_text = f"{name} is generally good to be around"
                    self.add(belief_text, "person_model", confidence=min(0.8, 0.4 + len(sentiments) * 0.05),
                             tick=tick, emotional_charge=avg * 0.5)
                    new_beliefs.append(belief_text)
                elif avg < -0.15:
                    belief_text = f"{name} tends to cause trouble or tension"
                    self.add(belief_text, "person_model", confidence=min(0.8, 0.4 + len(sentiments) * 0.05),
                             tick=tick, emotional_charge=avg * 0.5)
                    new_beliefs.append(belief_text)

        # Form beliefs about frequently visited locations
        for loc, count in location_counts.items():
            if count >= 4:
                belief_text = f"The {loc.replace('_', ' ')} is a place I find myself returning to"
                self.add(belief_text, "world_knowledge", confidence=0.6, tick=tick)
                new_beliefs.append(belief_text)

        return [Belief(content=t, category="extracted") for t in new_beliefs]

    def nightly_reflection_update(self, todays_episodes: list, existing_beliefs: list["Belief"] | None = None) -> list[str]:
        """Crystallize beliefs from today's experiences. Returns list of new/changed belief texts."""
        changes = []
        if not todays_episodes:
            return changes

        tick = todays_episodes[-1].tick if hasattr(todays_episodes[-1], "tick") else 0

        # Collect emotional summaries
        positive_events = [e for e in todays_episodes if getattr(e, "emotional_valence", 0) > 0.1]
        negative_events = [e for e in todays_episodes if getattr(e, "emotional_valence", 0) < -0.1]

        # If the day was overwhelmingly negative, form a cautious belief
        if len(negative_events) > len(positive_events) * 2 and len(negative_events) >= 3:
            text = "Things have not been going well lately"
            self.add(text, "self_belief", confidence=0.5, tick=tick, emotional_charge=-0.3)
            changes.append(text)

        # If the day was good, reinforce hope
        if len(positive_events) > len(negative_events) * 2 and len(positive_events) >= 3:
            text = "Things are looking up for me"
            self.add(text, "self_belief", confidence=0.5, tick=tick, emotional_charge=0.3)
            changes.append(text)

        # Reinforce existing beliefs that got evidence today
        for ep in todays_episodes:
            content_lower = getattr(ep, "content", "").lower()
            for b in self.beliefs:
                if any(w in content_lower for w in b.content.lower().split()[:4] if len(w) > 3):
                    valence = getattr(ep, "emotional_valence", 0)
                    if (valence > 0 and b.emotional_charge >= 0) or (valence < 0 and b.emotional_charge <= 0):
                        b.reinforce(tick)
                    else:
                        b.challenge(tick)

        # Prune beliefs with very low confidence that have been contradicted
        self.beliefs = [b for b in self.beliefs if not (b.confidence < 0.15 and b.contradicting_count >= 2)]

        # Run episode extraction too
        self.extract_from_episodes(todays_episodes)

        return changes

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
        lines = []
        for b in selected:
            suffix = ""
            if b.is_actively_questioned:
                suffix = " [questioning this]"
            elif b.confidence < 0.4:
                suffix = " [uncertain]"
            lines.append(f"- {b.content} (confidence: {b.confidence:.0%}{suffix})")
        return "Your beliefs:\n" + "\n".join(lines)

    def to_list(self) -> list[dict]:
        return [b.to_dict() for b in self.beliefs]

    def load_from_list(self, data: list[dict]):
        self.beliefs = []
        for d in data:
            self.beliefs.append(Belief(
                content=d.get("content", ""), category=d.get("category", "world_knowledge"),
                confidence=d.get("confidence", 0.5), emotional_charge=d.get("charge", 0.0),
                source_type=d.get("source", "personal_experience"),
                evidence_count=d.get("evidence_count", d.get("supporting_count", 1)),
                last_updated_tick=d.get("last_updated_tick", d.get("last_reinforced", 0)),
            ))

    @staticmethod
    def _similar(a: str, b: str) -> bool:
        a_words = set(a.lower().split())
        b_words = set(b.lower().split())
        if not a_words or not b_words:
            return False
        overlap = len(a_words & b_words)
        return overlap / min(len(a_words), len(b_words)) > 0.5
