"""Core Agent class — position, state, schedule following, movement."""

from dataclasses import dataclass, field
from typing import Optional

from agents.profiles import AgentProfile, ScheduleEntry
from agents.memory import MemoryStream, MemoryEntry
from simulation.actions import ActionType, AgentAction
from simulation.world import World


@dataclass
class AgentState:
    energy: float = 1.0
    hunger: float = 0.0
    mood: float = 0.7
    wealth: int = 0


class Agent:
    def __init__(self, profile: AgentProfile, world: World):
        self.id = profile.id
        self.name = profile.name
        self.profile = profile
        self.world = world

        # Position
        entry = world.get_building_entry(profile.home)
        self.position: tuple[int, int] = entry
        self.current_location: str = profile.home

        # State
        self.state = AgentState(wealth=profile.wealth)
        self.current_action = ActionType.SLEEPING
        self.emotion = "neutral"

        # Movement
        self.path: list[tuple[int, int]] = []
        self.path_index: int = 0
        self.move_target: Optional[str] = None  # building_id we're heading to

        # Schedule
        self.schedule = profile.schedule  # static fallback
        self.dynamic_schedule: list[ScheduleEntry] | None = None  # LLM-generated daily plan
        self._current_schedule_index = 0

        # Cognition V2 — 6-layer system
        from agents.cognition_v2.emotions import EmotionalState
        from agents.cognition_v2.drives import DriveSystem
        from agents.cognition_v2.episodic_memory import EpisodicMemory
        from agents.cognition_v2.working_memory import WorkingMemory
        from agents.cognition_v2.beliefs import BeliefSystem
        from agents.cognition_v2.mental_models import MentalModelSystem

        baseline_valence = (profile.personality.get("agreeableness", 0.5) + profile.personality.get("extraversion", 0.5)) / 2 - 0.2
        self.emotional_state = EmotionalState(baseline_valence=baseline_valence)
        self.drives = DriveSystem()
        self.episodic_memory = EpisodicMemory()
        self.working_memory = WorkingMemory()
        self.belief_system = BeliefSystem()
        self.mental_models = MentalModelSystem()

        # Seed initial beliefs from backstory
        self.belief_system.add(profile.backstory[:100], "self_belief", 0.8, tick=0)
        for value in profile.values:
            self.belief_system.add(f"I value {value}", "self_belief", 0.9, tick=0)

        # Legacy compatibility — old systems still reference these
        self.inner_thought: str = ""
        self.daily_plan: str = ""
        self.memory = self.episodic_memory  # alias for old code
        self.relationships: dict[str, dict] = dict(profile.relationships)
        self.transactions: list[dict] = []

        # Phase 1: Deeper stories
        self.secrets: list[dict] = [dict(s) for s in profile.secrets]
        # Economics
        self.debt: float = 0
        self.daily_income: float = 0
        self.daily_expenses: float = 0

        # Phase 2-3: Richer world
        self.inventory: list[dict] = []
        self.mailbox: list[dict] = []
        self.reputation: dict[str, float] = {
            "generosity": 0.5, "honesty": 0.5, "reliability": 0.5, "kindness": 0.5,
        }
        self.social_commitments: list[dict] = []  # {what, where, when (hour), with: [names], day, recurring}
        self.active_goals: list[dict] = [
            {"text": g, "created_tick": 0, "source": "personality", "priority": 0.5, "status": "active", "progress_notes": []}
            for g in profile.goals
        ]
        from agents.profiles import seed_opinions
        self.opinions: dict[str, dict] = seed_opinions(profile.personality, profile.values)

    def restore_from_save(self, data: dict):
        """Restore agent state from a saved dictionary."""
        if data.get("position"):
            self.position = tuple(data["position"])
        if data.get("current_location"):
            self.current_location = data["current_location"]
        if data.get("emotion"):
            self.emotion = data["emotion"]
        if data.get("inner_thought"):
            self.inner_thought = data["inner_thought"]
        if data.get("daily_plan"):
            self.daily_plan = data["daily_plan"]

        # Restore action
        action_str = data.get("current_action", "idle")
        try:
            self.current_action = ActionType(action_str)
        except ValueError:
            self.current_action = ActionType.IDLE

        # Restore state (energy, hunger, mood, wealth)
        if data.get("state"):
            s = data["state"]
            self.state.energy = s.get("energy", self.state.energy)
            self.state.hunger = s.get("hunger", self.state.hunger)
            self.state.mood = s.get("mood", self.state.mood)
            self.state.wealth = s.get("wealth", self.state.wealth)

        # Restore relationships
        if data.get("relationships"):
            self.relationships = data["relationships"]

        # Restore transactions
        if data.get("transactions"):
            self.transactions = data["transactions"][-50:]

        # Restore Phase 1 fields (only override if saved data is non-empty)
        if data.get("secrets") and len(data["secrets"]) > 0:
            self.secrets = data["secrets"]
        if data.get("active_goals") and len(data["active_goals"]) > 0:
            self.active_goals = data["active_goals"]
        if data.get("opinions") and len(data["opinions"]) > 0:
            self.opinions = data["opinions"]
        # Phase 2-3 fields
        if data.get("reputation") and len(data["reputation"]) > 0:
            self.reputation = data["reputation"]
        if data.get("inventory"):
            self.inventory = data["inventory"]
        if data.get("mailbox"):
            self.mailbox = data["mailbox"]
        if data.get("social_commitments"):
            self.social_commitments = data["social_commitments"]

        # Restore memories
        if data.get("memories"):
            for m in data["memories"]:
                self.memory.add(MemoryEntry(
                    tick=m.get("tick", 0),
                    content=m.get("content", ""),
                    importance=m.get("importance", 5.0),
                    memory_type=m.get("type", "observation"),
                    related_agents=m.get("relatedAgents", []),
                    location=m.get("location", ""),
                ))

    def update(self, hour: float, world: World) -> list[dict]:
        """Tick update: follow schedule, move along path."""
        events = []

        # Determine what the schedule says we should be doing
        target_entry = self._get_current_schedule_entry(hour)

        if target_entry and target_entry.location != self.current_location:
            # Need to move to a new location (and not already walking somewhere)
            if self.move_target != target_entry.location and not self.path:
                self._start_walking(target_entry.location)
                events.append({
                    "type": "agent_move",
                    "agentId": self.id,
                    "targetLocation": target_entry.location,
                    "path": list(self.path),
                })

        # Continue walking if we have a path
        if self.path and self.path_index < len(self.path):
            self.current_action = ActionType.WALKING
            self.position = self.path[self.path_index]
            self.path_index += 1

            if self.path_index >= len(self.path):
                # Arrived at destination
                self.path = []
                self.path_index = 0
                if self.move_target:
                    self.current_location = self.move_target
                    self.move_target = None
                if target_entry:
                    self._set_activity(target_entry.activity)
                    events.append(self._make_action_event())
        elif target_entry:
            # At destination, doing scheduled activity
            self._set_activity(target_entry.activity)

        # Update state
        self._update_needs(hour)

        return events

    def _get_current_schedule_entry(self, hour: float) -> Optional[ScheduleEntry]:
        """Find what schedule entry applies at the given hour. Prefers dynamic schedule."""
        # Use dynamic schedule if available, fall back to static
        schedule = self.dynamic_schedule if self.dynamic_schedule else self.schedule
        current = None
        for entry in schedule:
            if hour >= entry.hour:
                current = entry
            else:
                break
        # Handle wrap-around (early morning before first entry)
        if current is None and schedule:
            current = schedule[-1]
        return current

    def _start_walking(self, building_id: str):
        """Calculate path to a building and start walking."""
        target = self.world.get_building_entry(building_id)
        self.path = self.world.find_path(self.position, target)
        self.path_index = 0
        self.move_target = building_id
        self.current_action = ActionType.WALKING

    def _set_activity(self, activity: str):
        """Set current action from schedule activity string."""
        activity_map = {
            "working": ActionType.WORKING,
            "eating": ActionType.EATING,
            "sleeping": ActionType.SLEEPING,
            "reflecting": ActionType.REFLECTING,
            "buying": ActionType.BUYING,
            "selling": ActionType.SELLING,
            "idle": ActionType.IDLE,
        }
        self.current_action = activity_map.get(activity, ActionType.IDLE)

    def _update_needs(self, hour: float):
        """Simple needs simulation."""
        if self.current_action == ActionType.SLEEPING:
            self.state.energy = min(1.0, self.state.energy + 0.01)
            self.state.hunger = min(1.0, self.state.hunger + 0.002)
        elif self.current_action == ActionType.EATING:
            self.state.hunger = max(0.0, self.state.hunger - 0.1)
            self.state.mood = min(1.0, self.state.mood + 0.02)
        elif self.current_action == ActionType.WORKING:
            self.state.energy = max(0.0, self.state.energy - 0.005)
            self.state.hunger = min(1.0, self.state.hunger + 0.005)
        else:
            self.state.energy = max(0.0, self.state.energy - 0.002)
            self.state.hunger = min(1.0, self.state.hunger + 0.003)

    def _make_action_event(self) -> dict:
        return {
            "type": "agent_action",
            "agentId": self.id,
            "action": self.current_action.value,
            "location": list(self.position),
            "targetLocation": self.current_location,
            "emotion": self.emotion,
        }

    def _get_summary(self) -> str:
        """Short summary: who they are + what's been happening."""
        who = f"{self.profile.age}yo {self.profile.job}."
        # Try to find the most recent notable memory
        notable = ""
        for m in reversed(self.memory.memories):
            intensity = getattr(m, "emotional_intensity", getattr(m, "importance", 5) / 10)
            category = getattr(m, "category", getattr(m, "memory_type", ""))
            if intensity >= 0.6 and category in ("reflection", "emotion", "conversation"):
                notable = m.content[:80]
                break
        if not notable:
            # Fall back to backstory excerpt
            notable = self.profile.backstory[:80]
        return f"{who} {notable}"

    def to_dict(self) -> dict:
        """Serialize agent state for WebSocket."""
        # Sync emotion from emotional state system
        dominant_emotion, intensity = self.emotional_state.get_dominant_emotion()
        self.emotion = dominant_emotion if intensity > 0.2 else "neutral"

        return {
            "id": self.id,
            "name": self.name,
            "age": self.profile.age,
            "job": self.profile.job,
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
                "wealth": round(self.state.wealth, 2),
                "debt": round(self.debt, 2),
                "dailyIncome": round(self.daily_income, 2),
                "dailyExpenses": round(self.daily_expenses, 2),
            },
            "emotions": self.emotional_state.to_dict(),
            "drives": self.drives.to_dict(),
            "workingMemory": self.working_memory.to_dict(),
            "transactions": self.transactions[-10:],
        }

    def to_detail_dict(self) -> dict:
        """Full agent detail for inspector panel."""
        return {
            **self.to_dict(),
            "personality": self.profile.personality,
            "values": self.profile.values,
            "goals": [g["text"] for g in self.active_goals if g["status"] == "active"],
            "activeGoals": self.active_goals,
            "fears": self.profile.fears,
            "backstory": self.profile.backstory,
            "dailyPlan": self.daily_plan,
            "secrets": self.secrets,
            "opinions": self.opinions,
            "reputation": self.reputation,
            "inventory": self.inventory,
            "mailbox": self.mailbox,
            "socialCommitments": self.social_commitments,
            "memories": self.episodic_memory.to_list(50),
            "beliefs": self.belief_system.to_list(),
            "mentalModels": self.mental_models.to_dict(),
            "relationships": self.relationships,
            "transactions": self.transactions[-30:],
            "schedule": [
                {"hour": s.hour, "location": s.location, "activity": s.activity}
                for s in self.schedule
            ],
        }
