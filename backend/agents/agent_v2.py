"""Open-ended agent — no assigned role, driven by needs and personality."""

import random
from typing import Optional

from agents.profiles_v2 import AgentProfileV2
from agents.cognition_v2.emotions import EmotionalState
from agents.cognition_v2.drives import DriveSystem
from agents.cognition_v2.episodic_memory import EpisodicMemory
from agents.cognition_v2.working_memory import WorkingMemory
from agents.cognition_v2.beliefs import BeliefSystem
from agents.cognition_v2.mental_models import MentalModelSystem
from agents.cognition_v2.skills import SkillMemory
from agents.cognition_v2.world_model import WorldModelMemory
from agents.cognition_v2.identity import Identity
from simulation.actions import ActionType


class AgentV2:
    def __init__(self, profile: AgentProfileV2, world):
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
        self.self_concept: str | None = None  # Emerges over time

        # V2 Cognitive Architecture
        baseline_v = (profile.personality.get("agreeableness", 0.5) + profile.personality.get("extraversion", 0.5)) / 2 - 0.2
        self.emotional_state = EmotionalState(baseline_valence=baseline_v)
        self.drives = DriveSystem()
        self.drives.hunger = 0.5  # Haven't eaten in a while — need food soon
        self.drives.shelter_need = 0.4  # No home
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
        self.opinions: dict = {}
        self.secrets: list[dict] = []
        self.reputation: dict = {"generosity": 0.5, "honesty": 0.5, "reliability": 0.5, "kindness": 0.5}

        # Movement
        self.path: list[tuple[int, int]] = []
        self.path_index: int = 0
        self.move_target: str | None = None

        # No schedule — driven by needs
        self.is_in_conversation: bool = False
        self.conversation_cooldown: int = 0  # Ticks before agent can chat again

        # Initial working memory
        self.working_memory.push("We just arrived at this abandoned settlement.")
        self.working_memory.push("I need to find food, water, and shelter.")
        self.working_memory.set_worry("What if there isn't enough for everyone?")

    def update(self, hour: float, world) -> list[dict]:
        """Basic tick update — movement along path + location discovery."""
        events = []

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

    def get_routine_action(self, hour: float, time_of_day: str) -> dict:
        """Drive-based routine behavior — agents only go to places they know or can see."""
        import random as _rand

        # Night → sleep wherever
        if time_of_day == "night" or hour >= 22 or hour < 5:
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
            has_wood = any(i.get("name") == "wood" for i in self.inventory)
            if has_wood:
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
        for loc_id, claim in self.world_model.known_claims.items():
            if claim.get("claimed_by") == self.name:
                return loc_id
        return None

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
            "emotion": self.emotion,
            "innerThought": self.inner_thought,
            "colorIndex": self.profile.color_index,
            "summary": self._get_summary(),
            "state": {
                "energy": round(1.0 - self.drives.rest, 2),
                "hunger": round(self.drives.hunger, 2),
                "mood": round(max(0, min(1, (self.emotional_state.valence + 1) / 2)), 2),
                "wealth": 0,
                "debt": 0,
                "dailyIncome": 0,
                "dailyExpenses": 0,
            },
            "emotions": self.emotional_state.to_dict(),
            "drives": self.drives.to_dict(),
            "workingMemory": self.working_memory.to_dict(),
            "transactions": [],
            "inventory": [{"name": i.get("name", str(i))} for i in self.inventory[:5]],
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
            "selfConcept": self.self_concept,
            "secrets": [],
            "opinions": {},
            "reputation": self.reputation,
            "inventory": self.inventory,
            "socialCommitments": self.social_commitments,
            "memories": self.episodic_memory.to_list(50),
            "beliefs": self.belief_system.to_list(),
            "mentalModels": self.mental_models.to_dict(),
            "skills": self.skill_memory.to_dict(),
            "worldKnowledge": self.world_model.to_dict(),
            "relationships": self.relationships,
            "transactions": [],
            "schedule": [],
        }
