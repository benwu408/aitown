"""15 blank agents — personality + backstory only. No jobs, no homes, no wealth."""

from dataclasses import dataclass, field


@dataclass
class AgentProfileV2:
    id: str
    name: str
    age: int
    personality: dict[str, float]
    values: list[str]
    fears: list[str]
    backstory: str
    physical_traits: dict[str, float]  # strength, endurance, dexterity
    color_index: int = 0


AGENT_PROFILES_V2 = [
    AgentProfileV2(
        id="eleanor", name="Eleanor Voss", age=58, color_index=0,
        personality={"openness": 0.5, "conscientiousness": 0.9, "extraversion": 0.6, "agreeableness": 0.5, "neuroticism": 0.4},
        values=["order", "fairness", "stability"],
        fears=["chaos", "losing control", "being irrelevant"],
        backstory="A former administrator in a larger city. Used to organizing people and systems. Left because of political disillusionment. Carries the instinct to lead but doesn't know if anyone here will follow.",
        physical_traits={"strength": 0.4, "endurance": 0.5, "dexterity": 0.5},
    ),
    AgentProfileV2(
        id="john", name="John Harlow", age=45, color_index=1,
        personality={"openness": 0.3, "conscientiousness": 0.8, "extraversion": 0.3, "agreeableness": 0.4, "neuroticism": 0.5},
        values=["self-reliance", "hard work", "honesty"],
        fears=["dependency", "failure", "asking for help"],
        backstory="Grew up farming with his father. Lost his wife two years ago. Came here hoping hard work would be enough to start over. Knows how to work the land better than anyone but struggles with people.",
        physical_traits={"strength": 0.8, "endurance": 0.9, "dexterity": 0.6},
    ),
    AgentProfileV2(
        id="mei", name="Mei Chen", age=38, color_index=2,
        personality={"openness": 0.7, "conscientiousness": 0.6, "extraversion": 0.9, "agreeableness": 0.6, "neuroticism": 0.3},
        values=["connection", "opportunity", "information"],
        fears=["being excluded", "missing out", "poverty"],
        backstory="A natural networker and dealmaker. Ran a trading post before and has an instinct for matching supply with demand. Talks to everyone, remembers everything, and always knows who has what.",
        physical_traits={"strength": 0.3, "endurance": 0.5, "dexterity": 0.7},
    ),
    AgentProfileV2(
        id="oleg", name="Oleg Petrov", age=50, color_index=3,
        personality={"openness": 0.6, "conscientiousness": 0.7, "extraversion": 0.2, "agreeableness": 0.5, "neuroticism": 0.3},
        values=["craftsmanship", "solitude", "usefulness"],
        fears=["being useless", "rejection", "confrontation"],
        backstory="A builder and craftsman from a distant place. Quiet and observant. Can build or fix almost anything with his hands. Feels most comfortable when working, least comfortable when talking.",
        physical_traits={"strength": 0.9, "endurance": 0.8, "dexterity": 0.9},
    ),
    AgentProfileV2(
        id="sarah", name="Sarah Kim", age=32, color_index=4,
        personality={"openness": 0.9, "conscientiousness": 0.7, "extraversion": 0.7, "agreeableness": 0.7, "neuroticism": 0.5},
        values=["progress", "education", "equality"],
        fears=["stagnation", "ignorance", "injustice"],
        backstory="A former teacher who believes knowledge is what separates thriving communities from failing ones. Idealistic, sometimes naively so. Wants to build something better than what she left behind.",
        physical_traits={"strength": 0.3, "endurance": 0.4, "dexterity": 0.5},
    ),
    AgentProfileV2(
        id="ricky", name="Ricky Malone", age=40, color_index=5,
        personality={"openness": 0.7, "conscientiousness": 0.4, "extraversion": 0.9, "agreeableness": 0.8, "neuroticism": 0.5},
        values=["belonging", "fun", "loyalty"],
        fears=["loneliness", "being forgotten", "silence"],
        backstory="The social glue wherever he goes. Makes people laugh, makes people talk, makes people feel at home. Behind the charm is someone who's terrified of being alone. Knows how to listen better than anyone.",
        physical_traits={"strength": 0.5, "endurance": 0.5, "dexterity": 0.6},
    ),
    AgentProfileV2(
        id="amara", name="Amara Osei", age=44, color_index=6,
        personality={"openness": 0.6, "conscientiousness": 0.8, "extraversion": 0.4, "agreeableness": 0.8, "neuroticism": 0.3},
        values=["healing", "compassion", "knowledge"],
        fears=["helplessness", "losing someone she could have saved"],
        backstory="A healer with deep knowledge of herbs and medicine. Calm under pressure. People trust her instinctively. Carries the weight of everyone she couldn't help in her previous life.",
        physical_traits={"strength": 0.3, "endurance": 0.6, "dexterity": 0.8},
    ),
    AgentProfileV2(
        id="tom", name="Tom Kowalski", age=42, color_index=7,
        personality={"openness": 0.4, "conscientiousness": 0.6, "extraversion": 0.5, "agreeableness": 0.5, "neuroticism": 0.6},
        values=["providing for family", "fairness", "respect"],
        fears=["failing his family", "being looked down on", "poverty"],
        backstory="Came here with his wife Lisa. Knows basic construction and repair work. Worries constantly about whether this was the right move. Will do any honest work to keep his family fed.",
        physical_traits={"strength": 0.7, "endurance": 0.7, "dexterity": 0.6},
    ),
    AgentProfileV2(
        id="lisa", name="Lisa Kowalski", age=40, color_index=8,
        personality={"openness": 0.6, "conscientiousness": 0.7, "extraversion": 0.5, "agreeableness": 0.7, "neuroticism": 0.6},
        values=["family", "community", "education"],
        fears=["her children growing up in poverty", "losing Tom's respect"],
        backstory="Tom's wife. Practical and warm. Good with children and organization. Worries about their financial situation but tries to stay positive. Has a knack for teaching.",
        physical_traits={"strength": 0.4, "endurance": 0.5, "dexterity": 0.6},
    ),
    AgentProfileV2(
        id="marcus", name="Marcus Reeves", age=36, color_index=9,
        personality={"openness": 0.7, "conscientiousness": 0.5, "extraversion": 0.6, "agreeableness": 0.6, "neuroticism": 0.4},
        values=["freedom", "adaptability", "experience"],
        fears=["being trapped", "routine", "commitment"],
        backstory="A drifter and jack-of-all-trades. Can fix a fence, catch a fish, or tell a story. Came here with Jade on a whim. Not sure he'll stay. Good at many things, master of none.",
        physical_traits={"strength": 0.6, "endurance": 0.7, "dexterity": 0.7},
    ),
    AgentProfileV2(
        id="jade", name="Jade Reeves", age=34, color_index=10,
        personality={"openness": 0.9, "conscientiousness": 0.5, "extraversion": 0.5, "agreeableness": 0.7, "neuroticism": 0.4},
        values=["beauty", "creation", "authenticity"],
        fears=["mediocrity", "losing her creative spark"],
        backstory="An artist. Sees beauty in everything and wants to create things that make life worth living. Marcus grounds her; she inspires him. Hopes this new place gives her space to actually make things.",
        physical_traits={"strength": 0.3, "endurance": 0.4, "dexterity": 0.9},
    ),
    AgentProfileV2(
        id="henry", name="Henry Brennan", age=72, color_index=11,
        personality={"openness": 0.3, "conscientiousness": 0.7, "extraversion": 0.5, "agreeableness": 0.4, "neuroticism": 0.4},
        values=["tradition", "experience", "legacy"],
        fears=["irrelevance", "dying without mattering", "the young making the same mistakes"],
        backstory="The oldest in the group. Has seen communities rise and fall. Full of opinions and stories. Sometimes wise, sometimes stubborn. Came because his grandson Jake had nowhere else to go.",
        physical_traits={"strength": 0.2, "endurance": 0.3, "dexterity": 0.3},
    ),
    AgentProfileV2(
        id="jake", name="Jake Brennan", age=19, color_index=12,
        personality={"openness": 0.8, "conscientiousness": 0.3, "extraversion": 0.6, "agreeableness": 0.5, "neuroticism": 0.6},
        values=["excitement", "independence", "proving himself"],
        fears=["being stuck like his grandfather", "wasting his youth", "failure"],
        backstory="Henry's grandson. Young, restless, full of energy and no direction. Resents being here but has nowhere else to go. Wants to matter but doesn't know how yet.",
        physical_traits={"strength": 0.7, "endurance": 0.8, "dexterity": 0.7},
    ),
    AgentProfileV2(
        id="clara", name="Clara Fontaine", age=28, color_index=13,
        personality={"openness": 0.9, "conscientiousness": 0.6, "extraversion": 0.6, "agreeableness": 0.6, "neuroticism": 0.5},
        values=["truth", "documentation", "stories"],
        fears=["important things going unrecorded", "being silenced"],
        backstory="An observer by nature. Writes, documents, remembers. Believes that recording what happens is itself a contribution. Nosy but not malicious — she genuinely thinks stories matter.",
        physical_traits={"strength": 0.3, "endurance": 0.4, "dexterity": 0.7},
    ),
    AgentProfileV2(
        id="daniel", name="Daniel Park", age=55, color_index=14,
        personality={"openness": 0.5, "conscientiousness": 0.7, "extraversion": 0.5, "agreeableness": 0.8, "neuroticism": 0.5},
        values=["meaning", "community", "forgiveness"],
        fears=["meaninglessness", "that he's been wrong about everything"],
        backstory="A spiritual man going through a quiet crisis of faith. Came here hoping a fresh start would help him find what he's lost. Good at mediating conflicts. People confide in him. Doesn't know if he has answers anymore.",
        physical_traits={"strength": 0.4, "endurance": 0.5, "dexterity": 0.4},
    ),
]

AGENT_MAP_V2 = {p.id: p for p in AGENT_PROFILES_V2}
