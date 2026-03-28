"""Identity system — the agent's evolving sense of self in the community."""


class Identity:
    def __init__(self):
        self.self_narrative: str = ""              # "I'm a builder. I came here to start over."
        self.role_in_community: str = ""           # Emerges: "the farmer", "the peacekeeper"
        self.sense_of_belonging: float = 0.0       # 0 (outsider) to 1 (this is home)
        self.sense_of_purpose: float = 0.0         # 0 (lost) to 1 (know why I'm here)
        self.demonstrated_values: dict = {}        # {"helping_others": 0.7, "self_interest": 0.3}
        self.perceived_reputation: str = ""        # "People see me as reliable but quiet"
        self.reputation_anxiety: float = 0.0       # How much I worry about what others think
        self.satisfaction_with_role: float = 0.5
        self.satisfaction_with_relationships: float = 0.5
        self.satisfaction_with_community: float = 0.5
        self.life_satisfaction: float = 0.5

    def update_belonging(self, has_home: bool, num_friends: int, days_in_settlement: int):
        """Belonging grows with time, shelter, and friendships."""
        target = 0.0
        if has_home:
            target += 0.3
        target += min(0.3, num_friends * 0.1)
        target += min(0.3, days_in_settlement * 0.03)
        self.sense_of_belonging += (target - self.sense_of_belonging) * 0.05

    def update_purpose(self, has_role: bool, has_goals: bool, competence_satisfaction: float):
        """Purpose grows when agent has a role and is good at it."""
        target = 0.0
        if has_role:
            target += 0.4
        if has_goals:
            target += 0.3
        target += competence_satisfaction * 0.3
        self.sense_of_purpose += (target - self.sense_of_purpose) * 0.05

    def get_prompt_context(self) -> str:
        parts = []
        if self.self_narrative:
            parts.append(f"Your self-narrative: {self.self_narrative}")
        if self.role_in_community:
            parts.append(f"Your role here: {self.role_in_community}")

        if self.sense_of_belonging < 0.3:
            parts.append("You still feel like an outsider here.")
        elif self.sense_of_belonging > 0.7:
            parts.append("This place is starting to feel like home.")

        if self.sense_of_purpose < 0.3:
            parts.append("You're not sure what your purpose is yet.")
        elif self.sense_of_purpose > 0.7:
            parts.append("You know your place and your purpose here.")

        if self.perceived_reputation:
            parts.append(f"You think others see you as: {self.perceived_reputation}")

        return "\n".join(parts) if parts else "You're still figuring out who you are in this place."

    def to_dict(self) -> dict:
        return {
            "narrative": self.self_narrative,
            "role": self.role_in_community,
            "belonging": round(self.sense_of_belonging, 2),
            "purpose": round(self.sense_of_purpose, 2),
            "values": self.demonstrated_values,
            "reputation": self.perceived_reputation,
            "satisfaction": round(self.life_satisfaction, 2),
        }

    def load_from_dict(self, d: dict):
        self.self_narrative = d.get("narrative", "")
        self.role_in_community = d.get("role", "")
        self.sense_of_belonging = d.get("belonging", 0.0)
        self.sense_of_purpose = d.get("purpose", 0.0)
        self.demonstrated_values = d.get("values", {})
        self.perceived_reputation = d.get("reputation", "")
        self.life_satisfaction = d.get("satisfaction", 0.5)
