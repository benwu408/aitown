"""All 15 agent definitions with personalities, homes, workplaces, and schedules."""

from dataclasses import dataclass, field


@dataclass
class ScheduleEntry:
    hour: float  # 0-24
    location: str  # building_id
    activity: str  # action description


@dataclass
class AgentProfile:
    id: str
    name: str
    age: int
    job: str
    workplace: str
    home: str
    personality: dict[str, float]  # Big Five traits (0-1)
    values: list[str]
    goals: list[str]
    fears: list[str]
    backstory: str
    wealth: int
    schedule: list[ScheduleEntry]
    relationships: dict[str, dict] = field(default_factory=dict)
    color_index: int = 0
    secrets: list[dict] = field(default_factory=list)


# Town topics for opinion system
TOWN_TOPICS = ["taxes", "clinic_funding", "modernization", "outsiders", "school_budget", "tradition"]


def seed_opinions(personality: dict[str, float], values: list[str]) -> dict[str, dict]:
    """Generate initial opinions based on personality traits and values."""
    o = personality.get("openness", 0.5)
    c = personality.get("conscientiousness", 0.5)
    a = personality.get("agreeableness", 0.5)
    opinions = {}
    opinions["taxes"] = {"stance": round((c - 0.5) * 0.6, 2), "confidence": 0.3, "last_updated": 0}
    opinions["clinic_funding"] = {"stance": round((a - 0.3) * 0.8, 2), "confidence": 0.3, "last_updated": 0}
    opinions["modernization"] = {"stance": round((o - 0.5) * 1.0, 2), "confidence": 0.3, "last_updated": 0}
    opinions["outsiders"] = {"stance": round((o + a - 1.0) * 0.5, 2), "confidence": 0.2, "last_updated": 0}
    opinions["school_budget"] = {"stance": round((o - 0.3) * 0.6, 2), "confidence": 0.2, "last_updated": 0}
    opinions["tradition"] = {"stance": round((c - o) * 0.8, 2), "confidence": 0.3, "last_updated": 0}
    # Boost confidence for values-aligned topics
    if "tradition" in values:
        opinions["tradition"]["stance"] = max(opinions["tradition"]["stance"], 0.3)
        opinions["tradition"]["confidence"] = 0.6
    if "progress" in values or "education" in values:
        opinions["modernization"]["stance"] = max(opinions["modernization"]["stance"], 0.3)
        opinions["modernization"]["confidence"] = 0.5
    if "healing" in values or "service" in values:
        opinions["clinic_funding"]["stance"] = max(opinions["clinic_funding"]["stance"], 0.4)
        opinions["clinic_funding"]["confidence"] = 0.6
    return opinions


