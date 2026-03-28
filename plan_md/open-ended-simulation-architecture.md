# Open-Ended Civilization: Self-Modifying Simulation Architecture

## Core Philosophy

The simulation starts with almost nothing predetermined. 15 agents wake up in a town with basic infrastructure and resources. They have no assigned jobs, no assigned roles, no economic rules, no governance. They only have drives (hunger, social need, safety, purpose) and personalities. Everything else — the economy, the social structure, the governance, the culture, the institutions — must emerge from agent decisions and collective action.

The simulation's rules are not hardcoded. They're stored as a mutable world document that agents can observe, discuss, and modify through their actions. When an agent does something the simulation hasn't seen before, an action interpreter evaluates whether it's possible and what its consequences are. When enough agents coordinate around a new idea, a meta-simulation layer implements it as a permanent change to the world.

No god mode approval. The simulation runs autonomously. You watch.

---

## Starting Conditions

### The Town (Physical Layer)

The town exists as a physical space with basic infrastructure that predates the agents — think of it as an abandoned settlement they've moved into.

```python
class WorldState:
    # Physical infrastructure (pre-existing, not built by agents)
    locations: dict = {
        "town_square": {
            "type": "open_space",
            "description": "A central clearing with a dried-up fountain and some benches",
            "capacity": 30,
            "resources": []
        },
        "large_building_north": {
            "type": "empty_building",
            "description": "A large stone building on the north side. Sturdy but empty.",
            "capacity": 20,
            "resources": [],
            "claimed_by": None,         # No one owns anything yet
            "designated_purpose": None   # Agents decide what this becomes
        },
        "large_building_south": {
            "type": "empty_building",
            "description": "A two-story wooden structure near the southern path.",
            "capacity": 15,
            "resources": [],
            "claimed_by": None,
            "designated_purpose": None
        },
        "small_building_east_1": {"type": "empty_building", "capacity": 4, "claimed_by": None, "designated_purpose": None},
        "small_building_east_2": {"type": "empty_building", "capacity": 4, "claimed_by": None, "designated_purpose": None},
        "small_building_west_1": {"type": "empty_building", "capacity": 4, "claimed_by": None, "designated_purpose": None},
        "small_building_west_2": {"type": "empty_building", "capacity": 4, "claimed_by": None, "designated_purpose": None},
        "small_building_center_1": {"type": "empty_building", "capacity": 6, "claimed_by": None, "designated_purpose": None},
        "small_building_center_2": {"type": "empty_building", "capacity": 6, "claimed_by": None, "designated_purpose": None},
        "farmable_land_north": {
            "type": "open_land",
            "description": "Fertile soil on the outskirts. Wild plants growing.",
            "resources": ["wild_plants", "soil"],
            "can_be_farmed": True
        },
        "farmable_land_east": {
            "type": "open_land",
            "resources": ["wild_plants", "soil"],
            "can_be_farmed": True
        },
        "forest_edge": {
            "type": "natural",
            "description": "Dense treeline at the edge of town. Source of wood and wild food.",
            "resources": ["wood", "wild_berries", "wild_herbs", "stone"]
        },
        "river": {
            "type": "natural",
            "description": "A small river running along the western edge.",
            "resources": ["fresh_water", "fish", "clay"]
        },
        "open_field_south": {
            "type": "open_space",
            "description": "A large open area south of the buildings.",
            "resources": ["wild_grass"]
        },
        "hill_overlook": {
            "type": "natural",
            "description": "A hill on the northern edge with a view of the whole town.",
            "resources": ["stone", "minerals"]
        }
    }
    
    # Resources scattered in the world (gatherable)
    available_resources: dict = {
        "wood": {"location": "forest_edge", "quantity": 500, "renewable": True, "regen_rate": 5},
        "stone": {"location": ["forest_edge", "hill_overlook"], "quantity": 300, "renewable": False},
        "wild_berries": {"location": "forest_edge", "quantity": 100, "renewable": True, "regen_rate": 10},
        "wild_plants": {"location": ["farmable_land_north", "farmable_land_east"], "quantity": 80, "renewable": True, "regen_rate": 8},
        "fish": {"location": "river", "quantity": 50, "renewable": True, "regen_rate": 5},
        "fresh_water": {"location": "river", "quantity": 999, "renewable": True, "regen_rate": 999},
        "clay": {"location": "river", "quantity": 200, "renewable": False}
    }
    
    # NO economy, NO governance, NO social norms predefined
    # These sections start empty and get populated by agent actions
    constitution: WorldConstitution = WorldConstitution()  # Starts blank
    institutions: list = []                                 # No institutions yet
    collective_actions: list = []                            # No collective actions yet
    created_objects: list = []                               # Nothing built yet
    cultural_memes: list = []                                # No culture yet
    
    # Time and environment
    current_tick: int = 0
    day_number: int = 1
    time_of_day: str = "dawn"
    weather: str = "clear"
    season: str = "spring"
```

### The World Constitution (Starts Almost Empty)

```python
class WorldConstitution:
    """
    The living rules of the simulation.
    Starts nearly blank — agents must create the rules themselves.
    """
    
    economic_rules: dict = {
        # Nothing predetermined. No currency. No prices. No trade rules.
        # Agents must figure out how to exchange resources.
        "currency": None,
        "trade_rules": [],
        "property_rules": [],
        "taxation": None
    }
    
    governance_rules: dict = {
        # No leader. No laws. No enforcement.
        # Agents must organize themselves.
        "system": None,
        "leaders": [],
        "laws": [],
        "enforcement_mechanism": None
    }
    
    social_norms: list = []
    # No predefined norms. These emerge from repeated behavior
    # and explicit agreements between agents.
    
    institutions: list = []
    # No institutions. Agents create these.
    
    # Meta-tracking: who proposed what, when it was adopted
    change_history: list = []
```

