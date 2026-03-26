from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ActionType(str, Enum):
    IDLE = "idle"
    WALKING = "walking"
    WORKING = "working"
    TALKING = "talking"
    BUYING = "buying"
    SELLING = "selling"
    EATING = "eating"
    SLEEPING = "sleeping"
    DELIVERING = "delivering"
    ATTENDING_EVENT = "attending_event"
    REFLECTING = "reflecting"
    ARGUING = "arguing"
    CELEBRATING = "celebrating"
    STEALING = "stealing"
    GIVING = "giving"
    ANNOUNCING = "announcing"


@dataclass
class AgentAction:
    agent_id: str
    action_type: ActionType
    target_location: Optional[str] = None
    target_agent: Optional[str] = None
    item: Optional[str] = None
    speech: Optional[str] = None
    inner_thought: Optional[str] = None
    emotion: str = "neutral"
    is_stealth: bool = False
    metadata: dict = field(default_factory=dict)

    def to_event(self) -> dict:
        return {
            "type": "agent_action",
            "agentId": self.agent_id,
            "action": self.action_type.value,
            "targetLocation": self.target_location,
            "targetAgent": self.target_agent,
            "item": self.item,
            "speech": self.speech,
            "innerThought": self.inner_thought,
            "emotion": self.emotion,
            "isStealth": self.is_stealth,
        }
