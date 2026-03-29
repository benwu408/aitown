"""Mental models -- each agent's theory of mind about other agents."""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("agentica.mental_models")

SYNTHESIS_PROMPT = """You just interacted with {other_name}. Here's what happened:
{interaction_summary}

Your previous understanding of {other_name}:
- Personality: {prev_personality}
- Trust level: {prev_trust:.0%}
- Reliability: {prev_reliability:.0%}
- Emotional safety: {prev_emotional_safety:.0%}
- How they handle stress: {prev_stress_response}
- Relationship trajectory: {prev_trajectory}

Based on this interaction, update your mental model. Return JSON:
{{
  "personality": "updated personality description (1-2 sentences)",
  "what_they_think_of_me": "how you think they currently see you",
  "trust_delta": 0.0,
  "comfort_delta": 0.0,
  "reliability_delta": 0.0,
  "emotional_safety_delta": 0.0,
  "gut_feeling_direction": "warmer/colder/unchanged",
  "stress_response": "updated or same",
  "trajectory": "getting_closer|drifting_apart|stable|tense",
  "predicted_behavior": "what you think they'll do next in a similar situation",
  "new_insight": "something you learned about them, or null",
  "suspected_goals": ["what they seem to want"],
  "perceived_values": ["values you think matter to them"],
  "perceived_fears": ["fears you think they have"],
  "unresolved_issue": "new unresolved issue or null"
}}"""


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

    perceived_values: list[str] = field(default_factory=list)
    perceived_fears: list[str] = field(default_factory=list)
    what_motivates_them: str = ""
    what_triggers_them: str = ""
    what_i_think_they_think_of_me: str = ""
    suspected_goals: list[str] = field(default_factory=list)
    suspected_secrets: list[str] = field(default_factory=list)
    predicted_behaviors: list[str] = field(default_factory=list)

    trust: float = 0.5
    comfort_level: float = 0.3
    predictability: float = 0.3
    reliability: float = 0.5
    generosity: float = 0.5
    emotional_safety: float = 0.5
    gut_feeling: float = 0.0
    leadership_influence: float = 0.0
    reciprocity_balance: float = 0.0
    alliance_lean: float = 0.0
    competence_by_domain: dict[str, float] = field(default_factory=dict)
    relationship_trajectory: str = "new"
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
        parts.append(
            f"  Trust: {self.trust:.0%} | Reliability: {self.reliability:.0%} | Emotional safety: {self.emotional_safety:.0%}"
        )
        parts.append(f"  Gut feeling around them: {self.gut_feeling:+.2f}")
        if self.what_i_think_they_think_of_me:
            parts.append(f"  You think they see you as: {self.what_i_think_they_think_of_me}")
        if self.unresolved_issues:
            parts.append(f"  Unresolved between you: {', '.join(self.unresolved_issues[:2])}")
        if self.predicted_behaviors:
            parts.append(f"  You expect them to: {self.predicted_behaviors[-1]}")
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
            "what_they_think_of_me": self.what_i_think_they_think_of_me,
            "values": self.perceived_values,
            "fears": self.perceived_fears,
            "suspected_goals": self.suspected_goals,
            "predicted_behaviors": self.predicted_behaviors,
            "trust": round(self.trust, 2),
            "comfort": round(self.comfort_level, 2),
            "reliability": round(self.reliability, 2),
            "generosity": round(self.generosity, 2),
            "emotional_safety": round(self.emotional_safety, 2),
            "gut_feeling": round(self.gut_feeling, 2),
            "leadership_influence": round(self.leadership_influence, 2),
            "reciprocity_balance": round(self.reciprocity_balance, 2),
            "alliance_lean": round(self.alliance_lean, 2),
            "competence_by_domain": self.competence_by_domain,
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
            perceived_values=d.get("values", []),
            perceived_fears=d.get("fears", []),
            what_i_think_they_think_of_me=d.get("what_they_think_of_me", ""),
            suspected_goals=d.get("suspected_goals", []),
            predicted_behaviors=d.get("predicted_behaviors", []),
            trust=d.get("trust", 0.5),
            comfort_level=d.get("comfort", 0.3),
            reliability=d.get("reliability", 0.5),
            generosity=d.get("generosity", 0.5),
            emotional_safety=d.get("emotional_safety", 0.5),
            gut_feeling=d.get("gut_feeling", 0.0),
            leadership_influence=d.get("leadership_influence", 0.0),
            reciprocity_balance=d.get("reciprocity_balance", 0.0),
            alliance_lean=d.get("alliance_lean", 0.0),
            competence_by_domain=d.get("competence_by_domain", {}),
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
                                trust_delta: float = 0, comfort_delta: float = 0,
                                reliability_delta: float = 0, generosity_delta: float = 0,
                                emotional_safety_delta: float = 0, alliance_delta: float = 0,
                                leadership_delta: float = 0, domain: str = "", competence_delta: float = 0,
                                gut_feeling_delta: float = 0, perceived_by_me: str = ""):
        model = self.get_or_create(name)
        model.last_updated = tick
        if trust_delta:
            model.trust = max(0.0, min(1.0, model.trust + trust_delta))
        if comfort_delta:
            model.comfort_level = max(0.0, min(1.0, model.comfort_level + comfort_delta))
        if reliability_delta:
            model.reliability = max(0.0, min(1.0, model.reliability + reliability_delta))
        if generosity_delta:
            model.generosity = max(0.0, min(1.0, model.generosity + generosity_delta))
        if emotional_safety_delta:
            model.emotional_safety = max(0.0, min(1.0, model.emotional_safety + emotional_safety_delta))
        if gut_feeling_delta:
            model.gut_feeling = max(-1.0, min(1.0, model.gut_feeling + gut_feeling_delta))
        if alliance_delta:
            model.alliance_lean = max(-1.0, min(1.0, model.alliance_lean + alliance_delta))
        if leadership_delta:
            model.leadership_influence = max(0.0, min(1.0, model.leadership_influence + leadership_delta))
        if domain:
            current = model.competence_by_domain.get(domain, 0.3)
            model.competence_by_domain[domain] = max(0.0, min(1.0, current + competence_delta))
        if perception:
            model.perceived_personality = perception
        if perceived_by_me:
            model.what_i_think_they_think_of_me = perceived_by_me

    def apply_emotional_residue(self, name: str, tick: int, emotional_valence: float = 0.0,
                                emotional_intensity: float = 0.0, source: str = ""):
        model = self.get_or_create(name)
        residue = max(-0.18, min(0.18, emotional_valence * max(0.2, emotional_intensity)))
        if source == "argument":
            residue = min(residue, -0.08)
        model.gut_feeling = max(-1.0, min(1.0, model.gut_feeling + residue))
        model.last_updated = tick

    async def synthesize_after_interaction(self, agent, other_agent, interaction_summary: str,
                                           llm_client=None):
        """Update mental model of other_agent after interaction using LLM or numeric fallback."""
        other_name = other_agent.name if hasattr(other_agent, "name") else str(other_agent)
        model = self.get_or_create(other_name)
        tick = getattr(agent, "_current_tick", 0) if hasattr(agent, "_current_tick") else 0

        if llm_client is None:
            # Numeric fallback -- small positive bump from any interaction
            model.comfort_level = min(1.0, model.comfort_level + 0.03)
            model.trust = min(1.0, model.trust + 0.01)
            model.last_updated = tick
            return

        prompt = SYNTHESIS_PROMPT.format(
            other_name=other_name,
            interaction_summary=interaction_summary[:500],
            prev_personality=model.perceived_personality,
            prev_trust=model.trust,
            prev_reliability=model.reliability,
            prev_emotional_safety=model.emotional_safety,
            prev_stress_response=model.how_they_handle_stress,
            prev_trajectory=model.relationship_trajectory,
        )

        agent_name = agent.name if hasattr(agent, "name") else "Agent"
        sys_msg = f"You are {agent_name}, reflecting on someone you just interacted with."

        try:
            result = await llm_client.generate_json(sys_msg, prompt, default={})
        except Exception:
            logger.warning(f"LLM synthesis failed for {agent_name} -> {other_name}, using fallback")
            model.comfort_level = min(1.0, model.comfort_level + 0.03)
            model.last_updated = tick
            return

        if result.get("personality"):
            model.perceived_personality = result["personality"]
        if result.get("what_they_think_of_me"):
            model.what_i_think_they_think_of_me = result["what_they_think_of_me"]
        for field_name in ("trust_delta", "comfort_delta", "reliability_delta", "emotional_safety_delta"):
            delta = result.get(field_name, 0)
            if not isinstance(delta, (int, float)):
                continue
            delta = max(-0.2, min(0.2, delta))
            attr = field_name.replace("_delta", "")
            if attr == "trust":
                model.trust = max(0.0, min(1.0, model.trust + delta))
            elif attr == "comfort":
                model.comfort_level = max(0.0, min(1.0, model.comfort_level + delta))
            elif attr == "reliability":
                model.reliability = max(0.0, min(1.0, model.reliability + delta))
            elif attr == "emotional_safety":
                model.emotional_safety = max(0.0, min(1.0, model.emotional_safety + delta))

        if result.get("stress_response"):
            model.how_they_handle_stress = result["stress_response"]
        if result.get("trajectory") in ("getting_closer", "drifting_apart", "stable", "tense"):
            model.relationship_trajectory = result["trajectory"]
        if result.get("predicted_behavior"):
            model.predicted_behaviors.append(result["predicted_behavior"])
            model.predicted_behaviors = model.predicted_behaviors[-5:]
        if isinstance(result.get("suspected_goals"), list):
            model.suspected_goals = [str(goal)[:120] for goal in result["suspected_goals"][:4] if goal]
        if isinstance(result.get("perceived_values"), list):
            model.perceived_values = [str(value)[:80] for value in result["perceived_values"][:4] if value]
        if isinstance(result.get("perceived_fears"), list):
            model.perceived_fears = [str(fear)[:80] for fear in result["perceived_fears"][:4] if fear]
        if result.get("new_insight") and result["new_insight"] != "null":
            if len(model.perceived_motivations) < 5:
                model.perceived_motivations.append(result["new_insight"])
        unresolved = result.get("unresolved_issue")
        if unresolved and unresolved != "null":
            model.unresolved_issues.append(str(unresolved)[:140])
            model.unresolved_issues = model.unresolved_issues[-4:]
        direction = str(result.get("gut_feeling_direction", "unchanged")).lower()
        if direction == "warmer":
            model.gut_feeling = max(-1.0, min(1.0, model.gut_feeling + 0.08))
        elif direction == "colder":
            model.gut_feeling = max(-1.0, min(1.0, model.gut_feeling - 0.08))

        model.last_updated = tick

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