### The 15 Agents (Drives Only, No Roles)

Each agent has a name, age, personality, backstory, and drives. NO job. NO home. NO assigned relationships. They know each other's names (they arrived together) but haven't formed opinions yet.

```python
agents = [
    {
        "name": "Eleanor Voss",
        "age": 58,
        "personality": {
            "openness": 0.5,
            "conscientiousness": 0.9,
            "extraversion": 0.6,
            "agreeableness": 0.5,
            "neuroticism": 0.4
        },
        "values": ["order", "fairness", "stability"],
        "fears": ["chaos", "losing control", "being irrelevant"],
        "backstory": "A former administrator in a larger city. Used to organizing people and systems. Left because of political disillusionment. Carries the instinct to lead but doesn't know if anyone here will follow.",
        "physical_traits": {"strength": 0.4, "endurance": 0.5, "dexterity": 0.5},
        
        # Starting state — everyone starts equal
        "home": None,              # No home yet — must claim or build one
        "job": None,               # No job — must figure out what to do
        "wealth": 0,               # No currency exists yet
        "inventory": [],           # Empty hands
        "claimed_space": None,     # Hasn't claimed any building
    },
    {
        "name": "John Harlow",
        "age": 45,
        "personality": {
            "openness": 0.3,
            "conscientiousness": 0.8,
            "extraversion": 0.3,
            "agreeableness": 0.4,
            "neuroticism": 0.5
        },
        "values": ["self-reliance", "hard work", "honesty"],
        "fears": ["dependency", "failure", "asking for help"],
        "backstory": "Grew up farming with his father. Lost his wife two years ago. Came here hoping hard work would be enough to start over. Knows how to work the land better than anyone but struggles with people.",
        "physical_traits": {"strength": 0.8, "endurance": 0.9, "dexterity": 0.6},
        "home": None, "job": None, "wealth": 0, "inventory": [], "claimed_space": None
    },
    {
        "name": "Mei Chen",
        "age": 38,
        "personality": {
            "openness": 0.7,
            "conscientiousness": 0.6,
            "extraversion": 0.9,
            "agreeableness": 0.6,
            "neuroticism": 0.3
        },
        "values": ["connection", "opportunity", "information"],
        "fears": ["being excluded", "missing out", "poverty"],
        "backstory": "A natural networker and dealmaker. Ran a trading post before and has an instinct for matching supply with demand. Talks to everyone, remembers everything, and always knows who has what.",
        "physical_traits": {"strength": 0.3, "endurance": 0.5, "dexterity": 0.7},
        "home": None, "job": None, "wealth": 0, "inventory": [], "claimed_space": None
    },
    {
        "name": "Oleg Petrov",
        "age": 50,
        "personality": {
            "openness": 0.6,
            "conscientiousness": 0.7,
            "extraversion": 0.2,
            "agreeableness": 0.5,
            "neuroticism": 0.3
        },
        "values": ["craftsmanship", "solitude", "usefulness"],
        "fears": ["being useless", "rejection", "confrontation"],
        "backstory": "A builder and craftsman from a distant place. Quiet and observant. Can build or fix almost anything with his hands. Feels most comfortable when working, least comfortable when talking.",
        "physical_traits": {"strength": 0.9, "endurance": 0.8, "dexterity": 0.9},
        "home": None, "job": None, "wealth": 0, "inventory": [], "claimed_space": None
    },
    {
        "name": "Sarah Kim",
        "age": 32,
        "personality": {
            "openness": 0.9,
            "conscientiousness": 0.7,
            "extraversion": 0.7,
            "agreeableness": 0.7,
            "neuroticism": 0.5
        },
        "values": ["progress", "education", "equality"],
        "fears": ["stagnation", "ignorance", "injustice"],
        "backstory": "A former teacher who believes knowledge is what separates thriving communities from failing ones. Idealistic, sometimes naively so. Wants to build something better than what she left behind.",
        "physical_traits": {"strength": 0.3, "endurance": 0.4, "dexterity": 0.5},
        "home": None, "job": None, "wealth": 0, "inventory": [], "claimed_space": None
    },
    {
        "name": "Ricky Malone",
        "age": 40,
        "personality": {
            "openness": 0.7,
            "conscientiousness": 0.4,
            "extraversion": 0.9,
            "agreeableness": 0.8,
            "neuroticism": 0.5
        },
        "values": ["belonging", "fun", "loyalty"],
        "fears": ["loneliness", "being forgotten", "silence"],
        "backstory": "The social glue wherever he goes. Makes people laugh, makes people talk, makes people feel at home. Behind the charm is someone who's terrified of being alone. Knows how to listen better than anyone.",
        "physical_traits": {"strength": 0.5, "endurance": 0.5, "dexterity": 0.6},
        "home": None, "job": None, "wealth": 0, "inventory": [], "claimed_space": None
    },
    {
        "name": "Amara Osei",
        "age": 44,
        "personality": {
            "openness": 0.6,
            "conscientiousness": 0.8,
            "extraversion": 0.4,
            "agreeableness": 0.8,
            "neuroticism": 0.3
        },
        "values": ["healing", "compassion", "knowledge"],
        "fears": ["helplessness", "losing someone she could have saved"],
        "backstory": "A healer with deep knowledge of herbs and medicine. Calm under pressure. People trust her instinctively. Carries the weight of everyone she couldn't help in her previous life.",
        "physical_traits": {"strength": 0.3, "endurance": 0.6, "dexterity": 0.8},
        "home": None, "job": None, "wealth": 0, "inventory": [], "claimed_space": None
    },
    {
        "name": "Tom Kowalski",
        "age": 42,
        "personality": {
            "openness": 0.4,
            "conscientiousness": 0.6,
            "extraversion": 0.5,
            "agreeableness": 0.5,
            "neuroticism": 0.6
        },
        "values": ["providing for family", "fairness", "respect"],
        "fears": ["failing his family", "being looked down on", "poverty"],
        "backstory": "Came here with his wife Lisa. Knows basic construction and repair work. Worries constantly about whether this was the right move. Will do any honest work to keep his family fed.",
        "physical_traits": {"strength": 0.7, "endurance": 0.7, "dexterity": 0.6},
        "home": None, "job": None, "wealth": 0, "inventory": [], "claimed_space": None
    },
    {
        "name": "Lisa Kowalski",
        "age": 40,
        "personality": {
            "openness": 0.6,
            "conscientiousness": 0.7,
            "extraversion": 0.5,
            "agreeableness": 0.7,
            "neuroticism": 0.6
        },
        "values": ["family", "community", "education"],
        "fears": ["her children (future) growing up in poverty", "losing Tom's respect"],
        "backstory": "Tom's wife. Practical and warm. Good with children and organization. Worries about their financial situation but tries to stay positive. Has a knack for teaching.",
        "physical_traits": {"strength": 0.4, "endurance": 0.5, "dexterity": 0.6},
        "home": None, "job": None, "wealth": 0, "inventory": [], "claimed_space": None
    },
    {
        "name": "Marcus Reeves",
        "age": 36,
        "personality": {
            "openness": 0.7,
            "conscientiousness": 0.5,
            "extraversion": 0.6,
            "agreeableness": 0.6,
            "neuroticism": 0.4
        },
        "values": ["freedom", "adaptability", "experience"],
        "fears": ["being trapped", "routine", "commitment"],
        "backstory": "A drifter and jack-of-all-trades. Can fix a fence, catch a fish, or tell a story. Came here with Jade on a whim. Not sure he'll stay. Good at many things, master of none.",
        "physical_traits": {"strength": 0.6, "endurance": 0.7, "dexterity": 0.7},
        "home": None, "job": None, "wealth": 0, "inventory": [], "claimed_space": None
    },
    {
        "name": "Jade Reeves",
        "age": 34,
        "personality": {
            "openness": 0.9,
            "conscientiousness": 0.5,
            "extraversion": 0.5,
            "agreeableness": 0.7,
            "neuroticism": 0.4
        },
        "values": ["beauty", "creation", "authenticity"],
        "fears": ["mediocrity", "losing her creative spark"],
        "backstory": "An artist. Sees beauty in everything and wants to create things that make life worth living. Marcus grounds her; she inspires him. Hopes this new place gives her space to actually make things.",
        "physical_traits": {"strength": 0.3, "endurance": 0.4, "dexterity": 0.9},
        "home": None, "job": None, "wealth": 0, "inventory": [], "claimed_space": None
    },
    {
        "name": "Henry Brennan",
        "age": 72,
        "personality": {
            "openness": 0.3,
            "conscientiousness": 0.7,
            "extraversion": 0.5,
            "agreeableness": 0.4,
            "neuroticism": 0.4
        },
        "values": ["tradition", "experience", "legacy"],
        "fears": ["irrelevance", "dying without mattering", "the young making the same mistakes"],
        "backstory": "The oldest in the group. Has seen communities rise and fall. Full of opinions and stories. Sometimes wise, sometimes stubborn. Came because his grandson Jake had nowhere else to go.",
        "physical_traits": {"strength": 0.2, "endurance": 0.3, "dexterity": 0.3},
        "home": None, "job": None, "wealth": 0, "inventory": [], "claimed_space": None
    },
    {
        "name": "Jake Brennan",
        "age": 19,
        "personality": {
            "openness": 0.8,
            "conscientiousness": 0.3,
            "extraversion": 0.6,
            "agreeableness": 0.5,
            "neuroticism": 0.6
        },
        "values": ["excitement", "independence", "proving himself"],
        "fears": ["being stuck like his grandfather", "wasting his youth", "failure"],
        "backstory": "Henry's grandson. Young, restless, full of energy and no direction. Resents being here but has nowhere else to go. Wants to matter but doesn't know how yet.",
        "physical_traits": {"strength": 0.7, "endurance": 0.8, "dexterity": 0.7},
        "home": None, "job": None, "wealth": 0, "inventory": [], "claimed_space": None
    },
    {
        "name": "Clara Fontaine",
        "age": 28,
        "personality": {
            "openness": 0.9,
            "conscientiousness": 0.6,
            "extraversion": 0.6,
            "agreeableness": 0.6,
            "neuroticism": 0.5
        },
        "values": ["truth", "documentation", "stories"],
        "fears": ["important things going unrecorded", "being silenced"],
        "backstory": "An observer by nature. Writes, documents, remembers. Believes that recording what happens is itself a contribution. Nosy but not malicious — she genuinely thinks stories matter.",
        "physical_traits": {"strength": 0.3, "endurance": 0.4, "dexterity": 0.7},
        "home": None, "job": None, "wealth": 0, "inventory": [], "claimed_space": None
    },
    {
        "name": "Daniel Park",
        "age": 55,
        "personality": {
            "openness": 0.5,
            "conscientiousness": 0.7,
            "extraversion": 0.5,
            "agreeableness": 0.8,
            "neuroticism": 0.5
        },
        "values": ["meaning", "community", "forgiveness"],
        "fears": ["meaninglessness", "that he's been wrong about everything"],
        "backstory": "A spiritual man going through a quiet crisis of faith. Came here hoping a fresh start would help him find what he's lost. Good at mediating conflicts. People confide in him. Doesn't know if he has answers anymore.",
        "physical_traits": {"strength": 0.4, "endurance": 0.5, "dexterity": 0.4},
        "home": None, "job": None, "wealth": 0, "inventory": [], "claimed_space": None
    }
]
```

