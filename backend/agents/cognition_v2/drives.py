"""Drive system — biological and psychological needs that operate below conscious decision-making."""


class DriveSystem:
    def __init__(self):
        # Biological
        self.hunger: float = 0.2
        self.rest: float = 0.2

        # Psychological
        self.social_need: float = 0.3
        self.autonomy_need: float = 0.2
        self.competence_need: float = 0.2
        self.purpose_need: float = 0.2
        self.safety_need: float = 0.2
        self.shelter_need: float = 0.4  # Starts high — no home yet

        self._prev_dominant: str = ""

    def tick_update(self, is_working: bool, is_sleeping: bool, is_alone: bool,
                    is_socializing: bool, wealth: float, daily_expense: float = 10,
                    has_home: bool = False):
        """Update drives each tick based on current state."""
        # Hunger — increases constantly, faster when working
        self.hunger = min(1.0, self.hunger + 0.002 + (0.001 if is_working else 0))

        # Rest — increases during activity, decreases during sleep
        if is_sleeping:
            self.rest = max(0.0, self.rest - 0.01)
            self.hunger = min(1.0, self.hunger + 0.0005)
        else:
            self.rest = min(1.0, self.rest + 0.001 + (0.002 if is_working else 0))

        # Social need — increases when alone
        if is_alone:
            self.social_need = min(1.0, self.social_need + 0.002)
        if is_socializing:
            self.social_need = max(0.0, self.social_need - 0.01)

        # Safety — scales with financial insecurity
        if wealth < daily_expense * 3:
            self.safety_need = min(1.0, self.safety_need + 0.003)
        else:
            self.safety_need = max(0.0, self.safety_need - 0.001)

        # Competence — decreases when idle too long
        if is_working:
            self.competence_need = max(0.0, self.competence_need - 0.001)
        else:
            self.competence_need = min(1.0, self.competence_need + 0.0006)

        # Shelter — rises when homeless, drops when sheltered
        if has_home:
            self.shelter_need = max(0.0, self.shelter_need - 0.005)
        else:
            self.shelter_need = min(1.0, self.shelter_need + 0.001)

    def satisfy_hunger(self):
        self.hunger = max(0.0, self.hunger - 0.6)

    def satisfy_social(self):
        self.social_need = max(0.0, self.social_need - 0.2)

    def satisfy_shelter(self):
        self.shelter_need = 0.0

    def get_dominant_drive(self) -> tuple[str, float]:
        drives = {
            "hunger": self.hunger, "rest": self.rest,
            "social": self.social_need, "autonomy": self.autonomy_need,
            "competence": self.competence_need, "purpose": self.purpose_need,
            "safety": self.safety_need, "shelter": self.shelter_need,
        }
        dominant = max(drives, key=drives.get)
        return dominant, drives[dominant]

    def dominant_drive_changed(self) -> bool:
        current = self.get_dominant_drive()[0]
        changed = current != self._prev_dominant
        self._prev_dominant = current
        return changed

    def should_interrupt_plan(self) -> tuple[bool, str]:
        """Drives above critical thresholds override conscious plans."""
        if self.hunger > 0.8:
            return True, "find_food"
        if self.rest > 0.9:
            return True, "go_sleep"
        if self.social_need > 0.85:
            return True, "seek_company"
        if self.safety_need > 0.9:
            return True, "seek_safety"
        if self.shelter_need > 0.8:
            return True, "build_shelter"
        return False, ""

    def get_prompt_description(self) -> str:
        dominant, level = self.get_dominant_drive()
        if level < 0.3:
            return "Your basic needs are mostly met."
        descs = {
            "hunger": f"You're {'hungry' if level < 0.7 else 'starving'}.",
            "rest": f"You're {'tired' if level < 0.7 else 'exhausted'}.",
            "social": f"You {'could use some company' if level < 0.7 else 'desperately need human connection'}.",
            "autonomy": f"You feel {'a bit constrained' if level < 0.7 else 'trapped and powerless'}.",
            "competence": f"You feel {'a bit useless' if level < 0.7 else 'like you cannot do anything right'}.",
            "purpose": f"You are {'questioning what it is all for' if level < 0.7 else 'feeling completely purposeless'}.",
            "safety": f"You feel {'financially uneasy' if level < 0.7 else 'deeply insecure about your future'}.",
            "shelter": f"You {'want a proper shelter' if level < 0.7 else 'desperately need a place to call home'}.",
        }
        return descs.get(dominant, "")

    def to_dict(self) -> dict:
        return {
            "hunger": round(self.hunger, 2), "rest": round(self.rest, 2),
            "social": round(self.social_need, 2), "autonomy": round(self.autonomy_need, 2),
            "competence": round(self.competence_need, 2), "purpose": round(self.purpose_need, 2),
            "safety": round(self.safety_need, 2), "shelter": round(self.shelter_need, 2),
            "dominant": self.get_dominant_drive()[0],
        }

    def load_from_dict(self, d: dict):
        for k in ["hunger", "rest", "social_need", "autonomy_need", "competence_need",
                   "purpose_need", "safety_need", "shelter_need"]:
            short = k.replace("_need", "")
            if short in d:
                setattr(self, k, d[short])
            elif k in d:
                setattr(self, k, d[k])
