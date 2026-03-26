import asyncio
import logging
import random
from typing import Callable, Coroutine

from config import settings
from simulation.time_manager import TimeManager
from simulation.world import World
from agents.agent import Agent
from agents.profiles import AGENT_PROFILES
from agents.conversation import conversation_manager
from systems.economy import EconomySystem
from systems.social import social_system
from db.database import init_db, save_world_state
from agents.cognition import cognition_system
from simulation.event_system import event_system

logger = logging.getLogger("agentica.engine")

# Social locations where conversations can happen
SOCIAL_LOCATIONS = {"tavern", "park", "general_store", "bakery", "church", "town_hall"}


class SimulationEngine:
    def __init__(self):
        self.tick = 0
        self.speed = 1
        self.running = False
        self.time_manager = TimeManager(ticks_per_day=settings.ticks_per_day)
        self.world = World()
        self._broadcast: Callable[[dict], Coroutine] | None = None
        self.agents: dict[str, Agent] = {}
        self.economy = EconomySystem()
        self._pending_conversations: list = []
        self._init_agents()

    def _init_agents(self):
        for profile in AGENT_PROFILES:
            agent = Agent(profile, self.world)
            self.agents[agent.id] = agent
        logger.info(f"Initialized {len(self.agents)} agents")

    async def _try_restore(self):
        """Try to restore simulation from saved state."""
        from db.database import load_world_state
        save = await load_world_state()
        if not save:
            logger.info("No save found, starting fresh")
            return

        # Restore world state
        self.tick = save["tick"]
        self.time_manager.day = save["day"]
        self.time_manager.tick_in_day = self.tick % self.time_manager.ticks_per_day
        self.time_manager.season = save.get("season", "spring")
        self.time_manager.weather = save.get("weather", "clear")

        # Restore economy
        econ = save.get("economy", {})
        if econ.get("prices"):
            for item, price in econ["prices"].items():
                self.economy.prices[item] = price
        if econ.get("supply"):
            for item, supply in econ["supply"].items():
                self.economy.supply[item] = supply
        if econ.get("treasury"):
            self.economy.treasury = econ["treasury"]

        # Restore agents
        agent_saves = save.get("agents", {})
        restored = 0
        for agent_id, agent_data in agent_saves.items():
            if agent_id in self.agents:
                self.agents[agent_id].restore_from_save(agent_data)
                restored += 1

        logger.info(f"Restored save: tick {self.tick}, day {self.time_manager.day}, {restored} agents")

    def set_broadcast(self, fn: Callable[[dict], Coroutine]):
        self._broadcast = fn

    def set_speed(self, speed: int):
        self.speed = max(0, min(10, speed))
        logger.info(f"Speed set to {self.speed}")

    def stop(self):
        self.running = False

    async def run(self):
        self.running = True
        await init_db()
        await self._try_restore()
        logger.info("Simulation loop started")

        while self.running:
            if self.speed == 0:
                await asyncio.sleep(0.1)
                continue

            interval = settings.tick_duration_ms / 1000.0 / self.speed
            await asyncio.sleep(interval)

            self.tick += 1
            self.time_manager.advance()

            # Process rule-based tick
            events = self._process_tick()

            # Process async LLM conversations (non-blocking)
            conv_events = await self._process_conversations()
            events.extend(conv_events)

            # Cognition: reflections and daily plans (async)
            cog_events = await self._process_cognition()
            events.extend(cog_events)

            # Process ongoing events (drought, winter, etc.)
            event_system.tick(self.economy)

            # Include any god-mode events buffered since last tick
            god_events = getattr(self, "_god_events", [])
            if god_events:
                events.extend(god_events)
                self._god_events = []

            # Auto-save every 50 ticks
            if self.tick % 50 == 0:
                asyncio.create_task(save_world_state(self))

            if self._broadcast:
                await self._broadcast({
                    "type": "tick",
                    "data": {
                        "tick": self.tick,
                        "time": self.time_manager.to_dict(),
                        "events": events,
                        "agents": [a.to_dict() for a in self.agents.values()],
                    },
                })

    def _process_tick(self) -> list[dict]:
        """Process one simulation tick (rule-based). Returns events."""
        events = []
        hour = self.time_manager.hour

        for agent in self.agents.values():
            agent_events = agent.update(hour, self.world)
            events.extend(agent_events)

        # Economic processing
        econ_events = self.economy.tick(self.agents, hour, self.tick)
        events.extend(econ_events)

        # Gossip propagation (every 20 ticks)
        if self.tick % 20 == 0:
            gossip_events = social_system.propagate_gossip(self.agents, self.tick)
            events.extend(gossip_events)

        # Check for potential conversations
        self._check_conversation_opportunities()

        return events

    def _check_conversation_opportunities(self):
        """Find agents at the same social location who could talk."""
        if self.time_manager.is_night:
            return

        # Group agents by location
        by_location: dict[str, list[Agent]] = {}
        for agent in self.agents.values():
            if agent.current_action.value in ("walking", "sleeping"):
                continue
            loc = agent.current_location
            if loc in SOCIAL_LOCATIONS:
                by_location.setdefault(loc, []).append(agent)

        # For each location with 2+ agents, maybe start a conversation
        for loc, agents_here in by_location.items():
            if len(agents_here) < 2:
                continue

            # Pick a random pair
            random.shuffle(agents_here)
            for i in range(0, len(agents_here) - 1, 2):
                a, b = agents_here[i], agents_here[i + 1]
                if conversation_manager.can_converse(a.id, b.id, self.tick):
                    # ~50% chance per tick to start talking
                    if random.random() < 0.5:
                        self._pending_conversations.append((a, b, loc))
                        break  # Max 1 new conversation per location per tick

    async def _process_conversations(self) -> list[dict]:
        """Run pending conversations (async LLM calls)."""
        events = []
        pending = self._pending_conversations[:]
        self._pending_conversations.clear()

        if not pending:
            return events

        # Run up to 2 conversations concurrently per tick
        tasks = []
        for a, b, loc in pending[:2]:
            tasks.append(
                conversation_manager.run_conversation(
                    a, b, loc, self.time_manager.time_of_day, self.tick
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, list):
                events.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"Conversation error: {result}")

        return events

    def get_world_state(self) -> dict:
        return {
            "tick": self.tick,
            "time": self.time_manager.to_dict(),
            "agents": [a.to_dict() for a in self.agents.values()],
            "weather": self.time_manager.weather,
            "speed": self.speed,
            "economy": self.economy.to_dict(),
        }

    def get_dashboard_data(self) -> dict:
        """Full town data for the dashboard view."""
        agents_list = list(self.agents.values())
        agent_details = [a.to_detail_dict() for a in agents_list]

        # Compute town-wide stats
        moods = [a.state.mood for a in agents_list]
        wealths = [a.state.wealth for a in agents_list]
        memory_counts = [len(a.memory.memories) for a in agents_list]
        rel_counts = [len(a.relationships) for a in agents_list]

        richest = max(agents_list, key=lambda a: a.state.wealth)
        poorest = min(agents_list, key=lambda a: a.state.wealth)
        happiest = max(agents_list, key=lambda a: a.state.mood)
        saddest = min(agents_list, key=lambda a: a.state.mood)
        most_connected = max(agents_list, key=lambda a: len(a.relationships))
        total_convos = sum(
            1 for a in agents_list
            for m in a.memory.memories if m.memory_type == "conversation"
        )
        total_reflections = sum(
            1 for a in agents_list
            for m in a.memory.memories if m.memory_type == "reflection"
        )

        return {
            "tick": self.tick,
            "time": self.time_manager.to_dict(),
            "agents": agent_details,
            "economy": self.economy.to_dict(),
            "activeEvents": event_system.active_events,
            "eventLog": event_system.event_log[-50:],
            "townStats": {
                "population": len(agents_list),
                "avgMood": round(sum(moods) / len(moods), 2) if moods else 0,
                "avgWealth": round(sum(wealths) / len(wealths), 1) if wealths else 0,
                "totalWealth": sum(wealths),
                "totalMemories": sum(memory_counts),
                "totalConversations": total_convos,
                "totalReflections": total_reflections,
                "totalTransactions": self.economy.total_transactions,
                "richest": {"name": richest.name, "wealth": richest.state.wealth},
                "poorest": {"name": poorest.name, "wealth": poorest.state.wealth},
                "happiest": {"name": happiest.name, "mood": round(happiest.state.mood, 2)},
                "saddest": {"name": saddest.name, "mood": round(saddest.state.mood, 2)},
                "mostConnected": {"name": most_connected.name, "connections": len(most_connected.relationships)},
                "totalGodEvents": len(event_system.event_log),
            },
        }

    def get_agent_detail(self, agent_id: str) -> dict:
        agent = self.agents.get(agent_id)
        if not agent:
            return {"error": f"Agent {agent_id} not found"}
        return agent.to_detail_dict()

    async def _process_cognition(self) -> list[dict]:
        """Run cognitive processes — reflections and daily plans."""
        events = []

        # Only process cognition for 1-2 agents per tick to save LLM budget
        agents_list = list(self.agents.values())
        random.shuffle(agents_list)

        for agent in agents_list[:2]:
            # Reflections
            ref_events = await cognition_system.maybe_reflect(
                agent, self.tick, settings.reflection_interval
            )
            events.extend(ref_events)

            # Daily plans (at start of day)
            if self.time_manager.hour < 7.5 and self.time_manager.hour > 6.5:
                plan_events = await cognition_system.maybe_plan(
                    agent, self.time_manager.day, self.tick
                )
                events.extend(plan_events)

        return events

    def handle_god_command(self, command: str, params: dict):
        """Handle god-mode commands."""
        logger.info(f"God command: {command} params={params}")

        if command == "inject_event":
            event_type = params.get("event_type", "")
            event_params = params.get("params", {})
            events = event_system.inject_event(
                event_type, event_params, self.agents, self.economy, self.tick
            )
            # Buffer events for next broadcast
            self._god_events = getattr(self, "_god_events", [])
            self._god_events.extend(events)

        elif command == "modify_agent":
            agent_id = params.get("agent_id")
            if agent_id and agent_id in self.agents:
                agent = self.agents[agent_id]
                if "wealth" in params:
                    agent.state.wealth = params["wealth"]
                if "mood" in params:
                    agent.state.mood = params["mood"]
                if "energy" in params:
                    agent.state.energy = params["energy"]

        elif command == "whisper":
            agent_id = params.get("agent_id")
            thought = params.get("thought", "")
            if agent_id and agent_id in self.agents and thought:
                agent = self.agents[agent_id]
                from agents.memory import MemoryEntry
                agent.memory.add(MemoryEntry(
                    tick=self.tick,
                    content=thought,
                    importance=9.0,
                    memory_type="observation",
                ))
                agent.inner_thought = thought

        elif command == "set_weather":
            weather = params.get("weather", "clear")
            self.time_manager.weather = weather