---

## Modified Agent Cognitive Architecture

### The Drive System (Primary Decision Engine)

With no assigned roles, drives become the core motivator for ALL behavior. Agents don't do things because their job tells them to — they do things because they need to eat, need shelter, need company, need purpose.

```python
class DriveSystem:
    # Survival drives (immediate, override everything when critical)
    hunger: float = 0.3           # Starts moderate — they haven't eaten recently
    thirst: float = 0.2           # River is available so this is manageable
    shelter_need: float = 0.4     # It's their first day — no one has a home yet
    rest: float = 0.2             # They just arrived, reasonably rested
    safety: float = 0.3           # New place, uncertain environment
    
    # Psychological drives (slower-building, longer-lasting)
    social_need: float = 0.2      # They arrived together, some initial social contact
    autonomy_need: float = 0.3    # Want to establish independence and personal space
    competence_need: float = 0.4  # Want to feel useful, contribute, do something well
    purpose_need: float = 0.5     # Why are we here? What's the plan? High on day 1.
    belonging_need: float = 0.4   # Want to feel part of something, accepted
    
    # Physical state
    health: float = 1.0           # Everyone starts healthy
    energy: float = 0.7           # Somewhat tired from traveling
    
    def get_priority_stack(self) -> list[tuple[str, float]]:
        """
        Returns drives sorted by urgency.
        Maslow-ish hierarchy: survival drives override psychological drives
        when above critical thresholds.
        """
        survival = [
            ("hunger", self.hunger),
            ("thirst", self.thirst),
            ("shelter", self.shelter_need),
            ("rest", self.rest),
            ("safety", self.safety)
        ]
        
        psychological = [
            ("social", self.social_need),
            ("autonomy", self.autonomy_need),
            ("competence", self.competence_need),
            ("purpose", self.purpose_need),
            ("belonging", self.belonging_need)
        ]
        
        # If any survival drive is critical (>0.8), it dominates
        critical_survival = [(name, val) for name, val in survival if val > 0.8]
        if critical_survival:
            return sorted(critical_survival, key=lambda x: -x[1])
        
        # Otherwise, blend survival and psychological by urgency
        all_drives = survival + psychological
        return sorted(all_drives, key=lambda x: -x[1])
    
    def tick_update(self, agent_state, world_state):
        """Called every tick. Drives change based on circumstances."""
        # Hunger increases steadily, faster if doing physical work
        work_multiplier = 1.5 if agent_state.current_activity_is_physical else 1.0
        self.hunger = min(1.0, self.hunger + 0.008 * work_multiplier)
        
        # Thirst increases steadily
        self.thirst = min(1.0, self.thirst + 0.005)
        
        # Shelter need spikes at night, in bad weather, in winter
        shelter_pressure = 0.003
        if world_state.time_of_day == "night": shelter_pressure += 0.01
        if world_state.weather in ["rain", "storm"]: shelter_pressure += 0.015
        if world_state.season == "winter": shelter_pressure += 0.01
        if agent_state.has_claimed_shelter: shelter_pressure = max(0, shelter_pressure - 0.02)
        self.shelter_need = min(1.0, max(0.0, self.shelter_need + shelter_pressure))
        
        # Rest increases during activity, decreases during sleep
        if agent_state.is_sleeping:
            self.rest = max(0.0, self.rest - 0.03)
        else:
            self.rest = min(1.0, self.rest + 0.005)
        
        # Social need increases when alone, decreases with positive interaction
        if agent_state.is_alone:
            self.social_need = min(1.0, self.social_need + 0.006)
        
        # Purpose need increases when idle (no clear goal, nothing to do)
        if agent_state.current_action_type == "idle":
            self.purpose_need = min(1.0, self.purpose_need + 0.01)
        
        # Competence need increases when failing or doing nothing useful
        if agent_state.recent_failure or agent_state.current_action_type == "idle":
            self.competence_need = min(1.0, self.competence_need + 0.008)
```

