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
from systems.social import social_system, bulletin_board
from db.database import init_db, save_world_state
from agents.cognition import cognition_system
from simulation.event_system import event_system
from simulation.actions import ActionType

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
        self.day_recaps: list[dict] = []
        self.story_highlights: list[dict] = []
        self._last_recap_day: int = 0
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
            # Seed some initial gossip
            social_system.add_gossip("Mei Chen", "Eleanor Voss", "Eleanor has been spending a lot of treasury money lately", 7.0)
            social_system.add_gossip("Henry Brennan", "Jake Brennan", "Jake wants to leave town for the city", 6.0)
            social_system.add_gossip("Clara Fontaine", "Oleg Petrov", "Oleg has a mysterious past from before he came here", 6.0)
            return

        # Restore world grid
        world_data = save.get("world")
        if world_data:
            self.world.load_from_save(world_data)
            logger.info("World grid restored from save")

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
            old_season = self.time_manager.season
            self.time_manager.advance()

            # Detect season change
            if self.time_manager.season != old_season:
                season_event = self._on_season_change(self.time_manager.season)
                # Will be included in events via _god_events buffer

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

            # Crime checks (every 5 ticks)
            if self.tick % 5 == 0:
                crime_events = self._check_crimes()
                events.extend(crime_events)

            # Story detection (every 50 ticks)
            if self.tick % 50 == 0:
                new_highlights = self._detect_stories()
                self.story_highlights.extend(new_highlights)
                for h in new_highlights:
                    events.append({"type": "system_event", "eventType": "story_highlight", "label": h["type"].title(), "description": h["text"]})

            # Daily recap (at end of day)
            if self.time_manager.hour > 23.5 and self.time_manager.day > self._last_recap_day:
                self._last_recap_day = self.time_manager.day
                asyncio.create_task(self._generate_daily_recap())

            # Pre-generate autobiographies at noon
            if 12.0 < self.time_manager.hour < 12.5:
                asyncio.create_task(self._pregenerate_autobiographies())

            # Include any god-mode events buffered since last tick
            god_events = getattr(self, "_god_events", [])
            if god_events:
                events.extend(god_events)
                self._god_events = []

            # Auto-save every 50 ticks
            if self.tick % 50 == 0:
                asyncio.create_task(save_world_state(self))

            # Collect tile changes
            tile_changes = self.world.flush_changes()

            if self._broadcast:
                msg: dict = {
                    "type": "tick",
                    "data": {
                        "tick": self.tick,
                        "time": self.time_manager.to_dict(),
                        "events": events,
                        "agents": [a.to_dict() for a in self.agents.values()],
                        "storyHighlights": self.story_highlights[-20:],
                    },
                }
                if tile_changes:
                    msg["data"]["tileChanges"] = tile_changes
                    msg["data"]["buildings"] = self.world.get_buildings_list()
                await self._broadcast(msg)

    def _process_tick(self) -> list[dict]:
        """Process one simulation tick (rule-based). Returns events."""
        events = []

        # Clean up expired commitments (once per day at start)
        if self.time_manager.tick_in_day == 0:
            for agent in self.agents.values():
                agent.social_commitments = [
                    c for c in agent.social_commitments
                    if c.get("day", 0) >= self.time_manager.day or c.get("recurring")
                ]
        hour = self.time_manager.hour

        for agent in self.agents.values():
            agent_events = agent.update(hour, self.world)
            events.extend(agent_events)

            # Update drives (deterministic, every tick)
            is_alone = all(
                other.current_location != agent.current_location
                for other in self.agents.values() if other.id != agent.id
            )
            agent.drives.tick_update(
                is_working=agent.current_action.value == "working",
                is_sleeping=agent.current_action.value == "sleeping",
                is_alone=is_alone,
                is_socializing=agent.current_action.value == "talking",
                wealth=agent.state.wealth,
            )

            # Satisfy hunger when eating
            if agent.current_action.value == "eating":
                agent.drives.satisfy_hunger()

            # Satisfy social when talking
            if agent.current_action.value == "talking":
                agent.drives.satisfy_social()

            # Decay emotions toward baseline
            agent.emotional_state.decay(1)

        # Economic processing
        econ_events = self.economy.tick(self.agents, hour, self.tick, self.time_manager.season, settings.ticks_per_day)
        events.extend(econ_events)

        # Gossip propagation (every 10 ticks)
        if self.tick % 10 == 0:
            gossip_events = social_system.propagate_gossip(self.agents, self.tick)
            events.extend(gossip_events)

        # Caravan trader departure check
        self._check_caravan_departure()

        # Construction processing (every 20 ticks)
        if self.tick % 20 == 0:
            build_events = self._process_construction()
            events.extend(build_events)

        # Trade caravans (check every day at noon)
        if self.time_manager.hour > 12.0 and self.time_manager.hour < 12.5:
            caravan_events = self._check_trade_caravan()
            events.extend(caravan_events)

        # Check for potential conversations
        self._check_conversation_opportunities()

        return events

    def _check_conversation_opportunities(self):
        """Find agents at the same location who could talk. Planned meetups are guaranteed."""
        if self.time_manager.is_night:
            return

        hour = self.time_manager.hour
        planned_pairs: set[frozenset] = set()

        # Check social commitments — guaranteed conversations for planned meetups
        from agents.memory import MemoryEntry
        for agent in self.agents.values():
            for commitment in agent.social_commitments[:]:
                commit_day = commitment.get("day", 0)
                commit_hour = commitment.get("when", 0)
                if not ((commit_day == self.time_manager.day or commitment.get("recurring")) and abs(hour - commit_hour) < 0.5):
                    continue

                commit_location = commitment.get("where", "")
                commit_with = commitment.get("with", [])

                if commit_with:
                    # Paired commitment — guaranteed conversation if both at same location
                    for other_name in commit_with:
                        other = None
                        for a in self.agents.values():
                            if a.name == other_name:
                                other = a
                                break
                        if other and other.current_location == agent.current_location:
                            pair = frozenset({agent.id, other.id})
                            if pair not in planned_pairs and conversation_manager.can_converse(agent.id, other.id, self.tick):
                                planned_pairs.add(pair)
                                self._pending_conversations.append((agent, other, agent.current_location))
                else:
                    # Solo commitment — resolve when agent arrives at the location
                    if agent.current_location == commit_location:
                        what = commitment.get("what", "something")
                        # Check if the person they wanted to see is actually here
                        people_here = [a.name for a in self.agents.values()
                                      if a.current_location == commit_location and a.id != agent.id]
                        if people_here:
                            agent.memory.add(MemoryEntry(
                                tick=self.tick,
                                content=f"I went to {commit_location.replace('_', ' ')} to {what}. I found {', '.join(people_here[:2])} there.",
                                importance=6.0, memory_type="action",
                                related_agents=people_here[:2],
                            ))
                        else:
                            agent.memory.add(MemoryEntry(
                                tick=self.tick,
                                content=f"I went to {commit_location.replace('_', ' ')} to {what}, but nobody was there.",
                                importance=4.0, memory_type="action",
                            ))
                        # Mark as done
                        if not commitment.get("recurring"):
                            agent.social_commitments.remove(commitment)
                            continue

                # Remove non-recurring commitments after their day passes
                if not commitment.get("recurring") and commit_day < self.time_manager.day:
                    agent.social_commitments.remove(commitment)

        # Group agents by location for random conversations (any location, not just social)
        by_location: dict[str, list[Agent]] = {}
        for agent in self.agents.values():
            if agent.current_action.value in ("walking", "sleeping"):
                continue
            loc = agent.current_location
            by_location.setdefault(loc, []).append(agent)

        # For each location with 2+ agents, maybe start a conversation
        for loc, agents_here in by_location.items():
            if len(agents_here) < 2:
                continue

            random.shuffle(agents_here)
            for i in range(0, len(agents_here) - 1, 2):
                a, b = agents_here[i], agents_here[i + 1]
                pair = frozenset({a.id, b.id})
                if pair in planned_pairs:
                    continue  # Already queued from commitment
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
                    a, b, loc, self.time_manager.time_of_day, self.tick, self.time_manager.day
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
            "buildings": self.world.get_buildings_list(),
            "tileGrid": self.world.get_tile_grid(),
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
            "dayRecaps": self.day_recaps[-30:],
            "bulletinBoard": bulletin_board.get_recent(20),
            "storyHighlights": self.story_highlights[-50:],
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
                "secretsDiscovered": sum(
                    1 for a in agents_list for s in a.secrets if len(s.get("known_by", [])) > 0
                ),
                "totalSecrets": sum(len(a.secrets) for a in agents_list),
                "dynamicGoals": sum(
                    1 for a in agents_list for g in a.active_goals
                    if g.get("source") != "personality" and g.get("status") == "active"
                ),
            },
        }

    def get_agent_detail(self, agent_id: str) -> dict:
        agent = self.agents.get(agent_id)
        if not agent:
            return {"error": f"Agent {agent_id} not found"}
        return agent.to_detail_dict()

    async def _process_cognition(self) -> list[dict]:
        """Run cognitive processes — V2 architecture with inner monologue, reflections, daily plans."""
        events = []
        agents_list = list(self.agents.values())
        random.shuffle(agents_list)

        # Inner monologue: 1 random agent per tick (every tick, lightweight)
        if agents_list and self.tick % 3 == 0:
            from agents.cognition_v2.inner_monologue import generate_thought
            agent = agents_list[0]
            thought = await generate_thought(
                agent, agent.current_location,
                self.time_manager.time_of_day, agent.current_action.value,
            )
            if thought:
                events.append({
                    "type": "agent_thought", "agentId": agent.id,
                    "thought": thought,
                })

        # Reflections: 1-2 random agents per tick (heavier LLM call)
        for agent in agents_list[:2]:
            ref_events = await cognition_system.maybe_reflect(
                agent, self.tick, settings.reflection_interval, self.time_manager.day
            )
            events.extend(ref_events)

        # Evening reflections (once per day at 22:00)
        if 22.0 < self.time_manager.hour < 22.5:
            from agents.cognition_v2.daily_cycle import evening_reflection
            for agent in agents_list[:3]:  # 3 agents per tick during evening window
                try:
                    await evening_reflection(agent, self.time_manager.day, self.tick)
                except Exception as e:
                    logger.error(f"Evening reflection failed for {agent.name}: {e}")

        # Morning plans: ALL agents at dawn
        if self.time_manager.hour < 7.5 and self.time_manager.hour > 6.5:
            from agents.cognition_v2.daily_cycle import morning_plan
            from llm.prompts import get_location_list
            locations = get_location_list()
            for agent in agents_list:
                try:
                    result = await morning_plan(agent, self.time_manager.day, self.tick, locations)
                    # Parse schedule from result
                    schedule_data = result.get("schedule", [])
                    if schedule_data and isinstance(schedule_data, list) and len(schedule_data) >= 3:
                        from agents.profiles import ScheduleEntry
                        from simulation.world import BUILDING_MAP
                        valid_locs = set(BUILDING_MAP.keys())
                        new_sched = []
                        for entry in schedule_data:
                            if isinstance(entry, dict):
                                loc = entry.get("location", "")
                                if loc in valid_locs:
                                    new_sched.append(ScheduleEntry(
                                        float(entry.get("hour", 8)), loc, entry.get("activity", "idle")
                                    ))
                        if len(new_sched) >= 3:
                            new_sched.sort(key=lambda e: e.hour)
                            agent.dynamic_schedule = new_sched
                    events.append({
                        "type": "agent_thought", "agentId": agent.id,
                        "thought": f"Plan: {agent.daily_plan[:80]}",
                    })
                except Exception as e:
                    logger.error(f"Morning plan failed for {agent.name}: {e}")

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

        elif command == "world_edit":
            action = params.get("action")
            col = params.get("col", 0)
            row = params.get("row", 0)
            if action == "set_terrain":
                self.world.set_tile_type(col, row, params.get("terrain_type", "grass"))
            elif action == "build":
                w = params.get("width", 2)
                h = params.get("height", 2)
                build_col, build_row = col, row
                if params.get("auto_place"):
                    spot = self.world.find_empty_space(w, h)
                    if spot:
                        build_col, build_row = spot
                    else:
                        logger.warning("No empty space found for building")
                        return
                bid = self.world.add_structure(
                    build_col, build_row, w, h,
                    params.get("structure_type", "house"),
                    params.get("label", "New Building"),
                    params.get("owner", ""),
                )
                if bid:
                    label = params.get("label", "New Building")
                    self._god_events = getattr(self, "_god_events", [])
                    self._god_events.append({
                        "type": "system_event",
                        "eventType": "building_constructed",
                        "label": "Building Constructed",
                        "description": f"{label} built at ({build_col},{build_row})",
                    })
                    # Notify all agents about the new building
                    from agents.memory import MemoryEntry
                    for agent in self.agents.values():
                        agent.memory.add(MemoryEntry(
                            tick=self.tick,
                            content=f"A new {params.get('structure_type', 'building')} called '{label}' has been built in town!",
                            importance=7.0,
                            memory_type="observation",
                        ))
            elif action == "demolish":
                bid = params.get("building_id", "")
                self.world.remove_structure(bid)
            elif action == "set_decoration":
                self.world.set_decoration(col, row, params.get("decoration"))
            elif action == "clear":
                self.world.set_decoration(col, row, None)
                tile = self.world.get_tile(col, row)
                if tile:
                    tile["type"] = "grass"
                    tile["walkable"] = True

    # --- Construction system ---
    def _process_construction(self) -> list[dict]:
        """Check if any agent has a build goal and execute it."""
        events = []
        from agents.memory import MemoryEntry
        from simulation.world import STRUCTURE_COSTS

        for agent in self.agents.values():
            for goal in agent.active_goals:
                if goal["status"] != "active":
                    continue
                text = goal["text"].lower()
                if "build" not in text:
                    continue

                # Parse what they want to build
                btype = "house"  # default
                for t in ["clinic", "bakery", "workshop", "tavern", "general_store", "barn", "school", "church", "house", "market_stall"]:
                    if t.replace("_", " ") in text or t in text:
                        btype = t
                        break

                cost_info = STRUCTURE_COSTS.get(btype, {"coins": 200, "tools": 5})
                cost = cost_info["coins"]

                # Can they afford it? (agent pays or treasury pays for public buildings)
                payer_wealth = agent.state.wealth
                use_treasury = btype in ("clinic", "school", "church") and self.economy.treasury > cost
                if use_treasury:
                    payer_wealth = self.economy.treasury

                if payer_wealth < cost:
                    continue

                # Find space
                spot = self.world.find_empty_space(2, 2)
                if not spot:
                    continue

                # Build it!
                label = f"{agent.name}'s {btype.replace('_', ' ').title()}"
                if btype == "clinic":
                    label = "Town Clinic"
                elif btype in ("school", "church"):
                    label = f"New {btype.title()}"

                if use_treasury:
                    self.economy.treasury -= cost
                else:
                    agent.state.wealth -= cost

                bid = self.world.add_structure(spot[0], spot[1], 2, 2, btype, label, agent.id)
                if bid:
                    goal["status"] = "completed"
                    agent.memory.add(MemoryEntry(
                        tick=self.tick,
                        content=f"I built a {btype.replace('_', ' ')}! It cost {cost} coins. It's called '{label}'.",
                        importance=10.0, memory_type="action",
                    ))
                    # Notify everyone
                    for other in self.agents.values():
                        if other.id != agent.id:
                            other.memory.add(MemoryEntry(
                                tick=self.tick,
                                content=f"{agent.name} has built a new {btype.replace('_', ' ')} called '{label}'!",
                                importance=8.0, memory_type="observation",
                            ))
                    events.append({
                        "type": "system_event", "eventType": "building_constructed",
                        "label": "New Building!", "description": f"{agent.name} built {label}",
                    })
                    logger.info(f"{agent.name} built {btype} '{label}' at {spot}")
                    break  # One build per agent per check

        return events

    # --- Trade Caravans ---
    _last_caravan_day: int = 0

    def _check_trade_caravan(self) -> list[dict]:
        """Spawn a trade caravan every 7-10 days."""
        events = []
        from agents.memory import MemoryEntry

        if self.time_manager.day - self._last_caravan_day < 7:
            return events

        self._last_caravan_day = self.time_manager.day

        CARAVAN_TYPES = [
            {"name": "Grain Merchant from the North", "goods": {"food": 20, "bread": 10}, "buys": "crafts"},
            {"name": "Tool Trader from the East", "goods": {"tools": 10}, "buys": "food"},
            {"name": "Cloth Merchant from the South", "goods": {"crafts": 15}, "buys": "ale"},
            {"name": "Medicine Peddler from the West", "goods": {"medicine": 8}, "buys": "food"},
            {"name": "Ale Merchant from the Valley", "goods": {"ale": 20}, "buys": "bread"},
        ]

        import random
        caravan = random.choice(CARAVAN_TYPES)

        # Boost supply
        for item, qty in caravan["goods"].items():
            self.economy.supply[item] = self.economy.supply.get(item, 0) + qty

        # Temporarily drop prices for caravan goods
        for item in caravan["goods"]:
            if item in self.economy.prices:
                self.economy.prices[item] *= 0.7

        # Notify all agents
        for agent in self.agents.values():
            agent.memory.add(MemoryEntry(
                tick=self.tick,
                content=f"A {caravan['name']} has arrived in town! They're selling {', '.join(caravan['goods'].keys())} at good prices and buying {caravan['buys']}.",
                importance=7.0, memory_type="observation",
            ))

        events.append({
            "type": "system_event", "eventType": "trade_caravan",
            "label": "Trade Caravan!", "description": f"A {caravan['name']} has arrived with goods!",
        })

        # Spawn temporary trader agent
        self._spawn_caravan_trader(caravan["name"])
        logger.info(f"Trade caravan arrived: {caravan['name']}")

        return events

    _caravan_trader_id: str | None = None
    _caravan_leave_day: int = 0

    def _spawn_caravan_trader(self, name: str):
        """Create a temporary trader agent that walks around town."""
        from agents.profiles import AgentProfile, ScheduleEntry
        from agents.agent import Agent

        # Remove old caravan trader if still present
        if self._caravan_trader_id and self._caravan_trader_id in self.agents:
            del self.agents[self._caravan_trader_id]

        trader_id = "caravan_trader"
        profile = AgentProfile(
            id=trader_id,
            name=name.split(" from ")[0] if " from " in name else "Caravan Trader",
            age=35,
            job="Trader",
            workplace="general_store",
            home="general_store",
            personality={"openness": 0.8, "conscientiousness": 0.6, "extraversion": 0.9, "agreeableness": 0.7, "neuroticism": 0.2},
            values=["trade", "travel", "profit"],
            goals=["Sell goods", "Meet the locals", "Find good deals"],
            fears=["Bad weather on the road"],
            backstory=f"A traveling merchant who visits small towns to trade. Currently passing through Agentica.",
            wealth=500,
            color_index=15,
            schedule=[
                ScheduleEntry(8.0, "general_store", "selling"),
                ScheduleEntry(11.0, "tavern", "eating"),
                ScheduleEntry(13.0, "town_hall", "idle"),
                ScheduleEntry(15.0, "general_store", "selling"),
                ScheduleEntry(18.0, "tavern", "eating"),
                ScheduleEntry(21.0, "general_store", "sleeping"),
            ],
        )

        trader = Agent(profile, self.world)
        # Start at map edge and walk in
        trader.position = self.world.get_building_entry("general_store")
        trader.current_location = "general_store"
        trader.current_action = ActionType.IDLE
        trader.emotion = "friendly"
        trader.inner_thought = "Let's see what this town has to offer."

        self.agents[trader_id] = trader
        self._caravan_trader_id = trader_id
        self._caravan_leave_day = self.time_manager.day + 1
        logger.info(f"Spawned caravan trader: {profile.name}")

    def _check_caravan_departure(self):
        """Remove the caravan trader after 1 day."""
        if self._caravan_trader_id and self.time_manager.day >= self._caravan_leave_day:
            if self._caravan_trader_id in self.agents:
                trader = self.agents[self._caravan_trader_id]
                # Notify everyone
                from agents.memory import MemoryEntry
                for agent in self.agents.values():
                    if agent.id != self._caravan_trader_id:
                        agent.memory.add(MemoryEntry(
                            tick=self.tick,
                            content=f"The traveling merchant {trader.name} has left town.",
                            importance=5.0, memory_type="observation",
                        ))
                del self.agents[self._caravan_trader_id]
                logger.info(f"Caravan trader departed")
            self._caravan_trader_id = None

    # --- Season changes ---
    def _on_season_change(self, new_season: str):
        from agents.memory import MemoryEntry
        SEASON_MESSAGES = {
            "spring": "Spring has arrived! The snow is melting and planting season begins.",
            "summer": "Summer is here. The crops are growing and the days are long and warm.",
            "autumn": "Autumn has come. Harvest time — the fields are golden and food is plentiful.",
            "winter": "Winter has set in. Food is scarce, prices are rising, and everyone needs warmth.",
        }
        msg = SEASON_MESSAGES.get(new_season, f"The season has changed to {new_season}.")
        for agent in self.agents.values():
            agent.memory.add(MemoryEntry(
                tick=self.tick, content=msg, importance=7.0, memory_type="observation",
            ))
        self._god_events = getattr(self, "_god_events", [])
        self._god_events.append({
            "type": "system_event", "eventType": "season_change",
            "label": f"{new_season.title()} Arrives", "description": msg,
        })

    # --- Crime system ---
    def _check_crimes(self) -> list[dict]:
        """Check for desperate agents who might steal."""
        events = []
        for agent in self.agents.values():
            if agent.state.wealth < 10 and agent.state.hunger > 0.7 and agent.state.mood < 0.3:
                if random.random() < 0.02:  # 2% per tick
                    from agents.memory import MemoryEntry
                    # Find a wealthier agent or steal from store
                    stolen_amount = random.randint(5, 15)
                    agent.state.wealth += stolen_amount
                    agent.emotion = "guilty"
                    agent.memory.add(MemoryEntry(
                        tick=self.tick,
                        content=f"I was desperate and stole {stolen_amount} coins. I feel terrible about it.",
                        importance=10.0, memory_type="emotion",
                    ))
                    agent.reputation["honesty"] = max(0, agent.reputation.get("honesty", 0.5) - 0.2)
                    # Check for witnesses (agents at same location)
                    for other in self.agents.values():
                        if other.id != agent.id and other.current_location == agent.current_location:
                            other.memory.add(MemoryEntry(
                                tick=self.tick,
                                content=f"I saw {agent.name} stealing! I can't believe it.",
                                importance=9.0, memory_type="observation",
                                related_agents=[agent.name],
                            ))
                            # Damage relationship
                            if agent.name not in other.relationships:
                                other.relationships[agent.name] = {"sentiment": 0.5, "trust": 0.5, "familiarity": 0.1, "notes": "Acquaintance"}
                            other.relationships[agent.name]["trust"] = max(0, other.relationships[agent.name].get("trust", 0.5) - 0.3)
                            other.relationships[agent.name]["sentiment"] = max(-1, other.relationships[agent.name].get("sentiment", 0.5) - 0.2)
                            events.append({
                                "type": "agent_thought", "agentId": other.id,
                                "thought": f"I saw {agent.name} stealing!",
                            })
                    events.append({
                        "type": "system_event", "eventType": "crime",
                        "label": "Theft", "description": f"{agent.name} stole {stolen_amount} coins out of desperation",
                    })
        return events

    # --- Story detection ---
    def _detect_stories(self) -> list[dict]:
        """Detect narratively interesting events."""
        highlights = []
        for agent in self.agents.values():
            # Wealth crisis
            if agent.state.wealth < 15 and not getattr(agent, "_crisis_flagged", False):
                highlights.append({"type": "crisis", "agentId": agent.id, "agentName": agent.name, "text": f"{agent.name} is running out of money ({agent.state.wealth} coins)"})
                agent._crisis_flagged = True
            elif agent.state.wealth >= 30:
                agent._crisis_flagged = False
            # Secret exposed
            for s in agent.secrets:
                if len(s.get("known_by", [])) >= 3 and not s.get("highlighted"):
                    highlights.append({"type": "scandal", "agentId": agent.id, "agentName": agent.name, "text": f"{agent.name}'s secret exposed: {s['content'][:60]}"})
                    s["highlighted"] = True
            # Goal achieved
            for g in agent.active_goals:
                if g["status"] == "completed" and not g.get("highlighted"):
                    highlights.append({"type": "achievement", "agentId": agent.id, "agentName": agent.name, "text": f"{agent.name} achieved: {g['text']}"})
                    g["highlighted"] = True
            # New dynamic goal
            for g in agent.active_goals:
                if g.get("source") != "personality" and not g.get("announced") and g["status"] == "active":
                    highlights.append({"type": "new_goal", "agentId": agent.id, "agentName": agent.name, "text": f"{agent.name} has a new goal: {g['text']}"})
                    g["announced"] = True
        return highlights

    # --- Daily recap ---
    async def _generate_daily_recap(self):
        """Generate a day recap summary."""
        from llm.client import llm_client
        # Collect today's key memories across all agents
        today_memories = []
        for agent in self.agents.values():
            for m in agent.memory.recent(10):
                if getattr(m, 'emotional_intensity', getattr(m, 'importance', 5) / 10) >= 0.6:
                    today_memories.append(f"{agent.name}: {m.content}")
        if not today_memories:
            return
        memories_text = "\n".join(today_memories[-15:])
        result = await llm_client.generate(
            "You are a narrator summarizing a day in a small town simulation called Agentica.",
            f"Here are today's most notable events in the town:\n{memories_text}\n\nSummarize what happened today in 2-3 sentences. Be specific about names and events.",
            temperature=0.7, max_tokens=200,
        )
        if result:
            self.day_recaps.append({"day": self.time_manager.day, "summary": result.strip(), "tick": self.tick})

    # --- Autobiography ---
    _autobiography_cache: dict[str, dict] = {}  # agent_id -> {"day": int, "text": str}

    async def generate_autobiography(self, agent_id: str) -> str:
        """Generate a first-person narrative for an agent. Cached per sim day."""
        agent = self.agents.get(agent_id)
        if not agent:
            return "Agent not found."

        # Return cached version if same day
        cached = self._autobiography_cache.get(agent_id)
        if cached and cached["day"] == self.time_manager.day:
            return cached["text"]

        from llm.client import llm_client
        # Gather key data
        memories = [m.content for m in agent.memory.recent(20) if getattr(m, 'emotional_intensity', getattr(m, 'importance', 5)) >= 0.5]
        goals = [g["text"] for g in agent.active_goals if g["status"] == "active"]
        completed = [g["text"] for g in agent.active_goals if g["status"] == "completed"]
        rels = []
        for name, rel in agent.relationships.items():
            sent = rel.get("sentiment", 0.5)
            if sent > 0.6:
                rels.append(f"close friend: {name}")
            elif sent < 0.2:
                rels.append(f"strained relationship: {name}")

        context = f"""Agent: {agent.name}, {agent.profile.age}yo {agent.profile.job}
Current mood: {agent.emotion}, wealth: {agent.state.wealth} coins
Day: {self.time_manager.day}, Season: {self.time_manager.season}
Key memories:\n{chr(10).join('- ' + m for m in memories[-10:])}
Active goals: {', '.join(goals) or 'none'}
Completed goals: {', '.join(completed) or 'none'}
Key relationships: {', '.join(rels) or 'still getting to know people'}
Secret: {agent.secrets[0]['content'] if agent.secrets else 'none'}"""

        result = await llm_client.generate(
            f"You are {agent.name}. Write a first-person narrative (1 paragraph, 4-6 sentences) about your life in Agentica so far. Be emotional, specific, and authentic. Reference real events from your memories.",
            context, temperature=0.9, max_tokens=300,
        )
        text = result or "I'm still finding my way in this town..."
        self._autobiography_cache[agent_id] = {"day": self.time_manager.day, "text": text}
        return text

    _autobio_pregenerated_day: int = 0

    async def _pregenerate_autobiographies(self):
        """Pre-generate all agent autobiographies at noon. Runs once per day."""
        if self._autobio_pregenerated_day >= self.time_manager.day:
            return
        self._autobio_pregenerated_day = self.time_manager.day
        logger.info("Pre-generating autobiographies for all agents...")
        for agent_id in self.agents:
            await self.generate_autobiography(agent_id)
        logger.info("All autobiographies pre-generated")
