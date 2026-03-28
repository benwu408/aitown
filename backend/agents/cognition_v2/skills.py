"""Skill discovery memory — tracks what the agent has tried and what they're good at."""


class SkillMemory:
    def __init__(self):
        self.activities: dict[str, dict] = {}

    def record_attempt(self, activity: str, success: bool, enjoyment: float = 0.5):
        if activity not in self.activities:
            self.activities[activity] = {"attempts": 0, "successes": 0, "enjoyment": 0.0, "skill_level": 0.0}
        entry = self.activities[activity]
        entry["attempts"] += 1
        if success:
            entry["successes"] += 1
        entry["enjoyment"] = entry["enjoyment"] * 0.7 + enjoyment * 0.3
        entry["skill_level"] = min(1.0, entry["successes"] / max(entry["attempts"], 1) * 0.5 + entry["attempts"] * 0.02)

    def has_skill(self, name: str) -> bool:
        return name in self.activities and self.activities[name]["skill_level"] > 0.2

    def get_best_skills(self, n: int = 3) -> list[tuple[str, dict]]:
        return sorted(self.activities.items(), key=lambda x: x[1]["skill_level"], reverse=True)[:n]

    def get_most_enjoyed(self, n: int = 3) -> list[tuple[str, dict]]:
        return sorted(self.activities.items(), key=lambda x: x[1]["enjoyment"], reverse=True)[:n]

    def get_dominant_activity(self) -> str | None:
        if not self.activities:
            return None
        best = max(self.activities.items(), key=lambda x: x[1]["attempts"])
        return best[0] if best[1]["attempts"] >= 5 else None

    def get_prompt_summary(self) -> str:
        if not self.activities:
            return "No skills discovered yet."
        top = self.get_best_skills(3)
        return "Skills: " + ", ".join(f"{name} ({d['skill_level']:.0%})" for name, d in top)

    def to_dict(self) -> dict:
        return dict(self.activities)

    def load_from_dict(self, d: dict):
        self.activities = d
