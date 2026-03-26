"""God-mode event injection system."""

import logging
import random
from agents.memory import MemoryEntry

logger = logging.getLogger("agentica.events")


def _update_rel(agent, other_name: str, sentiment_delta: float = 0, trust_delta: float = 0):
    """Helper to update an agent's relationship with another."""
    if other_name not in agent.relationships:
        agent.relationships[other_name] = {"sentiment": 0.5, "trust": 0.5, "familiarity": 0.1, "notes": "Acquaintance"}
    rel = agent.relationships[other_name]
    rel["sentiment"] = max(-1.0, min(1.0, rel.get("sentiment", 0.5) + sentiment_delta))
    rel["trust"] = max(0.0, min(1.0, rel.get("trust", 0.5) + trust_delta))

# Pre-built event definitions
EVENT_TYPES = {
    "drought": {
        "label": "Drought",
        "description": "Farm output halved for 10 days",
        "duration": 10,
    },
    "building_fire": {
        "label": "Building Fire",
        "description": "A building catches fire and is damaged",
    },
    "stranger_arrives": {
        "label": "Stranger Arrives",
        "description": "A mysterious stranger visits town for 5 days",
    },
    "festival": {
        "label": "Festival",
        "description": "Town celebrates with a festival in the square",
    },
    "election": {
        "label": "Town Election",
        "description": "An election is called for mayor",
    },
    "illness": {
        "label": "Agent Illness",
        "description": "An agent falls seriously ill",
        "params": ["agent_id"],
    },
    "price_crash": {
        "label": "Price Crash",
        "description": "A good's price drops dramatically",
        "params": ["item"],
    },
    "trade_caravan": {
        "label": "Trade Caravan",
        "description": "A caravan arrives with cheap goods",
    },
    "harsh_winter": {
        "label": "Harsh Winter",
        "description": "Food and fuel demand doubles",
        "duration": 15,
    },
    "secret_revealed": {
        "label": "Secret Revealed",
        "description": "An agent's secret becomes public",
        "params": ["agent_id", "secret"],
    },
}

# Buildings that can catch fire (not critical infrastructure)
BURNABLE_BUILDINGS = ["barn", "bakery", "workshop", "tavern", "school", "general_store"]

# Stranger rumors to inject
STRANGER_RUMORS = [
    "The stranger says there's a gold vein in the hills to the north.",
    "The stranger warned that a plague is spreading in the next town over.",
    "The stranger claims to be a merchant looking for a new trade route.",
    "The stranger asked a lot of questions about the town's leadership.",
    "The stranger carries strange books and speaks of distant lands.",
    "The stranger offered to buy land in town at a high price.",
]


