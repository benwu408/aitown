"""Open-ended agent — no assigned role, driven by needs and personality."""

import random
from typing import Optional

from agents.profiles import AgentProfile
from agents.cognition.emotions import EmotionalState
from agents.cognition.drives import DriveSystem
from agents.cognition.episodic_memory import EpisodicMemory
from agents.cognition.working_memory import WorkingMemory
from agents.cognition.beliefs import BeliefSystem
from agents.cognition.mental_models import MentalModelSystem
from agents.cognition.skills import SkillMemory
from agents.cognition.world_model import WorldModelMemory
from agents.cognition.identity import Identity
from simulation.actions import ActionType


class Agent:
    def __init__(self, profile: AgentProfile, world):
        self.id = profile.id
        self.name = profile.name
        self.profile = profile
        self.world = world

        # Physical position — everyone starts at clearing
        entry = world.get_location_entry("clearing")
        self.position: tuple[int, int] = entry
        self.current_location: str = "clearing"
        self.previous_location: str = ""

        # Core state
        self.current_action = ActionType.IDLE
        self.inner_thought: str = "Where am I? What do we do now?"
        self.daily_plan: str = ""
        self.daily_schedule: list[dict] = []
        self.current_plan_step: dict | None = None
        self.long_term_goals: list[dict] = []
        self.active_intentions: list[dict] = []
        self.current_plan: dict | None = None
        self.fallback_plan: dict | None = None
        self.blocked_reasons: list[dict] = []
        self.decision_rationale: dict = {}
        self.life_events: list[dict] = []
        self.reciprocity_ledger: dict[str, dict] = {}
        self.proposal_stances: dict[str, dict] = {}
        self.project_roles: list[dict] = []
        self.current_institution_roles: list[dict] = []
        self.active_conflicts: list[dict] = []
        self.plan_mode: str = "improvising"
        self.plan_deviation_reason: str = ""
        self.self_concept: str | None = None  # Emerges over time

        # Cognitive Architecture
        baseline_v = (profile.personality.get("agreeableness", 0.5) + profile.personality.get("extraversion", 0.5)) / 2 - 0.2
        self.emotional_state = EmotionalState(baseline_valence=baseline_v)
        self.drives = DriveSystem()
        self.drives.hunger = 0.5  # Haven't eaten in a while — need food soon
        # Personality-seeded shelter urgency: neurotic agents feel it sooner, open agents are fine roughing it
        neuro = profile.personality.get("neuroticism", 0.5)
        openness = profile.personality.get("openness", 0.5)
        self.drives.shelter_need = 0.15 + neuro * 0.3 - openness * 0.1
        self.drives._shelter_growth_rate = 0.0007 + neuro * 0.0006 + profile.personality.get("conscientiousness", 0.5) * 0.0003
        self.drives.purpose_need = 0.5  # Why are we here?
        self.drives.social_need = 0.3
        self.episodic_memory = EpisodicMemory()
        self.working_memory = WorkingMemory()
        self.belief_system = BeliefSystem()
        self.mental_models = MentalModelSystem()
        self.skill_memory = SkillMemory()
        self.world_model = WorldModelMemory()
        self.identity = Identity()

        # Seed initial beliefs from backstory
        self.belief_system.add(profile.backstory[:100], "self_belief", 0.8, tick=0)
        for v in profile.values:
            self.belief_system.add(f"I value {v}", "self_belief", 0.9, tick=0)

        # Legacy compat
        self.memory = self.episodic_memory
        self.emotion = "neutral"
        self.relationships: dict[str, dict] = {}
        self.active_goals: list[dict] = []
        self.transactions: list[dict] = []
        self.inventory: list[dict] = []
        self.debt: float = 0
        self.daily_income: float = 0
        self.daily_expenses: float = 0
        self.social_commitments: list[dict] = []
        self.current_commitment: dict | None = None
        self.opinions: dict = {}
        self.secrets: list[dict] = []
        self.reputation: dict = {"generosity": 0.5, "honesty": 0.5, "reliability": 0.5, "kindness": 0.5}

        # Health
        self.health: float = 1.0
        self.is_sick: bool = False
        self.sick_since_tick: int = 0
        self.last_steal_attempt_tick: int = -999

        # Movement
        self.path: list[tuple[int, int]] = []
        self.path_index: int = 0
        self.move_target: str | None = None
        self.paused_path: list[tuple[int, int]] = []
        self.paused_path_index: int = 0
        self.paused_move_target: str | None = None
        self.talking_until_tick: int = 0
        self.sleep_until_tick: int = 0
        seed = sum(ord(ch) for ch in profile.id)
        self.sleep_start_hour: int = 21 + (seed % 4)
        self.wake_hour: int = 5 + ((seed // 3) % 3)

        self.is_in_conversation: bool = False
        self.conversation_cooldown: int = 0  # Ticks before agent can chat again
        self.current_conversation_id: str | None = None

        # Initial working memory
        self.working_memory.push("We just arrived at this abandoned settlement.")
        self.working_memory.push("I need to find food, water, and shelter.")
        self.working_memory.set_worry("What if there isn't enough for everyone?")

    def _inventory_value(self) -> float:
        """Rough 'wealth' estimate based on effort values of held items."""
        from systems.economy import EFFORT_VALUES
        total = 0.0
        for item in self.inventory:
            name = item.get("name", "")
            qty = int(item.get("quantity", 1))
            total += EFFORT_VALUES.get(name, 1.0) * qty
        return round(total, 1)

    def inventory_count(self, item_name: str) -> int:
        total = 0
        for item in self.inventory:
            if item.get("name") == item_name:
                total += int(item.get("quantity", 1))
        return total

    def consume_inventory(self, item_name: str, quantity: int) -> bool:
        remaining = quantity
        for item in list(self.inventory):
            if item.get("name") != item_name:
                continue
            item_qty = int(item.get("quantity", 1))
            take = min(item_qty, remaining)
            remaining -= take
            left = item_qty - take
            if left > 0:
                item["quantity"] = left
            else:
                self.inventory.remove(item)
            if remaining <= 0:
                return True
        return remaining <= 0

    def add_blocked_reason(self, reason: str, tick: int, severity: float = 0.5):
        if not reason:
            return
        if any(existing.get("reason") == reason for existing in self.blocked_reasons[:5]):
            return
        self.blocked_reasons.insert(0, {"reason": reason, "tick": tick, "severity": round(severity, 2)})
        self.blocked_reasons = self.blocked_reasons[:8]

    def add_life_event(self, summary: str, tick: int, category: str = "milestone", impact: float = 0.5):
        if not summary:
            return
        self.life_events.insert(0, {
            "summary": summary,
            "tick": tick,
            "category": category,
            "impact": round(impact, 2),
        })
        self.life_events = self.life_events[:20]

    def set_decision_rationale(self, chosen: dict, candidates: list[dict]):
        ranked = sorted(candidates, key=lambda item: item.get("score", 0), reverse=True)[:4]
        self.decision_rationale = {
            "chosen": chosen,
            "considered": ranked,
        }

    def note_reciprocity(self, other_name: str, gave: dict | None = None, received: dict | None = None):
        ledger = self.reciprocity_ledger.setdefault(other_name, {"gave": {}, "received": {}, "balance": 0.0})
        if gave:
            for item, qty in gave.items():
                ledger["gave"][item] = ledger["gave"].get(item, 0) + qty
                ledger["balance"] += qty
        if received:
            for item, qty in received.items():
                ledger["received"][item] = ledger["received"].get(item, 0) + qty
                ledger["balance"] -= qty

    def set_proposal_stance(self, proposal_id: str, stance: str, reason: str = "", legitimacy: float = 0.0):
        self.proposal_stances[proposal_id] = {
            "stance": stance,
            "reason": reason,
            "legitimacy": round(legitimacy, 2),
        }

    def note_conflict(self, other_name: str, summary: str, tick: int, severity: float = 0.5, kind: str = "social"):
        if not other_name or not summary:
            return
        if any(
            conflict.get("with") == other_name and conflict.get("summary") == summary
            for conflict in self.active_conflicts[:6]
        ):
            return
        self.active_conflicts.insert(0, {
            "with": other_name,
            "summary": summary,
            "tick": tick,
            "severity": round(severity, 2),
            "kind": kind,
            "status": "active",
        })
        self.active_conflicts = self.active_conflicts[:8]

    def resolve_conflict(self, other_name: str, contains: str = ""):
        self.active_conflicts = [
            conflict for conflict in self.active_conflicts
            if not (
                conflict.get("with") == other_name
                and (not contains or contains.lower() in conflict.get("summary", "").lower())
            )
        ][:8]

    def bump_identity(self, event_summary: str, role_hint: str = ""):
        if role_hint and not self.self_concept:
            self.self_concept = role_hint
        best_skill = self.skill_memory.get_dominant_activity()
        if best_skill and not self.self_concept:
            self.self_concept = best_skill.replace("_", " ")
        narrative_parts = []
        if self.self_concept:
            narrative_parts.append(f"I'm becoming {self.self_concept}.")
        if event_summary:
            narrative_parts.append(event_summary)
        if self.working_memory.background_worry:
            narrative_parts.append(f"What's weighing on me: {self.working_memory.background_worry}")
        self.identity.self_narrative = " ".join(narrative_parts[:3]).strip()

    def update(self, hour: float, world) -> list[dict]:
        """Basic tick update — movement along path + location discovery."""
        events = []

        if self.is_in_conversation or (self.current_action == ActionType.TALKING and self.talking_until_tick > 0):
            return events

        # Continue walking if we have a path
        if self.path and self.path_index < len(self.path):
            self.current_action = ActionType.WALKING
            self.position = self.path[self.path_index]
            self.path_index += 1

            if self.path_index >= len(self.path):
                self.path = []
                self.path_index = 0
                if self.move_target:
                    self.previous_location = self.current_location
                    self.current_location = self.move_target
                    self.move_target = None
                self.current_action = ActionType.IDLE

        # Discover locations by proximity — check if we're inside any named location
        col, row = self.position
        for loc_id, loc in world.locations.items():
            if self.world_model.knows_location(loc_id):
                continue
            lc, lr = loc["col"], loc["row"]
            lw, lh = loc["width"], loc["height"]
            # Are we inside or within 2 tiles of this location?
            if lc - 2 <= col < lc + lw + 2 and lr - 2 <= row < lr + lh + 2:
                self.world_model.discover_location(
                    loc_id, loc.get("description", ""),
                    loc.get("resources", []), 0
                )
                # Update current_location if we're inside the bounds
                if lc <= col < lc + lw and lr <= row < lr + lh:
                    self.current_location = loc_id
                # Memory of discovery
                self.episodic_memory.add_simple(
                    f"I discovered {loc.get('label', loc_id)}! {loc.get('description', '')}",
                    tick=0, day=0, time_of_day="", location=loc_id,
                    category="observation", intensity=0.6, emotion="curious",
                )
                self.inner_thought = f"I found the {loc.get('label', loc_id)}!"
                events.append({
                    "type": "agent_thought", "agentId": self.id,
                    "thought": f"Discovered: {loc.get('label', loc_id)}",
                })

        return events

    def start_walking(self, target_loc: str):
        target = self.world.get_location_entry(target_loc)
        self.path = self.world.find_path(self.position, target)
        self.path_index = 0
        self.move_target = target_loc
        self.current_action = ActionType.WALKING

    def pause_for_conversation(self, until_tick: int):
        if self.path and not self.paused_path:
            self.paused_path = list(self.path)
            self.paused_path_index = self.path_index
            self.paused_move_target = self.move_target
        self.path = []
        self.path_index = 0
        self.move_target = None
        self.current_action = ActionType.TALKING
        self.talking_until_tick = max(self.talking_until_tick, until_tick)

    def resume_after_conversation(self):
        if self.paused_path:
            self.path = list(self.paused_path)
            self.path_index = self.paused_path_index
            self.move_target = self.paused_move_target
            self.paused_path = []
            self.paused_path_index = 0
            self.paused_move_target = None
            self.current_action = ActionType.WALKING if self.path and self.path_index < len(self.path) else ActionType.IDLE
        else:
            self.current_action = ActionType.IDLE
        self.talking_until_tick = 0

    def start_sleeping_until(self, until_tick: int):
        self.current_action = ActionType.SLEEPING
        self.sleep_until_tick = until_tick

    def wake_up(self):
        self.current_action = ActionType.IDLE
        self.sleep_until_tick = 0

    def get_routine_action(self, hour: float, time_of_day: str) -> dict:
        """Drive-based routine behavior — agents only go to places they know or can see."""
        import random as _rand

        # Allow agents with strong purpose to resist non-critical drive interrupts
        has_urgent_intention = any(
            i.get("urgency", 0) > 0.7 and i.get("status") == "active"
            for i in self.active_intentions[:3]
        )
        should_interrupt, interrupt_type = self.drives.should_interrupt_plan(can_resist=has_urgent_intention)
        # If we resisted a drive that would have interrupted without can_resist, note the stress
        if has_urgent_intention and not should_interrupt:
            would_interrupt, _ = self.drives.should_interrupt_plan(can_resist=False)
            if would_interrupt:
                self.emotional_state.apply_event("anxiety", 0.1)

        # Personal night window → head home and sleep (but not if just woken up with low tiredness)
        if self.prefers_sleeping_now(hour) and self.drives.rest > 0.3:
            home = self._find_home()
            return {"action": "sleeping", "target": home or self.current_location, "thought": "Time to rest."}

        # Critical hunger → find food (only truly desperate hunger overrides shelter)
        if self.drives.hunger > 0.7:
            # Check if there's food RIGHT HERE
            resources_here = self.world.get_resources_at(self.current_location)
            if any(r in resources_here for r in ["wild_berries", "fish", "wild_plants"]):
                return {"action": "eating", "target": self.current_location, "thought": "I'll eat what's here."}

            # Go to a KNOWN food location
            food_locs = self.world_model.get_known_resource_locations("wild_berries") + \
                       self.world_model.get_known_resource_locations("fish") + \
                       self.world_model.get_known_resource_locations("wild_plants")
            food_locs = [l for l in food_locs if l != self.current_location]
            if food_locs:
                target = _rand.choice(food_locs)
                return {"action": "walking", "target": target, "thought": "I know where food is. Heading there now."}

            # Don't know where food is → explore in a random direction
            return self._explore_unknown("I need to find food. Let me search around.")

        # CRITICAL shelter need → prioritized over moderate hunger
        if self.drives.shelter_need > 0.7:
            if self.inventory_count("wood") >= 5:
                return {"action": "building", "target": self.current_location, "thought": "I have wood. Time to build a shelter."}
            # Go to forest to gather wood
            forest_locs = self.world_model.get_known_resource_locations("wood")
            if forest_locs:
                if self.current_location in forest_locs:
                    return {"action": "gathering_wood", "target": self.current_location, "thought": "I need wood for a shelter."}
                target = _rand.choice(forest_locs)
                return {"action": "walking", "target": target, "thought": "I need wood to build a shelter."}
            # Don't know where wood is — explore to find it
            return self._explore_unknown("I need to find wood for a shelter. Let me look around.")

        # At a food location with moderate hunger → eat
        resources_here = self.world.get_resources_at(self.current_location)
        if self.drives.hunger > 0.25 and any(r in resources_here for r in ["wild_berries", "fish", "wild_plants"]):
            return {"action": "eating", "target": self.current_location, "thought": "Might as well eat while I'm here."}

        # Moderate hunger → find food
        if self.drives.hunger > 0.5:
            food_locs = self.world_model.get_known_resource_locations("wild_berries") + \
                       self.world_model.get_known_resource_locations("fish") + \
                       self.world_model.get_known_resource_locations("wild_plants")
            food_locs = [l for l in food_locs if l != self.current_location]
            if food_locs:
                target = _rand.choice(food_locs)
                return {"action": "walking", "target": target, "thought": "Getting hungry. I should find food."}

        # Exhausted → sleep
        if self.drives.rest > 0.7:
            home = self._find_home()
            return {"action": "sleeping", "target": home or self.current_location, "thought": "I need to rest."}

        # EXPLORE — only places we haven't been
        # Agents don't know where all locations are — they discover them by wandering
        known = set(self.world_model.known_locations.keys())
        if len(known) < len(self.world.get_all_location_ids()):
            explore_chance = 0.3 + self.profile.personality.get("openness", 0.5) * 0.3
            if _rand.random() < explore_chance:
                return self._explore_unknown("I should explore. Who knows what's out there.")

        # Socially satisfied → go do something else (prevents clustering)
        if self.drives.social_need < 0.15:
            other_locs = [l for l in self.world_model.known_locations if l != self.current_location]
            if other_locs:
                target = _rand.choice(other_locs)
                return {"action": "walking", "target": target, "thought": "Time to go do something useful."}
            return self._explore_unknown("I should go explore while I have the energy.")

        # Revisit known locations
        known_locs = list(self.world_model.known_locations.keys())
        if known_locs and _rand.random() < 0.4:
            target = _rand.choice(known_locs)
            if target != self.current_location:
                return {"action": "walking", "target": target, "thought": f"I'll head to the {target.replace('_', ' ')}."}

        # Social need → go back to clearing
        if self.drives.social_need > 0.4 and self.current_location != "clearing":
            return {"action": "walking", "target": "clearing", "thought": "I should go see if anyone else is around."}

        # Idle
        return {"action": "idle", "target": self.current_location, "thought": "Taking in the surroundings."}

    def _explore_unknown(self, thought: str) -> dict:
        """Pick a random direction to wander and discover new places."""
        import random as _rand
        # Walk to a random point on the map (not a named location — just wander)
        # Pick a random tile that's walkable and reasonably far
        for _ in range(10):
            target_col = self.position[0] + _rand.randint(-12, 12)
            target_row = self.position[1] + _rand.randint(-12, 12)
            target_col = max(2, min(37, target_col))
            target_row = max(2, min(37, target_row))
            if self.world.is_walkable(target_col, target_row):
                # Check if we'd pass through any named location on the way
                # For simplicity, just walk to the random point
                self.path = self.world.find_path(self.position, (target_col, target_row))
                self.path_index = 0
                self.current_action = ActionType.WALKING
                return {"action": "walking_explore", "target": self.current_location, "thought": thought}
        # Couldn't find a good direction — head to clearing
        return {"action": "walking", "target": "clearing", "thought": "I'll head back to the clearing."}

    def _find_home(self) -> str | None:
        """Find the agent's claimed shelter."""
        if self.current_location in self.world.locations:
            current = self.world.locations[self.current_location]
            if current.get("type") == "built_structure" and current.get("claimed_by") == self.name:
                return self.current_location

        for loc_id, claim in self.world_model.known_claims.items():
            if claim.get("claimed_by") == self.name:
                return loc_id

        for loc_id, loc in self.world.locations.items():
            if loc.get("type") == "built_structure" and loc.get("claimed_by") == self.name:
                self.world_model.learn_claim(loc_id, self.name, loc.get("designated_purpose", ""))
                return loc_id
        return None

    def prefers_sleeping_now(self, hour: float) -> bool:
        return hour >= self.sleep_start_hour or hour < self.wake_hour

    def to_dict(self) -> dict:
        dominant_emotion, intensity = self.emotional_state.get_dominant_emotion()
        self.emotion = dominant_emotion if intensity > 0.2 else "neutral"

        return {
            "id": self.id,
            "name": self.name,
            "age": self.profile.age,
            "job": self.self_concept or "newcomer",
            "position": list(self.position),
            "currentLocation": self.current_location,
            "currentAction": self.current_action.value,
            "conversationId": self.current_conversation_id,
            "emotion": self.emotion,
            "innerThought": self.inner_thought,
            "colorIndex": self.profile.color_index,
            "sleepWindow": {"startHour": self.sleep_start_hour, "wakeHour": self.wake_hour},
            "summary": self._get_summary(),
            "health": round(self.health, 2),
            "isSick": self.is_sick,
            "state": {
                "energy": round(1.0 - self.drives.rest, 2),
                "hunger": round(self.drives.hunger, 2),
                "mood": round(max(0, min(1, (self.emotional_state.valence + 1) / 2)), 2),
                "health": round(self.health, 2),
                "wealth": self._inventory_value(),
                "debt": round(self.debt, 1),
                "dailyIncome": round(self.daily_income, 1),
                "dailyExpenses": round(self.daily_expenses, 1),
                "tradeCount": len(self.transactions),
            },
            "emotions": self.emotional_state.to_dict(),
            "drives": self.drives.to_dict(),
            "workingMemory": self.working_memory.to_dict(),
            "transactions": self.transactions[-5:],
            "inventory": [{"name": i.get("name", str(i)), "quantity": i.get("quantity", 1)} for i in self.inventory[:10]],
            "socialCommitments": self.social_commitments[:5],
            "longTermGoals": self.long_term_goals[:5],
            "activeIntentions": self.active_intentions[:5],
            "currentPlan": self.current_plan,
            "fallbackPlan": self.fallback_plan,
            "blockedReasons": self.blocked_reasons[:5],
            "decisionRationale": self.decision_rationale,
            "proposalStances": self.proposal_stances,
            "projectRoles": self.project_roles[:5],
            "currentInstitutionRoles": self.current_institution_roles[:5],
            "activeConflicts": self.active_conflicts[:5],
            "planMode": self.plan_mode,
            "planDeviationReason": self.plan_deviation_reason,
            "currentPlanStep": self.current_plan_step,
        }

    def _get_summary(self) -> str:
        role = self.self_concept or "newcomer"
        recent = ""
        for m in reversed(self.episodic_memory.episodes):
            if m.emotional_intensity >= 0.5:
                recent = m.content[:60]
                break
        if not recent:
            recent = self.profile.backstory[:60]
        return f"{self.profile.age}yo {role}. {recent}"

    def to_detail_dict(self) -> dict:
        return {
            **self.to_dict(),
            "personality": self.profile.personality,
            "values": self.profile.values,
            "goals": [g["text"] for g in self.active_goals if g.get("status") == "active"],
            "activeGoals": self.active_goals,
            "fears": self.profile.fears,
            "backstory": self.profile.backstory,
            "physicalTraits": self.profile.physical_traits,
            "dailyPlan": self.daily_plan,
            "longTermGoals": self.long_term_goals,
            "activeIntentions": self.active_intentions,
            "currentPlan": self.current_plan,
            "fallbackPlan": self.fallback_plan,
            "blockedReasons": self.blocked_reasons,
            "decisionRationale": self.decision_rationale,
            "planMode": self.plan_mode,
            "planDeviationReason": self.plan_deviation_reason,
            "selfConcept": self.self_concept,
            "identityNarrative": self.identity.self_narrative,
            "lifeEvents": self.life_events,
            "reciprocityLedger": self.reciprocity_ledger,
            "proposalStances": self.proposal_stances,
            "projectRoles": self.project_roles,
            "currentInstitutionRoles": self.current_institution_roles,
            "activeConflicts": self.active_conflicts,
            "secrets": [],
            "opinions": {},
            "reputation": self.reputation,
            "inventory": self.inventory,
            "socialCommitments": self.social_commitments,
            "memories": self.episodic_memory.to_list(50),
            "beliefs": self.belief_system.to_list(),
            "mentalModels": self.mental_models.to_dict(),
            "socialModels": self.mental_models.to_dict(),
            "skills": self.skill_memory.to_dict(),
            "worldKnowledge": self.world_model.to_dict(),
            "relationships": self.relationships,
            "transactions": [],
            "schedule": self.daily_schedule,
            "currentPlanStep": self.current_plan_step,
            "currentCommitment": self.current_commitment,
        }
