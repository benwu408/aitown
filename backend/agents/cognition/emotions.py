"""Deterministic emotional state engine -- 10 emotion dimensions with decay toward baseline."""


DECAY_RATES = {
    "joy": 0.05,
    "anger": 0.03,
    "sadness": 0.01,
    "anxiety": 0.015,
    "loneliness": 0.01,
    "pride": 0.04,
    "shame": 0.008,
    "gratitude": 0.03,
    "resentment": 0.005,
    "hope": 0.02,
}


class EmotionalState:
    def __init__(self, baseline_valence: float = 0.3, baseline_arousal: float = 0.4):
        self.valence: float = baseline_valence
        self.arousal: float = baseline_arousal
        self.baseline_valence = baseline_valence
        self.baseline_arousal = baseline_arousal

        self.anxiety: float = 0.1
        self.anger: float = 0.0
        self.sadness: float = 0.05
        self.joy: float = 0.2
        self.loneliness: float = 0.1
        self.pride: float = 0.1
        self.shame: float = 0.0
        self.gratitude: float = 0.05
        self.resentment: float = 0.0
        self.hope: float = 0.2

        self.suppression_level: float = 0.0
        self.resentment_target: str | None = None
        self._threshold_crossed: bool = False

    def apply_event(self, event_type: str, intensity: float = 1.0, target: str = ""):
        EVENT_EFFECTS = {
            "positive_conversation": {"valence": 0.1, "joy": 0.1, "loneliness": -0.15},
            "negative_conversation": {"valence": -0.1, "anger": 0.1, "sadness": 0.05},
            "insulted": {"valence": -0.2, "anger": 0.3, "shame": 0.1},
            "cant_afford_food": {"valence": -0.15, "anxiety": 0.2, "shame": 0.1},
            "received_help": {"valence": 0.2, "gratitude": 0.3, "hope": 0.1},
            "gossip_about_self": {"valence": -0.1, "anxiety": 0.15, "anger": 0.1},
            "goal_achieved": {"valence": 0.2, "pride": 0.3, "joy": 0.2},
            "ignored_excluded": {"valence": -0.1, "loneliness": 0.2, "sadness": 0.1},
            "witnessed_injustice": {"valence": -0.1, "anger": 0.2, "sadness": 0.1},
            "good_weather": {"valence": 0.05, "joy": 0.05},
            "failed_task": {"valence": -0.15, "shame": 0.15, "anxiety": 0.1},
            "trusted_with_secret": {"valence": 0.1, "pride": 0.1, "gratitude": 0.05},
            "promise_broken": {"valence": -0.15, "anger": 0.15, "resentment": 0.2},
            "secret_exposed": {"valence": -0.3, "shame": 0.3, "anxiety": 0.2},
            "earned_money": {"valence": 0.05, "pride": 0.05},
            "lost_money": {"valence": -0.05, "anxiety": 0.1},
            "social_interaction": {"loneliness": -0.1, "joy": 0.05},
            "alone_too_long": {"loneliness": 0.1, "sadness": 0.05},
            "shame": {"valence": -0.15, "shame": 0.25, "anxiety": 0.1},
            "anxiety": {"valence": -0.1, "anxiety": 0.2},
            "relief": {"valence": 0.1, "anxiety": -0.15, "joy": 0.05},
            # New event mappings
            "action_success": {"valence": 0.15, "pride": 0.2, "joy": 0.1, "hope": 0.05},
            "action_failure": {"valence": -0.1, "shame": 0.1, "anxiety": 0.05, "sadness": 0.05},
            "being_observed": {"anxiety": 0.08, "arousal": 0.1},
            "overheard_about_self_positive": {"valence": 0.15, "pride": 0.15, "joy": 0.1},
            "overheard_about_self_negative": {"valence": -0.2, "shame": 0.15, "anger": 0.1, "anxiety": 0.1},
            "drive_satisfied": {"valence": 0.1, "joy": 0.1, "anxiety": -0.05},
            "drive_deprived": {"valence": -0.1, "anxiety": 0.15, "sadness": 0.05},
            "hunger_satisfied": {"valence": 0.1, "joy": 0.08, "anxiety": -0.05},
            "thirst_satisfied": {"valence": 0.08, "joy": 0.05, "anxiety": -0.03},
            "rest_satisfied": {"valence": 0.1, "joy": 0.05, "hope": 0.05},
            "social_rejection": {"valence": -0.2, "loneliness": 0.25, "sadness": 0.15, "shame": 0.1},
            "social_acceptance": {"valence": 0.2, "joy": 0.15, "loneliness": -0.2, "hope": 0.1},
            "social_invitation": {"valence": 0.1, "joy": 0.1, "loneliness": -0.1},
            "compliment_received": {"valence": 0.15, "pride": 0.15, "joy": 0.1},
            "criticism_received": {"valence": -0.1, "shame": 0.1, "anger": 0.05, "sadness": 0.05},
            "helped_someone": {"valence": 0.15, "pride": 0.15, "joy": 0.1, "gratitude": 0.05},
            "betrayed": {"valence": -0.25, "anger": 0.25, "resentment": 0.3, "sadness": 0.1},
            "forgiven": {"valence": 0.15, "gratitude": 0.2, "hope": 0.1, "resentment": -0.15},
            "confrontation": {"arousal": 0.3, "anxiety": 0.15, "anger": 0.1},
            "shelter_built": {"valence": 0.2, "pride": 0.25, "joy": 0.15, "anxiety": -0.1},
            "lost_home": {"valence": -0.3, "sadness": 0.3, "anxiety": 0.25},
            "new_skill_learned": {"valence": 0.15, "pride": 0.2, "joy": 0.1, "hope": 0.05},
            "group_included": {"valence": 0.15, "joy": 0.1, "loneliness": -0.15},
            "group_excluded": {"valence": -0.15, "loneliness": 0.2, "sadness": 0.1, "resentment": 0.05},
        }

        effects = EVENT_EFFECTS.get(event_type, {})
        old_dominant = self.get_dominant_emotion()[1]

        for attr, delta in effects.items():
            if attr == "valence":
                self.valence = max(-1.0, min(1.0, self.valence + delta * intensity))
            elif attr == "arousal":
                self.arousal = max(0.0, min(1.0, self.arousal + delta * intensity))
            elif hasattr(self, attr):
                current = getattr(self, attr)
                if delta > 0:
                    setattr(self, attr, min(1.0, current + delta * intensity))
                else:
                    setattr(self, attr, max(0.0, current + delta * intensity))

        if "resentment" in effects and effects["resentment"] > 0 and target:
            self.resentment_target = target

        new_dominant = self.get_dominant_emotion()[1]
        if abs(new_dominant - old_dominant) > 0.15:
            self._threshold_crossed = True

    def decay(self, ticks: int = 1):
        for emotion, rate in DECAY_RATES.items():
            current = getattr(self, emotion)
            setattr(self, emotion, current * (1.0 - rate * ticks))

        self.valence += (self.baseline_valence - self.valence) * 0.01 * ticks
        self.arousal += (self.baseline_arousal - self.arousal) * 0.01 * ticks
        self._threshold_crossed = False

    def just_crossed_threshold(self) -> bool:
        return self._threshold_crossed

    def get_dominant_emotion(self) -> tuple[str, float]:
        emotions = {
            "anxious": self.anxiety, "angry": self.anger, "sad": self.sadness,
            "happy": self.joy, "lonely": self.loneliness, "proud": self.pride,
            "ashamed": self.shame, "grateful": self.gratitude,
            "resentful": self.resentment, "hopeful": self.hope,
        }
        dominant = max(emotions, key=emotions.get)
        return dominant, emotions[dominant]

    def get_prompt_description(self) -> str:
        parts = []
        if self.anxiety > 0.3:
            parts.append(f"{'nagging' if self.anxiety < 0.6 else 'gripping'} anxiety")
        if self.loneliness > 0.4:
            parts.append(f"{'undercurrent' if self.loneliness < 0.7 else 'aching'} loneliness")
        if self.anger > 0.3:
            parts.append(f"{'irritated' if self.anger < 0.6 else 'furious'}")
        if self.joy > 0.3:
            parts.append(f"{'content' if self.joy < 0.6 else 'genuinely happy'}")
        if self.sadness > 0.3:
            parts.append(f"{'melancholy' if self.sadness < 0.6 else 'deep sadness'}")
        if self.resentment > 0.3:
            parts.append(f"resentment{' toward ' + self.resentment_target if self.resentment_target else ''}")
        if self.pride > 0.4:
            parts.append(f"{'quiet pride' if self.pride < 0.7 else 'strong pride'}")
        if self.shame > 0.3:
            parts.append(f"{'lingering' if self.shame < 0.6 else 'heavy'} shame")
        if self.gratitude > 0.3:
            parts.append("gratitude")
        if self.hope > 0.4:
            parts.append(f"{'cautious' if self.hope < 0.7 else 'bright'} hope")

        if not parts:
            if self.valence > 0.1:
                return "You're feeling fairly calm and okay."
            elif self.valence < -0.1:
                return "You feel a bit low, but nothing specific is weighing on you."
            else:
                return "You're feeling neutral -- neither good nor bad."

        return "You feel: " + ", ".join(parts) + "."

    def to_dict(self) -> dict:
        return {
            "valence": round(self.valence, 2),
            "arousal": round(self.arousal, 2),
            "dominant": self.get_dominant_emotion()[0],
            "dominantIntensity": round(self.get_dominant_emotion()[1], 2),
            "anxiety": round(self.anxiety, 2),
            "anger": round(self.anger, 2),
            "sadness": round(self.sadness, 2),
            "joy": round(self.joy, 2),
            "loneliness": round(self.loneliness, 2),
            "pride": round(self.pride, 2),
            "shame": round(self.shame, 2),
            "gratitude": round(self.gratitude, 2),
            "resentment": round(self.resentment, 2),
            "hope": round(self.hope, 2),
        }

    def load_from_dict(self, d: dict):
        for k, v in d.items():
            if hasattr(self, k) and isinstance(v, (int, float)):
                setattr(self, k, v)
