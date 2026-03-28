"""Mental models — each agent's theory of mind about other agents."""

from dataclasses import dataclass, field


@dataclass
class MentalModel:
    target_name: str
    perceived_personality: str = "I don't know them well yet."
    perceived_motivations: list[str] = field(default_factory=list)
    perceived_emotional_state: str = "seems fine"
    perceived_struggles: list[str] = field(default_factory=list)

    how_they_handle_stress: str = "I'm not sure"
    how_they_respond_to_kindness: str = "seems to appreciate it"
    what_makes_them_angry: str = "I don't know yet"
    what_makes_them_happy: str = "I don't know yet"

    # Deeper theory of mind
    perceived_values: list[str] = field(default_factory=list)
    perceived_fears: list[str] = field(default_factory=list)
    what_motivates_them: str = ""
    what_triggers_them: str = ""
    what_i_think_they_think_of_me: str = ""
    suspected_goals: list[str] = field(default_factory=list)
    suspected_secrets: list[str] = field(default_factory=list)

    trust: float = 0.5
    comfort_level: float = 0.3
    predictability: float = 0.3
    relationship_trajectory: str = "new"  # getting_closer, drifting_apart, stable, tense
    unresolved_issues: list[str] = field(default_factory=list)

    last_updated: int = 0

    def is_stale(self, current_tick: int) -> bool:
        return (current_tick - self.last_updated) > 500

    def get_prompt_context(self) -> str:
        parts = [f"Your understanding of {self.target_name}:"]
        parts.append(f"  Personality: {self.perceived_personality}")
        if self.perceived_struggles:
            parts.append(f"  Struggles: {', '.join(self.perceived_struggles[:2])}")
        parts.append(f"  How they handle stress: {self.how_they_handle_stress}")
        parts.append(f"  How they respond to kindness: {self.how_they_respond_to_kindness}")
        parts.append(f"  Trust: {self.trust:.0%} | Comfort: {self.comfort_level:.0%}")
        if self.unresolved_issues:
            parts.append(f"  Unresolved between you: {', '.join(self.unresolved_issues[:2])}")
        parts.append(f"  Trajectory: {self.relationship_trajectory}")
        return "\n".join(parts)

    def to_dict(self) -> dict:
        return {
            "target": self.target_name,
            "personality": self.perceived_personality,
            "motivations": self.perceived_motivations,
            "emotional_state": self.perceived_emotional_state,
            "struggles": self.perceived_struggles,
            "stress_response": self.how_they_handle_stress,
            "kindness_response": self.how_they_respond_to_kindness,
            "trust": round(self.trust, 2),
            "comfort": round(self.comfort_level, 2),
            "trajectory": self.relationship_trajectory,
            "unresolved": self.unresolved_issues,
        }

    @staticmethod
    def from_dict(d: dict) -> "MentalModel":
        return MentalModel(
            target_name=d.get("target", ""),
            perceived_personality=d.get("personality", ""),
            perceived_motivations=d.get("motivations", []),
            perceived_emotional_state=d.get("emotional_state", ""),
            perceived_struggles=d.get("struggles", []),
            how_they_handle_stress=d.get("stress_response", ""),
            how_they_respond_to_kindness=d.get("kindness_response", ""),
            trust=d.get("trust", 0.5),
            comfort_level=d.get("comfort", 0.3),
            relationship_trajectory=d.get("trajectory", "new"),
            unresolved_issues=d.get("unresolved", []),
        )


class MentalModelSystem:
    def __init__(self):
        self.models: dict[str, MentalModel] = {}

    def get_or_create(self, name: str) -> MentalModel:
        if name not in self.models:
            self.models[name] = MentalModel(target_name=name)
        return self.models[name]

    def update_from_interaction(self, name: str, tick: int, perception: str = "",
                                trust_delta: float = 0, comfort_delta: float = 0):
        model = self.get_or_create(name)
        model.last_updated = tick
        if trust_delta:
            model.trust = max(0.0, min(1.0, model.trust + trust_delta))
        if comfort_delta:
            model.comfort_level = max(0.0, min(1.0, model.comfort_level + comfort_delta))
        if perception:
            model.perceived_personality = perception

    def get_prompt_for(self, name: str) -> str:
        if name in self.models:
            return self.models[name].get_prompt_context()
        return f"You don't know {name} very well."

    def to_dict(self) -> dict:
        return {name: model.to_dict() for name, model in self.models.items()}

    def load_from_dict(self, data: dict):
        self.models = {}
        for name, d in data.items():
            self.models[name] = MentalModel.from_dict(d)