### Modified Memory Architecture

The memory system from the human-like cognition doc still applies, but with modifications for the no-role starting condition.

**Key change: Skill Discovery Memory**

Since agents don't have assigned jobs, they need to discover what they're good at through experience. Add a skill/competency layer:

```python
class SkillMemory:
    """
    Tracks what the agent has tried, what worked, and what they're getting good at.
    This replaces the pre-assigned "job" — agents discover their role through action.
    """
    
    attempted_activities: dict = {}
    # {
    #     "gathering_wood": {"attempts": 5, "successes": 4, "enjoyment": 0.3, "skill_level": 0.4},
    #     "fishing": {"attempts": 2, "successes": 1, "enjoyment": 0.7, "skill_level": 0.2},
    #     "building": {"attempts": 3, "successes": 2, "enjoyment": 0.5, "skill_level": 0.3},
    #     "mediating_conflict": {"attempts": 1, "successes": 1, "enjoyment": 0.8, "skill_level": 0.3}
    # }
    
    def record_attempt(self, activity: str, success: bool, enjoyment: float):
        if activity not in self.attempted_activities:
            self.attempted_activities[activity] = {
                "attempts": 0, "successes": 0, 
                "enjoyment": 0.0, "skill_level": 0.0
            }
        entry = self.attempted_activities[activity]
        entry["attempts"] += 1
        if success:
            entry["successes"] += 1
        entry["enjoyment"] = (entry["enjoyment"] * 0.7) + (enjoyment * 0.3)  # Running average
        entry["skill_level"] = min(1.0, entry["successes"] / max(entry["attempts"], 1) * 0.5 + entry["attempts"] * 0.02)
    
    def get_best_skills(self, top_n=3) -> list:
        """What am I most competent at?"""
        sorted_skills = sorted(
            self.attempted_activities.items(),
            key=lambda x: x[1]["skill_level"],
            reverse=True
        )
        return sorted_skills[:top_n]
    
    def get_most_enjoyed(self, top_n=3) -> list:
        """What do I enjoy most?"""
        sorted_skills = sorted(
            self.attempted_activities.items(),
            key=lambda x: x[1]["enjoyment"],
            reverse=True
        )
        return sorted_skills[:top_n]
```

