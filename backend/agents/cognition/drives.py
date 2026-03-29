"""Drive system -- biological and psychological needs that operate below conscious decision-making."""


class DriveSystem:
    def __init__(self):
        # Biological
        self.hunger: float = 0.2
        self.rest: float = 0.2
        self.thirst: float = 0.15
        self.energy: float = 0.8  # 1 = full energy, decays toward 0
        self.health: float = 1.0  # 1 = perfect health, decays toward 0

        # Psychological
        self.social_need: float = 0.3
        self.belonging: float = 0.3  # social group pressure
        self.autonomy_need: float = 0.2
        self.competence_need: float = 0.2
        self.purpose_need: float = 0.2
        self.safety_need: float = 0.2
        self.shelter_need: float = 0.4
        self._shelter_growth_rate: float = 0.001

        self._prev_dominant: str = ""

        self._drives_meta: dict[str, dict] = {
            "hunger": {"decay_rate": 0.002, "urgency_threshold": 0.7},
            "rest": {"decay_rate": 0.0004, "urgency_threshold": 0.8},
            "thirst": {"decay_rate": 0.003, "urgency_threshold": 0.65},
            "energy": {"decay_rate": -0.001, "urgency_threshold": 0.25},  # urgency when LOW
            "health": {"decay_rate": 0.0, "urgency_threshold": 0.3},  # urgency when LOW
            "social": {"decay_rate": 0.002, "urgency_threshold": 0.7},
            "belonging": {"decay_rate": 0.001, "urgency_threshold": 0.7},
            "autonomy": {"decay_rate": 0.0006, "urgency_threshold": 0.75},
            "competence": {"decay_rate": 0.0006, "urgency_threshold": 0.7},
            "purpose": {"decay_rate": 0.0005, "urgency_threshold": 0.7},
            "safety": {"decay_rate": 0.001, "urgency_threshold": 0.8},
            "shelter": {"decay_rate": 0.001, "urgency_threshold": 0.7},
        }

    def compute_urgency(self, drive_name: str) -> float:
        meta = self._drives_meta.get(drive_name)
        if not meta:
            return 0.0
        val = self._get_drive_value(drive_name)
        threshold = meta["urgency_threshold"]
        # For energy and health, urgency is when value is LOW
        if drive_name in ("energy", "health"):
            if val > threshold:
                return 0.0
            return (threshold - val) / threshold
        if val < threshold:
            return 0.0
        return (val - threshold) / (1.0 - threshold)

    def get_most_urgent(self) -> tuple[str, float]:
        best_name, best_urgency = "", 0.0
        for name in self._drives_meta:
            u = self.compute_urgency(name)
            if u > best_urgency:
                best_urgency = u
                best_name = name
        return best_name, best_urgency

    def _get_drive_value(self, name: str) -> float:
        mapping = {
            "hunger": self.hunger, "rest": self.rest, "thirst": self.thirst,
            "energy": self.energy, "health": self.health,
            "social": self.social_need, "belonging": self.belonging,
            "autonomy": self.autonomy_need, "competence": self.competence_need,
            "purpose": self.purpose_need, "safety": self.safety_need, "shelter": self.shelter_need,
        }
        return mapping.get(name, 0.0)

    def tick_update(self, is_working: bool, is_sleeping: bool, is_alone: bool,
                    is_socializing: bool, wealth: float, daily_expense: float = 10,
                    has_home: bool = False, num_friends: int = 0):
        # Hunger
        self.hunger = min(1.0, self.hunger + 0.002 + (0.001 if is_working else 0))

        # Thirst -- rises faster than hunger
        self.thirst = min(1.0, self.thirst + 0.003 + (0.001 if is_working else 0))

        # Rest
        if is_sleeping:
            self.rest = max(0.0, self.rest - 0.005)
            self.hunger = min(1.0, self.hunger + 0.0005)
            self.energy = min(1.0, self.energy + 0.008)
        else:
            self.rest = min(1.0, self.rest + 0.0004 + (0.0008 if is_working else 0))
            self.energy = max(0.0, self.energy - 0.001 - (0.002 if is_working else 0))

        # Health -- degrades slowly when hungry/thirsty/exhausted, recovers when needs met
        damage = 0.0
        if self.hunger > 0.85:
            damage += 0.001
        if self.thirst > 0.85:
            damage += 0.0015
        if self.rest > 0.9:
            damage += 0.0005
        if damage > 0:
            self.health = max(0.0, self.health - damage)
        elif self.hunger < 0.3 and self.thirst < 0.3 and self.rest < 0.3:
            self.health = min(1.0, self.health + 0.002)

        # Social need
        if is_alone:
            self.social_need = min(1.0, self.social_need + 0.002)
        if is_socializing:
            self.social_need = max(0.0, self.social_need - 0.01)

        # Belonging -- slower than social_need, reduced by having friends
        if num_friends < 2:
            self.belonging = min(1.0, self.belonging + 0.001)
        elif num_friends >= 4:
            self.belonging = max(0.0, self.belonging - 0.002)
        if is_socializing:
            self.belonging = max(0.0, self.belonging - 0.003)

        # Safety
        if wealth < daily_expense * 3:
            self.safety_need = min(1.0, self.safety_need + 0.003)
        else:
            self.safety_need = max(0.0, self.safety_need - 0.001)

        # Competence
        if is_working:
            self.competence_need = max(0.0, self.competence_need - 0.001)
        else:
            self.competence_need = min(1.0, self.competence_need + 0.0006)

        # Shelter
        if has_home:
            self.shelter_need = max(0.0, self.shelter_need - 0.005)
        else:
            self.shelter_need = min(1.0, self.shelter_need + self._shelter_growth_rate)

    def satisfy_hunger(self):
        self.hunger = max(0.0, self.hunger - 0.6)

    def satisfy_thirst(self):
        self.thirst = max(0.0, self.thirst - 0.7)

    def satisfy_social(self):
        self.social_need = max(0.0, self.social_need - 0.2)

    def satisfy_shelter(self):
        self.shelter_need = 0.0

    def restore_energy(self, amount: float = 0.3):
        self.energy = min(1.0, self.energy + amount)

    def restore_health(self, amount: float = 0.2):
        self.health = min(1.0, self.health + amount)

    def get_dominant_drive(self) -> tuple[str, float]:
        drives = {
            "hunger": self.hunger, "rest": self.rest, "thirst": self.thirst,
            "social": self.social_need, "belonging": self.belonging,
            "autonomy": self.autonomy_need,
            "competence": self.competence_need, "purpose": self.purpose_need,
            "safety": self.safety_need, "shelter": self.shelter_need,
        }
        # Energy and health are inverted (low = bad)
        drives["energy_deprived"] = 1.0 - self.energy
        drives["health_deprived"] = 1.0 - self.health
        dominant = max(drives, key=drives.get)
        # Remap back for cleaner names
        if dominant == "energy_deprived":
            return "energy", 1.0 - self.energy
        if dominant == "health_deprived":
            return "health", 1.0 - self.health
        return dominant, drives[dominant]

    def dominant_drive_changed(self) -> bool:
        current = self.get_dominant_drive()[0]
        changed = current != self._prev_dominant
        self._prev_dominant = current
        return changed

    def should_interrupt_plan(self, can_resist: bool = False) -> tuple[bool, str]:
        resisting = can_resist and self.purpose_need > 0.7
        if self.hunger > 0.8:
            if resisting and self.hunger < 0.95:
                return False, ""
            return True, "find_food"
        if self.thirst > 0.75:
            if resisting and self.thirst < 0.9:
                return False, ""
            return True, "find_water"
        if self.rest > 0.9:
            if resisting and self.rest < 0.98:
                return False, ""
            return True, "go_sleep"
        if self.energy < 0.15:
            if resisting and self.energy > 0.05:
                return False, ""
            return True, "go_sleep"
        if self.health < 0.2:
            return True, "seek_safety"
        if self.social_need > 0.85:
            if resisting:
                return False, ""
            return True, "seek_company"
        if self.belonging > 0.85:
            if resisting:
                return False, ""
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
            "thirst": f"You're {'thirsty' if level < 0.7 else 'parched and desperate for water'}.",
            "energy": f"You're {'running low on energy' if level < 0.7 else 'completely drained'}.",
            "health": f"You feel {'a bit unwell' if level < 0.7 else 'seriously ill'}.",
            "social": f"You {'could use some company' if level < 0.7 else 'desperately need human connection'}.",
            "belonging": f"You {'feel like you do not quite fit in' if level < 0.7 else 'feel like a total outsider with no group'}.",
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
            "thirst": round(self.thirst, 2),
            "energy": round(self.energy, 2), "health": round(self.health, 2),
            "social": round(self.social_need, 2), "belonging": round(self.belonging, 2),
            "autonomy": round(self.autonomy_need, 2),
            "competence": round(self.competence_need, 2), "purpose": round(self.purpose_need, 2),
            "safety": round(self.safety_need, 2), "shelter": round(self.shelter_need, 2),
            "dominant": self.get_dominant_drive()[0],
        }

    def load_from_dict(self, d: dict):
        for k in ["hunger", "rest", "thirst", "energy", "health",
                   "social_need", "belonging", "autonomy_need", "competence_need",
                   "purpose_need", "safety_need", "shelter_need"]:
            short = k.replace("_need", "")
            if short in d:
                setattr(self, k, d[short])
            elif k in d:
                setattr(self, k, d[k])
