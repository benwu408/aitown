"""Identity system -- the agent's evolving sense of self in the community."""


class Identity:
    def __init__(self):
        self.self_narrative: str = ""
        self.role_in_community: str = ""
        self.sense_of_belonging: float = 0.0
        self.sense_of_purpose: float = 0.0
        self.demonstrated_values: dict = {}
        self.perceived_reputation: str = ""
        self.reputation_anxiety: float = 0.0
        self.satisfaction_with_role: float = 0.5
        self.satisfaction_with_relationships: float = 0.5
        self.satisfaction_with_community: float = 0.5
        self.life_satisfaction: float = 0.5

        self.identity_tensions: list[dict] = []
        self.long_arc_goals: list[dict] = []

    def update_belonging(self, has_home: bool, num_friends: int, days_in_settlement: int):
        target = 0.0
        if has_home:
            target += 0.3
        target += min(0.3, num_friends * 0.1)
        target += min(0.3, days_in_settlement * 0.03)
        self.sense_of_belonging += (target - self.sense_of_belonging) * 0.05

    def update_purpose(self, has_role: bool, has_goals: bool, competence_satisfaction: float):
        target = 0.0
        if has_role:
            target += 0.4
        if has_goals:
            target += 0.3
        target += competence_satisfaction * 0.3
        self.sense_of_purpose += (target - self.sense_of_purpose) * 0.05

    def detect_tensions(self, beliefs: list, relationships: dict, recent_episodes: list) -> list[dict]:
        """Find mismatches between self-concept and reality."""
        self.identity_tensions = []

        # Tension: I think I'm helpful but nobody asks me for help
        self_beliefs = [b for b in beliefs if getattr(b, "category", "") == "self_belief"]
        for b in self_beliefs:
            content_lower = b.content.lower()
            # "I value helping" but no recent episodes of actually helping
            if "help" in content_lower or "kind" in content_lower:
                helped_recently = any(
                    "help" in getattr(e, "content", "").lower() and getattr(e, "my_role", "") == "caused"
                    for e in recent_episodes[-20:]
                )
                if not helped_recently:
                    self.identity_tensions.append({
                        "type": "value_action_gap",
                        "belief": b.content,
                        "reality": "I haven't actually helped anyone recently",
                        "severity": 0.5,
                    })

        # Tension: I see myself as a leader but nobody follows
        if self.role_in_community and "lead" in self.role_in_community.lower():
            follower_count = sum(1 for r in relationships.values() if r.get("trust", 0) > 0.6)
            if follower_count < 2:
                self.identity_tensions.append({
                    "type": "role_reality_gap",
                    "belief": f"I see myself as {self.role_in_community}",
                    "reality": "Few people trust me enough to follow my lead",
                    "severity": 0.6,
                })

        # Tension: Low belonging but narrative says "this is home"
        if self.sense_of_belonging < 0.3 and "home" in self.self_narrative.lower():
            self.identity_tensions.append({
                "type": "narrative_feeling_gap",
                "belief": "I tell myself this is home",
                "reality": "I still feel like an outsider",
                "severity": 0.4,
            })

        # Tension: High purpose but low satisfaction
        if self.sense_of_purpose > 0.6 and self.satisfaction_with_role < 0.3:
            self.identity_tensions.append({
                "type": "purpose_satisfaction_gap",
                "belief": "I know what I should be doing",
                "reality": "But I'm not satisfied with how it's going",
                "severity": 0.5,
            })

        # Tension: Negative reputation doesn't match self-image
        if self.perceived_reputation:
            neg_words = ["unreliable", "selfish", "lazy", "mean", "dishonest"]
            if any(w in self.perceived_reputation.lower() for w in neg_words):
                pos_self_beliefs = [b for b in self_beliefs if getattr(b, "emotional_charge", 0) > 0]
                if pos_self_beliefs:
                    self.identity_tensions.append({
                        "type": "reputation_self_gap",
                        "belief": "I believe I'm a good person",
                        "reality": f"Others see me as {self.perceived_reputation}",
                        "severity": 0.7,
                    })

        self.identity_tensions = self.identity_tensions[:5]
        return self.identity_tensions

    def generate_goals_from_tensions(self) -> list[dict]:
        """Produce long-arc goals from identity conflicts."""
        self.long_arc_goals = []
        for tension in self.identity_tensions:
            t_type = tension.get("type", "")
            severity = tension.get("severity", 0.5)

            if t_type == "value_action_gap":
                self.long_arc_goals.append({
                    "text": f"Actually live up to my values: {tension['belief']}",
                    "source": "identity_tension",
                    "priority": severity,
                    "category": "self_improvement",
                })
            elif t_type == "role_reality_gap":
                self.long_arc_goals.append({
                    "text": "Earn the trust and respect of others to fulfill my role",
                    "source": "identity_tension",
                    "priority": severity,
                    "category": "social",
                })
            elif t_type == "narrative_feeling_gap":
                self.long_arc_goals.append({
                    "text": "Build real connections so this place truly feels like home",
                    "source": "identity_tension",
                    "priority": severity,
                    "category": "belonging",
                })
            elif t_type == "purpose_satisfaction_gap":
                self.long_arc_goals.append({
                    "text": "Find a way to make my work more fulfilling",
                    "source": "identity_tension",
                    "priority": severity,
                    "category": "purpose",
                })
            elif t_type == "reputation_self_gap":
                self.long_arc_goals.append({
                    "text": "Show people who I really am through my actions",
                    "source": "identity_tension",
                    "priority": severity,
                    "category": "reputation",
                })

        self.long_arc_goals = self.long_arc_goals[:4]
        return self.long_arc_goals

    def update_self_narrative(self, recent_episodes: list, beliefs: list) -> str:
        """Evolve the agent's self-story based on recent experience and beliefs."""
        parts = []

        # Core role
        if self.role_in_community:
            parts.append(f"I'm {self.role_in_community}.")

        # Self-beliefs that are high confidence
        strong_beliefs = [b for b in beliefs
                          if getattr(b, "category", "") == "self_belief"
                          and getattr(b, "confidence", 0) > 0.6]
        if strong_beliefs:
            parts.append(strong_beliefs[0].content)

        # Recent significant event
        significant = [e for e in recent_episodes[-10:]
                       if getattr(e, "emotional_intensity", 0) > 0.5]
        if significant:
            parts.append(f"Recently: {significant[-1].content[:80]}")

        # Tensions
        if self.identity_tensions:
            tension = self.identity_tensions[0]
            parts.append(f"What troubles me: {tension.get('reality', '')}")

        # Belonging
        if self.sense_of_belonging > 0.6:
            parts.append("This place is becoming home.")
        elif self.sense_of_belonging < 0.25:
            parts.append("I'm still finding my place here.")

        new_narrative = " ".join(parts[:4]).strip()
        if new_narrative:
            self.self_narrative = new_narrative
        return self.self_narrative

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

        if self.identity_tensions:
            t = self.identity_tensions[0]
            parts.append(f"An inner conflict: {t.get('belief', '')} vs {t.get('reality', '')}")

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
            "tensions": self.identity_tensions,
            "long_arc_goals": self.long_arc_goals,
        }

    def load_from_dict(self, d: dict):
        self.self_narrative = d.get("narrative", "")
        self.role_in_community = d.get("role", "")
        self.sense_of_belonging = d.get("belonging", 0.0)
        self.sense_of_purpose = d.get("purpose", 0.0)
        self.demonstrated_values = d.get("values", {})
        self.perceived_reputation = d.get("reputation", "")
        self.life_satisfaction = d.get("satisfaction", 0.5)
        self.identity_tensions = d.get("tensions", [])
        self.long_arc_goals = d.get("long_arc_goals", [])