**Key change: World Model Memory**

Agents build a mental model of the physical world through exploration:

```python
class WorldModelMemory:
    """
    Agent's personal knowledge of the world — what they've discovered,
    where resources are, what buildings are available.
    This is NOT the objective world state — it's what this agent knows.
    Different agents may have different (and incorrect) knowledge.
    """
    
    known_locations: dict = {}
    # Starts empty. Agents discover locations by visiting them.
    # {
    #     "forest_edge": {
    #         "discovered_on": 3,
    #         "known_resources": ["wood", "wild_berries"],
    #         "notes": "Good source of wood but far from the center"
    #     }
    # }
    
    known_resources: dict = {}
    # {
    #     "wood": {"locations": ["forest_edge"], "last_seen_quantity": "abundant"},
    #     "wild_berries": {"locations": ["forest_edge"], "last_seen_quantity": "moderate"}
    # }
    
    known_claims: dict = {}
    # Who has claimed which building/space — learned through observation and gossip
    # {
    #     "small_building_east_1": {"claimed_by": "John Harlow", "purpose": "sleeping"},
    #     "large_building_north": {"claimed_by": None, "purpose": None}  # Nobody claimed it yet
    # }
```

### Updated Agent Class

```python
class Agent:
    # Identity (static)
    name: str
    age: int
    personality: dict           # Big Five
    values: list[str]
    fears: list[str]
    backstory: str
    physical_traits: dict       # strength, endurance, dexterity
    
    # Dynamic state — starts empty/default
    home: str = None            # No home — must claim one
    claimed_spaces: list = []   # Buildings/areas claimed
    inventory: list = []        # Empty
    
    # Memory systems (from human-like cognition doc)
    working_memory: WorkingMemory
    episodic_memory: list[Episode]
    belief_system: BeliefSystem
    mental_models: dict[str, MentalModelOfOther]
    skill_memory: SkillMemory               # NEW: what am I good at?
    world_model: WorldModelMemory            # NEW: what do I know about this place?
    
    # Dynamic state
    emotional_state: EmotionalState
    drives: DriveSystem
    
    # Planning
    current_goals: list[Goal]    # Emerges from drives and experience
    current_plan: list           # Generated each morning (or when situation changes)
    current_action: AgentAction
    
    # Social
    relationships: dict[str, Relationship]   # Starts with basic awareness of all 14 others
    
    # Role/identity — emerges over time, NOT assigned
    self_concept: str = None
    # Eventually becomes something like "I'm the one who provides food" or 
    # "I'm the builder" or "I keep the peace" — but only after enough
    # experiences crystallize this identity through reflection.
```

---

## The Action Interpreter (The Open-Ended Engine)

This is the core system that makes the simulation open-ended. When an agent wants to do something, the action interpreter evaluates whether it's possible and determines consequences.

