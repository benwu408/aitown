"""Skill discovery memory -- tracks what the agent has tried and what they're good at."""


class SkillMemory:
    def __init__(self):
        self.activities: dict[str, dict] = {}

    def _ensure_fields(self, entry: dict):
        """Ensure all expected fields exist on a skill entry."""
        entry.setdefault("attempts", 0)
        entry.setdefault("successes", 0)
        entry.setdefault("failures", 0)
        entry.setdefault("enjoyment", 0.0)
        entry.setdefault("skill_level", 0.0)
        entry.setdefault("difficulty_estimate", 0.5)
        entry.setdefault("last_practiced_tick", 0)
        entry.setdefault("practice_streak", 0)

    def record_attempt(self, activity: str, success: bool, enjoyment: float = 0.5,
                       tick: int = 0):
        if activity not in self.activities:
            self.activities[activity] = {}
        entry = self.activities[activity]
        self._ensure_fields(entry)
        entry["attempts"] += 1
        if success:
            entry["successes"] += 1
        else:
            entry["failures"] += 1
        entry["enjoyment"] = entry["enjoyment"] * 0.7 + enjoyment * 0.3
        entry["skill_level"] = min(1.0, entry["successes"] / max(entry["attempts"], 1) * 0.5 + entry["attempts"] * 0.02)

        # Track practice streak
        if entry["last_practiced_tick"] > 0 and tick > 0:
            gap = tick - entry["last_practiced_tick"]
            if gap < 400:  # practiced recently
                entry["practice_streak"] += 1
            else:
                entry["practice_streak"] = 1
        else:
            entry["practice_streak"] = 1
        entry["last_practiced_tick"] = tick

    def record_success(self, skill: str, difficulty: float = 0.5, tick: int = 0):
        if skill not in self.activities:
            self.activities[skill] = {}
        entry = self.activities[skill]
        self._ensure_fields(entry)
        entry["attempts"] += 1
        entry["successes"] += 1
        # Skill grows more from harder tasks
        bonus = difficulty * 0.03
        entry["skill_level"] = min(1.0, entry["skill_level"] + 0.02 + bonus)
        entry["difficulty_estimate"] = entry["difficulty_estimate"] * 0.8 + difficulty * 0.2
        entry["enjoyment"] = min(1.0, entry["enjoyment"] + 0.05)
        if entry["last_practiced_tick"] > 0 and tick > 0 and (tick - entry["last_practiced_tick"]) < 400:
            entry["practice_streak"] += 1
        else:
            entry["practice_streak"] = 1
        entry["last_practiced_tick"] = tick

    def record_failure(self, skill: str, tick: int = 0):
        if skill not in self.activities:
            self.activities[skill] = {}
        entry = self.activities[skill]
        self._ensure_fields(entry)
        entry["attempts"] += 1
        entry["failures"] += 1
        entry["skill_level"] = max(0.0, entry["skill_level"] - 0.005)
        entry["enjoyment"] = max(0.0, entry["enjoyment"] - 0.03)
        entry["practice_streak"] = 0
        entry["last_practiced_tick"] = tick

    def get_skill_level(self, skill: str) -> float:
        entry = self.activities.get(skill)
        if not entry:
            return 0.0
        self._ensure_fields(entry)
        return entry["skill_level"]

    def has_skill(self, name: str) -> bool:
        return name in self.activities and self.get_skill_level(name) > 0.2

    def get_best_skills(self, n: int = 3) -> list[tuple[str, dict]]:
        for entry in self.activities.values():
            self._ensure_fields(entry)
        return sorted(self.activities.items(), key=lambda x: x[1]["skill_level"], reverse=True)[:n]

    def get_most_enjoyed(self, n: int = 3) -> list[tuple[str, dict]]:
        for entry in self.activities.values():
            self._ensure_fields(entry)
        return sorted(self.activities.items(), key=lambda x: x[1]["enjoyment"], reverse=True)[:n]

    def get_dominant_activity(self, last_n_days: int = 0) -> str | dict | None:
        """Return most-practiced activity. If last_n_days > 0, return a dict with details."""
        if not self.activities:
            return None
        for entry in self.activities.values():
            self._ensure_fields(entry)
        best = max(self.activities.items(), key=lambda x: x[1]["attempts"])
        if best[1]["attempts"] < 5:
            return None
        if last_n_days > 0:
            return {
                "activity": best[0],
                "attempts": best[1]["attempts"],
                "skill_level": best[1]["skill_level"],
                "enjoyment": best[1]["enjoyment"],
                "streak": best[1]["practice_streak"],
            }
        return best[0]

    def full_summary(self) -> str:
        if not self.activities:
            return "No skills developed yet."
        lines = []
        for name, entry in sorted(self.activities.items(), key=lambda x: x[1].get("skill_level", 0), reverse=True):
            self._ensure_fields(entry)
            success_rate = entry["successes"] / max(entry["attempts"], 1)
            enjoy_str = "loves" if entry["enjoyment"] > 0.7 else "likes" if entry["enjoyment"] > 0.4 else "tolerates"
            lines.append(
                f"- {name}: level {entry['skill_level']:.0%}, "
                f"{entry['attempts']} attempts ({success_rate:.0%} success), "
                f"{enjoy_str} it, streak {entry['practice_streak']}"
            )
        return "\n".join(lines[:8])

    def get_prompt_summary(self) -> str:
        if not self.activities:
            return "No skills discovered yet."
        top = self.get_best_skills(3)
        return "Skills: " + ", ".join(f"{name} ({d['skill_level']:.0%})" for name, d in top)

    def get_enjoyment_summary(self) -> str:
        if not self.activities:
            return "Haven't discovered what I enjoy yet."
        enjoyed = [item for item in self.get_most_enjoyed(2) if item[1]["attempts"] >= 3]
        if not enjoyed:
            return "Haven't discovered what I enjoy yet."
        return ", ".join(f"{name}" for name, d in enjoyed)

    def to_dict(self) -> dict:
        for entry in self.activities.values():
            self._ensure_fields(entry)
        return dict(self.activities)

    def load_from_dict(self, d: dict):
        self.activities = d
        for entry in self.activities.values():
            self._ensure_fields(entry)
