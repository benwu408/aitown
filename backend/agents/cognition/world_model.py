"""World model memory -- agent's personal knowledge of the physical and social world."""


class WorldModelMemory:
    def __init__(self):
        # Physical knowledge
        self.known_locations: dict[str, dict] = {}
        self.known_resources: dict[str, dict] = {}
        self.known_claims: dict[str, dict] = {}

        # Social knowledge
        self.known_roles: dict[str, str] = {}
        self.known_alliances: list[tuple[str, str]] = []
        self.known_conflicts: list[tuple[str, str]] = []
        self.known_norms: list[str] = []
        self.known_institutions: list[dict] = []

        # General knowledge with confidence
        self.knowledge: list[dict] = []  # [{"fact": str, "confidence": float, "source": str, "tick": int}]

    def discover_location(self, loc_id: str, description: str, resources: list[str], tick: int):
        self.known_locations[loc_id] = {
            "discovered_on": tick,
            "description": description,
            "known_resources": resources,
            "confidence": 0.9,
        }
        for res in resources:
            if res not in self.known_resources:
                self.known_resources[res] = {"locations": [], "last_seen_quantity": "unknown"}
            if loc_id not in self.known_resources[res]["locations"]:
                self.known_resources[res]["locations"].append(loc_id)

    def learn_claim(self, loc_id: str, claimed_by: str, purpose: str = ""):
        self.known_claims[loc_id] = {"claimed_by": claimed_by, "purpose": purpose}

    def learn_role(self, agent_name: str, role: str):
        self.known_roles[agent_name] = role

    def learn_norm(self, norm: str):
        if norm not in self.known_norms:
            self.known_norms.append(norm)

    def learn_alliance(self, a: str, b: str):
        pair = (a, b) if a < b else (b, a)
        if pair not in self.known_alliances:
            self.known_alliances.append(pair)

    def learn_conflict(self, a: str, b: str):
        pair = (a, b) if a < b else (b, a)
        if pair not in self.known_conflicts:
            self.known_conflicts.append(pair)

    def learn(self, fact: str, confidence: float = 0.7, source: str = "observation", tick: int = 0):
        """Add new knowledge with confidence level."""
        for k in self.knowledge:
            if k["fact"].lower() == fact.lower():
                # Reinforce existing knowledge
                k["confidence"] = min(1.0, k["confidence"] + 0.1)
                k["tick"] = tick
                return
        self.knowledge.append({
            "fact": fact,
            "confidence": max(0.0, min(1.0, confidence)),
            "source": source,
            "tick": tick,
        })
        # Cap knowledge list
        if len(self.knowledge) > 50:
            self.knowledge.sort(key=lambda k: k["confidence"], reverse=True)
            self.knowledge = self.knowledge[:50]

    def challenge(self, fact: str, counter_evidence: str = ""):
        """Reduce confidence when contradicted."""
        for k in self.knowledge:
            if self._fact_matches(k["fact"], fact):
                k["confidence"] = max(0.0, k["confidence"] - 0.2)
                if counter_evidence:
                    # Learn the counter-evidence at moderate confidence
                    self.learn(counter_evidence, confidence=0.5, source="contradiction")
                return
        # Also check norms
        for i, norm in enumerate(self.known_norms):
            if self._fact_matches(norm, fact):
                self.known_norms.pop(i)
                return

    def learn_from_conversation(self, source_name: str, info: str, trust_in_source: float):
        """Learn from what someone told us. Confidence scales with trust."""
        if not info:
            return
        confidence = 0.3 + trust_in_source * 0.4  # 0.3 to 0.7 based on trust
        self.learn(f"{source_name} says: {info[:80]}", confidence=confidence,
                   source=f"told_by:{source_name}")
        if trust_in_source > 0.4:
            self.learn_norm(f"{source_name} says: {info[:80]}")

    def get_knowledge_for_prompt(self) -> str:
        """Format knowledge with confidence indicators for LLM prompts."""
        if not self.knowledge:
            return ""
        lines = []
        for k in sorted(self.knowledge, key=lambda x: x["confidence"], reverse=True)[:8]:
            conf = k["confidence"]
            if conf > 0.8:
                marker = "[certain]"
            elif conf > 0.5:
                marker = "[likely]"
            elif conf > 0.3:
                marker = "[uncertain]"
            else:
                marker = "[doubtful]"
            lines.append(f"- {marker} {k['fact']}")
        return "What you know:\n" + "\n".join(lines) if lines else ""

    def knows_location(self, loc_id: str) -> bool:
        return loc_id in self.known_locations

    def get_known_resource_locations(self, resource: str) -> list[str]:
        r = self.known_resources.get(resource)
        return r["locations"] if r else []

    def get_knowledge_gaps(self) -> list[str]:
        gaps = []
        if len(self.known_locations) < 5:
            gaps.append("I haven't explored much of the area yet")
        if not self.known_roles:
            gaps.append("I don't know what everyone does around here")
        if not self.known_norms:
            gaps.append("I'm not sure what the social expectations are")
        if not self.known_institutions:
            gaps.append("There don't seem to be any organized structures yet")
        # Check for low-confidence knowledge
        uncertain = [k for k in self.knowledge if k["confidence"] < 0.4]
        if uncertain:
            gaps.append(f"I'm unsure about {len(uncertain)} things I've heard")
        return gaps

    def get_prompt_summary(self) -> str:
        if not self.known_locations:
            return "You haven't explored much yet. You're in an unfamiliar settlement."
        parts = [f"You know about {len(self.known_locations)} locations:"]
        for loc_id, info in list(self.known_locations.items())[:6]:
            res = ", ".join(info.get("known_resources", [])[:3])
            parts.append(f"- {loc_id}: {res or 'no resources noted'}")
        if self.known_claims:
            claimed = [f"{k}: claimed by {v['claimed_by']}" for k, v in self.known_claims.items()][:3]
            parts.append(f"Claimed spaces: {'; '.join(claimed)}")
        if self.known_roles:
            roles = [f"{name} ({role})" for name, role in list(self.known_roles.items())[:5]]
            parts.append(f"People and roles: {', '.join(roles)}")
        if self.known_norms:
            parts.append(f"Social norms: {'; '.join(self.known_norms[:3])}")

        # Append confident knowledge
        knowledge_prompt = self.get_knowledge_for_prompt()
        if knowledge_prompt:
            parts.append(knowledge_prompt)

        gaps = self.get_knowledge_gaps()
        if gaps:
            parts.append(f"What you don't know: {gaps[0]}")
        return "\n".join(parts)

    def to_dict(self) -> dict:
        return {
            "locations": self.known_locations,
            "resources": self.known_resources,
            "claims": self.known_claims,
            "roles": self.known_roles,
            "alliances": self.known_alliances,
            "conflicts": self.known_conflicts,
            "norms": self.known_norms,
            "institutions": self.known_institutions,
            "knowledge": self.knowledge,
        }

    def load_from_dict(self, d: dict):
        self.known_locations = d.get("locations", {})
        self.known_resources = d.get("resources", {})
        self.known_claims = d.get("claims", {})
        self.known_roles = d.get("roles", {})
        self.known_alliances = d.get("alliances", [])
        self.known_conflicts = d.get("conflicts", [])
        self.known_norms = d.get("norms", [])
        self.known_institutions = d.get("institutions", [])
        self.knowledge = d.get("knowledge", [])

    @staticmethod
    def _fact_matches(a: str, b: str) -> bool:
        a_words = set(a.lower().split())
        b_words = set(b.lower().split())
        if not a_words or not b_words:
            return False
        overlap = len(a_words & b_words)
        return overlap / min(len(a_words), len(b_words)) > 0.5