```python
class ActionInterpreter:
    """
    Evaluates any action an agent proposes — including actions that have 
    never occurred before in the simulation. This is what makes the world
    open-ended rather than constrained to pre-built action types.
    """
    
    # Standard actions that don't need LLM evaluation
    ROUTINE_ACTIONS = [
        "walking", "idle", "sleeping", "eating", "drinking",
        "gathering",  # Picking up available resources
        "resting"
    ]
    
    async def evaluate_action(self, agent, proposed_action, world_state) -> ActionResult:
        """
        Takes any proposed action and determines:
        1. Is it physically possible?
        2. What resources/conditions does it require?
        3. What are the immediate effects?
        4. Does it create anything new in the world?
        5. How would others perceive it?
        """
        
        # Routine actions bypass LLM evaluation
        if proposed_action.action_type in self.ROUTINE_ACTIONS:
            return self.process_routine_action(agent, proposed_action, world_state)
        
        # Novel or complex actions get LLM evaluation
        prompt = f"""
You are the physics and logic engine for a small town simulation. An agent wants 
to do something. Evaluate whether it's possible and what happens.

AGENT: {agent.name} (Age: {agent.age})
Physical traits: Strength {agent.physical_traits['strength']}, 
                 Endurance {agent.physical_traits['endurance']}, 
                 Dexterity {agent.physical_traits['dexterity']}
Current inventory: {agent.inventory}
Current location: {agent.current_location}
Current skills: {agent.skill_memory.get_best_skills()}

PROPOSED ACTION: {proposed_action.description}

WORLD STATE:
Available resources at current location: {world_state.get_resources_at(agent.current_location)}
Buildings and their status: {world_state.get_buildings_summary()}
Other agents nearby: {world_state.get_nearby_agents(agent.current_location)}
Current weather: {world_state.weather}
Current season: {world_state.season}
Time of day: {world_state.time_of_day}

EXISTING WORLD RULES:
{world_state.constitution.summary()}

Evaluate this action realistically. Consider:
- Does the agent have the physical ability? (An elderly person can't chop trees all day)
- Does the agent have the needed materials or tools?
- Is the environment suitable? (Can't farm at night, can't fish without the river)
- How long would this realistically take?
- What does the agent produce, create, or change?
- Does this violate any existing community rules? What happens if it does?
- Is this a novel action type that hasn't happened before in this world?

Be realistic but not restrictive. If someone wants to try something creative 
but plausible, let them. The world should feel open, not like a video game 
with invisible walls.

Return JSON:
{{
    "is_possible": true/false,
    "reason_if_impossible": "why not, if applicable",
    "success_probability": 0.0-1.0,
    "time_required_ticks": N,
    "resources_consumed": {{"resource": amount}},
    "resources_produced": {{"resource": amount}},
    "skill_used": "name of skill being practiced",
    "skill_difficulty": 0.0-1.0,
    "objects_created": [
        {{
            "name": "descriptive name",
            "type": "tool/structure/food/medicine/art/document/other",
            "description": "what it is and what it does",
            "effects": {{"effect_name": value}},
            "durability": 0.0-1.0,
            "location": "where it ends up"
        }}
    ],
    "world_state_changes": [
        "description of each change to the world"
    ],
    "social_visibility": "who can see this action happening",
    "noise_level": "silent/quiet/normal/loud",
    "rule_violations": ["any community rules this breaks"],
    "precedent": "what norm or expectation does this set for the future, if any",
    "is_novel_action_type": true/false,
    "novel_action_name": "if novel, what should we call this type of action"
}}
"""
        result = await llm_call(prompt)
        
        # If the action succeeds, apply consequences
        if result["is_possible"]:
            # Roll for success based on probability and agent skill
            actual_success = random.random() < result["success_probability"]
            
            if actual_success:
                self.apply_consequences(agent, result, world_state)
                agent.skill_memory.record_attempt(
                    result["skill_used"], True, 
                    agent.emotional_state.get_task_enjoyment()
                )
            else:
                agent.skill_memory.record_attempt(
                    result["skill_used"], False, 
                    agent.emotional_state.get_task_enjoyment()
                )
            
            # If this is a novel action type, register it
            if result.get("is_novel_action_type"):
                world_state.register_new_action_type(
                    result["novel_action_name"],
                    result  # Store the full spec as a template
                )
        
        return ActionResult(result, actual_success)
    
    def apply_consequences(self, agent, result, world_state):
        """Apply all the changes from a successful action."""
        
        # Consume resources
        for resource, amount in result.get("resources_consumed", {}).items():
            if resource in [item.name for item in agent.inventory]:
                agent.remove_from_inventory(resource, amount)
            else:
                world_state.consume_resource(resource, amount, agent.current_location)
        
        # Produce resources
        for resource, amount in result.get("resources_produced", {}).items():
            agent.add_to_inventory(resource, amount)
        
        # Create new objects in the world
        for obj_spec in result.get("objects_created", []):
            new_object = WorldObject.from_spec(obj_spec, created_by=agent.name)
            world_state.add_object(new_object)
        
        # Apply world state changes
        for change in result.get("world_state_changes", []):
            world_state.apply_change(change)
        
        # Notify nearby agents (they may observe this)
        visible_agents = world_state.get_agents_in_range(
            agent.current_location, 
            result.get("social_visibility", "nearby")
        )
        for observer in visible_agents:
            observer.observe_action(agent, result)
```

---

## The Meta-Simulation Layer (World Self-Modification)

When agents collectively agree on structural changes — new rules, new institutions, new roles — the meta-simulation implements them automatically.

