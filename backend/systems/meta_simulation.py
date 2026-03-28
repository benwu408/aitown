"""Meta-simulation — detects emergent structures and applies world self-modification."""

import logging

logger = logging.getLogger("agentica.meta")

MAX_CONSTITUTION_CHANGES_PER_DAY = 2
CHANGE_COOLDOWN_TICKS = 200


class MetaSimulation:
    def __init__(self):
        self._last_check_tick = 0
        self._changes_today = 0
        self._last_change_tick = 0
        self._last_check_day = 0

    def check(self, agents: dict, world, tick: int, day: int) -> list[dict]:
        """Run all implicit detection checks. Call every ~100 ticks."""
        events = []

        if day > self._last_check_day:
            self._changes_today = 0
            self._last_check_day = day

        if self._changes_today >= MAX_CONSTITUTION_CHANGES_PER_DAY:
            return events
        if tick - self._last_change_tick < CHANGE_COOLDOWN_TICKS:
            return events

        # --- Role emergence: agents who spend most time on one activity ---
        for agent in agents.values():
            dominant = agent.skill_memory.get_dominant_activity()
            if dominant and not agent.self_concept:
                agent.self_concept = dominant.replace("_", " ")
                agent.episodic_memory.add_simple(
                    f"I realize I've become the settlement's {agent.self_concept}. It happened naturally.",
                    tick=tick, day=day, time_of_day="", location=agent.current_location,
                    category="reflection", intensity=0.6, emotion="pride",
                )
                events.append({
                    "type": "system_event", "eventType": "role_emergence",
                    "label": "Role Emerged",
                    "description": f"{agent.name} has become the settlement's {agent.self_concept}",
                })
                logger.info(f"Role emergence: {agent.name} → {agent.self_concept}")

        # --- Leadership emergence: composite influence, not just mentions ---
        influence_scores: dict[str, float] = {}
        for candidate in agents.values():
            mention_score = 0.0
            trust_score = 0.0
            reliability_score = 0.0
            support_score = 0.0
            for observer in agents.values():
                if observer.id == candidate.id:
                    continue
                for ep in observer.episodic_memory.recent(20):
                    if candidate.name in ep.agents_involved:
                        mention_score += 0.2
                rel = observer.relationships.get(candidate.name, {})
                trust_score += rel.get("trust", 0.5)
                model = observer.mental_models.models.get(candidate.name)
                if model:
                    reliability_score += model.reliability
                    support_score += max(0.0, model.leadership_influence + model.alliance_lean * 0.5)
            influence_scores[candidate.name] = mention_score + trust_score + reliability_score + support_score

        if influence_scores:
            most_influential = max(influence_scores, key=influence_scores.get)
            threshold = len(agents) * 1.8
            if influence_scores[most_influential] > threshold:
                current_leader = world.constitution.governance_rules.get("informal_leader")
                if current_leader != most_influential:
                    world.constitution.governance_rules["informal_leader"] = most_influential
                    world.constitution.governance_rules["leadership_scores"] = {
                        name: round(score, 2) for name, score in sorted(influence_scores.items(), key=lambda item: item[1], reverse=True)[:5]
                    }
                    world.constitution.change_history.append({
                        "tick": tick, "type": "leadership_emergence",
                        "description": f"{most_influential} is becoming the informal leader",
                    })
                    events.append({
                        "type": "system_event", "eventType": "leadership_emergence",
                        "label": "Informal Leader",
                        "description": f"{most_influential} is emerging as the settlement's informal leader",
                    })
                    self._changes_today += 1
                    self._last_change_tick = tick

        # --- Social norm detection: repeated group behavior ---
        # If most agents gather at the same location in the evening → social gathering norm
        evening_locations: dict[str, int] = {}
        for agent in agents.values():
            for ep in agent.episodic_memory.by_category("observation", 10):
                if "clearing" in ep.content.lower() or "gathering" in ep.content.lower():
                    evening_locations["clearing"] = evening_locations.get("clearing", 0) + 1

        if evening_locations.get("clearing", 0) > len(agents) * 0.5:
            norm = "People gather at the clearing in the evenings"
            existing_norms = [n["text"] if isinstance(n, dict) else str(n) for n in world.constitution.social_norms]
            if norm not in existing_norms:
                world.add_norm(norm, tick, category="gathering", origin="implicit_behavior")
                world.constitution.change_history.append({
                    "tick": tick, "type": "norm_emergence",
                    "description": norm,
                })
                events.append({
                    "type": "system_event", "eventType": "norm_emergence",
                    "label": "Social Norm",
                    "description": f"New norm: {norm}",
                })

        # --- Property norm: if most agents have claimed spaces ---
        claimed = sum(1 for loc in world.locations.values() if loc.get("claimed_by"))
        existing_norms = [n["text"] if isinstance(n, dict) else str(n) for n in world.constitution.social_norms]
        if claimed >= 3 and "Respect claimed spaces" not in existing_norms:
            world.add_norm("Respect claimed spaces", tick, category="property", origin="implicit_behavior")
            world.constitution.change_history.append({
                "tick": tick, "type": "norm_emergence",
                "description": "Property rights emerging — agents respect claims",
            })

        # --- Currency emergence: track trade medium frequency ---
        if world.trades:
            item_counts: dict[str, int] = {}
            for trade in world.trades[-50:]:
                item = trade.get("item", "")
                if item:
                    item_counts[item] = item_counts.get(item, 0) + 1
            if item_counts:
                total_trades = sum(item_counts.values())
                most_traded = max(item_counts, key=item_counts.get)
                if item_counts[most_traded] / total_trades > 0.6 and total_trades >= 5:
                    current_currency = world.constitution.economic_rules.get("currency")
                    if current_currency != most_traded:
                        world.constitution.economic_rules["currency"] = most_traded
                        world.constitution.change_history.append({
                            "tick": tick, "type": "currency_emergence",
                            "description": f"{most_traded} has become the de facto currency",
                        })
                        events.append({
                            "type": "system_event", "eventType": "currency_emergence",
                            "label": "Currency Emerged!",
                            "description": f"{most_traded} is now used as currency in most trades",
                        })
                        self._changes_today += 1
                        self._last_change_tick = tick

        # --- Institution creation: repeated gatherings at built structures ---
        built_structures = [loc_id for loc_id, loc in world.locations.items() if loc.get("type") == "built_structure"]
        for loc_id in built_structures:
            agents_here = sum(1 for a in agents.values() if a.current_location == loc_id)
            if agents_here >= 3:
                existing = [i for i in world.constitution.institutions if i.get("location") == loc_id]
                if not existing:
                    loc = world.locations[loc_id]
                    inst_name = f"Gathering at {loc.get('label', loc_id)}"
                    world.constitution.institutions.append({
                        "id": f"institution_{len(world.constitution.institutions) + 1}_{tick}",
                        "name": inst_name,
                        "location": loc_id,
                        "formed_tick": tick,
                        "purpose": "social gathering",
                        "members": [a.name for a in agents.values() if a.current_location == loc_id][:6],
                        "roles": {},
                        "operating_norm_ids": [],
                        "legitimacy": 0.5,
                        "activity_level": 0.4,
                    })
                    world.constitution.change_history.append({
                        "tick": tick, "type": "institution_creation",
                        "description": f"New institution: {inst_name}",
                    })
                    events.append({
                        "type": "system_event", "eventType": "institution_creation",
                        "label": "New Institution",
                        "description": inst_name,
                    })
                    self._changes_today += 1
                    self._last_change_tick = tick

        return events

    async def process_proposal(self, agent, proposal_text: str, agents: dict, world) -> dict | None:
        """Evaluate a formal proposal from an agent."""
        from llm.client import llm_client

        # Get support from nearby agents
        supporters = []
        for other in agents.values():
            if other.id == agent.id:
                continue
            if other.current_location == agent.current_location:
                rel = other.relationships.get(agent.name, {})
                trust = rel.get("trust", 0.5)
                if trust > 0.4:
                    supporters.append(other.name)

        if len(supporters) < 2:
            return None  # Not enough support

        # LLM evaluates the proposal
        result = await llm_client.generate_json(
            "You evaluate proposals for a frontier settlement.",
            f"""Evaluate this proposal for a small frontier settlement:

PROPOSAL: {proposal_text}
PROPOSED BY: {agent.name}
SUPPORTERS: {', '.join(supporters)}
CURRENT RULES: {world.constitution.summary()}

Is this proposal coherent, useful, and implementable?

Return JSON:
{{"accepted": true/false, "reason": "why", "rule_text": "the formal rule if accepted"}}""",
            default={"accepted": False, "reason": "evaluation failed"},
        )

        if result.get("accepted") and result.get("rule_text"):
            world.add_norm(result["rule_text"], 0, category="proposal", origin="formal_proposal")
            world.constitution.change_history.append({
                "tick": 0, "type": "proposal_accepted",
                "description": f"{agent.name} proposed: {result['rule_text']}",
            })

        return result


meta_simulation = MetaSimulation()
