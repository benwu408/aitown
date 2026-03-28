"""Open-ended simulation engine — drive-based, no predetermined roles."""

import asyncio
import logging
import random
from typing import Callable, Coroutine

from config import settings, TICK_DURATION_MS, TICKS_PER_DAY, REFLECTION_INTERVAL
from simulation.time_manager import TimeManager
from simulation.world_v2 import WorldV2
from agents.agent_v2 import AgentV2
from agents.profiles_v2 import AGENT_PROFILES_V2
from simulation.actions import ActionType
from db.database_v2 import init_db_v2, save_world_state_v2, load_world_state_v2

logger = logging.getLogger("agentica.engine")


class SimulationEngineV2:
    def __init__(self):
        self.tick = 0
        self.speed = 1
        self.running = False
        self.time_manager = TimeManager(ticks_per_day=TICKS_PER_DAY)
        self.world = WorldV2()
        self._broadcast: Callable[[dict], Coroutine] | None = None
        self.agents: dict[str, AgentV2] = {}
        self.story_highlights: list[dict] = []
        self.day_recaps: list[dict] = []
        # Start at dawn, not midnight
        # Start at 6am (dawn)
        self.time_manager.tick_in_day = int(6.0 / 24.0 * TICKS_PER_DAY)
        self._active_conversations = 0
        self._last_morning_day = -1
        self._last_evening_day = -1
        self._init_agents()

    def _init_agents(self):
        # Spread agents around the clearing so they don't all spawn on the same tile
        base = self.world.get_location_entry("clearing")
        occupied: set[tuple[int, int]] = set()
        for profile in AGENT_PROFILES_V2:
            agent = AgentV2(profile, self.world)
            # Find a nearby unoccupied tile in a spiral around the entry point
            pos = self._find_unoccupied_near(base, occupied)
            agent.position = pos
            occupied.add(pos)
            self.agents[agent.id] = agent
        logger.info(f"Initialized {len(self.agents)} blank agents in abandoned settlement")

    def _find_unoccupied_near(self, center: tuple[int, int], occupied: set[tuple[int, int]]) -> tuple[int, int]:
        """Find the nearest unoccupied tile spiraling out from center."""
        cx, cy = center
        if (cx, cy) not in occupied:
            return (cx, cy)
        for radius in range(1, 10):
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    if abs(dx) == radius or abs(dy) == radius:
                        pos = (cx + dx, cy + dy)
                        if pos not in occupied and 0 <= pos[0] < self.world.width and 0 <= pos[1] < self.world.height:
                            return pos
        return (cx + 1, cy + 1)  # fallback

    def _restore_from_save(self, data: dict):
        """Restore full simulation state from a saved snapshot."""
        self.tick = data.get("tick", 0)
        self.time_manager.day = data.get("day", 0)
        self.time_manager.tick_in_day = data.get("tick_in_day", 0)
        self.speed = data.get("speed", 1)
        self.story_highlights = data.get("story_highlights", [])
        self.day_recaps = data.get("day_recaps", [])

        # Restore world
        if data.get("world"):
            self.world.load_from_save(data["world"])

        # Restore agents — match by ID to existing profiles
        saved_agents = data.get("agents", {})
        for agent_id, agent in self.agents.items():
            saved = saved_agents.get(agent_id)
            if not saved:
                continue

            # Position and basic state
            if saved.get("position"):
                agent.position = tuple(saved["position"])
            agent.current_location = saved.get("current_location", "clearing")
            agent.inner_thought = saved.get("inner_thought", "")
            agent.daily_plan = saved.get("daily_plan", "")
            agent.self_concept = saved.get("self_concept")
            agent.emotion = saved.get("emotion", "neutral")

            try:
                agent.current_action = ActionType(saved.get("current_action", "idle"))
            except ValueError:
                agent.current_action = ActionType.IDLE

            # Cognitive layers
            if saved.get("emotions"):
                agent.emotional_state.load_from_dict(saved["emotions"])
            if saved.get("drives"):
                agent.drives.load_from_dict(saved["drives"])
            if saved.get("episodic_memory"):
                agent.episodic_memory.load_from_list(saved["episodic_memory"])
            if saved.get("working_memory"):
                agent.working_memory.load_from_dict(saved["working_memory"])
            if saved.get("beliefs"):
                agent.belief_system.load_from_list(saved["beliefs"])
            if saved.get("mental_models"):
                agent.mental_models.load_from_dict(saved["mental_models"])
            if saved.get("skills"):
                agent.skill_memory.load_from_dict(saved["skills"])
            if saved.get("world_model"):
                agent.world_model.load_from_dict(saved["world_model"])

            # Social/inventory
            agent.relationships = saved.get("relationships", {})
            agent.active_goals = saved.get("active_goals", [])
            agent.inventory = saved.get("inventory", [])
            agent.secrets = saved.get("secrets", [])
            agent.opinions = saved.get("opinions", {})

        # Reset agents stuck in walking/talking with no path — they need to re-evaluate
        for agent in self.agents.values():
            if not agent.path and agent.current_action in (ActionType.WALKING, ActionType.TALKING):
                agent.current_action = ActionType.IDLE

        logger.info(f"Restored {len(saved_agents)} agents from save")

    def set_broadcast(self, fn):
        self._broadcast = fn

    def set_speed(self, speed: int):
        self.speed = max(0, min(10, speed))

    def stop(self):
        self.running = False
        # Save state synchronously-ish on shutdown
        asyncio.ensure_future(self._save_on_stop())

    async def _save_on_stop(self):
        try:
            await save_world_state_v2(self)
            logger.info("Saved state on shutdown")
        except Exception as e:
            logger.error(f"Failed to save on shutdown: {e}")

    async def run(self):
        self.running = True

        # Initialize DB and try to load saved state
        await init_db_v2()
        save_data = await load_world_state_v2()
        if save_data:
            self._restore_from_save(save_data)
            logger.info(f"Resumed from save — tick {self.tick}, day {self.time_manager.day}")
        else:
            logger.info("Open-ended simulation started — Day 1, Dawn")

        # Batch processing tuned for smooth visuals
        BATCH_SIZE = 1  # At 1x: 1 tick per broadcast = smoothest movement
        BROADCAST_INTERVAL = 0.3  # ~3.3 broadcasts/sec — smooth clock + visible walking
        FULL_STATE_INTERVAL = 15  # Full state (with drives/emotions) every 15 ticks

        while self.running:
            if self.speed == 0:
                await asyncio.sleep(0.1)
                continue

            interval = BROADCAST_INTERVAL / max(self.speed, 1)
            await asyncio.sleep(interval)

            # Process a batch of ticks without yielding to the event loop
            batch_events = []
            batch_count = BATCH_SIZE * max(self.speed, 1)
            batch_count = min(int(batch_count), 10)  # cap so it doesn't fly

            for _ in range(int(batch_count)):
                try:
                    self.tick += 1
                    self.time_manager.advance()
                    events = self._process_tick()
                    batch_events.extend(events)
                except Exception as e:
                    logger.error(f"Tick {self.tick} error: {e}")

                # Inner monologue (non-blocking, infrequent)
                if self.tick % 60 == 0:
                    asyncio.create_task(self._process_inner_monologue_background())

                # Resource regeneration
                if self.tick % 200 == 0:
                    self.world.regenerate_resources()

                # Auto-save every 100 ticks (~30 seconds at 1x)
                if self.tick % 100 == 0:
                    asyncio.create_task(save_world_state_v2(self))

            # ONE broadcast per batch — much less I/O
            if self._broadcast:
                try:
                    is_full = (self.tick % FULL_STATE_INTERVAL) < batch_count
                    if is_full:
                        await self._broadcast({
                            "type": "tick",
                            "data": {
                                "tick": self.tick,
                                "time": self.time_manager.to_dict(),
                                "events": batch_events,
                                "agents": [a.to_dict() for a in self.agents.values()],
                                "storyHighlights": self.story_highlights[-20:],
                            },
                        })
                    else:
                        await self._broadcast({
                            "type": "tick",
                            "data": {
                                "tick": self.tick,
                                "time": self.time_manager.to_dict(),
                                "events": batch_events,
                                "agents": [
                                    {"id": a.id, "position": list(a.position),
                                     "currentAction": a.current_action.value,
                                     "currentLocation": a.current_location,
                                     "emotion": a.emotion}
                                    for a in self.agents.values()
                                ],
                            },
                        })
                except Exception:
                    pass

    async def _broadcast_light(self, events):
        """Lightweight broadcast — just time, positions, and events. Small payload."""
        try:
            agents_light = [
                {"id": a.id, "position": list(a.position), "currentAction": a.current_action.value,
                 "currentLocation": a.current_location, "emotion": a.emotion}
                for a in self.agents.values()
            ]
            await self._broadcast({
                "type": "tick",
                "data": {
                    "tick": self.tick,
                    "time": self.time_manager.to_dict(),
                    "events": events,
                    "agents": agents_light,
                },
            })
        except Exception as e:
            logger.error(f"Light broadcast error: {e}")

    async def _broadcast_safe(self, events):
        try:
            await self._broadcast({
                "type": "tick",
                "data": {
                    "tick": self.tick,
                    "time": self.time_manager.to_dict(),
                    "events": events,
                    "agents": [a.to_dict() for a in self.agents.values()],
                    "storyHighlights": self.story_highlights[-20:],
                },
            })
        except Exception as e:
            logger.error(f"Broadcast error: {e}")

    def _process_tick(self) -> list[dict]:
        events = []
        hour = self.time_manager.hour
        time_of_day = self.time_manager.time_of_day

        for agent in self.agents.values():
            # Tick down conversation cooldown
            if agent.conversation_cooldown > 0:
                agent.conversation_cooldown -= 1

            # Update drives
            is_alone = all(
                other.current_location != agent.current_location
                for other in self.agents.values() if other.id != agent.id
            )
            has_home = any(
                loc.get("claimed_by") == agent.name
                for loc in self.world.locations.values()
                if loc.get("type") == "built_structure"
            )
            agent.drives.tick_update(
                is_working=agent.current_action.value in ("working", "building"),
                is_sleeping=agent.current_action.value == "sleeping",
                is_alone=is_alone,
                is_socializing=agent.current_action.value == "talking",
                wealth=0,
                has_home=has_home,
            )

            # Satisfy hunger when at food location and eating
            if agent.current_action.value == "eating":
                agent.drives.satisfy_hunger()

            # Decay emotions
            agent.emotional_state.decay(1)

            # Update working memory from drives (every 10 ticks)
            if self.tick % 10 == 0:
                agent.working_memory.update_from_drives(agent.drives)

            # Movement update
            agent_events = agent.update(hour, self.world)
            events.extend(agent_events)

            # Reset eating/sleeping to idle after each tick so agent re-evaluates
            if agent.current_action.value in ("eating", "sleeping") and not agent.path:
                agent.current_action = ActionType.IDLE

            # Drive-based routine behavior (if not walking or in conversation)
            if agent.current_action.value == "idle" and not agent.path:
                routine = agent.get_routine_action(hour, time_of_day)
                target = routine.get("target", agent.current_location)
                action = routine.get("action", "idle")

                if action == "walking" and target != agent.current_location:
                    agent.start_walking(target)
                    events.append({
                        "type": "agent_move",
                        "agentId": agent.id,
                        "targetLocation": target,
                    })
                elif action == "eating":
                    # Try to gather food at current location
                    resources_here = self.world.get_resources_at(agent.current_location)
                    ate = False
                    for food_type in ["wild_berries", "fish", "wild_plants"]:
                        if food_type in resources_here:
                            gathered = self.world.gather_resource(food_type, 1, agent.current_location)
                            if gathered > 0:
                                agent.inventory.append({"name": food_type, "quantity": gathered})
                                agent.drives.satisfy_hunger()
                                agent.skill_memory.record_attempt(
                                    "fishing" if food_type == "fish" else "gathering",
                                    True, 0.4
                                )
                                agent.current_action = ActionType.EATING
                                agent.emotional_state.apply_event("earned_money", 0.2)  # satisfaction
                                ate = True
                                break
                    if not ate:
                        # No food here — go back to idle so agent moves on
                        agent.current_action = ActionType.IDLE
                        agent.inner_thought = "Nothing to eat here..."
                elif action == "sleeping":
                    agent.current_action = ActionType.SLEEPING
                elif action == "gathering_wood":
                    # Gather wood from forest
                    gathered = self.world.gather_resource("wood", 1, agent.current_location)
                    if gathered > 0:
                        agent.inventory.append({"name": "wood", "quantity": gathered})
                        agent.skill_memory.record_attempt("gathering", True, 0.4)
                        agent.current_action = ActionType.WORKING
                    else:
                        agent.current_action = ActionType.IDLE
                elif action == "building":
                    # Build a shelter
                    spot = self.world.find_empty_space(2, 2)
                    if spot:
                        bid = self.world.build_structure(
                            spot[0], spot[1], 2, 2,
                            f"{agent.name.split()[0]}'s Shelter",
                            agent.name, "shelter",
                        )
                        if bid:
                            # Remove wood from inventory
                            for item in agent.inventory[:]:
                                if item.get("name") == "wood":
                                    agent.inventory.remove(item)
                                    break
                            agent.drives.satisfy_shelter()
                            agent.skill_memory.record_attempt("construction", True, 0.6)
                            agent.current_action = ActionType.BUILDING
                            agent.emotional_state.apply_event("accomplishment", 0.6)
                            agent.inner_thought = f"I built my own shelter!"
                            events.append({
                                "type": "system_event",
                                "eventType": "building_constructed",
                                "label": "Construction!",
                                "description": f"{agent.name} built a shelter",
                            })

                if routine.get("thought"):
                    agent.inner_thought = routine["thought"]

        # Prevent agents from standing on the exact same tile
        self._resolve_collisions()

        # Observations — agents notice nearby agents (every 10 ticks)
        if self.tick % 10 == 0:
            from systems.interactions import observation_system, VISUAL_RANGE
            for agent in self.agents.values():
                if agent.current_action.value in ("sleeping",):
                    continue
                for other in self.agents.values():
                    if other.id == agent.id:
                        continue
                    dist = abs(agent.position[0] - other.position[0]) + abs(agent.position[1] - other.position[1])
                    if dist <= VISUAL_RANGE:
                        obs = observation_system.generate_observation(agent, other, dist)
                        if obs:
                            agent.working_memory.latest_observation = obs

        # Full interaction pipeline (every 5 ticks to save CPU)
        if self.tick % 5 == 0:
            interaction_events = self._process_interactions()
            events.extend(interaction_events)

        # Gossip propagation (every 50 ticks)
        if self.tick % 50 == 0:
            try:
                from systems.social import social_system
                social_system.propagate_gossip(self.agents)
            except Exception:
                pass  # Social system may not be fully compatible yet

        # Daily cycle — morning planning at dawn, evening reflection at night
        day = self.time_manager.day
        if 6 <= hour < 7 and self._last_morning_day < day:
            self._last_morning_day = day
            asyncio.create_task(self._run_daily_morning())
        if 21 <= hour < 22 and self._last_evening_day < day:
            self._last_evening_day = day
            asyncio.create_task(self._run_daily_evening())

        # Novel actions via action interpreter (every 30 ticks, 1 random idle agent)
        if self.tick % 30 == 0:
            asyncio.create_task(self._process_novel_action())

        # Meta-simulation (every 100 ticks)
        if self.tick % 100 == 0:
            from systems.meta_simulation import meta_simulation
            meta_events = meta_simulation.check(self.agents, self.world, self.tick, self.time_manager.day)
            events.extend(meta_events)

        # Coherence check (every 200 ticks)
        if self.tick % 200 == 0:
            from systems.coherence import coherence_checker
            coherence_checker.check(self.agents, self.world)

        return events

    def _resolve_collisions(self):
        """Nudge agents so no two stand on the exact same tile."""
        occupied: dict[tuple[int, int], str] = {}  # pos -> first agent id
        for agent in self.agents.values():
            pos = agent.position
            if pos in occupied:
                # This agent collides — nudge to adjacent empty tile
                cx, cy = pos
                nudged = False
                for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)]:
                    candidate = (cx + dx, cy + dy)
                    if candidate not in occupied and 0 <= candidate[0] < self.world.width and 0 <= candidate[1] < self.world.height:
                        agent.position = candidate
                        occupied[candidate] = agent.id
                        nudged = True
                        break
                if not nudged:
                    occupied[pos] = agent.id  # give up, stay put
            else:
                occupied[pos] = agent.id

    def _process_interactions(self) -> list[dict]:
        """Spatial-hash optimized interaction pipeline."""
        events = []
        from systems.interactions import (
            interaction_decider, lightweight,
            select_interaction_type, ConversationV2, process_conversation_consequences,
            overhearing_system, INTERACTION_TYPES, CONVERSATION_RANGE,
        )

        # Spatial hash: group agents by location (O(n) instead of O(n²))
        by_location: dict[str, list] = {}
        for agent in self.agents.values():
            if agent.current_action.value in ("walking", "sleeping"):
                continue
            if getattr(agent, "is_in_conversation", False):
                continue
            if getattr(agent, "conversation_cooldown", 0) > 0:
                continue
            by_location.setdefault(agent.current_location, []).append(agent)

        # Only check interactions between agents at the SAME location
        for loc, agents_here in by_location.items():
            if len(agents_here) < 2:
                continue

            # Build perceived list cheaply (they're all at same location)
            for agent in agents_here:
                perceived = []
                for other in agents_here:
                    if other.id == agent.id or getattr(other, "is_in_conversation", False):
                        continue
                    dist = abs(agent.position[0] - other.position[0]) + abs(agent.position[1] - other.position[1])
                    perceived.append({
                        "agent": other, "distance": dist,
                        "attention": 0.3, "can_talk": dist <= CONVERSATION_RANGE,
                        "can_overhear": True, "same_location": True,
                    })

                if not perceived:
                    continue

                should, target, reason = interaction_decider.should_interact(agent, perceived)
                if not should or not target:
                    continue

                # Select interaction type
                rel = agent.relationships.get(target.name, {})
                itype = select_interaction_type(agent, target, reason, rel)
                type_info = INTERACTION_TYPES.get(itype, {})

                if not type_info.get("llm", False):
                    # Lightweight interaction — template based, no LLM
                    if itype == "greeting":
                        speech = lightweight.generate_greeting(agent, target, rel, self.time_manager.time_of_day)
                    else:
                        speech = lightweight.generate_small_talk(agent)

                    events.append({
                        "type": "agent_speak", "agentId": agent.id,
                        "targetId": target.id, "speech": speech,
                    })

                    # Satisfies social need and builds familiarity for BOTH
                    agent.drives.satisfy_social()
                    target.drives.satisfy_social()
                    agent.emotional_state.apply_event("social_interaction", 0.2)
                    target.emotional_state.apply_event("social_interaction", 0.2)
                    for a, b in [(agent, target), (target, agent)]:
                        if b.name not in a.relationships:
                            a.relationships[b.name] = {"sentiment": 0.5, "trust": 0.5, "familiarity": 0.0}
                        a.relationships[b.name]["familiarity"] = min(1.0, a.relationships[b.name].get("familiarity", 0) + 0.06)

                    # Overhearing: nearby agents catch fragments
                    for p in perceived:
                        if p["agent"].id != target.id and p["can_overhear"]:
                            overhearing_system.process(p["agent"], [agent.name, target.name], speech, p["distance"])

                else:
                    # Queue LLM conversation — cap at 2 concurrent to keep pace readable
                    if self._active_conversations >= 2:
                        continue  # Too many conversations already, skip
                    asyncio.create_task(self._run_conversation(agent, target, itype, reason))

                break  # One interaction per agent per cycle

        return events

    async def _run_conversation(self, agent, target, itype: str, reason: str):
        """Run an LLM-powered conversation in the background."""
        from systems.interactions import ConversationV2, process_conversation_consequences

        self._active_conversations += 1
        try:
            agent.is_in_conversation = True
            target.is_in_conversation = True

            convo = ConversationV2(agent, target, itype, reason, agent.current_location)

            # Opening
            opening = await convo.generate_turn(agent, target)
            if self._broadcast and opening.get("speech"):
                await self._broadcast({
                    "type": "tick",
                    "data": {
                        "tick": self.tick,
                        "time": self.time_manager.to_dict(),
                        "events": [{"type": "agent_speak", "agentId": agent.id, "targetId": target.id, "speech": opening["speech"]}],
                        "agents": [a.to_dict() for a in self.agents.values()],
                    },
                })

            # Multi-turn exchange
            speakers = [target, agent]
            current_speech = opening.get("speech", "")
            for turn_idx in range(convo.max_turns):
                speaker = speakers[turn_idx % 2]
                listener = speakers[(turn_idx + 1) % 2]

                result = await convo.generate_turn(speaker, listener, current_speech)
                current_speech = result.get("speech", "")

                if self._broadcast and current_speech:
                    await self._broadcast({
                        "type": "tick",
                        "data": {
                            "tick": self.tick,
                            "time": self.time_manager.to_dict(),
                            "events": [{"type": "agent_speak", "agentId": speaker.id, "targetId": listener.id, "speech": current_speech}],
                            "agents": [a.to_dict() for a in self.agents.values()],
                        },
                    })

                if not result.get("wants_to_continue", True):
                    break

            # Process consequences for both agents
            process_conversation_consequences(agent, target.name, convo)
            process_conversation_consequences(target, agent.name, convo)

        except Exception as e:
            logger.error(f"Conversation error: {e}")
        finally:
            agent.is_in_conversation = False
            target.is_in_conversation = False
            agent.conversation_cooldown = 30  # ~90 sim-minutes before next chat
            target.conversation_cooldown = 30
            self._active_conversations = max(0, self._active_conversations - 1)

            # Force dispersal — both agents walk to different locations after chatting
            for a in [agent, target]:
                known = list(a.world_model.known_locations.keys())
                elsewhere = [l for l in known if l != a.current_location]
                if elsewhere:
                    a.start_walking(random.choice(elsewhere))

    async def _process_inner_monologue_background(self):
        """Generate inner thought in background — doesn't block tick loop."""
        try:
            agents_list = list(self.agents.values())
            if not agents_list:
                return
            agent = random.choice(agents_list)
            from agents.cognition_v2.inner_monologue import generate_thought
            thought = await generate_thought(
                agent, agent.current_location,
                self.time_manager.time_of_day, agent.current_action.value,
            )
            if thought and self._broadcast:
                await self._broadcast({
                    "type": "tick",
                    "data": {
                        "tick": self.tick,
                        "time": self.time_manager.to_dict(),
                        "events": [{"type": "agent_thought", "agentId": agent.id, "thought": thought}],
                        "agents": [a.to_dict() for a in self.agents.values()],
                    },
                })
        except Exception as e:
            logger.error(f"Inner monologue error: {e}")

    async def _run_daily_morning(self):
        """Run morning planning for all agents."""
        from agents.cognition_v2.daily_cycle import morning_plan
        locations = ", ".join(self.world.get_all_location_ids())
        for agent in list(self.agents.values()):
            try:
                await morning_plan(agent, self.time_manager.day, self.tick, locations)
            except Exception as e:
                logger.error(f"Morning plan error for {agent.name}: {e}")
        logger.info(f"Morning planning complete for day {self.time_manager.day}")

    async def _run_daily_evening(self):
        """Run evening reflection for all agents."""
        from agents.cognition_v2.daily_cycle import evening_reflection
        for agent in list(self.agents.values()):
            try:
                await evening_reflection(agent, self.time_manager.day, self.tick)
            except Exception as e:
                logger.error(f"Evening reflection error for {agent.name}: {e}")
        logger.info(f"Evening reflection complete for day {self.time_manager.day}")

    async def _process_novel_action(self):
        """Pick one idle agent and let them attempt a creative action."""
        from systems.action_interpreter import ActionInterpreter
        idle_agents = [a for a in self.agents.values()
                       if a.current_action.value == "idle" and not a.path
                       and not getattr(a, "is_in_conversation", False)]
        if not idle_agents:
            return
        agent = random.choice(idle_agents)
        try:
            # Generate action idea from agent's drives and situation
            drive_desc = agent.drives.get_prompt_description()
            action_desc = f"{agent.name} wants to do something useful. {drive_desc} They are at {agent.current_location}."
            interpreter = ActionInterpreter()
            result = await interpreter.evaluate_action(agent, action_desc, self.world)
            if result.get("is_possible") and result.get("success_probability", 0) > 0.3:
                events = interpreter.apply_consequences(agent, result, self.world)
                if events and self._broadcast:
                    await self._broadcast({
                        "type": "tick",
                        "data": {
                            "tick": self.tick,
                            "time": self.time_manager.to_dict(),
                            "events": events,
                            "agents": [a.to_dict() for a in self.agents.values()],
                        },
                    })
        except Exception as e:
            logger.error(f"Novel action error for {agent.name}: {e}")

    def get_world_state(self) -> dict:
        return {
            "tick": self.tick,
            "time": self.time_manager.to_dict(),
            "agents": [a.to_dict() for a in self.agents.values()],
            "weather": self.time_manager.weather,
            "speed": self.speed,
            "economy": {"prices": {}, "supply": {}, "treasury": 0, "totalTransactions": 0},
            "buildings": self.world.get_buildings_list(),
            "tileGrid": self.world.get_tile_grid(),
            "worldSummary": self.world.get_world_summary(),
        }

    def get_agent_detail(self, agent_id: str) -> dict:
        agent = self.agents.get(agent_id)
        if not agent:
            return {"error": f"Agent {agent_id} not found"}
        return agent.to_detail_dict()

    def get_dashboard_data(self) -> dict:
        return {
            "tick": self.tick,
            "time": self.time_manager.to_dict(),
            "agents": [a.to_detail_dict() for a in self.agents.values()],
            "economy": {"prices": {}, "supply": {}, "treasury": 0},
            "constitution": self.world.constitution.to_dict(),
            "storyHighlights": self.story_highlights[-50:],
            "dayRecaps": self.day_recaps[-30:],
            "resources": self.world.resources,
            "worldSummary": self.world.get_world_summary(),
            "townStats": {
                "population": len(self.agents),
                "avgMood": round(sum(
                    (a.emotional_state.valence + 1) / 2 for a in self.agents.values()
                ) / max(len(self.agents), 1), 2),
                "totalMemories": sum(len(a.episodic_memory.episodes) for a in self.agents.values()),
                "claimedBuildings": sum(1 for loc in self.world.locations.values() if loc.get("claimed_by")),
                "unclaimedBuildings": len(self.world.get_unclaimed_buildings()),
                "totalSkillsDiscovered": sum(len(a.skill_memory.activities) for a in self.agents.values()),
                "totalLocationsDiscovered": sum(len(a.world_model.known_locations) for a in self.agents.values()),
            },
        }

    async def generate_autobiography(self, agent_id: str) -> str:
        agent = self.agents.get(agent_id)
        if not agent:
            return "Agent not found."
        from llm.client import llm_client
        memories = [m.content for m in agent.episodic_memory.recent(15)]
        skills = agent.skill_memory.get_prompt_summary()
        context = f"""Agent: {agent.name}, {agent.profile.age}yo
Day: {self.time_manager.day}, Season: {self.time_manager.season}
Self-concept: {agent.self_concept or 'still figuring things out'}
Skills: {skills}
Key memories:\n{chr(10).join('- ' + m for m in memories[-8:])}
Backstory: {agent.profile.backstory}"""
        result = await llm_client.generate(
            f"You are {agent.name}. Write a first-person narrative (1 paragraph, 4-6 sentences) about your experience so far in this new settlement. Be emotional and authentic.",
            context, temperature=0.9, max_tokens=300,
        )
        return result or "I'm still finding my way..."

    def handle_god_command(self, command: str, params: dict):
        logger.info(f"God command: {command} params={params}")
