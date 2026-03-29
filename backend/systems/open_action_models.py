"""Typed models for the open-ended action system."""

from dataclasses import dataclass, field
import uuid


@dataclass
class ActionIntent:
    agent_name: str
    description: str
    tick_started: int
    context: dict = field(default_factory=dict)


@dataclass
class ObjectSpec:
    name: str
    description: str
    category: str  # tool/structure/container/food/medicine/art/clothing/document/marker/furniture/mechanism/other
    effects: dict = field(default_factory=dict)
    durability: float = 1.0
    size: str = "small"  # tiny/small/medium/large/structure
    portable: bool = True
    visual_description: str = ""


@dataclass
class WorldChange:
    type: str  # terrain_modification/new_path/building_modification/resource_change/boundary_marker/other
    description: str = ""
    location: str = ""
    permanent: bool = False
    visual_change: str = ""


@dataclass
class SuccessOutcome:
    description: str = ""
    objects_created: list[ObjectSpec] = field(default_factory=list)
    resources_produced: dict[str, float] = field(default_factory=dict)
    world_changes: list[WorldChange] = field(default_factory=list)
    skill_practiced: str = ""
    skill_difficulty: float = 0.5
    knowledge_gained: str = ""


@dataclass
class FailureOutcome:
    description: str = ""
    materials_wasted: dict[str, float] = field(default_factory=dict)
    partial_result: str | None = None
    injury_risk: float = 0.0
    injury_description: str = ""


@dataclass
class Observability:
    who_can_see: str = "anyone at this location"
    what_they_see: str = ""
    noise_level: str = "normal"  # silent/quiet/normal/loud
    duration_visible: str = "brief moment"


@dataclass
class SocialImplications:
    rules_violated: list[str] = field(default_factory=list)
    precedent: str = ""
    likely_reactions: str = ""


@dataclass
class ActionEvaluation:
    feasible: bool = False
    why_not: str = ""
    success_chance: float = 0.0
    time_ticks: int = 1
    energy_cost: float = 0.1
    materials_consumed: dict[str, float] = field(default_factory=dict)
    on_success: SuccessOutcome = field(default_factory=SuccessOutcome)
    on_failure: FailureOutcome = field(default_factory=FailureOutcome)
    observability: Observability = field(default_factory=Observability)
    social_implications: SocialImplications = field(default_factory=SocialImplications)
    unlocks: list[str] = field(default_factory=list)


@dataclass
class ActionResult:
    intent: ActionIntent
    evaluation: ActionEvaluation
    success: bool
    outcome: SuccessOutcome | FailureOutcome
    tick_completed: int = 0


@dataclass
class WorldObject:
    id: str
    name: str
    description: str
    category: str
    effects: dict = field(default_factory=dict)
    durability: float = 1.0
    size: str = "small"
    portable: bool = True
    visual_description: str = ""
    created_by: str = ""
    created_on: int = 0
    location: str | None = None
    owner: str | None = None

    @staticmethod
    def generate_id() -> str:
        return f"obj_{uuid.uuid4().hex[:8]}"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "effects": self.effects,
            "durability": self.durability,
            "size": self.size,
            "portable": self.portable,
            "visual_description": self.visual_description,
            "created_by": self.created_by,
            "created_on": self.created_on,
            "location": self.location,
            "owner": self.owner,
        }

    @staticmethod
    def from_dict(d: dict) -> "WorldObject":
        return WorldObject(
            id=d["id"], name=d["name"], description=d.get("description", ""),
            category=d.get("category", "other"), effects=d.get("effects", {}),
            durability=d.get("durability", 1.0), size=d.get("size", "small"),
            portable=d.get("portable", True), visual_description=d.get("visual_description", ""),
            created_by=d.get("created_by", ""), created_on=d.get("created_on", 0),
            location=d.get("location"), owner=d.get("owner"),
        )


@dataclass
class ObservationRecord:
    observer: str
    actor: str
    what_seen: str
    result_visible: bool
    objects_visible: list[str] = field(default_factory=list)
    location: str = ""
    tick: int = 0
