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
        self.schedule = profile.schedule
        self._current_schedule_index = 0

        # Cognition
        self.inner_thought: str = ""
        self.daily_plan: str = ""
        self.memory = MemoryStream()
        self.relationships: dict[str, dict] = dict(profile.relationships)
        self.transactions: list[dict] = []  # {tick, item, price, action}

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
            # Need to move to a new location
            if self.move_target != target_entry.location:
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
        """Find what schedule entry applies at the given hour."""
        current = None
        for entry in self.schedule:
            if hour >= entry.hour:
                current = entry
            else:
                break
        # Handle wrap-around (early morning before first entry)
        if current is None and self.schedule:
            current = self.schedule[-1]
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

    def to_dict(self) -> dict:
        """Serialize agent state for WebSocket."""
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
            "state": {
                "energy": round(self.state.energy, 2),
                "hunger": round(self.state.hunger, 2),
                "mood": round(self.state.mood, 2),
                "wealth": self.state.wealth,
            },
        }

    def to_detail_dict(self) -> dict:
        """Full agent detail for inspector panel."""
        return {
            **self.to_dict(),
            "personality": self.profile.personality,
            "values": self.profile.values,
            "goals": self.profile.goals,
            "fears": self.profile.fears,
            "backstory": self.profile.backstory,
            "dailyPlan": self.daily_plan,
            "memories": self.memory.to_list(50),
            "relationships": self.relationships,
            "transactions": self.transactions[-30:],
            "schedule": [
                {"hour": s.hour, "location": s.location, "activity": s.activity}
                for s in self.schedule
            ],
        }