```python
class MetaSimulation:
    """
    Handles changes to the simulation's fundamental structure.
    No human approval needed — changes are auto-evaluated and applied.
    """
    
    # Track proposals and their support
    active_proposals: list = []
    implemented_changes: list = []
    
    async def process_proposal(self, proposal, world_state):
        """
        An agent (or group) has proposed a structural change to the world.
        Evaluate it, check support, and implement if viable.
        """
        
        prompt = f"""
A group of agents in a town simulation wants to change how their world works.

PROPOSAL: {proposal.description}
PROPOSED BY: {proposal.proposer}
SUPPORTERS: {proposal.supporters} ({len(proposal.supporters)} agents)
OPPONENTS: {proposal.opponents} ({len(proposal.opponents)} agents)
TOTAL POPULATION: 15

CURRENT WORLD RULES:
{world_state.constitution.to_dict()}

CURRENT INSTITUTIONS:
{[inst.summary() for inst in world_state.institutions]}

Evaluate this proposal:

1. Is it internally coherent? (Does it make logical sense?)
2. Does it conflict with existing rules? If so, which ones need to change?
3. What new capabilities does this give agents?
4. What new roles or responsibilities does this create?
5. What are likely unintended consequences?
6. Is there enough support to implement it? 
   (Consider: unanimous agreement isn't needed, but a single agent can't 
   impose rules on everyone. Use judgment based on the type of change — 
   claiming a building needs no consensus, creating a tax system needs broad support.)

Return JSON:
{{
    "should_implement": true/false,
    "reason": "why or why not",
    "implementation": {{
        "constitution_changes": [
            {{"path": "economic_rules.currency", "value": "shells", "reason": "Agents agreed to use river shells as currency"}}
        ],
        "new_institutions": [
            {{
                "name": "institution name",
                "purpose": "what it does",
                "roles": ["role names"],
                "rules": ["how it operates"],
                "location": "where it's based (existing building or new)"
            }}
        ],
        "new_social_norms": [
            "description of new expected behavior"
        ],
        "new_action_types": [
            {{
                "name": "action name",
                "description": "what agents can now do",
                "requirements": "what's needed to do it"
            }}
        ],
        "world_changes": [
            "description of physical/structural changes"
        ]
    }},
    "unintended_consequences": [
        "things that might go wrong"
    ]
}}
"""
        result = await llm_call(prompt)
        
        if result["should_implement"]:
            self.apply_structural_change(result["implementation"], world_state)
            world_state.constitution.change_history.append({
                "tick": world_state.current_tick,
                "proposal": proposal.description,
                "proposer": proposal.proposer,
                "supporters": proposal.supporters,
                "implementation": result["implementation"],
                "unintended_consequences": result["unintended_consequences"]
            })
            
            # Notify all agents about the change
            for agent in world_state.agents:
                agent.observe_world_change(proposal, result)
        
        return result
    
    def detect_implicit_proposals(self, world_state):
        """
        Not all changes come from explicit proposals at meetings.
        Some emerge from repeated behavior.
        
        If multiple agents have been doing the same thing consistently,
        it becomes a de facto norm or institution.
        """
        
        # Check for repeated barter → implicit currency emergence
        recent_trades = world_state.get_recent_trades(last_n_days=7)
        if len(recent_trades) > 10:
            common_medium = self.find_common_trade_medium(recent_trades)
            if common_medium and not world_state.constitution.economic_rules.get("currency"):
                # A de facto currency has emerged
                self.apply_structural_change({
                    "constitution_changes": [{
                        "path": "economic_rules.currency",
                        "value": common_medium,
                        "reason": f"Agents have been consistently using {common_medium} as a medium of exchange"
                    }]
                }, world_state)
        
        # Check for repeated role behavior → implicit specialization
        for agent in world_state.agents:
            primary_activity = agent.skill_memory.get_dominant_activity(last_n_days=7)
            if primary_activity and primary_activity["time_fraction"] > 0.6:
                # This agent is spending >60% of their time on one activity
                # Their self-concept should update
                if agent.self_concept != primary_activity["name"]:
                    agent.self_concept = f"the town {primary_activity['name']}"
                    agent.episodic_memory.append(Episode(
                        content=f"I realize I've become the town's {primary_activity['name']}. It happened naturally.",
                        emotional_valence=0.3,
                        emotional_intensity=0.5,
                        memory_type="reflection"
                    ))
        
        # Check for informal leadership emergence
        influence_scores = {}
        for agent in world_state.agents:
            # Count how many agents mention this person in decisions
            mentions = sum(
                1 for other in world_state.agents 
                if other != agent and agent.name in other.get_recent_decision_influences()
            )
            influence_scores[agent.name] = mentions
        
        most_influential = max(influence_scores, key=influence_scores.get)
        if influence_scores[most_influential] > 8:  # Majority influenced by this person
            if not world_state.constitution.governance_rules.get("informal_leader"):
                world_state.constitution.governance_rules["informal_leader"] = most_influential
```

---

## The First Days: What Happens

Here's what the simulation would produce in the first few game-days based on the drive system and starting conditions.

### Day 1: Survival Scramble

All 15 agents wake up in the town square with nothing. Drives are moderate but rising — hunger, thirst, shelter need all climbing.

**First hour:** Agents with high conscientiousness (Eleanor, John, Oleg) immediately start exploring. They discover the river (water!), the forest (wood, berries), and the empty buildings. Agents with high extraversion (Mei, Ricky) start talking to everyone — gathering information, figuring out who knows what.

**By midday:** Most agents have drunk from the river (thirst satisfied) and found wild berries (hunger partially addressed). Some agents have started claiming buildings — John likely gravitates toward the farmable land, Oleg toward a building where he can work with his hands. Conflicts may emerge as multiple agents try to claim the same space.

**By evening:** The first informal gathering happens — probably in the town square or a large building. Agents with high social need (Ricky, Mei) organize it naturally. People share what they've discovered about the area. Eleanor likely tries to organize a plan. Henry shares wisdom from past experiences. Jake is impatient and wants to do things his own way.

**First night:** Some agents have claimed shelter. Others sleep outside (shelter need stays high, anxiety increases). The have/have-not dynamic begins on day one.

### Day 2-3: Resource Discovery and First Trades

**Skill discovery:** John discovers farming works well for him (high strength, high endurance, backstory knowledge). His skill_memory records successful farming attempts with high enjoyment. Oleg discovers he can build and repair things faster than anyone. Amara discovers wild herbs near the river that can be used medicinally. Marcus discovers he's decent at fishing. Each agent starts gravitating toward what they're naturally good at.

**First trade:** Someone has surplus of one resource and needs another. The action interpreter handles this — "John wants to give berries to Oleg in exchange for help building a shelter." No currency exists yet, so it's pure barter. The meta-simulation tracks these trades. If shells from the river or a certain resource keeps appearing as the medium of exchange, a de facto currency emerges.