class EventSystem:
    def __init__(self):
        self.active_events: list[dict] = []
        self.event_log: list[dict] = []
        self.damaged_buildings: set[str] = set()

    def inject_event(self, event_type: str, params: dict, agents: dict, economy, tick: int) -> list[dict]:
        """Inject a god-mode event. Returns WebSocket events."""
        events = []

        if event_type not in EVENT_TYPES:
            logger.warning(f"Unknown event type: {event_type}")
            return events

        event_def = EVENT_TYPES[event_type]
        logger.info(f"Injecting event: {event_def['label']}")

        self.event_log.append({
            "type": event_type,
            "tick": tick,
            "params": params,
        })

        events.append({
            "type": "system_event",
            "eventType": event_type,
            "label": event_def["label"],
            "description": event_def["description"],
        })

        # --- DROUGHT ---
        if event_type == "drought":
            self.active_events.append({
                "type": "drought",
                "remaining_ticks": event_def.get("duration", 10) * 144,
            })
            for agent in agents.values():
                agent.memory.add(MemoryEntry(
                    tick=tick,
                    content="A terrible drought has hit the farm. Food will be scarce.",
                    importance=9.0,
                    memory_type="observation",
                ))

        # --- FESTIVAL ---
        elif event_type == "festival":
            agent_names = [a.name for a in agents.values()]
            for agent in agents.values():
                agent.memory.add(MemoryEntry(
                    tick=tick,
                    content="A festival has been announced in the town square! Everyone is heading to the park to celebrate.",
                    importance=7.0,
                    memory_type="observation",
                ))
                agent.state.mood = min(1.0, agent.state.mood + 0.2)
                agent._start_walking("park")
                # Festival builds community — small sentiment boost with everyone
                for other_name in agent_names:
                    if other_name != agent.name:
                        _update_rel(agent, other_name, sentiment_delta=0.03, trust_delta=0.01)

        # --- PRICE CRASH ---
        elif event_type == "price_crash":
            item = params.get("item", "food")
            if item in economy.prices:
                old_price = economy.prices[item]
                economy.prices[item] *= 0.5
                economy.supply[item] += 10
                for agent in agents.values():
                    agent.memory.add(MemoryEntry(
                        tick=tick,
                        content=f"The price of {item} has crashed from {old_price:.0f} to {economy.prices[item]:.0f} coins!",
                        importance=7.0,
                        memory_type="observation",
                    ))

        # --- TRADE CARAVAN ---
        elif event_type == "trade_caravan":
            for item in economy.supply:
                economy.supply[item] += 15
            for agent in agents.values():
                agent.memory.add(MemoryEntry(
                    tick=tick,
                    content="A trade caravan has arrived with lots of cheap goods!",
                    importance=6.0,
                    memory_type="observation",
                ))

        # --- ILLNESS ---
        elif event_type == "illness":
            target_id = params.get("agent_id")
            if target_id and target_id in agents:
                target = agents[target_id]
                target.state.energy = 0.2
                target.state.mood = max(0, target.state.mood - 0.3)
                target.inner_thought = "I feel terrible... I can barely move."
                target.emotion = "sick"
                target.memory.add(MemoryEntry(
                    tick=tick,
                    content="I've fallen seriously ill. I can barely stand.",
                    importance=10.0,
                    memory_type="emotion",
                ))
                # Send them home
                target._start_walking(target.profile.home)
                for agent in agents.values():
                    if agent.id != target_id:
                        agent.memory.add(MemoryEntry(
                            tick=tick,
                            content=f"{target.name} has fallen seriously ill.",
                            importance=8.0,
                            memory_type="observation",
                            related_agents=[target.name],
                        ))
                        # Friends feel sympathy
                        rel = agent.relationships.get(target.name, {})
                        if rel.get("sentiment", 0.5) > 0.4:
                            _update_rel(agent, target.name, sentiment_delta=0.05)
                # Doctor (Amara) gains trust with the sick agent
                if "amara" in agents and target_id != "amara":
                    _update_rel(agents["amara"], target.name, sentiment_delta=0.1, trust_delta=0.1)
                    _update_rel(target, "Amara Osei", sentiment_delta=0.05, trust_delta=0.08)

        # --- SECRET REVEALED ---
        elif event_type == "secret_revealed":
            target_id = params.get("agent_id")
            secret = params.get("secret", "has a dark past")
            if target_id and target_id in agents:
                target = agents[target_id]
                target.inner_thought = f"Everyone knows... they found out that I {secret}."
                target.emotion = "ashamed"
                target.state.mood = max(0, target.state.mood - 0.3)
                target.memory.add(MemoryEntry(
                    tick=tick,
                    content=f"My secret has been revealed to the whole town: I {secret}.",
                    importance=10.0,
                    memory_type="emotion",
                ))
                for agent in agents.values():
                    if agent.id != target_id:
                        agent.memory.add(MemoryEntry(
                            tick=tick,
                            content=f"It's been revealed that {target.name} {secret}!",
                            importance=9.0,
                            memory_type="observation",
                            related_agents=[target.name],
                        ))
                        # Trust drops — close friends less affected
                        rel = agent.relationships.get(target.name, {})
                        if rel.get("sentiment", 0.5) > 0.6:
                            _update_rel(agent, target.name, trust_delta=-0.05)
                        else:
                            _update_rel(agent, target.name, trust_delta=-0.15, sentiment_delta=-0.1)

        # --- HARSH WINTER ---
        elif event_type == "harsh_winter":
            self.active_events.append({
                "type": "harsh_winter",
                "remaining_ticks": event_def.get("duration", 15) * 144,
            })
            for agent in agents.values():
                agent.memory.add(MemoryEntry(
                    tick=tick,
                    content="A harsh winter has arrived. Everyone needs more food and warmth.",
                    importance=8.0,
                    memory_type="observation",
                ))
                agent.state.mood = max(0, agent.state.mood - 0.1)

        # --- STRANGER ARRIVES ---
        elif event_type == "stranger_arrives":
            rumor = random.choice(STRANGER_RUMORS)
            for agent in agents.values():
                agent.memory.add(MemoryEntry(
                    tick=tick,
                    content="A mysterious stranger has been spotted walking through town.",
                    importance=7.0,
                    memory_type="observation",
                ))
            # One random agent "meets" the stranger and learns something
            lucky_agent = random.choice(list(agents.values()))
            lucky_agent.memory.add(MemoryEntry(
                tick=tick,
                content=f"I spoke with the stranger at the town square. {rumor}",
                importance=9.0,
                memory_type="conversation",
            ))
            lucky_agent.inner_thought = f"That stranger told me something interesting... {rumor}"
            events.append({
                "type": "agent_thought",
                "agentId": lucky_agent.id,
                "thought": f"Met the stranger. {rumor}",
            })

        # --- ELECTION ---
        elif event_type == "election":
            for agent in agents.values():
                agent.memory.add(MemoryEntry(
                    tick=tick,
                    content="A town election has been called! The vote for mayor will happen soon.",
                    importance=9.0,
                    memory_type="observation",
                ))
            # Eleanor (current mayor) gets stressed
            if "eleanor" in agents:
                eleanor = agents["eleanor"]
                eleanor.memory.add(MemoryEntry(
                    tick=tick,
                    content="The election is coming. I need to prove I'm still the right leader for this town.",
                    importance=10.0,
                    memory_type="emotion",
                ))
                eleanor.inner_thought = "The election... I can't lose this."
                eleanor.emotion = "anxious"
                eleanor.state.mood = max(0, eleanor.state.mood - 0.2)
            # Sarah (challenger) gets excited
            if "sarah" in agents:
                sarah = agents["sarah"]
                sarah.memory.add(MemoryEntry(
                    tick=tick,
                    content="Finally! An election! This is my chance to bring real change to this town.",
                    importance=10.0,
                    memory_type="emotion",
                ))
                sarah.inner_thought = "This is it. My chance to change things."
                sarah.emotion = "excited"
                sarah.state.mood = min(1.0, sarah.state.mood + 0.2)
            # Everyone else picks a side based on personality
            for agent in agents.values():
                if agent.id in ("eleanor", "sarah"):
                    continue
                conscientiousness = agent.profile.personality.get("conscientiousness", 0.5)
                openness = agent.profile.personality.get("openness", 0.5)
                # High conscientiousness → Eleanor (stability), high openness → Sarah (change)
                if conscientiousness > openness:
                    agent.memory.add(MemoryEntry(
                        tick=tick,
                        content="I think Eleanor has done a decent job. Change is risky.",
                        importance=6.0,
                        memory_type="reflection",
                    ))
                else:
                    agent.memory.add(MemoryEntry(
                        tick=tick,
                        content="Maybe it's time for a change. Sarah has some good ideas.",
                        importance=6.0,
                        memory_type="reflection",
                    ))

        # --- BUILDING FIRE ---
        elif event_type == "building_fire":
            # Pick a building — use param or random
            target_building = params.get("building_id")
            if not target_building or target_building not in BURNABLE_BUILDINGS:
                target_building = random.choice(BURNABLE_BUILDINGS)

            self.damaged_buildings.add(target_building)
            building_label = target_building.replace("_", " ").title()

            for agent in agents.values():
                agent.memory.add(MemoryEntry(
                    tick=tick,
                    content=f"Fire! The {building_label} is on fire! People are rushing to help.",
                    importance=10.0,
                    memory_type="observation",
                ))
                # If agent is at the burning building, panic and flee
                if agent.current_location == target_building:
                    agent.emotion = "terrified"
                    agent.inner_thought = f"The {building_label} is on fire! I need to get out!"
                    agent.state.mood = max(0, agent.state.mood - 0.3)
                    agent._start_walking("park")  # Flee to park
                    events.append({
                        "type": "agent_thought",
                        "agentId": agent.id,
                        "thought": f"Fleeing the fire at {building_label}!",
                    })

            # Workers whose workplace burned get stressed
            for agent in agents.values():
                if agent.profile.workplace == target_building:
                    agent.memory.add(MemoryEntry(
                        tick=tick,
                        content=f"My workplace, the {building_label}, has been damaged by fire. What am I going to do?",
                        importance=10.0,
                        memory_type="emotion",
                    ))
                    agent.emotion = "devastated"
                    agent.state.mood = max(0, agent.state.mood - 0.4)

        return events

    def tick(self, economy):
        """Process ongoing events."""
        for event in self.active_events[:]:
            event["remaining_ticks"] -= 1
            if event["remaining_ticks"] <= 0:
                self.active_events.remove(event)
                continue

            if event["type"] == "drought":
                economy.supply["food"] = max(0, economy.supply.get("food", 0) - 0.05)

            elif event["type"] == "harsh_winter":
                economy.supply["food"] = max(0, economy.supply.get("food", 0) - 0.03)


event_system = EventSystem()