AGENT_PROFILES: list[AgentProfile] = [
    AgentProfile(
        id="eleanor",
        name="Eleanor Voss",
        age=58,
        job="Mayor",
        workplace="town_hall",
        home="house_1",
        personality={"openness": 0.5, "conscientiousness": 0.9, "extraversion": 0.6, "agreeableness": 0.5, "neuroticism": 0.4},
        values=["order", "fairness", "tradition"],
        goals=["Keep the town running smoothly", "Get re-elected", "Fund the new clinic"],
        fears=["Losing control", "Town falling apart"],
        backstory="Eleanor has been mayor for 12 years. She took the job after her husband passed and threw herself into public service.",
        wealth=800,
        color_index=0,
        secrets=[{"content": "I have been diverting small amounts from the town treasury for personal use", "known_by": [], "importance": 9.0, "discovered_tick": None}],
        schedule=[
            ScheduleEntry(6.0, "house_1", "sleeping"),
            ScheduleEntry(7.0, "house_1", "eating"),
            ScheduleEntry(8.0, "town_hall", "working"),
            ScheduleEntry(12.0, "bakery", "eating"),
            ScheduleEntry(13.0, "town_hall", "working"),
            ScheduleEntry(16.0, "park", "reflecting"),
            ScheduleEntry(18.0, "tavern", "eating"),
            ScheduleEntry(20.0, "house_1", "idle"),
            ScheduleEntry(22.0, "house_1", "sleeping"),
        ],
    ),
    AgentProfile(
        id="john",
        name="John Harlow",
        age=45,
        job="Farmer",
        workplace="farm",
        home="house_2",
        personality={"openness": 0.3, "conscientiousness": 0.8, "extraversion": 0.3, "agreeableness": 0.5, "neuroticism": 0.5},
        values=["hard work", "self-reliance", "land"],
        goals=["Keep the farm productive", "Save enough for retirement"],
        fears=["Crop failure", "Losing the farm"],
        backstory="John is a widower who inherited the farm from his father. He's practical and slightly grumpy but deeply reliable.",
        wealth=400,
        color_index=1,
        secrets=[{"content": "My farm is mortgaged and I am close to losing it entirely", "known_by": [], "importance": 9.0, "discovered_tick": None}],
        schedule=[
            ScheduleEntry(5.0, "farm", "working"),
            ScheduleEntry(12.0, "house_2", "eating"),
            ScheduleEntry(13.0, "farm", "working"),
            ScheduleEntry(15.0, "general_store", "selling"),
            ScheduleEntry(17.0, "tavern", "eating"),
            ScheduleEntry(20.0, "house_2", "idle"),
            ScheduleEntry(21.0, "house_2", "sleeping"),
        ],
    ),
    AgentProfile(
        id="mei",
        name="Mei Chen",
        age=38,
        job="Shopkeeper",
        workplace="general_store",
        home="house_6",
        personality={"openness": 0.7, "conscientiousness": 0.7, "extraversion": 0.9, "agreeableness": 0.6, "neuroticism": 0.3},
        values=["community", "entrepreneurship", "information"],
        goals=["Grow the store", "Know everyone's business", "Find a partner"],
        fears=["Being alone", "Store failing"],
        backstory="Mei is friendly and entrepreneurial. She runs the general store and knows everyone's business — the town's unofficial information hub.",
        wealth=600,
        color_index=2,
        secrets=[{"content": "I am in significant debt to a supplier in another town and cannot pay them back", "known_by": [], "importance": 8.0, "discovered_tick": None}],
        schedule=[
            ScheduleEntry(7.0, "general_store", "working"),
            ScheduleEntry(12.0, "bakery", "eating"),
            ScheduleEntry(13.0, "general_store", "working"),
            ScheduleEntry(18.0, "tavern", "eating"),
            ScheduleEntry(20.0, "house_6", "idle"),
            ScheduleEntry(22.0, "house_6", "sleeping"),
        ],
    ),
    AgentProfile(
        id="oleg",
        name="Oleg Petrov",
        age=50,
        job="Blacksmith",
        workplace="workshop",
        home="house_5",
        personality={"openness": 0.6, "conscientiousness": 0.8, "extraversion": 0.2, "agreeableness": 0.6, "neuroticism": 0.3},
        values=["craftsmanship", "honesty", "philosophy"],
        goals=["Master his craft", "Feel accepted in town"],
        fears=["Being seen as an outsider", "Losing his skill"],
        backstory="Oleg immigrated from another town years ago. He's quiet and philosophical, finding meaning through his work at the forge.",
        wealth=500,
        color_index=3,
        secrets=[{"content": "I fled my previous town after being accused of a crime I did not commit", "known_by": [], "importance": 8.0, "discovered_tick": None}],
        schedule=[
            ScheduleEntry(6.0, "workshop", "working"),
            ScheduleEntry(12.0, "house_5", "eating"),
            ScheduleEntry(13.0, "workshop", "working"),
            ScheduleEntry(17.0, "park", "reflecting"),
            ScheduleEntry(19.0, "tavern", "eating"),
            ScheduleEntry(21.0, "house_5", "sleeping"),
        ],
    ),
    AgentProfile(
        id="sarah",
        name="Sarah Kim",
        age=32,
        job="Teacher",
        workplace="school",
        home="house_6",
        personality={"openness": 0.9, "conscientiousness": 0.7, "extraversion": 0.7, "agreeableness": 0.8, "neuroticism": 0.4},
        values=["education", "progress", "equality"],
        goals=["Modernize the school", "Challenge Eleanor in the next election"],
        fears=["Being dismissed", "Stagnation"],
        backstory="Sarah is idealistic and passionate about education. She thinks the town needs to modernize and has been vocal about wanting change.",
        wealth=350,
        color_index=4,
        secrets=[{"content": "I have been secretly meeting with outside political organizers to plan a campaign against Eleanor", "known_by": [], "importance": 8.0, "discovered_tick": None}],
        schedule=[
            ScheduleEntry(7.0, "school", "working"),
            ScheduleEntry(12.0, "bakery", "eating"),
            ScheduleEntry(13.0, "school", "working"),
            ScheduleEntry(15.0, "park", "reflecting"),
            ScheduleEntry(17.0, "general_store", "buying"),
            ScheduleEntry(19.0, "tavern", "eating"),
            ScheduleEntry(21.0, "house_6", "sleeping"),
        ],
    ),
    AgentProfile(
        id="ricky",
        name="Ricky Malone",
        age=40,
        job="Bartender",
        workplace="tavern",
        home="tavern",
        personality={"openness": 0.7, "conscientiousness": 0.5, "extraversion": 0.9, "agreeableness": 0.8, "neuroticism": 0.5},
        values=["humor", "connection", "loyalty"],
        goals=["Make people happy", "Find genuine friendship"],
        fears=["Loneliness", "People seeing through his act"],
        backstory="Ricky is charismatic and funny, the social hub of town. He hears everyone's problems. Secretly lonely — the bartender nobody checks on.",
        wealth=450,
        color_index=5,
        secrets=[{"content": "I am an alcoholic and I drink alone every night after closing the tavern", "known_by": [], "importance": 7.0, "discovered_tick": None}],
        schedule=[
            ScheduleEntry(8.0, "tavern", "idle"),
            ScheduleEntry(10.0, "general_store", "buying"),
            ScheduleEntry(11.0, "tavern", "working"),
            ScheduleEntry(14.0, "park", "reflecting"),
            ScheduleEntry(16.0, "tavern", "working"),
            ScheduleEntry(23.0, "tavern", "sleeping"),
        ],
    ),
    AgentProfile(
        id="amara",
        name="Amara Osei",
        age=44,
        job="Doctor",
        workplace="house_4",  # makes house calls, no clinic yet
        home="house_4",
        personality={"openness": 0.7, "conscientiousness": 0.9, "extraversion": 0.5, "agreeableness": 0.9, "neuroticism": 0.2},
        values=["healing", "wisdom", "service"],
        goals=["Get funding for a clinic", "Keep everyone healthy"],
        fears=["Someone dying on her watch", "Funding never coming"],
        backstory="Amara is calm, wise, and universally respected. She makes house calls since there's no clinic — her biggest frustration.",
        wealth=500,
        color_index=6,
        secrets=[{"content": "I lost a patient in my previous town due to a mistake I made, and I blame myself every day", "known_by": [], "importance": 9.0, "discovered_tick": None}],
        schedule=[
            ScheduleEntry(7.0, "house_4", "working"),
            ScheduleEntry(9.0, "house_5", "working"),  # house call
            ScheduleEntry(11.0, "house_2", "working"),  # house call
            ScheduleEntry(13.0, "bakery", "eating"),
            ScheduleEntry(14.0, "town_hall", "working"),  # lobbying for clinic
            ScheduleEntry(16.0, "church", "reflecting"),
            ScheduleEntry(18.0, "tavern", "eating"),
            ScheduleEntry(20.0, "house_4", "idle"),
            ScheduleEntry(22.0, "house_4", "sleeping"),
        ],
    ),
    AgentProfile(
        id="tom",
        name="Tom Kowalski",
        age=42,
        job="Builder",
        workplace="workshop",
        home="house_3",
        personality={"openness": 0.4, "conscientiousness": 0.7, "extraversion": 0.5, "agreeableness": 0.5, "neuroticism": 0.6},
        values=["family", "stability", "hard work"],
        goals=["Provide for his family", "Get a raise"],
        fears=["Financial ruin", "Disappointing Lisa"],
        backstory="Tom works at the workshop with Oleg. He and Lisa have financial struggles and argue about money sometimes.",
        wealth=250,
        color_index=7,
        secrets=[{"content": "I have been gambling secretly and hiding my losses from Lisa", "known_by": [], "importance": 8.0, "discovered_tick": None}],
        schedule=[
            ScheduleEntry(7.0, "workshop", "working"),
            ScheduleEntry(12.0, "house_3", "eating"),
            ScheduleEntry(13.0, "workshop", "working"),
            ScheduleEntry(16.0, "house_3", "idle"),
            ScheduleEntry(18.0, "tavern", "eating"),
            ScheduleEntry(20.0, "house_3", "idle"),
            ScheduleEntry(22.0, "house_3", "sleeping"),
        ],
    ),
    AgentProfile(
        id="lisa",
        name="Lisa Kowalski",
        age=40,
        job="Teaching Assistant",
        workplace="school",
        home="house_3",
        personality={"openness": 0.6, "conscientiousness": 0.8, "extraversion": 0.6, "agreeableness": 0.7, "neuroticism": 0.5},
        values=["family", "education", "thrift"],
        goals=["Help at the school", "Manage family finances", "Save for children's future"],
        fears=["Poverty", "Tom losing his job"],
        backstory="Lisa helps at the school and tries to stretch every coin. The financial stress shows in her arguments with Tom.",
        wealth=250,
        color_index=8,
        secrets=[{"content": "I have been skimming small amounts from the school supply budget to buy food for my family", "known_by": [], "importance": 8.0, "discovered_tick": None}],
        schedule=[
            ScheduleEntry(7.0, "school", "working"),
            ScheduleEntry(12.0, "house_3", "eating"),
            ScheduleEntry(13.0, "school", "working"),
            ScheduleEntry(14.0, "general_store", "buying"),
            ScheduleEntry(16.0, "house_3", "idle"),
            ScheduleEntry(19.0, "house_3", "eating"),
            ScheduleEntry(22.0, "house_3", "sleeping"),
        ],
    ),
    AgentProfile(
        id="marcus",
        name="Marcus Reeves",
        age=36,
        job="Handyman",
        workplace="town_hall",
        home="house_4",
        personality={"openness": 0.5, "conscientiousness": 0.6, "extraversion": 0.6, "agreeableness": 0.7, "neuroticism": 0.4},
        values=["adaptability", "family", "making do"],
        goals=["Establish himself in town", "Find steady work"],
        fears=["Not fitting in", "Jade's art not selling"],
        backstory="Marcus is the town's part-time handyman. He and Jade are the newest arrivals, still building relationships.",
        wealth=200,
        color_index=9,
        secrets=[{"content": "I have a criminal record from before moving to this town that no one here knows about", "known_by": [], "importance": 9.0, "discovered_tick": None}],
        schedule=[
            ScheduleEntry(7.0, "town_hall", "working"),
            ScheduleEntry(9.0, "workshop", "working"),
            ScheduleEntry(12.0, "bakery", "eating"),
            ScheduleEntry(13.0, "farm", "working"),
            ScheduleEntry(16.0, "house_4", "idle"),
            ScheduleEntry(18.0, "tavern", "eating"),
            ScheduleEntry(21.0, "house_4", "sleeping"),
        ],
    ),
    AgentProfile(
        id="jade",
        name="Jade Reeves",
        age=34,
        job="Artist",
        workplace="house_4",
        home="house_4",
        personality={"openness": 0.95, "conscientiousness": 0.4, "extraversion": 0.5, "agreeableness": 0.7, "neuroticism": 0.5},
        values=["creativity", "beauty", "expression"],
        goals=["Sell crafts at the store", "Find artistic inspiration", "Feel at home here"],
        fears=["Never being taken seriously", "Financial dependence"],
        backstory="Jade is an aspiring artist who sells crafts. She's creative and expressive but worries about making enough to contribute.",
        wealth=200,
        color_index=10,
        secrets=[{"content": "Some of my crafts are actually forged copies of famous artworks that I sell as originals", "known_by": [], "importance": 8.0, "discovered_tick": None}],
        schedule=[
            ScheduleEntry(8.0, "house_4", "working"),  # crafting
            ScheduleEntry(11.0, "general_store", "selling"),
            ScheduleEntry(13.0, "bakery", "eating"),
            ScheduleEntry(14.0, "park", "reflecting"),
            ScheduleEntry(16.0, "pond", "reflecting"),
            ScheduleEntry(18.0, "house_4", "eating"),
            ScheduleEntry(22.0, "house_4", "sleeping"),
        ],
    ),
    AgentProfile(
        id="henry",
        name="Henry Brennan",
        age=72,
        job="Retired",
        workplace="park",
        home="house_5",
        personality={"openness": 0.3, "conscientiousness": 0.6, "extraversion": 0.5, "agreeableness": 0.4, "neuroticism": 0.4},
        values=["tradition", "respect", "stories"],
        goals=["Pass on wisdom", "Keep Jake grounded", "Enjoy remaining years"],
        fears=["Being forgotten", "Jake leaving"],
        backstory="Henry is a town elder with strong opinions and lots of stories. Retired and often on the park bench, he watches the town change.",
        wealth=350,
        color_index=11,
        secrets=[{"content": "I am sitting on a large inheritance that I have never told Jake about", "known_by": [], "importance": 7.0, "discovered_tick": None}],
        schedule=[
            ScheduleEntry(7.0, "house_5", "eating"),
            ScheduleEntry(8.0, "park", "reflecting"),
            ScheduleEntry(11.0, "general_store", "buying"),
            ScheduleEntry(12.0, "bakery", "eating"),
            ScheduleEntry(14.0, "church", "reflecting"),
            ScheduleEntry(16.0, "tavern", "eating"),
            ScheduleEntry(19.0, "house_5", "idle"),
            ScheduleEntry(21.0, "house_5", "sleeping"),
        ],
    ),
    AgentProfile(
        id="jake",
        name="Jake Brennan",
        age=19,
        job="Odd Jobs",
        workplace="farm",
        home="house_5",
        personality={"openness": 0.8, "conscientiousness": 0.3, "extraversion": 0.7, "agreeableness": 0.4, "neuroticism": 0.6},
        values=["freedom", "excitement", "independence"],
        goals=["Leave for the city", "Find something meaningful", "Save enough to move"],
        fears=["Being stuck here forever", "Becoming like grandpa"],
        backstory="Jake is restless and wants to leave for the city. He works odd jobs reluctantly and clashes with his grandfather about the future.",
        wealth=80,
        color_index=12,
        secrets=[{"content": "I have already secretly bought a one-way ticket to leave town and start a new life in the city", "known_by": [], "importance": 8.0, "discovered_tick": None}],
        schedule=[
            ScheduleEntry(8.0, "house_5", "eating"),
            ScheduleEntry(9.0, "farm", "working"),
            ScheduleEntry(12.0, "tavern", "eating"),
            ScheduleEntry(14.0, "pond", "reflecting"),
            ScheduleEntry(16.0, "general_store", "buying"),
            ScheduleEntry(18.0, "tavern", "eating"),
            ScheduleEntry(22.0, "house_5", "sleeping"),
        ],
    ),
    AgentProfile(
        id="clara",
        name="Clara Fontaine",
        age=28,
        job="Journalist",
        workplace="tavern",
        home="house_6",
        personality={"openness": 0.9, "conscientiousness": 0.6, "extraversion": 0.8, "agreeableness": 0.6, "neuroticism": 0.5},
        values=["truth", "stories", "curiosity"],
        goals=["Document everything", "Write a great story", "Uncover town secrets"],
        fears=["Missing the big story", "Being seen as just a gossip"],
        backstory="Clara is the town's unofficial journalist. She writes a small newsletter and documents everything. Nosy but well-intentioned.",
        wealth=200,
        color_index=13,
        secrets=[{"content": "I fabricated a major story in my newsletter last year and I am terrified someone will find out", "known_by": [], "importance": 8.0, "discovered_tick": None}],
        schedule=[
            ScheduleEntry(7.0, "house_6", "working"),  # writing
            ScheduleEntry(9.0, "town_hall", "working"),  # reporting
            ScheduleEntry(11.0, "general_store", "idle"),  # gathering info
            ScheduleEntry(12.0, "bakery", "eating"),
            ScheduleEntry(13.0, "farm", "idle"),  # visiting
            ScheduleEntry(15.0, "workshop", "idle"),  # visiting
            ScheduleEntry(17.0, "tavern", "working"),  # writing
            ScheduleEntry(20.0, "house_6", "idle"),
            ScheduleEntry(22.0, "house_6", "sleeping"),
        ],
    ),
    AgentProfile(
        id="daniel",
        name="Daniel Park",
        age=55,
        job="Reverend",
        workplace="church",
        home="church",
        personality={"openness": 0.6, "conscientiousness": 0.8, "extraversion": 0.6, "agreeableness": 0.9, "neuroticism": 0.5},
        values=["faith", "community", "compassion"],
        goals=["Guide the community", "Mediate disputes", "Find his own peace"],
        fears=["Losing his faith", "Failing those who trust him"],
        backstory="Reverend Park runs the church and is the moral compass of town. He mediates disputes but is secretly questioning his faith.",
        wealth=300,
        color_index=14,
        secrets=[{"content": "I have completely lost my faith and have been faking my devotion for years", "known_by": [], "importance": 9.0, "discovered_tick": None}],
        schedule=[
            ScheduleEntry(6.0, "church", "reflecting"),
            ScheduleEntry(8.0, "church", "working"),
            ScheduleEntry(12.0, "bakery", "eating"),
            ScheduleEntry(13.0, "church", "working"),
            ScheduleEntry(15.0, "house_5", "idle"),  # visiting Henry
            ScheduleEntry(17.0, "park", "reflecting"),
            ScheduleEntry(19.0, "tavern", "eating"),
            ScheduleEntry(21.0, "church", "sleeping"),
        ],
    ),
]

AGENT_MAP = {p.id: p for p in AGENT_PROFILES}