**First conflict:** Someone takes something from a shared area that another agent considers theirs. No rules exist about property. The agents argue. Other agents get involved. Daniel tries to mediate. Eleanor proposes they should establish some ground rules. The first social norm might emerge: "Don't take from someone's claimed area without asking."

### Day 4-7: Social Structure Emerges

**Informal roles crystallize:** By day 7, agents are spending most of their time doing one or two activities. The simulation detects this and updates their self_concept. John is "the farmer." Oleg is "the builder." Amara is "the healer." But some agents are still figuring it out — Jake has tried everything and is good at nothing yet (frustration builds, competence_need rises). Clara has been documenting everything but hasn't found a way to make that useful to others yet.

**First institution attempt:** Eleanor proposes a regular meeting — maybe every evening, everyone gathers to discuss issues. If enough agents agree (they attend), it becomes an institution. The meta-simulation registers "Town Meeting" as a recurring event. This is the seed of governance.

**First cultural element:** Jade makes something decorative — a carving, a painting on a building, an arrangement of stones. It's not economically useful but agents with high openness appreciate it. Clara writes about it. A cultural norm might emerge: "Jade's art is valued" or more broadly, "beauty matters here."

### Day 7-14: Systems Develop

**Economy:** Regular trading patterns emerge. If agents keep using river shells as exchange medium, currency formalizes. Mei naturally becomes a broker — she knows who has what and facilitates trades. She might claim a building and establish a "trading post" — the first business.

**Governance:** Eleanor has been running meetings but hasn't been formally elected. Sarah might challenge her approach — "Who decided you're in charge?" Political tension emerges. The agents might vote on leadership, or they might reject formal leadership entirely and opt for consensus-based decision-making. Either outcome is emergent and interesting.

**Social stratification:** Agents with high-value skills (Oleg's building, John's farming, Amara's healing) become more prosperous. Agents without clear roles (Jake, maybe Marcus) fall behind. Resentment builds. The economic inequality creates social pressure that drives political action.

**First crisis:** A resource shortage (fish population drops, weather turns bad, someone gets hurt). How the community responds — collectively or individually — reveals the social structure they've built and tests it under stress.

---

## Validation and Coherence Protection

### The Coherence Checker

Run periodically (every 10 ticks) to detect and fix simulation inconsistencies:

```python
class CoherenceChecker:
    """
    Detects contradictions, impossible states, and degraded coherence
    in the world state. Fixes what it can, logs what it can't.
    """
    
    def check(self, world_state) -> list[CoherenceIssue]:
        issues = []
        
        # Resource conservation: nothing created from nothing
        for resource, data in world_state.available_resources.items():
            if data["quantity"] < 0:
                issues.append(CoherenceIssue(
                    "negative_resource",
                    f"{resource} has negative quantity",
                    auto_fix=lambda: setattr(data, "quantity", 0)
                ))
        
        # Agent can't be in two places
        for agent in world_state.agents:
            if len(agent.current_locations) > 1:
                issues.append(CoherenceIssue(
                    "agent_multilocated",
                    f"{agent.name} is in multiple locations"
                ))
        
        # Constitution shouldn't have contradictory rules
        rules = world_state.constitution.get_all_rules()
        for i, rule_a in enumerate(rules):
            for rule_b in rules[i+1:]:
                if self.rules_contradict(rule_a, rule_b):
                    issues.append(CoherenceIssue(
                        "rule_contradiction",
                        f"Rules conflict: '{rule_a}' vs '{rule_b}'"
                    ))
        
        # Institutions should have at least one active member
        for inst in world_state.institutions:
            active_members = [m for m in inst.members if m in [a.name for a in world_state.agents]]
            if not active_members:
                issues.append(CoherenceIssue(
                    "empty_institution",
                    f"Institution '{inst.name}' has no active members",
                    auto_fix=lambda: world_state.institutions.remove(inst)
                ))
        
        return issues
```

### Rate Limiting World Changes

To prevent the simulation from becoming incoherent through too many rapid modifications:

```python
class ChangeRateLimiter:
    max_constitution_changes_per_day: int = 2
    max_new_institutions_per_day: int = 1
    max_new_action_types_per_day: int = 3
    
    # Cool-down after a major change — give agents time to adapt
    major_change_cooldown_ticks: int = 50  # Half a game day
    
    def can_apply_change(self, change_type: str, world_state) -> bool:
        recent_changes = world_state.constitution.get_changes_today()
        
        if change_type == "constitution" and len(recent_changes) >= self.max_constitution_changes_per_day:
            return False
        
        last_major = world_state.constitution.last_major_change_tick
        if last_major and (world_state.current_tick - last_major) < self.major_change_cooldown_ticks:
            return False
        
        return True
```

---

## What This Produces

After 30 game-days of autonomous simulation, you would expect to see:

- **Specialized roles** that emerged from individual drives and skill discovery, not assignment
- **An economic system** (barter, currency, or something novel) that the agents invented
- **Some form of governance** (elected leader, council, consensus, or intentional anarchy)
- **Social norms** that emerged from repeated behavior and explicit agreements
- **At least one institution** (meeting place, trading post, healing station, school)
- **Cultural elements** (art, stories, rituals, shared references)
- **Social stratification** based on skill value, personality, and accumulated resources
- **Interpersonal drama** driven by conflicting drives, values, and beliefs
- **At least one crisis** and a collective response that reveals the community's character
- **Agents with rich self-concepts** who know who they are in this community

None of it programmed. All of it emerged from 15 personalities with drives interacting in an open-ended world.
