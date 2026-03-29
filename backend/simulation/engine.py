"""Open-ended simulation engine — drive-based, no predetermined roles."""

import asyncio
import logging
import random
from typing import Callable, Coroutine

from config import TICK_DURATION_MS, TICKS_PER_DAY
from simulation.time_manager import TimeManager
from simulation.world import World
from agents.agent import Agent
from agents.profiles import AGENT_PROFILES
from simulation.actions import ActionType
from db.database import init_db, save_world_state, load_world_state

logger = logging.getLogger("agentica.engine")


class SimulationEngine:
    def __init__(self):
        self.tick = 0
        self.speed = 1
        self.running = False
        self.time_manager = TimeManager(ticks_per_day=TICKS_PER_DAY)
        self.world = World()
        self.world._time_manager = self.time_manager
        self._broadcast: Callable[[dict], Coroutine] | None = None
        self.agents: dict[str, Agent] = {}
        self.story_highlights: list[dict] = []
        self.day_recaps: list[dict] = []
        self.debug_events: list[dict] = []
        self._world_state_dirty = False
        self._save_lock = asyncio.Lock()
        self._save_task: asyncio.Task | None = None
        self._last_saved_tick = 0
        self.time_manager.tick_in_day = int(6.0 / 24.0 * TICKS_PER_DAY)
        self._live_conversations: dict = {}  # id -> LiveConversation
        self._last_morning_day = -1
        self._last_evening_day = -1
        self._init_agents()

    def _init_agents(self):
        base = self.world.get_location_entry("clearing")
        occupied: set[tuple[int, int]] = set()
        for profile in AGENT_PROFILES:
            agent = Agent(profile, self.world)
            pos = self._find_unoccupied_near(base, occupied)
            agent.position = pos
            occupied.add(pos)
            self.agents[agent.id] = agent
        logger.info("Initialized %s agents in wilderness start", len(self.agents))

    def _find_unoccupied_near(self, center: tuple[int, int], occupied: set[tuple[int, int]]) -> tuple[int, int]:
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
        return (cx + 1, cy + 1)

    def _run_reflection_catchup(self, agent: Agent):
        todays = agent.episodic_memory.episodes[-20:]
        agent.identity.detect_tensions(agent.belief_system.beliefs, agent.relationships, todays)
        agent.identity.generate_goals_from_tensions()
        agent.identity.update_self_narrative(todays, agent.belief_system.beliefs)
        migrated_goals = []
        for goal in getattr(agent.identity, "long_arc_goals", [])[:4]:
            text = str(goal.get("text", "")).strip()
            if not text:
                continue
            migrated_goals.append({
                "text": text,
                "why": goal.get("why") or "This feels tied to who I'm becoming.",
                "priority": round(float(goal.get("priority", 0.6)), 2),
                "category": goal.get("category", "identity"),
                "source": goal.get("source", "identity_tension"),
            })
        agent.long_term_goals = migrated_goals
        agent.active_goals = [
            goal for goal in agent.active_goals
            if goal.get("status") == "active" and goal.get("kind") == "daily_focus"
        ]
        for goal in agent.long_term_goals[:3]:
            if not any(existing.get("text") == goal.get("text") for existing in agent.active_goals):
                agent.active_goals.append({
                    "text": goal.get("text", ""),
                    "status": "active",
                    "source": goal.get("source", "identity_tension"),
                    "priority": goal.get("priority", 0.6),
                    "created_tick": self.tick,
                    "kind": "long_arc",
                })
        agent.active_goals = agent.active_goals[:6]

    def _migrate_goal_hierarchy(self, agent: Agent, saved: dict):
        legacy_long_term = saved.get("long_term_goals", []) or []
        explicit_identity_goals = [
            goal for goal in legacy_long_term
            if isinstance(goal, dict) and str(goal.get("source", "")).startswith("identity")
        ]
        if explicit_identity_goals:
            agent.long_term_goals = explicit_identity_goals[:4]
        else:
            agent.long_term_goals = []
            for goal in legacy_long_term[:6]:
                if isinstance(goal, dict):
                    text = goal.get("text") or goal.get("goal") or ""
                else:
                    text = str(goal)
                text = str(text).strip()
                if not text:
                    continue
                agent.add_intention(
                    text,
                    "Recovered from an older save and needs reevaluation.",
                    0.55,
                    "save_migration",
                    target_location=agent.current_location,
                    next_step=text,
                    status="candidate",
                    created_tick=self.tick,
                    expires_after_ticks=180,
                    refresh_on_relevance=True,
                )
        for intent in list(agent.active_intentions):
            intent.setdefault("created_tick", self.tick)
            intent.setdefault("expires_after_ticks", 200)
            intent.setdefault("refresh_on_relevance", False)
        self._run_reflection_catchup(agent)
        agent.goal_hierarchy_migrated = True

    async def _synthesize_conversation_models(self, convo, participants: list[Agent]):
        from llm.client import llm_client

        significant = bool(
            convo.structured_commitments
            or convo.structured_proposals
            or convo.interaction_type in {"deep_conversation", "argument", "negotiation", "comforting"}
        )
        if not significant:
            return
        summary_lines = []
        for turn in convo.turns[-6:]:
            speaker = turn.get("speaker")
            speech = turn.get("speech", "")
            if speaker and speech:
                summary_lines.append(f"{speaker}: {speech[:160]}")
        summary = "\n".join(summary_lines) or f"A significant {convo.interaction_type} happened."
        for agent in participants:
            for other in participants:
                if other.id == agent.id:
                    continue
                await agent.mental_models.synthesize_after_interaction(
                    agent,
                    other,
                    interaction_summary=summary,
                    llm_client=llm_client,
                )

    def _restore_from_save(self, data: dict):
        self.tick = data.get("tick", 0)
        self.time_manager.day = data.get("day", 0)
        self.time_manager.tick_in_day = data.get("tick_in_day", 0)
        self.speed = data.get("speed", 1)
        self.story_highlights = data.get("story_highlights", [])
        self.day_recaps = data.get("day_recaps", [])
        self.debug_events = data.get("debug_events", [])

        if data.get("world"):
            self.world.load_from_save(data["world"])
            self.world._time_manager = self.time_manager

        saved_agents = data.get("agents", {})
        for agent_id, agent in self.agents.items():
            saved = saved_agents.get(agent_id)
            if not saved:
                continue

            if saved.get("position"):
                agent.position = tuple(saved["position"])
            agent.current_location = saved.get("current_location", "clearing")
            agent.inner_thought = saved.get("inner_thought", "")
            agent.daily_plan = saved.get("daily_plan", "")
            agent.daily_schedule = saved.get("daily_schedule", [])
            agent.current_plan_step = saved.get("current_plan_step")
            agent.long_term_goals = saved.get("long_term_goals", [])
            agent.active_intentions = saved.get("active_intentions", [])
            agent.current_plan = saved.get("current_plan")
            agent.fallback_plan = saved.get("fallback_plan")
            agent.blocked_reasons = saved.get("blocked_reasons", [])
            agent.decision_rationale = saved.get("decision_rationale", {})
            agent.life_events = saved.get("life_events", [])
            agent.reciprocity_ledger = saved.get("reciprocity_ledger", {})
            agent.proposal_stances = saved.get("proposal_stances", {})
            agent.project_roles = saved.get("project_roles", [])
            agent.current_institution_roles = saved.get("current_institution_roles", [])
            agent.active_conflicts = saved.get("active_conflicts", [])
            agent.plan_mode = saved.get("plan_mode", "improvising")
            agent.plan_deviation_reason = saved.get("plan_deviation_reason", "")
            agent.self_concept = saved.get("self_concept")
            agent.emotion = saved.get("emotion", "neutral")

            try:
                agent.current_action = ActionType(saved.get("current_action", "idle"))
            except ValueError:
                agent.current_action = ActionType.IDLE

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

            agent.relationships = saved.get("relationships", {})
            agent.active_goals = saved.get("active_goals", [])
            agent.social_commitments = saved.get("social_commitments", [])
            agent.inventory = saved.get("inventory", [])
            agent.secrets = saved.get("secrets", [])
            agent.opinions = saved.get("opinions", {})

            # Health
            agent.health = saved.get("health", 1.0)
            agent.is_sick = saved.get("is_sick", False)
            agent.sick_since_tick = saved.get("sick_since_tick", 0)
            agent.last_steal_attempt_tick = saved.get("last_steal_attempt_tick", -999)
            self._migrate_goal_hierarchy(agent, saved)

        for agent in self.agents.values():
            if not agent.path and agent.current_action in (ActionType.WALKING, ActionType.TALKING):
                agent.current_action = ActionType.IDLE

        logger.info("Restored %s agents from save", len(saved_agents))

    def set_broadcast(self, fn):
        self._broadcast = fn

    def set_speed(self, speed: int):
        self.speed = max(0, min(10, speed))

    async def _flush_save(self):
        async with self._save_lock:
            await save_world_state(self)
            self._last_saved_tick = self.tick

    def _request_save(self, force: bool = False):
        if not force and (self.tick - self._last_saved_tick) < 20 and not self._world_state_dirty:
            return
        if self._save_task and not self._save_task.done():
            return
        self._save_task = asyncio.create_task(self._flush_save())

    async def stop(self):
        self.running = False
        try:
            if self._save_task and not self._save_task.done():
                await self._save_task
            await self._flush_save()
            logger.info("Saved state on shutdown")
        except Exception as e:
            logger.error("Failed to save on shutdown: %s", e)

    async def run(self):
        self.running = True
        await init_db()
        save_data = await load_world_state()
        if save_data:
            self._restore_from_save(save_data)
            logger.info("Resumed from save — tick %s, day %s", self.tick, self.time_manager.day)
        else:
            logger.info("Open-ended simulation started — Day 1, Dawn")

        batch_size = 1
        broadcast_interval = 0.3
        full_state_interval = 15

        while self.running:
            if self.speed == 0:
                await asyncio.sleep(0.1)
                continue

            await asyncio.sleep(broadcast_interval / max(self.speed, 1))
            batch_events = []
            batch_count = min(int(batch_size * max(self.speed, 1)), 10)

            for _ in range(batch_count):
                try:
                    self.tick += 1
                    self.time_manager.advance()
                    events = self._process_tick()
                    batch_events.extend(events)
                except Exception as e:
                    logger.error("Tick %s error: %s", self.tick, e)

                if self.tick % 5 == 0:
                    asyncio.create_task(self._process_inner_monologue_background())
                if self.tick % 200 == 0:
                    self.world.regenerate_resources()
                    self._world_state_dirty = True
                if self.tick % 20 == 0:
                    self._request_save()

            if self._broadcast:
                try:
                    is_full = (self.tick % full_state_interval) < batch_count or self._world_state_dirty
                    if is_full:
                        await self._broadcast({
                            "type": "tick",
                            "data": {
                                "tick": self.tick,
                                "time": self.time_manager.to_dict(),
                                "events": batch_events,
                                "agents": [a.to_dict() for a in self.agents.values()],
                                "storyHighlights": self.story_highlights[-20:],
                                "tileGrid": self.world.get_tile_grid(),
                                "buildings": self.world.get_buildings_list(),
                                "worldObjects": self._serialize_world_objects(),
                                "innovations": self._serialize_innovations(),
                                "patterns": self._serialize_patterns(),
                                "timelineEvents": self._serialize_timeline_events(),
                            },
                        })
                        self._world_state_dirty = False
                        self._request_save()
                    else:
                        await self._broadcast({
                            "type": "tick",
                            "data": {
                                "tick": self.tick,
                                "time": self.time_manager.to_dict(),
                                "events": batch_events,
                                "agents": [
                                    {
                                        "id": a.id,
                                        "position": list(a.position),
                                        "currentAction": a.current_action.value,
                                        "currentLocation": a.current_location,
                                        "emotion": a.emotion,
                                    }
                                    for a in self.agents.values()
                                ],
                            },
                        })
                except Exception:
                    pass

    def _record_debug_event(self, event_type: str, description: str):
        self.debug_events.append({
            "tick": self.tick,
            "type": event_type,
            "description": description,
        })
        self.debug_events = self.debug_events[-50:]

    def _add_story_highlight(self, highlight_type: str, text: str, agent_id: str | None = None, agent_name: str | None = None):
        self.story_highlights.append({
            "type": highlight_type,
            "text": text,
            "agentId": agent_id,
            "agentName": agent_name,
            "tick": self.tick,
            "day": self.time_manager.day,
        })
        self.story_highlights = self.story_highlights[-80:]

    def _next_id(self, prefix: str, items: list[dict]) -> str:
        return f"{prefix}_{len(items) + 1}_{self.tick}"

    def _support_score_for(self, observer: Agent, proposer_name: str) -> float:
        rel = observer.relationships.get(proposer_name, {})
        model = observer.mental_models.models.get(proposer_name)
        trust = rel.get("trust", 0.5)
        reliability = model.reliability if model else 0.5
        influence = model.leadership_influence if model else 0.0
        reciprocity = 0.0
        ledger = observer.reciprocity_ledger.get(proposer_name)
        if ledger:
            reciprocity = max(-0.15, min(0.15, float(ledger.get("balance", 0.0)) * 0.05))
        agreeableness = observer.profile.personality.get("agreeableness", 0.5)
        return trust * 0.4 + reliability * 0.28 + influence * 0.12 + agreeableness * 0.15 + reciprocity

    def _institution_weight_for(self, agent: Agent, location: str | None = None) -> float:
        weight = 0.0
        for role in agent.current_institution_roles:
            if location and role.get("location") not in {None, "", location}:
                continue
            weight += 0.08 if role.get("role") in {"member", "steward"} else 0.14
        return weight

    def _project_weight_for(self, agent: Agent, location: str | None = None) -> float:
        weight = 0.0
        for role in agent.project_roles:
            if location and role.get("location") not in {None, "", location}:
                continue
            weight += 0.08 if role.get("role") == "worker" else 0.14
        return weight

    def _record_social_breach(self, agent: Agent, others: list[str], description: str, kind: str = "social", severity: float = 0.5):
        for other_name in others:
            if not other_name or other_name == agent.name:
                continue
            agent.note_conflict(other_name, description, self.tick, severity=severity, kind=kind)
            other = next((a for a in self.agents.values() if a.name == other_name), None)
            if other:
                other.note_conflict(agent.name, description, self.tick, severity=severity, kind=kind)
                rel = other.relationships.setdefault(agent.name, {"sentiment": 0.5, "trust": 0.5, "familiarity": 0.1})
                rel["trust"] = max(0.0, rel.get("trust", 0.5) - severity * 0.08)

    def _refresh_social_world_knowledge(self):
        institution_summaries = [
            {
                "name": inst.get("name"),
                "location": inst.get("location"),
                "purpose": inst.get("purpose"),
                "legitimacy": inst.get("legitimacy", 0.0),
            }
            for inst in self.world.constitution.institutions[-8:]
        ]
        norm_texts = [
            n["text"] if isinstance(n, dict) else str(n)
            for n in self.world.constitution.social_norms[-10:]
        ]
        for agent in self.agents.values():
            agent.world_model.known_institutions = institution_summaries[-8:]
            for text in norm_texts[-6:]:
                agent.world_model.learn_norm(text)

    def _synthesize_identity(self):
        for agent in self.agents.values():
            fragments: list[str] = []
            if agent.active_conflicts:
                fragments.append(f"I still feel tension with {agent.active_conflicts[0]['with']}.")
            if agent.current_institution_roles:
                role = agent.current_institution_roles[0]
                role_name = role.get('role', 'member')
                fragments.append(f"I serve as {role_name} in a local group.")
            if agent.project_roles:
                proj_role = agent.project_roles[0].get('role', 'helper')
                fragments.append(f"I'm helping out as {proj_role} on a project.")
            if agent.life_events:
                event_text = agent.life_events[0].get("summary", "")
                if len(event_text) > 80:
                    event_text = event_text[:80].rsplit(' ', 1)[0] + '...'
                if event_text:
                    fragments.append(event_text)
            if agent.working_memory.background_worry:
                worry = agent.working_memory.background_worry
                if len(worry) > 80:
                    worry = worry[:80].rsplit(' ', 1)[0] + '...'
                fragments.append(f"What still nags at me: {worry}")
            summary = " ".join(f for f in fragments[:4] if f).strip()
            if summary:
                agent.identity.self_narrative = summary[:320]

    def _make_proposal(self, proposer: Agent, description: str, location: str, participants: list[str] | None = None, kind: str = "social_rule") -> dict:
        proposal = {
            "id": self._next_id("proposal", self.world.active_proposals),
            "kind": kind,
            "description": description,
            "proposer": proposer.name,
            "supporters": [name for name in (participants or []) if name != proposer.name],
            "opponents": [],
            "status": "drafted",
            "location": location,
            "affected_agents": participants or [proposer.name],
            "affected_locations": [location],
            "legitimacy": 0.35,
            "deadline_tick": self.tick + 180,
            "created_tick": self.tick,
            "resolution": "",
        }
        self.world.add_proposal(proposal)
        proposer.set_proposal_stance(proposal["id"], "support", "I proposed this.", legitimacy=proposal["legitimacy"])
        from systems.pattern_detector import pattern_detector
        pattern_detector.record_action(proposer.name, {
            "type": "proposal", "location": location, "target": "",
            "description": description[:80],
        }, self.tick)
        return proposal

    def _make_meeting(self, topic: str, location: str, participants: list[str], related_proposal_ids: list[str]) -> dict:
        meeting = {
            "id": self._next_id("meeting", self.world.meetings),
            "topic": topic,
            "location": location,
            "participants": participants,
            "agenda": [topic],
            "related_proposal_ids": related_proposal_ids,
            "scheduled_day": self.time_manager.day,
            "scheduled_hour": max(7, min(20, int(self.time_manager.hour) + 1)),
            "status": "scheduled",
            "outcome": "",
        }
        self.world.upsert_meeting(meeting)
        return meeting

    def _create_project_from_proposal(self, proposal: dict) -> dict:
        kind = "communal_fire"
        name = "Communal Fire"
        lower = proposal.get("description", "").lower()
        render_as_structure = False
        width = height = 2
        if "storage" in lower:
            kind, name, render_as_structure = "storage", "Food Storage", True
        elif "workshop" in lower:
            kind, name, render_as_structure = "workshop", "Workshop", True
        elif "meeting" in lower:
            kind, name, render_as_structure = "meeting_place", "Meeting Place", True
        elif "farm" in lower or "plot" in lower:
            kind, name = "farm_plot", "Farm Plot"
        elif "path" in lower or "road" in lower:
            kind, name = "paths", "Settlement Paths"
        location = proposal.get("location", "clearing")
        entry = self.world.get_location(location) or {}
        col = entry.get("col", 18)
        row = entry.get("row", 18)
        project = {
            "id": self._next_id("project", self.world.projects),
            "name": name,
            "kind": kind,
            "sponsor": proposal.get("proposer"),
            "supporters": proposal.get("supporters", []),
            "location": location,
            "public_private": "public",
            "required_materials": {"wood": 4 if kind in {"communal_fire", "meeting_place"} else 6, "stone": 2 if kind in {"communal_fire", "paths"} else 0},
            "required_labor": 6 if kind in {"workshop", "meeting_place", "storage"} else 4,
            "progress": 0.0,
            "current_stage": "gathering_materials",
            "blockers": [],
            "status": "active",
            "benefits": [kind.replace("_", " ")],
            "render_as_structure": render_as_structure,
            "col": col,
            "row": row,
            "width": width,
            "height": height,
        }
        self.world.upsert_project(project)
        return project

    def _evaluate_proposal_kind(self, description: str) -> str:
        lower = description.lower()
        if any(word in lower for word in ("rule", "respect", "share", "must", "should", "currency", "money", "trade", "market", "price", "barter", "exchange", "tax", "tariff")):
            return "social_rule"
        if any(word in lower for word in ("meeting", "gathering place", "hall")):
            return "institution"
        if any(word in lower for word in ("fire", "storage", "farm", "workshop", "path", "road", "meeting place")):
            return "project"
        return "collective_decision"

    def _seed_social_proposals(self) -> list[dict]:
        events = []
        existing_descriptions = {p.get("description") for p in self.world.active_proposals}
        for agent in self.agents.values():
            conflict = next((c for c in agent.active_conflicts if c.get("status") == "active"), None)
            if conflict and "claim" in conflict.get("summary", "").lower():
                description = "Respect claimed spaces and ask before entering."
                if description not in existing_descriptions:
                    proposal = self._make_proposal(agent, description, agent.current_location, participants=[agent.name], kind="social_rule")
                    existing_descriptions.add(description)
                    events.append({"type": "system_event", "eventType": "proposal_created", "label": "Proposal", "description": f"{agent.name} wants a clearer rule: {proposal['description']}"})
            blocked = next((b for b in agent.blocked_reasons if "wood" in b.get("reason", "").lower() or "food" in b.get("reason", "").lower()), None)
            if blocked:
                description = "We should build a communal fire in the clearing." if "wood" in blocked.get("reason", "").lower() else "We should create a shared food storage area."
                if description not in existing_descriptions:
                    proposal = self._make_proposal(agent, description, "clearing", participants=[agent.name], kind="project")
                    existing_descriptions.add(description)
                    events.append({"type": "system_event", "eventType": "proposal_created", "label": "Proposal", "description": f"{agent.name} turned a problem into a proposal: {proposal['description']}"})
        return events

    def _run_institution_upkeep(self) -> list[dict]:
        events = []
        for agent in self.agents.values():
            agent.current_institution_roles = []
        for inst in self.world.constitution.institutions:
            members = inst.get("members", [])
            location = inst.get("location", "clearing")
            roles = inst.setdefault("roles", {})
            recurring = inst.setdefault("recurring_actions", [])
            if not recurring:
                recurring.append({
                    "kind": "meeting",
                    "topic": inst.get("purpose", inst.get("name", "Institution check-in")),
                    "frequency_days": 1,
                    "hour": 18,
                    "next_day": self.time_manager.day,
                })
            for member_name in members:
                agent = next((a for a in self.agents.values() if a.name == member_name), None)
                if not agent:
                    continue
                inst_name = inst.get("name", "a group")
                # Truncate long institution names for readable display
                if len(inst_name) > 40:
                    inst_name = inst_name[:40].rsplit(' ', 1)[0] + '...'
                agent.current_institution_roles.append({
                    "institution_id": inst.get("id"),
                    "institution_name": inst_name,
                    "role": roles.get(member_name, "member"),
                    "location": location,
                })
            for action in recurring:
                if action.get("kind") != "meeting" or action.get("next_day", self.time_manager.day) > self.time_manager.day:
                    continue
                meeting_id = f"{inst.get('id')}_{self.time_manager.day}_{action.get('topic', 'meeting')}"
                if any(m.get("id") == meeting_id for m in self.world.meetings):
                    continue
                meeting = {
                    "id": meeting_id,
                    "topic": action.get("topic", inst.get("name", "Meeting")),
                    "location": location,
                    "participants": members[:8],
                    "agenda": [action.get("topic", inst.get("purpose", "coordination"))],
                    "related_proposal_ids": [],
                    "scheduled_day": self.time_manager.day,
                    "scheduled_hour": int(action.get("hour", 18)),
                    "status": "scheduled",
                    "outcome": "",
                    "institution_id": inst.get("id"),
                    "facilitator": next(iter(roles.keys()), members[0] if members else None),
                }
                self.world.upsert_meeting(meeting)
                for member_name in meeting["participants"]:
                    agent = next((a for a in self.agents.values() if a.name == member_name), None)
                    if not agent:
                        continue
                    topic = meeting['topic']
                    short_topic = topic[:50].rsplit(' ', 1)[0] + '...' if len(topic) > 50 else topic
                    desc = f"Attend group meeting: {short_topic}"
                    duplicate = any(
                        c.get("kind") == "meeting"
                        and c.get("description") == desc
                        and c.get("scheduled_day") == meeting["scheduled_day"]
                        for c in agent.social_commitments
                    )
                    if not duplicate:
                        agent.social_commitments.append({
                            "kind": "meeting",
                            "description": desc,
                            "participants": meeting["participants"],
                            "location": location,
                            "time_hint": "evening",
                            "scheduled_day": meeting["scheduled_day"],
                            "scheduled_hour": meeting["scheduled_hour"],
                            "required_resources": [],
                            "recurring": True,
                            "status": "planned",
                            "source_conversation_tick": self.tick,
                            "with": [name for name in meeting["participants"] if name != agent.name],
                        })
                action["next_day"] = self.time_manager.day + max(1, int(action.get("frequency_days", 1)))
                events.append({"type": "system_event", "eventType": "institution_meeting", "label": "Institution", "description": f"{inst.get('name')} scheduled a meeting at {location.replace('_', ' ')}."})
        return events

    def _staff_projects(self) -> list[dict]:
        events = []
        for project in self.world.projects:
            if project.get("status") != "active":
                continue
            location = project.get("location", "clearing")
            supporters = list(dict.fromkeys([project.get("sponsor"), *project.get("supporters", [])]))
            assigned_roles = {}
            for name in supporters:
                if not name:
                    continue
                agent = next((a for a in self.agents.values() if a.name == name), None)
                if not agent:
                    continue
                build_skill = agent.skill_memory.activities.get("construction", {}).get("skill_level", 0.0)
                gather_skill = agent.skill_memory.activities.get("gathering", {}).get("skill_level", 0.0)
                role = "builder" if build_skill >= gather_skill else "supplier"
                assigned_roles[name] = role
                agent.project_roles = [r for r in agent.project_roles if r.get("project_id") != project.get("id")]
                agent.project_roles.append({"project_id": project.get("id"), "role": role, "location": location})
                description = f"Help with {project.get('name')}"
                if not any(i.get("goal") == description for i in agent.active_intentions):
                    next_step = f"Bring materials to {location}" if role == "supplier" else f"Work on {project.get('name')} at {location}"
                    agent.add_intention(
                        description,
                        "This project needs follow-through from the people backing it.",
                        0.62,
                        "project",
                        target_location=location,
                        next_step=next_step,
                        status="active",
                        created_tick=self.tick,
                        expires_after_ticks=240,
                        refresh_on_relevance=True,
                    )
            project["assigned_roles"] = assigned_roles
            if assigned_roles:
                events.append({"type": "system_event", "eventType": "project_staffed", "label": "Project Staffing", "description": f"{project.get('name')} assigned {len(assigned_roles)} roles."})
        return events

    def _process_missed_obligations(self) -> list[dict]:
        events = []
        for agent in self.agents.values():
            for commitment in agent.social_commitments:
                if commitment.get("status") not in (None, "planned", "in_progress"):
                    continue
                if commitment.get("scheduled_day") != self.time_manager.day:
                    continue
                if self.time_manager.hour <= commitment.get("scheduled_hour", 12) + 2:
                    continue
                commitment["status"] = "failed"
                others = [name for name in commitment.get("participants", []) if name != agent.name]
                raw_desc = commitment.get('description', 'an obligation')
                # Truncate long proposal/task descriptions to keep conflict summaries readable
                short_desc = raw_desc[:60].rsplit(' ', 1)[0] + '...' if len(raw_desc) > 60 else raw_desc
                description = f"{agent.name} didn't show up for: {short_desc}"
                self._record_social_breach(agent, others, description, kind="obligation", severity=0.55)
                self.world.add_norm_violation({
                    "tick": self.tick,
                    "agent": agent.name,
                    "norm": "Keep your commitments",
                    "location": commitment.get("location", agent.current_location),
                    "description": description,
                })
                agent.add_life_event(description, self.tick, category="social_failure", impact=0.55)
                events.append({"type": "system_event", "eventType": "commitment_missed", "label": "Missed Obligation", "description": description})
        return events

    def _process_active_proposals(self) -> list[dict]:
        events = []
        existing_descriptions = {p.get("description") for p in self.world.active_proposals}
        for agent in self.agents.values():
            for intention in agent.active_intentions:
                if intention.get("source") != "proposal":
                    continue
                description = intention.get("goal")
                if not description or description in existing_descriptions:
                    continue
                proposal = self._make_proposal(
                    agent,
                    description,
                    intention.get("target_location") or agent.current_location,
                    participants=[agent.name],
                    kind=self._evaluate_proposal_kind(description),
                )
                existing_descriptions.add(description)
                events.append({"type": "system_event", "eventType": "proposal_created", "label": "Proposal", "description": f"{agent.name} is pushing a proposal: {proposal['description']}"})
        if not self.world.active_proposals:
            return events
        self.world.coalitions = []
        for proposal in self.world.active_proposals:
            if proposal.get("status") in {"accepted", "rejected", "abandoned"}:
                continue
            proposal["status"] = "gathering_support" if proposal["status"] == "drafted" else proposal["status"]
            supporters = {proposal.get("proposer")}
            opponents = set()
            for agent in self.agents.values():
                if agent.name == proposal.get("proposer"):
                    continue
                if proposal.get("location") and self.world.get_distance(agent.current_location, proposal["location"]) > 20:
                    continue
                score = self._support_score_for(agent, proposal["proposer"])
                stance = "neutral"
                if score > 0.6:
                    supporters.add(agent.name)
                    stance = "support"
                elif score < 0.38:
                    opponents.add(agent.name)
                    stance = "oppose"
                agent.set_proposal_stance(proposal["id"], stance, f"social score {score:.2f}", legitimacy=proposal.get("legitimacy", 0.0))
            proposal["supporters"] = sorted(supporters)
            proposal["opponents"] = sorted(opponents)
            sponsor = next((a for a in self.agents.values() if a.name == proposal.get("proposer")), None)
            sponsor_bonus = 0.0
            if sponsor:
                sponsor_bonus += self._institution_weight_for(sponsor, proposal.get("location"))
                sponsor_bonus += sum(
                    0.05 for event in sponsor.life_events[:4]
                    if event.get("category") in {"project", "success"} and proposal.get("kind") in {"project", "institution"}
                )
            proposal["legitimacy"] = round(max(0.0, min(1.0, len(supporters) / max(len(self.agents), 1) - len(opponents) * 0.03 + 0.25 + sponsor_bonus)), 2)
            if len(supporters) >= 3:
                self.world.coalitions.append({
                    "id": f"coalition_{proposal['id']}",
                    "proposal_id": proposal["id"],
                    "members": proposal["supporters"],
                    "purpose": proposal["description"],
                    "strength": proposal["legitimacy"],
                })
            if proposal["status"] == "gathering_support" and len(supporters) >= 3:
                proposal["status"] = "active_discussion"
                meeting = self._make_meeting(proposal["description"], proposal["location"], proposal["supporters"][:6], [proposal["id"]])
                meeting["agenda"] = [proposal["description"], "hear support and opposition", "decide next step"]
                for agent in self.agents.values():
                    if agent.name in meeting["participants"]:
                        agent.social_commitments.append({
                            "kind": "meeting",
                            "description": f"Attend meeting about a proposal" if len(proposal['description']) > 50 else f"Attend meeting about {proposal['description']}",
                            "participants": meeting["participants"],
                            "location": meeting["location"],
                            "time_hint": "soon",
                            "scheduled_day": meeting["scheduled_day"],
                            "scheduled_hour": meeting["scheduled_hour"],
                            "required_resources": [],
                            "recurring": False,
                            "status": "planned",
                            "source_conversation_tick": self.tick,
                            "with": [name for name in meeting["participants"] if name != agent.name],
                        })
                events.append({"type": "system_event", "eventType": "proposal_advanced", "label": "Proposal", "description": f"{proposal['description']} has enough support for a meeting."})
            due = self.tick >= proposal.get("deadline_tick", self.tick)
            if proposal["status"] == "active_discussion" and (proposal["legitimacy"] >= 0.55 or due):
                accepted = proposal["legitimacy"] >= 0.55 and len(proposal["supporters"]) > len(proposal["opponents"])
                proposal["status"] = "accepted" if accepted else "rejected"
                proposal["resolution"] = "support carried it" if accepted else "not enough support"
                if accepted:
                    applied = self._apply_structured_proposal(proposal)
                    if applied:
                        events.extend(applied)
                else:
                    events.append({"type": "system_event", "eventType": "proposal_rejected", "label": "Proposal Rejected", "description": proposal["description"]})
        return events

    def _apply_structured_proposal(self, proposal: dict) -> list[dict]:
        events = []
        description = proposal.get("description", "")
        location = proposal.get("location", "clearing")
        kind = proposal.get("kind", "collective_decision")
        if kind in ("economic_rule", "social_rule"):
            norm = self.world.add_norm(description, self.tick, category="proposal", origin="collective_agreement")
            self.world.constitution.change_history.append({"tick": self.tick, "type": "proposal_accepted", "description": description})
            events.append({"type": "system_event", "eventType": "norm_emergence", "label": "Social Norm", "description": norm["text"]})
        elif kind == "institution":
            meeting = next((m for m in self.world.meetings if proposal["id"] in m.get("related_proposal_ids", [])), None)
            institution = {
                "id": self._next_id("institution", self.world.constitution.institutions),
                "name": f"{location.replace('_', ' ').title()} Council" if "meeting" in description.lower() else description[:40],
                "purpose": description,
                "location": location,
                "members": proposal.get("supporters", [])[:6],
                "roles": {proposal.get("proposer"): "convener"},
                "operating_norm_ids": [],
                "legitimacy": proposal.get("legitimacy", 0.5),
                "activity_level": 0.5,
                "formed_tick": self.tick,
                "recurring_actions": [{
                    "kind": "meeting",
                    "topic": description,
                    "frequency_days": 1,
                    "hour": 18,
                    "next_day": self.time_manager.day,
                }],
                "status": "active",
            }
            self.world.constitution.institutions.append(institution)
            if meeting:
                meeting["status"] = "completed"
                meeting["outcome"] = f"Formed institution: {institution['name']}"
            events.append({"type": "system_event", "eventType": "institution_creation", "label": "New Institution", "description": institution["name"]})
        elif kind == "project":
            project = self._create_project_from_proposal(proposal)
            for agent in self.agents.values():
                if agent.name in project.get("supporters", []) or agent.name == project.get("sponsor"):
                    agent.add_intention(
                        f"Help build {project['name']}",
                        "This project now has enough support to become real.",
                        0.64,
                        "project",
                        target_location=project["location"],
                        next_step=f"Bring materials and work on {project['name']}",
                        status="active",
                        created_tick=self.tick,
                        expires_after_ticks=240,
                        refresh_on_relevance=True,
                    )
            events.append({"type": "system_event", "eventType": "project_started", "label": "Project Started", "description": project["name"]})
        else:
            norm = self.world.add_norm(f"People should honor decisions like: {description}", self.tick, category="governance", origin="proposal")
            events.append({"type": "system_event", "eventType": "proposal_accepted", "label": "Collective Decision", "description": norm["text"]})
        return events

    def _process_meetings(self) -> list[dict]:
        events = []
        for meeting in self.world.meetings:
            if meeting.get("status") != "scheduled":
                continue
            if meeting.get("scheduled_day") != self.time_manager.day:
                continue
            if abs(self.time_manager.hour - meeting.get("scheduled_hour", 12)) > 0.5:
                continue
            present = [a.name for a in self.agents.values() if a.current_location == meeting.get("location") and a.name in meeting.get("participants", [])]
            if len(present) >= max(2, len(meeting.get("participants", [])) // 2):
                meeting["status"] = "completed"
                facilitator = meeting.get("facilitator") or (present[0] if present else None)
                meeting["facilitator"] = facilitator
                meeting["outcome"] = f"{len(present)} people met about {meeting['topic']}"
                for proposal in self.world.active_proposals:
                    if proposal["id"] in meeting.get("related_proposal_ids", []):
                        proposal["legitimacy"] = round(min(1.0, proposal.get("legitimacy", 0.5) + 0.08), 2)
                        proposal["supporters"] = sorted(set(proposal.get("supporters", []) + present))
                for name in present:
                    agent = next((a for a in self.agents.values() if a.name == name), None)
                    if agent:
                        agent.add_life_event(f"Attended meeting about {meeting['topic']}.", self.tick, category="meeting", impact=0.35)
                        if facilitator == name:
                            agent.bump_identity(f"I helped guide a meeting about {meeting['topic']}.", role_hint="organizer")
                inst = next((i for i in self.world.constitution.institutions if i.get("id") == meeting.get("institution_id")), None)
                if inst:
                    inst["activity_level"] = round(min(1.0, inst.get("activity_level", 0.4) + 0.08), 2)
                    inst["legitimacy"] = round(min(1.0, inst.get("legitimacy", 0.4) + 0.05), 2)
                events.append({"type": "system_event", "eventType": "meeting_held", "label": "Meeting", "description": meeting["outcome"]})
                # Run actual group conversation asynchronously
                present_agents = [a for a in self.agents.values() if a.name in present]
                if len(present_agents) >= 2:
                    asyncio.create_task(self._run_group_meeting(meeting, present_agents))
        return events

    async def _run_group_meeting(self, meeting: dict, participants: list):
        """Run an LLM-powered group conversation for a meeting."""
        from systems.interactions import GroupConversation, process_conversation_consequences, overhearing_system
        try:
            for p in participants:
                p.is_in_conversation = True

            group_convo = GroupConversation(
                participants=participants,
                topic=meeting.get("topic", "community matters"),
                location=meeting.get("location", "clearing"),
                max_rounds=2,
            )
            transcript = await group_convo.run()

            # Broadcast speech events
            for turn in transcript:
                speaker_agent = next((a for a in participants if a.name == turn.get("speaker")), None)
                if speaker_agent and self._broadcast and turn.get("speech"):
                    await self._broadcast({"type": "tick", "data": {
                        "tick": self.tick,
                        "time": self.time_manager.to_dict(),
                        "events": [{"type": "agent_speak", "agentId": speaker_agent.id, "speech": turn["speech"]}],
                        "agents": [a.to_dict() for a in self.agents.values()],
                    }})

            # Apply consequences: every participant gets memory and relationship updates
            all_names = [a.name for a in self.agents.values()]
            for agent in participants:
                others = [p.name for p in participants if p.id != agent.id]
                summary = f"Meeting about {meeting.get('topic', 'community matters')}: " + "; ".join(
                    f"{t['speaker']}: {t.get('speech', '...')[:40]}" for t in transcript[:4]
                )
                agent.episodic_memory.add_simple(
                    summary, tick=self.tick, day=self.time_manager.day,
                    time_of_day=self.time_manager.time_of_day, location=meeting.get("location", ""),
                    category="conversation", intensity=0.6, emotion="engaged", agents=others,
                )
                for other_name in others:
                    if other_name not in agent.relationships:
                        agent.relationships[other_name] = {"sentiment": 0.5, "trust": 0.5, "familiarity": 0.1}
                    agent.relationships[other_name]["familiarity"] = min(
                        1.0, agent.relationships[other_name].get("familiarity", 0.1) + 0.02
                    )

            # Create proposals from meeting
            for proposal in group_convo.structured_proposals:
                proposer_name = None
                for turn in transcript:
                    act = turn.get("actionable")
                    if isinstance(act, dict) and act.get("kind") == "proposal" and act.get("description") == proposal.get("description"):
                        proposer_name = turn.get("speaker")
                        break
                proposer = next((a for a in participants if a.name == proposer_name), participants[0]) if proposer_name else participants[0]
                self._make_proposal(
                    proposer, proposal.get("description", ""), meeting.get("location", ""),
                    proposal.get("participants", [p.name for p in participants]),
                    kind="social_rule",
                )

            # Process support/opposition signals
            for commitment in group_convo.structured_commitments:
                kind = commitment.get("kind")
                desc = commitment.get("description", "")
                for agent in participants:
                    if kind == "support_signal":
                        agent.mental_models.update_from_interaction(
                            commitment.get("speaker", ""), tick=self.tick, alliance_delta=0.05,
                        )
                    elif kind == "opposition_signal":
                        agent.mental_models.update_from_interaction(
                            commitment.get("speaker", ""), tick=self.tick, alliance_delta=-0.05,
                        )

            # Overhearing by non-participants at the same location
            for turn in transcript:
                speaker_name = turn.get("speaker", "")
                speech = turn.get("speech", "")
                if not speech:
                    continue
                for observer in self.agents.values():
                    if observer.name in [p.name for p in participants]:
                        continue
                    if observer.current_location != meeting.get("location"):
                        continue
                    dist = 2  # Same location, close proximity
                    overhearing_system.process(observer, [speaker_name, "meeting"], speech, dist)

            self._add_story_highlight(
                "meeting_held",
                f"Group meeting about '{meeting.get('topic', '?')}' with {len(participants)} people.",
                agent_name=participants[0].name if participants else None,
            )
        except Exception as e:
            logger.error("Group meeting error: %s", e)
        finally:
            for p in participants:
                p.is_in_conversation = False
                p.conversation_cooldown = 30

    def _apply_social_enforcement(self) -> list[dict]:
        events = []
        respect_claims = any((n["text"] if isinstance(n, dict) else str(n)) == "Respect claimed spaces" for n in self.world.constitution.social_norms)
        if any(c.get("status") == "failed" for a in self.agents.values() for c in a.social_commitments[-4:]):
            self.world.add_norm("Keep your commitments", self.tick, category="cooperation", origin="emergent")
        for agent in self.agents.values():
            loc = self.world.locations.get(agent.current_location)
            if loc and respect_claims:
                owner = loc.get("claimed_by")
                if owner and owner != agent.name and loc.get("type") == "built_structure":
                    violation = {
                        "tick": self.tick,
                        "agent": agent.name,
                        "norm": "Respect claimed spaces",
                        "location": agent.current_location,
                        "description": f"{agent.name} entered {agent.current_location} claimed by {owner} without clear permission.",
                    }
                    recent = self.world.norm_violations[-5:]
                    if any(v.get("agent") == agent.name and v.get("location") == agent.current_location for v in recent):
                        continue
                    self.world.add_norm_violation(violation)
                    self._record_social_breach(agent, [owner], violation["description"], kind="claim", severity=0.65)
                    owner_agent = next((a for a in self.agents.values() if a.name == owner), None)
                    if owner_agent:
                        owner_agent.episodic_memory.add_simple(
                            f"{agent.name} ignored my claim on {agent.current_location}.",
                            self.tick, self.time_manager.day, self.time_manager.time_of_day, agent.current_location,
                            category="emotion", intensity=0.7, emotion="resentful", agents=[agent.name],
                        )
                    events.append({"type": "system_event", "eventType": "norm_violation", "label": "Norm Violation", "description": violation["description"]})
            self.world.recognize_norm("Keep your commitments", agent.name, amount=0.005)
        return events

    def _work_on_projects(self) -> list[dict]:
        events = []
        for project in self.world.projects:
            if project.get("status") != "active":
                continue
            supporters = set(project.get("supporters", []))
            sponsor = project.get("sponsor")
            if sponsor:
                supporters.add(sponsor)
            workers = [a for a in self.agents.values() if a.name in supporters and a.current_location == project.get("location")]
            if not workers:
                continue
            required = project.get("required_materials", {})
            missing = []
            for material, qty in required.items():
                if qty <= 0:
                    continue
                available = sum(a.inventory_count(material) for a in workers)
                if available < qty:
                    missing.append(material)
            if missing:
                project["current_stage"] = "gathering_materials"
                project["blockers"] = [f"Need more {m.replace('_', ' ')}" for m in missing]
                for worker in workers:
                    worker.add_blocked_reason(project["blockers"][0], self.tick, severity=0.6)
                    worker.add_intention(
                        f"Find materials for {project['name']}",
                        f"The project is blocked until we bring more {missing[0].replace('_', ' ')}.",
                        0.6,
                        "project_supply",
                        target_location="forest_edge" if missing[0] == "wood" else project.get("location"),
                        next_step=f"gather {missing[0].replace('_', ' ')}",
                        status="active",
                        created_tick=self.tick,
                        expires_after_ticks=220,
                        refresh_on_relevance=True,
                    )
                continue
            project["current_stage"] = "building"
            project["blockers"] = []
            labor_gain = 0.0
            for worker in workers:
                skill = worker.skill_memory.activities.get("construction", {}).get("skill_level", 0.2)
                labor_gain += 0.8 + skill + worker.profile.physical_traits.get("strength", 0.5) * 0.4
                worker.project_roles = [r for r in worker.project_roles if r.get("project_id") != project["id"]]
                worker.project_roles.append({"project_id": project["id"], "role": "worker"})
            project["progress"] = round(project.get("progress", 0.0) + labor_gain / max(project.get("required_labor", 4), 1), 2)
            if project["progress"] >= 1.0:
                for material, qty in required.items():
                    remaining = qty
                    for worker in workers:
                        if remaining <= 0:
                            break
                        take = min(worker.inventory_count(material), remaining)
                        if take > 0:
                            worker.consume_inventory(material, take)
                            remaining -= take
                project["status"] = "completed"
                project["current_stage"] = "complete"
                project["progress"] = 1.0
                if project.get("render_as_structure"):
                    self.world.build_structure(project.get("col", 20), project.get("row", 20), project.get("width", 2), project.get("height", 2), project["name"], builder=project.get("sponsor", ""), purpose=project.get("kind", "project"))
                if project.get("kind") == "meeting_place":
                    self.world.constitution.institutions.append({
                        "id": self._next_id("institution", self.world.constitution.institutions),
                        "name": f"{project['name']} Assembly",
                        "purpose": "recurring coordination",
                        "location": project.get("location"),
                        "members": list(project.get("assigned_roles", {}).keys()),
                        "roles": {project.get("sponsor"): "convener"} if project.get("sponsor") else {},
                        "operating_norm_ids": [],
                        "legitimacy": 0.55,
                        "activity_level": 0.45,
                        "formed_tick": self.tick,
                        "recurring_actions": [{"kind": "meeting", "topic": f"Maintain {project['name']}", "frequency_days": 1, "hour": 18, "next_day": self.time_manager.day + 1}],
                        "status": "active",
                    })
                for worker in workers:
                    worker.add_life_event(f"Helped complete {project['name']}.", self.tick, category="project", impact=0.7)
                    worker.bump_identity(f"I helped complete {project['name']}.", role_hint="builder")
                self._world_state_dirty = True
                events.append({"type": "system_event", "eventType": "project_completed", "label": "Project Complete", "description": project["name"]})
            else:
                events.append({"type": "system_event", "eventType": "project_progress", "label": "Project Progress", "description": f"{project['name']} reached {int(project['progress'] * 100)}%."})
        return events

    def _execute_trade(self, agent: Agent, partner: Agent, give_item: str, give_qty: int, recv_item: str, recv_qty: int, context: str = "barter") -> list[dict]:
        """Legacy shim: route exchange attempts through the open-ended action executor."""
        give_label = give_item.replace("_", " ")
        recv_label = recv_item.replace("_", " ")
        description = (
            f"{agent.name} tries to exchange {give_qty} {give_label} with {partner.name} "
            f"for {recv_qty} {recv_label} at {agent.current_location.replace('_', ' ')}."
        )
        asyncio.create_task(self._execute_open_ended_action(agent, description))
        return [{
            "type": "system_event",
            "eventType": "exchange_attempt",
            "label": "Exchange Attempt",
            "description": description,
        }]

    def _pick_trade_items(self, agent_a: Agent, agent_b: Agent) -> tuple[str | None, str | None]:
        """Pick the best items for a trade between two agents based on needs and surplus."""
        from systems.economy import FOOD_ITEMS, BUILDING_ITEMS

        a_needs_food = agent_a.drives.hunger > 0.3
        a_needs_building = agent_a.drives.shelter_need > 0.3
        b_needs_food = agent_b.drives.hunger > 0.3
        b_needs_building = agent_b.drives.shelter_need > 0.3

        # What does A have that B wants?
        a_give = None
        if b_needs_food:
            for item in FOOD_ITEMS:
                if agent_a.inventory_count(item) > 0:
                    a_give = item
                    break
        if not a_give and b_needs_building:
            for item in BUILDING_ITEMS:
                if agent_a.inventory_count(item) > 0:
                    a_give = item
                    break
        if not a_give:
            # Give whatever we have most of
            best_item, best_qty = None, 0
            for inv_item in agent_a.inventory:
                name = inv_item.get("name", "")
                qty = int(inv_item.get("quantity", 1))
                if qty > best_qty:
                    best_item, best_qty = name, qty
            a_give = best_item

        # What does B have that A wants?
        b_give = None
        if a_needs_food:
            for item in FOOD_ITEMS:
                if agent_b.inventory_count(item) > 0:
                    b_give = item
                    break
        if not b_give and a_needs_building:
            for item in BUILDING_ITEMS:
                if agent_b.inventory_count(item) > 0:
                    b_give = item
                    break
        if not b_give:
            best_item, best_qty = None, 0
            for inv_item in agent_b.inventory:
                name = inv_item.get("name", "")
                qty = int(inv_item.get("quantity", 1))
                if qty > best_qty:
                    best_item, best_qty = name, qty
            b_give = best_item

        if a_give and b_give and a_give != b_give:
            return a_give, b_give
        return None, None

    def _get_active_schedule_step(self, agent: Agent) -> dict | None:
        if not agent.daily_schedule:
            return None
        schedule = sorted(agent.daily_schedule, key=lambda step: step.get("hour", 0))
        active = schedule[0]
        for idx, step in enumerate(schedule):
            step_hour = int(step.get("hour", 0))
            next_hour = int(schedule[idx + 1].get("hour", 24)) if idx + 1 < len(schedule) else 24
            if step_hour <= self.time_manager.hour < next_hour:
                active = step
                break
            if self.time_manager.hour >= step_hour:
                active = step
        return active

    def _advance_current_plan(self, agent: Agent, status: str, note: str = ""):
        if not agent.current_plan:
            return
        steps = agent.current_plan.get("candidate_steps") or []
        step_index = int(agent.current_plan.get("step_index", 0))
        if status == "completed" and step_index < len(steps) - 1:
            agent.current_plan["step_index"] = step_index + 1
        elif status == "completed":
            agent.current_plan["status"] = "completed"
        elif status == "blocked":
            agent.current_plan["status"] = "blocked"
        if note:
            agent.current_plan["last_note"] = note

    def _note_plan_outcome(self, agent: Agent, success: bool, category: str, summary: str, tick: int | None = None):
        tick = self.tick if tick is None else tick
        if success:
            agent.bump_identity(summary, category if category not in {"eating", "sleeping"} else "")
            agent.add_life_event(summary, tick, category="success", impact=0.55)
            if agent.blocked_reasons:
                agent.blocked_reasons = [r for r in agent.blocked_reasons if category not in r.get("reason", "")]
        else:
            blocked = f"{category}: {summary}"
            agent.add_blocked_reason(blocked, tick, severity=0.65)
            agent.add_life_event(summary, tick, category="setback", impact=0.45)
            if agent.current_plan and not agent.fallback_plan:
                agent.fallback_plan = {
                    "goal": f"Recover from blocked {category}",
                    "steps": [agent.current_plan.get("fallback") or "Regroup and try a smaller step."],
                    "status": "active",
                }
            if summary:
                agent.working_memory.set_worry(summary)
            repeated = sum(1 for reason in agent.blocked_reasons if category in reason.get("reason", ""))
            if repeated >= 2:
                agent.add_intention(
                    f"Get unstuck on {category.replace('_', ' ')}",
                    "I've hit the same obstacle more than once and need a different approach.",
                    0.66,
                    "plan_revision",
                    target_location=agent.current_location,
                    next_step="ask for help or try a smaller version of the task",
                    status="active",
                    created_tick=tick,
                    expires_after_ticks=180,
                    refresh_on_relevance=True,
                )
        for goal in agent.active_goals:
            if goal.get("status") != "active":
                continue
            notes = goal.setdefault("progress_notes", [])
            notes.append(summary)
            goal["progress_notes"] = notes[-4:]
            if success and any(word in goal.get("text", "").lower() for word in category.replace("_", " ").split()):
                goal["status"] = "completed"
                break

    def _score_intention_candidate(self, agent: Agent, candidate: dict) -> float:
        score = float(candidate.get("base_score", 0.25))
        label = f"{candidate.get('why', '')} {candidate.get('description', '')}".lower()
        routine = candidate.get("routine") or {}
        routine_action = routine.get("action", "")
        if "hunger" in label or "food" in label:
            score += agent.drives.hunger * 0.5
        if routine_action == "eating":
            score += agent.drives.hunger * 0.55
        if "sleep" in label or "rest" in label:
            score += agent.drives.rest * 0.5
        if routine_action == "sleeping":
            score += agent.drives.rest * 0.55
        if "shelter" in label or "wood" in label or "build" in label:
            score += agent.drives.shelter_need * 0.45
        if routine_action in {"building", "gathering"} and any(word in label for word in ("wood", "shelter", "build")):
            score += agent.drives.shelter_need * 0.22
        if candidate.get("source") == "commitment":
            score += 0.25
        if candidate.get("source") == "scheduled":
            score += 0.18
        if agent.working_memory.current_goal and candidate.get("description") and agent.working_memory.current_goal.lower() in candidate["description"].lower():
            score += 0.15
        if agent.working_memory.background_worry and candidate.get("why") and agent.working_memory.background_worry.lower()[:18] in candidate["why"].lower():
            score += 0.12
        if candidate.get("location") == agent.current_location:
            score += 0.04
        score += self._institution_weight_for(agent, candidate.get("location"))
        score += self._project_weight_for(agent, candidate.get("location"))
        if candidate.get("source") in {"meeting", "institution"}:
            score += 0.16
        if candidate.get("source") == "trade":
            score += 0.12 + min(agent.drives.hunger, agent.drives.shelter_need) * 0.18
        keep_commitments = any(
            (n["text"] if isinstance(n, dict) else str(n)) == "Keep your commitments"
            for n in self.world.constitution.social_norms
        )
        if keep_commitments and candidate.get("source") == "commitment":
            score += 0.12
        if agent.active_conflicts and candidate.get("source") in {"support", "alliance"}:
            score -= 0.08
        return round(score, 3)

    def _scheduled_step_to_action(self, agent: Agent, scheduled_step: dict) -> dict | None:
        activity = str(scheduled_step.get("activity", "idle")).lower()
        location = scheduled_step.get("location", agent.current_location)
        action = "idle"
        resource = None

        if location != agent.current_location:
            action = "walking"
        elif "sleep" in activity or "rest" in activity:
            action = "sleeping"
        elif "eat" in activity or "food" in activity:
            action = "eating"
        elif "build" in activity or "construct" in activity:
            action = "building"
        elif "gather wood" in activity or ("wood" in activity and "gather" in activity):
            action = "gathering"
            resource = "wood"
        elif "fish" in activity:
            action = "gathering"
            resource = "fish"
        elif "berry" in activity:
            action = "gathering"
            resource = "wild_berries"
        elif "herb" in activity:
            action = "gathering"
            resource = "wild_herbs"
        elif "plant" in activity or "forage" in activity:
            action = "gathering"
            resource = "wild_plants"
        elif any(word in activity for word in ("talk", "meet", "social", "visit", "explore", "look", "inspect")):
            action = "walking" if location != agent.current_location else "idle"
        elif any(word in activity for word in ("work", "practice", "train")):
            action = "working"

        return {
            "action": action,
            "target": location,
            "resource": resource,
            "thought": f"Stick to the plan: {activity} at {location.replace('_', ' ')}.",
        }

    def _get_planned_action(self, agent: Agent, hour: float, time_of_day: str) -> tuple[dict | None, str | None]:
        scheduled_step = self._get_active_schedule_step(agent)
        agent.current_plan_step = scheduled_step
        if agent.drives.hunger > 0.88:
            agent.plan_mode = "deviating"
            agent.plan_deviation_reason = "my body forced food to the top"
            routine = agent.get_routine_action(hour, time_of_day)
            agent.set_decision_rationale({
                "source": "drive_override",
                "description": "Urgent hunger override",
                "why": "My body forced food to the top.",
                "score": 1.0,
            }, [])
            return routine, agent.plan_deviation_reason
        if agent.drives.rest > 0.9:
            agent.plan_mode = "deviating"
            agent.plan_deviation_reason = "my body forced rest to the top"
            routine = agent.get_routine_action(hour, time_of_day)
            agent.set_decision_rationale({
                "source": "drive_override",
                "description": "Urgent exhaustion override",
                "why": "My body forced rest to the top.",
                "score": 1.0,
            }, [])
            return routine, agent.plan_deviation_reason
        candidates: list[dict] = []
        if scheduled_step:
            scheduled_action = self._scheduled_step_to_action(agent, scheduled_step)
            candidates.append({
                "source": "scheduled",
                "description": scheduled_step.get("activity", "follow the daily schedule"),
                "why": "This is the plan I set for today.",
                "location": scheduled_step.get("location", agent.current_location),
                "routine": scheduled_action,
                "base_score": 0.48,
            })
        if agent.current_commitment:
            commitment = agent.current_commitment
            candidates.append({
                "source": "commitment",
                "description": commitment.get("description", "follow through on a commitment"),
                "why": "I told someone I'd do this.",
                "location": commitment.get("location", agent.current_location),
                "routine": {
                    "action": "walking" if commitment.get("location") != agent.current_location else "idle",
                    "target": commitment.get("location", agent.current_location),
                    "thought": f"Follow through: {commitment.get('description', 'commitment')}.",
                },
                "base_score": 0.72,
            })
        for intention in agent.active_intentions[:5]:
            if intention.get("status") not in ("active", "candidate"):
                continue
            location = intention.get("target_location") or agent.current_location
            step_text = intention.get("next_step") or intention.get("goal", "make progress")
            temp_step = {"activity": step_text, "location": location}
            candidates.append({
                "source": intention.get("source", "intention"),
                "description": intention.get("goal", step_text),
                "why": intention.get("why", "This keeps pulling at my attention."),
                "location": location,
                "routine": self._scheduled_step_to_action(agent, temp_step),
                "base_score": float(intention.get("urgency", 0.45)),
                "intention": intention,
            })

        routine_need = agent.get_routine_action(hour, time_of_day)
        candidates.append({
            "source": "drive_loop",
            "description": routine_need.get("thought", "respond to immediate needs"),
            "why": "My body and situation are pushing me this way.",
            "location": routine_need.get("target", agent.current_location),
            "routine": routine_need,
            "base_score": 0.22,
        })

        for candidate in candidates:
            candidate["score"] = self._score_intention_candidate(agent, candidate)

        if not candidates:
            agent.plan_mode = "improvising"
            agent.plan_deviation_reason = ""
            agent.set_decision_rationale({"source": "none", "description": "No strong options"}, [])
            return None, None

        chosen = max(candidates, key=lambda item: item.get("score", 0))
        agent.set_decision_rationale({
            "source": chosen.get("source"),
            "description": chosen.get("description"),
            "why": chosen.get("why"),
            "score": chosen.get("score"),
        }, candidates)

        if chosen.get("source") == "scheduled":
            agent.plan_mode = "scheduled"
            agent.plan_deviation_reason = ""
            return chosen.get("routine"), None

        if chosen.get("source") == "commitment":
            agent.plan_mode = "commitment"
            agent.plan_deviation_reason = "following through on a commitment"
            return chosen.get("routine"), agent.plan_deviation_reason

        if scheduled_step:
            agent.plan_mode = "deviating"
            agent.plan_deviation_reason = chosen.get("why", "a stronger intention won out")
            return chosen.get("routine"), agent.plan_deviation_reason

        agent.plan_mode = "intention_led"
        agent.plan_deviation_reason = ""
        return chosen.get("routine"), None

    def _next_morning_tick(self, wake_hour: int = 6) -> int:
        current_day = self.time_manager.day
        ticks_per_hour = self.time_manager.ticks_per_day / 24
        wake_tick_in_day = int(wake_hour * ticks_per_hour)
        if self.time_manager.hour < wake_hour:
            return self.tick + max(1, wake_tick_in_day - self.time_manager.tick_in_day)
        ticks_until_midnight = self.time_manager.ticks_per_day - self.time_manager.tick_in_day
        ticks_next_day = wake_tick_in_day
        return self.tick + ticks_until_midnight + ticks_next_day

    # ── Emergent behavior methods ──────────────────────────────────

    def _check_desperation_actions(self) -> list[dict]:
        """Agents in extreme need may steal food.  Gated by personality, not LLM."""
        from systems.economy import FOOD_ITEMS
        events: list[dict] = []
        for agent in self.agents.values():
            if agent.drives.hunger < 0.85 or agent.is_in_conversation:
                continue
            if self.tick - agent.last_steal_attempt_tick < 200:
                continue
            has_food = any(i.get("name") in FOOD_ITEMS for i in agent.inventory)
            if has_food:
                continue

            # Find nearby targets with food
            candidates = []
            for other in self.agents.values():
                if other.id == agent.id:
                    continue
                dist = abs(agent.position[0] - other.position[0]) + abs(agent.position[1] - other.position[1])
                if dist > 3:
                    continue
                target_food = [i for i in other.inventory if i.get("name") in FOOD_ITEMS]
                if target_food:
                    candidates.append((other, target_food[0], dist))
            if not candidates:
                continue

            # Personality gate
            conscientiousness = agent.profile.personality.get("conscientiousness", 0.5)
            agreeableness = agent.profile.personality.get("agreeableness", 0.5)
            resistance = conscientiousness * 0.4 + agreeableness * 0.3
            desperation = (agent.drives.hunger - 0.7) * 3.0
            if random.random() > desperation - resistance:
                continue

            agent.last_steal_attempt_tick = self.tick
            target, food_item, dist = min(candidates, key=lambda x: x[2])
            food_name = food_item.get("name", "food")

            # Transfer
            if target.consume_inventory(food_name, 1):
                agent.inventory.append({"name": food_name, "quantity": 1})

            agent.current_action = ActionType.STEALING

            # Detection
            dexterity = agent.profile.physical_traits.get("dexterity", 0.5)
            detection_chance = 0.4 + (1.0 - dexterity) * 0.3
            detected_by: list[str] = []
            if random.random() < detection_chance:
                detected_by.append(target.name)
            for observer in self.agents.values():
                if observer.id in (agent.id, target.id):
                    continue
                obs_dist = abs(observer.position[0] - agent.position[0]) + abs(observer.position[1] - agent.position[1])
                if obs_dist <= 4 and random.random() < 0.3:
                    detected_by.append(observer.name)

            if detected_by:
                self._record_social_breach(agent, detected_by, f"{agent.name} stole {food_name} from {target.name}", kind="theft", severity=0.7)
                agent.reputation["honesty"] = max(0.0, agent.reputation.get("honesty", 0.5) - 0.15)
                agent.emotional_state.apply_event("shame", 0.5)
                target.emotional_state.apply_event("witnessed_injustice", 0.6)
                for name in detected_by:
                    det = next((a for a in self.agents.values() if a.name == name), None)
                    if det:
                        det.episodic_memory.add_simple(
                            f"I saw {agent.name} steal {food_name} from {target.name}!",
                            tick=self.tick, day=self.time_manager.day,
                            time_of_day=self.time_manager.time_of_day, location=agent.current_location,
                            category="observation", intensity=0.8, emotion="shocked", agents=[agent.name, target.name],
                        )
                self.world.add_norm_violation({
                    "tick": self.tick, "agent": agent.name, "norm": "Do not steal",
                    "location": agent.current_location,
                    "description": f"{agent.name} stole {food_name} from {target.name}",
                })
                self._add_story_highlight("crisis", f"{agent.name} was caught stealing from {target.name}!", agent.id, agent.name)
                events.append({"type": "system_event", "eventType": "theft_detected", "label": "Theft!", "description": f"{agent.name} stole {food_name} from {target.name}"})
            else:
                agent.episodic_memory.add_simple(
                    f"I stole some {food_name} from {target.name}. Nobody saw.",
                    tick=self.tick, day=self.time_manager.day,
                    time_of_day=self.time_manager.time_of_day, location=agent.current_location,
                    category="action", intensity=0.7, emotion="guilty", agents=[target.name],
                )
                agent.secrets.append({"content": f"Stole {food_name} from {target.name}", "tick": self.tick})
                agent.emotional_state.apply_event("shame", 0.3)

        return events

    def _process_sickness(self) -> list[dict]:
        """Simple health/sickness system.  Agents can get sick and heal with herbs."""
        events: list[dict] = []
        for agent in self.agents.values():
            if agent.is_sick:
                agent.health = max(0.1, agent.health - 0.05)
                agent.drives.rest = min(1.0, agent.drives.rest + 0.05)
                # Self-heal with herbs
                if agent.inventory_count("wild_herbs") >= 1:
                    agent.consume_inventory("wild_herbs", 1)
                    agent.is_sick = False
                    agent.sick_since_tick = 0
                    agent.health = min(1.0, agent.health + 0.3)
                    agent.episodic_memory.add_simple(
                        "I used some herbs and I'm starting to feel better.",
                        tick=self.tick, day=self.time_manager.day,
                        time_of_day=self.time_manager.time_of_day, location=agent.current_location,
                        category="action", intensity=0.5, emotion="relieved",
                    )
                    events.append({"type": "system_event", "eventType": "healed", "label": "Healed", "description": f"{agent.name} recovered using herbs."})
                elif self.tick - agent.sick_since_tick > 300 and random.random() < 0.3:
                    agent.is_sick = False
                    agent.sick_since_tick = 0
                    agent.health = min(1.0, agent.health + 0.1)
            else:
                base_chance = 0.005
                if agent.drives.rest > 0.7:
                    base_chance += 0.01
                if agent.health < 0.7:
                    base_chance += 0.01
                if random.random() < base_chance:
                    agent.is_sick = True
                    agent.sick_since_tick = self.tick
                    agent.health = max(0.3, agent.health - 0.2)
                    agent.working_memory.push("I don't feel well...")
                    agent.emotional_state.apply_event("anxiety", 0.3)
                    self._add_story_highlight("health", f"{agent.name} has fallen ill.", agent.id, agent.name)
                    events.append({"type": "system_event", "eventType": "fell_sick", "label": "Illness", "description": f"{agent.name} has fallen ill."})
        return events

    def _check_creative_actions(self) -> list[dict]:
        """Agents with high openness sometimes start a creative open-ended action."""
        events: list[dict] = []
        for agent in self.agents.values():
            if agent.current_action.value != "idle" or agent.is_in_conversation:
                continue
            openness = agent.profile.personality.get("openness", 0.5)
            if openness < 0.6:
                continue
            if agent.drives.hunger > 0.6 or agent.drives.rest > 0.7:
                continue
            if random.random() > openness * 0.15:
                continue

            description = (
                f"{agent.name} wants to make something expressive from materials around "
                f"{agent.current_location.replace('_', ' ')}."
            )
            asyncio.create_task(self._execute_open_ended_action(agent, description))
            self._add_story_highlight("culture", f"{agent.name} started a creative experiment at {agent.current_location.replace('_', ' ')}.", agent.id, agent.name)
            events.append({"type": "system_event", "eventType": "creative_attempt", "label": "Creative Attempt", "description": f"{agent.name} started making something expressive at {agent.current_location}."})
        return events

    # ── End emergent behavior methods ────────────────────────────

    def _process_tick(self) -> list[dict]:
        events = []
        hour = self.time_manager.hour
        time_of_day = self.time_manager.time_of_day

        if self.time_manager.tick_in_day == 0:
            for agent in self.agents.values():
                agent.social_commitments = [
                    c for c in agent.social_commitments
                    if c.get("recurring") or c.get("scheduled_day", self.time_manager.day) >= self.time_manager.day
                ]

        commitment_events = self._execute_commitments()
        events.extend(commitment_events)
        if self.tick % 12 == 0:
            events.extend(self._run_institution_upkeep())
            events.extend(self._staff_projects())
            self._refresh_social_world_knowledge()
            self._synthesize_identity()
        events.extend(self._process_missed_obligations())
        events.extend(self._seed_social_proposals())
        events.extend(self._process_meetings())
        events.extend(self._process_active_proposals())
        if self.tick % 15 == 0:
            events.extend(self._work_on_projects())
        if self.tick % 10 == 0:
            events.extend(self._apply_social_enforcement())

        for agent in self.agents.values():
            if agent.conversation_cooldown > 0:
                agent.conversation_cooldown -= 1
            if not agent.is_in_conversation and agent.current_action == ActionType.TALKING and agent.talking_until_tick and self.tick >= agent.talking_until_tick:
                agent.resume_after_conversation()
            if agent.current_action == ActionType.SLEEPING:
                if agent.sleep_until_tick and self.tick < agent.sleep_until_tick:
                    continue
                else:
                    agent.wake_up()

            is_alone = all(other.current_location != agent.current_location for other in self.agents.values() if other.id != agent.id)
            has_home = any(loc.get("claimed_by") == agent.name for loc in self.world.locations.values() if loc.get("type") == "built_structure")
            num_friends = sum(1 for r in agent.relationships.values() if r.get("trust", 0) > 0.5)
            agent.drives.tick_update(
                is_working=agent.current_action.value in ("working", "building"),
                is_sleeping=agent.current_action.value == "sleeping",
                is_alone=is_alone,
                is_socializing=agent.current_action.value == "talking",
                wealth=0,
                has_home=has_home,
                num_friends=num_friends,
            )
            # Weather/season affect energy drain
            energy_mod = self.world.get_energy_drain_modifier()
            if energy_mod > 1.0:
                extra = (energy_mod - 1.0) * 0.002
                agent.drives.rest = min(1.0, agent.drives.rest + extra)
                agent.drives.hunger = min(1.0, agent.drives.hunger + extra * 0.5)

            if agent.current_action.value == "eating":
                agent.drives.satisfy_hunger()
                agent.drives.satisfy_thirst()
            agent.emotional_state.decay(1)
            # Keep sickness in the agent's conscious awareness
            if agent.is_sick and self.tick % 20 == 0:
                agent.working_memory.latest_sensation = "I feel feverish and weak."
            if self.tick % 10 == 0:
                agent.working_memory.update_from_drives(agent.drives)

            agent_events = agent.update(hour, self.world)
            events.extend(agent_events)

            if agent.current_action.value in ("eating", "working", "building") and not agent.path:
                agent.current_action = ActionType.IDLE

            if agent.current_action.value == "idle" and not agent.path and not agent.current_commitment:
                previous_plan_mode = agent.plan_mode
                previous_deviation_reason = agent.plan_deviation_reason
                routine, deviation_reason = self._get_planned_action(agent, hour, time_of_day)
                if not routine:
                    routine = agent.get_routine_action(hour, time_of_day)
                target = routine.get("target", agent.current_location)
                action = routine.get("action", "idle")

                if deviation_reason and previous_deviation_reason != deviation_reason:
                    events.append({
                        "type": "system_event",
                        "eventType": "plan_shift",
                        "label": "Plan Shift",
                        "description": f"{agent.name} went off-plan because of {deviation_reason}.",
                    })
                elif previous_plan_mode == "deviating" and agent.plan_mode == "scheduled" and agent.current_plan_step:
                    events.append({
                        "type": "system_event",
                        "eventType": "plan_resumed",
                        "label": "Back On Plan",
                        "description": f"{agent.name} returned to the daily plan: {agent.current_plan_step.get('activity', 'planned task')}.",
                    })

                if action == "walking" and target != agent.current_location:
                    from systems.interactions import avoidance_system
                    avoid_pos = avoidance_system.get_avoidance_positions(agent, self.agents)
                    agent.start_walking(target, avoidance_targets=avoid_pos if avoid_pos else None)
                    events.append({"type": "agent_move", "agentId": agent.id, "targetLocation": target})
                elif action == "eating":
                    ate_event = self._handle_eating(agent)
                    if ate_event:
                        events.append(ate_event)
                elif action == "sleeping":
                    if target != agent.current_location:
                        from systems.interactions import avoidance_system as _avoid
                        _avoid_pos = _avoid.get_avoidance_positions(agent, self.agents)
                        agent.start_walking(target, avoidance_targets=_avoid_pos if _avoid_pos else None)
                        agent.inner_thought = f"I should get back to {target.replace('_', ' ')} and sleep there."
                        events.append({"type": "agent_move", "agentId": agent.id, "targetLocation": target})
                    else:
                        agent.start_sleeping_until(self._next_morning_tick(agent.wake_hour))
                elif action == "gathering_wood":
                    gather_event = self._gather_resource_for_agent(agent, "wood")
                    if gather_event:
                        events.append(gather_event)
                elif action == "gathering":
                    gather_event = self._gather_resource_for_agent(agent, routine.get("resource", "wood"))
                    if gather_event:
                        events.append(gather_event)
                elif action == "building":
                    build_event = self._build_shelter(agent)
                    if build_event:
                        events.append(build_event)
                elif action == "working":
                    agent.current_action = ActionType.WORKING

                if routine.get("thought"):
                    agent.inner_thought = routine["thought"]

        self._resolve_collisions()

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
                        obs = observation_system.generate_observation(agent, other, dist, tick=self.tick)
                        if obs:
                            agent.working_memory.latest_observation = obs

        if self.tick % 5 == 0:
            events.extend(self._process_interactions())

        day = self.time_manager.day
        if 6 <= hour < 7 and self._last_morning_day < day:
            self._last_morning_day = day
            asyncio.create_task(self._run_daily_morning())
        if 21 <= hour < 22 and self._last_evening_day < day:
            self._last_evening_day = day
            asyncio.create_task(self._run_daily_evening())
            asyncio.create_task(self._generate_day_recap(day))

        # Per-agent novelty-driven decisions every 10 ticks
        if self.tick % 10 == 0:
            asyncio.create_task(self._process_novelty_decisions())

        if self.tick % 30 == 0:
            events.extend(self._check_desperation_actions())

        if self.tick % 50 == 0:
            events.extend(self._process_sickness())

        if self.tick % 80 == 0:
            events.extend(self._check_creative_actions())

        # Pattern detection every 50 ticks
        if self.tick % 50 == 0:
            from systems.pattern_detector import pattern_detector
            pattern_events = pattern_detector.check(self.agents, self.world, self.tick, self.time_manager.day)
            events.extend(pattern_events)
            for event in pattern_events:
                description = event.get("description", "")
                self._record_timeline_event(
                    "pattern_detected",
                    event.get("label", "Pattern Detected"),
                    description,
                    [],
                )
                if self._broadcast:
                    asyncio.create_task(self._broadcast_message("pattern_event", {
                        "type": "social" if "gather" in description.lower() else "norm" if "norm" in description.lower() else "social",
                        "name": event.get("label", "Pattern"),
                        "description": description,
                        "emerged_on": self.time_manager.day,
                    }))
                    asyncio.create_task(self._broadcast_message("timeline_event", self._serialize_timeline_events()[-1]))

        if self.tick % 100 == 0:
            from systems.meta_simulation import meta_simulation
            events.extend(meta_simulation.check(self.agents, self.world, self.tick, self.time_manager.day))

        # Sync weather/season to world and decay objects
        if self.tick % 50 == 0:
            self.world.update_weather_season(self.time_manager.weather, self.time_manager.season)
            object_delta = self.world.decay_all_objects(self.time_manager.weather)
            if self._broadcast and any(object_delta.values()):
                asyncio.create_task(self._broadcast_message("world_object_delta", object_delta))

        if self.tick % 200 == 0:
            from systems.coherence import coherence_checker
            coherence_checker.check(self.agents, self.world)

        return events

    def _handle_eating(self, agent) -> dict | None:
        resources_here = self.world.get_resources_at(agent.current_location)
        for food_type in ["wild_berries", "fish", "wild_plants", "wild_herbs"]:
            if food_type not in resources_here:
                continue
            gathered = self.world.gather_resource(food_type, 1, agent.current_location)
            if gathered <= 0:
                continue
            agent.inventory.append({"name": food_type, "quantity": gathered})
            agent.drives.satisfy_hunger()
            food_enjoy = 0.35 + agent.profile.personality.get("openness", 0.5) * 0.2 if food_type == "fish" else 0.35 + agent.profile.physical_traits.get("endurance", 0.5) * 0.2
            agent.skill_memory.record_attempt("fishing" if food_type == "fish" else "gathering", True, food_enjoy)
            agent.current_action = ActionType.EATING
            agent.emotional_state.apply_event("earned_money", 0.2)
            self._advance_current_plan(agent, "completed", f"Ate {food_type.replace('_', ' ')}.")
            self._note_plan_outcome(agent, True, "eating", f"I managed to eat {food_type.replace('_', ' ')}.")
            return {"type": "agent_action", "agentId": agent.id, "action": "eating", "targetLocation": agent.current_location}
        agent.current_action = ActionType.IDLE
        agent.inner_thought = "Nothing edible here right now..."
        self._advance_current_plan(agent, "blocked", "No food available here.")
        self._note_plan_outcome(agent, False, "food", "I came up empty looking for food.")
        return None

    def _gather_resource_for_agent(self, agent, resource: str) -> dict | None:
        skill_level = agent.skill_memory.activities.get("gathering", {}).get("skill_level", 0.0)
        amount = 1 + (1 if skill_level >= 0.3 else 0) + (1 if skill_level >= 0.7 else 0)
        # Apply season modifier to gathering yield
        season_mod = self.world.get_season_resource_modifier(resource)
        weather_mod = self.world.get_weather_modifier("gathering")
        amount = max(1, int(amount * season_mod * weather_mod))
        gathered = self.world.gather_resource(resource, amount, agent.current_location)
        if gathered <= 0:
            agent.current_action = ActionType.IDLE
            self._advance_current_plan(agent, "blocked", f"Couldn't get {resource}.")
            self._note_plan_outcome(agent, False, resource, f"I couldn't gather any {resource.replace('_', ' ')} here.")
            return None
        agent.inventory.append({"name": resource, "quantity": gathered})
        gather_enjoy = 0.35 + agent.profile.physical_traits.get("endurance", 0.5) * 0.2
        agent.skill_memory.record_attempt("gathering", True, gather_enjoy)
        agent.current_action = ActionType.WORKING
        agent.inner_thought = f"I gathered some {resource.replace('_', ' ')}."
        self._advance_current_plan(agent, "completed", f"Gathered {resource.replace('_', ' ')}.")
        self._note_plan_outcome(agent, True, resource, f"I gathered {resource.replace('_', ' ')} and made progress.")
        self._world_state_dirty = True
        from systems.pattern_detector import pattern_detector
        pattern_detector.record_action(agent.name, {
            "type": "gathering", "location": agent.current_location, "resource": resource,
        }, self.tick)
        return {"type": "agent_action", "agentId": agent.id, "action": "working", "targetLocation": agent.current_location}

    def _build_shelter(self, agent, label: str | None = None, purpose: str = "shelter") -> dict | None:
        # Weather check: building in storm is nearly impossible
        build_mod = self.world.get_weather_modifier("building")
        if build_mod < 0.3 and random.random() > build_mod:
            agent.inner_thought = "The weather is too bad to build right now."
            self._note_plan_outcome(agent, False, "building", "Weather prevented building.")
            return None
        if agent.inventory_count("wood") < 5:
            agent.inner_thought = "I still need more wood before I can build."
            self._advance_current_plan(agent, "blocked", "Not enough wood to build.")
            self._note_plan_outcome(agent, False, "building", "I don't have enough wood to build yet.")
            return None
        spot = self.world.find_empty_space(2, 2)
        if not spot:
            self._advance_current_plan(agent, "blocked", "Couldn't find a safe building spot.")
            self._note_plan_outcome(agent, False, "building", "I couldn't find anywhere workable to build.")
            return None
        bid = self.world.build_structure(spot[0], spot[1], 2, 2, label or f"{agent.name.split()[0]}'s Shelter", agent.name, purpose)
        if not bid:
            self._advance_current_plan(agent, "blocked", "The build attempt failed.")
            self._note_plan_outcome(agent, False, "building", "The build attempt fell through.")
            return None
        agent.consume_inventory("wood", 5)
        agent.drives.satisfy_shelter()
        build_enjoy = 0.4 + agent.profile.physical_traits.get("strength", 0.5) * 0.15 + agent.profile.physical_traits.get("dexterity", 0.5) * 0.1
        agent.skill_memory.record_attempt("construction", True, build_enjoy)
        agent.current_action = ActionType.BUILDING
        agent.emotional_state.apply_event("accomplishment", 0.6)
        agent.inner_thought = f"I built {label or 'a shelter'}!"
        agent.world_model.learn_claim(bid, agent.name, purpose)
        agent.mental_models.update_from_interaction(agent.name, tick=self.tick, domain="construction", competence_delta=0.05)
        self._advance_current_plan(agent, "completed", f"Built {label or 'a shelter'}.")
        self._note_plan_outcome(agent, True, "building", f"I built {label or 'a shelter'} and it changes what tomorrow looks like.")
        self._world_state_dirty = True
        self._add_story_highlight("achievement", f"{agent.name} built: {label or 'a shelter'}", agent.id, agent.name)
        from systems.pattern_detector import pattern_detector
        pattern_detector.record_action(agent.name, {
            "type": "building", "location": agent.current_location, "label": label or "shelter",
        }, self.tick)
        return {"type": "system_event", "eventType": "building_constructed", "label": "Construction", "description": f"{agent.name} built {label or 'a shelter'}"}

    def _execute_commitments(self) -> list[dict]:
        events = []
        for agent in self.agents.values():
            agent.current_commitment = None
            for commitment in agent.social_commitments:
                if commitment.get("status") not in (None, "planned", "in_progress"):
                    continue
                if commitment.get("scheduled_day", self.time_manager.day) != self.time_manager.day:
                    continue
                scheduled_hour = commitment.get("scheduled_hour", 12)
                if abs(self.time_manager.hour - scheduled_hour) > 1.0:
                    continue
                agent.current_commitment = commitment
                agent.plan_mode = "commitment"
                agent.plan_deviation_reason = "following through on a commitment"
                commitment["status"] = "in_progress"
                if agent.current_location != commitment.get("location") and not agent.path:
                    agent.start_walking(commitment.get("location", agent.current_location))
                    events.append({"type": "agent_move", "agentId": agent.id, "targetLocation": commitment.get("location")})
                else:
                    outcome = self._resolve_commitment(agent, commitment)
                    if outcome:
                        events.extend(outcome)
                break
        return events

    def _resolve_commitment(self, agent, commitment: dict) -> list[dict]:
        location = commitment.get("location", agent.current_location)
        others = [a for a in self.agents.values() if a.name in commitment.get("with", [])]
        arrived = [a for a in others if a.current_location == location]
        kind = commitment.get("kind", "decision_to_meet")
        if others and not arrived:
            return []

        events = []
        if kind in ("decision_to_meet", "agreement"):
            commitment["status"] = "completed"
            text = f"{agent.name} followed through on a plan to meet at {location.replace('_', ' ')}."
            agent.episodic_memory.add_simple(text, self.tick, self.time_manager.day, self.time_manager.time_of_day, location, category="action", intensity=0.6, emotion="satisfied", agents=[a.name for a in others])
            self._note_plan_outcome(agent, True, "commitment", text)
            for other in others:
                agent.resolve_conflict(other.name, "failed to show")
                other.resolve_conflict(agent.name, "failed to show")
            events.append({"type": "system_event", "eventType": "plan_followthrough", "label": "Plans Kept", "description": text})
        elif kind == "decision_to_visit":
            commitment["status"] = "completed"
            agent.working_memory.push(f"I made it to {location.replace('_', ' ')} like we said we would.")
            self._note_plan_outcome(agent, True, "visit", f"I followed through on visiting {location.replace('_', ' ')}.")
            events.append({"type": "system_event", "eventType": "visit_completed", "label": "Visit", "description": f"{agent.name} followed through on a visit to {location.replace('_', ' ')}."})
        elif kind == "decision_to_gather":
            resource = commitment.get("required_resources", ["wood"])[0]
            gathered = self._gather_resource_for_agent(agent, resource)
            if gathered:
                commitment["status"] = "completed"
                events.append(gathered)
                events.append({"type": "system_event", "eventType": "plan_followthrough", "label": "Gathering Plan", "description": f"{agent.name} carried out a plan to gather {resource.replace('_', ' ')}."})
        elif kind == "decision_to_build":
            build_event = self._build_shelter(agent, label=f"{agent.name.split()[0]}'s Build", purpose="planned_build")
            if build_event:
                commitment["status"] = "completed"
                events.append(build_event)
            else:
                commitment["status"] = "failed"
                agent.emotional_state.apply_event("negative_conversation", 0.2)
                agent.working_memory.set_worry("I couldn't follow through on that building plan.")
                self._note_plan_outcome(agent, False, "commitment", "I let a building promise slip because I wasn't ready.")
                events.append({"type": "system_event", "eventType": "plan_failed", "label": "Missed Plan", "description": f"{agent.name} could not follow through on the building plan."})
        elif kind in ("barter_offer", "offer"):
            partner_names = commitment.get("with", [])
            partner = next((a for a in self.agents.values() if a.name in partner_names and a.current_location == location), None)
            if partner:
                commitment["status"] = "completed"
                description = commitment.get("description") or f"{agent.name} tries to work out an exchange with {partner.name} at {location.replace('_', ' ')}."
                asyncio.create_task(self._execute_open_ended_action(agent, description))
                self._note_plan_outcome(agent, True, "exchange", f"Tried to work out an exchange with {partner.name}.")
            else:
                # Partner isn't here yet, keep waiting
                pass
        elif kind == "proposal":
            result = self._apply_proposal(agent, commitment)
            if result:
                commitment["status"] = "completed"
                events.append(result)
        elif kind == "meeting":
            commitment["status"] = "completed"
            agent.episodic_memory.add_simple(
                f"I showed up for a meeting about {commitment.get('description', 'a proposal')}.",
                self.tick, self.time_manager.day, self.time_manager.time_of_day, location,
                category="action", intensity=0.5, emotion="focused", agents=[a.name for a in others],
            )
            for other in others:
                agent.resolve_conflict(other.name, "failed to show")
            events.append({"type": "system_event", "eventType": "meeting_attended", "label": "Meeting", "description": f"{agent.name} attended a meeting at {location.replace('_', ' ')}."})
        return events

    def _apply_proposal(self, agent, commitment: dict) -> dict | None:
        description = commitment.get("description", "")
        location = commitment.get("location", agent.current_location)
        lower = description.lower()
        if any(word in lower for word in ("claim", "home", "ours")) and self.world.claim_location(location, agent.name, "claimed by conversation"):
            agent.world_model.learn_claim(location, agent.name, "claimed by conversation")
            self.world.constitution.change_history.append({"tick": self.tick, "type": "claim", "description": f"{agent.name} claimed {location}"})
            return {"type": "system_event", "eventType": "claim_made", "label": "Claim", "description": f"{agent.name} claimed {location.replace('_', ' ')}."}
        proposal = self._make_proposal(
            agent,
            description,
            location,
            participants=[agent.name, *commitment.get("with", [])],
            kind=self._evaluate_proposal_kind(description),
        )
        meeting = self._make_meeting(description, location, proposal["supporters"][:6] + [agent.name], [proposal["id"]])
        return {"type": "system_event", "eventType": "proposal_created", "label": "Proposal", "description": f"{agent.name} proposed: {description} (meeting at {meeting['location'].replace('_', ' ')})."}

    def _resolve_collisions(self):
        occupied: dict[tuple[int, int], str] = {}
        for agent in self.agents.values():
            pos = agent.position
            if pos in occupied:
                cx, cy = pos
                for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)]:
                    candidate = (cx + dx, cy + dy)
                    if candidate not in occupied and 0 <= candidate[0] < self.world.width and 0 <= candidate[1] < self.world.height and self.world.is_walkable(candidate[0], candidate[1]):
                        agent.position = candidate
                        occupied[candidate] = agent.id
                        break
            else:
                occupied[pos] = agent.id

    def _process_interactions(self) -> list[dict]:
        events = []
        from systems.interactions import (
            interaction_decider, lightweight, select_interaction_type,
            overhearing_system, INTERACTION_TYPES, CONVERSATION_RANGE,
            awareness_system, LiveConversation, should_join_conversation,
        )

        # Phase 0: check if nearby agents should join active conversations
        for convo in list(self._live_conversations.values()):
            if not convo.is_active or len(convo.participants) >= LiveConversation.MAX_PARTICIPANTS:
                continue
            # Find a representative position from participants
            ref = convo.participants[0]
            rx, ry = ref.position
            for agent in self.agents.values():
                if agent.is_in_conversation or agent.conversation_cooldown > 0:
                    continue
                if agent.current_action.value in ("walking", "sleeping"):
                    continue
                ax, ay = agent.position
                dist = abs(ax - rx) + abs(ay - ry)
                if dist > CONVERSATION_RANGE:
                    continue
                if should_join_conversation(agent, convo, dist):
                    convo.add_participant(agent)
                    agent.is_in_conversation = True
                    agent.current_conversation_id = convo.id
                    agent.pause_for_conversation(self.tick + 12)
                    events.append({"type": "system_event", "eventType": "conversation_joined", "label": "Conversation", "description": f"{agent.name} joined the conversation with {', '.join(p.name for p in convo.participants if p.id != agent.id)}."})
                    if len(convo.participants) >= LiveConversation.MAX_PARTICIPANTS:
                        break

        # Phase 1: find new interaction pairs
        social_candidates = [
            agent for agent in self.agents.values()
            if agent.current_action.value not in ("walking", "sleeping")
            and not getattr(agent, "is_in_conversation", False)
            and getattr(agent, "conversation_cooldown", 0) <= 0
            and not agent.prefers_sleeping_now(self.time_manager.hour)
        ]

        for agent in social_candidates:
            perceived = awareness_system.get_perceived(agent, self.agents, self.world)
            perceived = [p for p in perceived if p["distance"] <= CONVERSATION_RANGE + 1]
            if not perceived:
                continue
            should, target, reason = interaction_decider.should_interact(agent, perceived)
            if not should or not target:
                continue
            rel = agent.relationships.get(target.name, {})
            itype = select_interaction_type(agent, target, reason, rel)
            type_info = INTERACTION_TYPES.get(itype, {})
            if not type_info.get("llm", False):
                agent.pause_for_conversation(self.tick + 8)
                target.pause_for_conversation(self.tick + 8)
                speech = lightweight.generate_greeting(agent, target, rel, self.time_manager.time_of_day) if itype == "greeting" else lightweight.generate_small_talk(agent)
                events.append({"type": "agent_speak", "agentId": agent.id, "targetId": target.id, "speech": speech})
                events.append({"type": "system_event", "eventType": "conversation_started", "label": "Conversation", "description": f"{agent.name} started talking with {target.name} ({reason})."})
                agent.drives.satisfy_social()
                target.drives.satisfy_social()
                agent.emotional_state.apply_event("social_interaction", 0.2)
                target.emotional_state.apply_event("social_interaction", 0.2)
                for a, b in [(agent, target), (target, agent)]:
                    if b.name not in a.relationships:
                        a.relationships[b.name] = {"sentiment": 0.5, "trust": 0.5, "familiarity": 0.0}
                    a.relationships[b.name]["familiarity"] = min(1.0, a.relationships[b.name].get("familiarity", 0) + 0.06)
                for p in perceived:
                    if p["agent"].id != target.id and p["can_overhear"]:
                        overhearing_system.process(p["agent"], [agent.name, target.name], speech, p["distance"])
            else:
                if len(self._live_conversations) >= 3:
                    continue
                convo = LiveConversation(agent, target, itype, reason, agent.current_location)
                self._live_conversations[convo.id] = convo
                agent.pause_for_conversation(self.tick + 12)
                target.pause_for_conversation(self.tick + 12)
                agent.is_in_conversation = True
                target.is_in_conversation = True
                agent.current_conversation_id = convo.id
                target.current_conversation_id = convo.id
                events.append({"type": "system_event", "eventType": "conversation_started", "label": "Conversation", "description": f"{agent.name} approached {target.name} to talk ({reason})."})
                asyncio.create_task(self._run_live_conversation(convo))
        return events

    async def _run_live_conversation(self, convo):
        from systems.interactions import process_conversation_consequences, should_leave_conversation, overhearing_system, CONVERSATION_RANGE

        try:
            initiator = convo.participants[0]

            # Opening turn
            opening = await convo.generate_turn(initiator)
            if self._broadcast and opening.get("speech"):
                await self._broadcast({"type": "tick", "data": {"tick": self.tick, "time": self.time_manager.to_dict(), "events": [{"type": "agent_speak", "agentId": initiator.id, "conversationId": convo.id, "speech": opening["speech"]}], "agents": [a.to_dict() for a in self.agents.values()]}})

            for _turn_idx in range(convo.max_turns):
                if not convo.is_active or len(convo.participants) < 2:
                    break

                # Check for voluntary leaves (non-speaker participants)
                for p in list(convo.participants):
                    if should_leave_conversation(p, convo):
                        convo.remove_participant(p)
                        p.is_in_conversation = False
                        p.current_conversation_id = None
                        p.conversation_cooldown = 30
                        p.talking_until_tick = max(p.talking_until_tick, self.tick + 6)
                        if self._broadcast:
                            await self._broadcast({"type": "tick", "data": {"tick": self.tick, "time": self.time_manager.to_dict(), "events": [{"type": "system_event", "eventType": "conversation_left", "label": "Conversation", "description": f"{p.name} left the conversation."}], "agents": [a.to_dict() for a in self.agents.values()]}})

                if len(convo.participants) < 2:
                    break

                # Select next speaker and generate turn
                speaker = convo.select_next_speaker()
                if not speaker:
                    break
                result = await convo.generate_turn(speaker)
                speech = result.get("speech", "")

                if self._broadcast and speech:
                    await self._broadcast({"type": "tick", "data": {"tick": self.tick, "time": self.time_manager.to_dict(), "events": [{"type": "agent_speak", "agentId": speaker.id, "conversationId": convo.id, "speech": speech}], "agents": [a.to_dict() for a in self.agents.values()]}})

                # Handle speaker wanting to leave
                if result.get("wants_to_leave") and len(convo.participants) > 2:
                    convo.remove_participant(speaker)
                    speaker.is_in_conversation = False
                    speaker.current_conversation_id = None
                    speaker.conversation_cooldown = 30
                    speaker.talking_until_tick = max(speaker.talking_until_tick, self.tick + 6)
                    continue
                if not result.get("wants_to_continue", True):
                    break

                # Overhearing for nearby non-participants
                if speech:
                    speaker_names = [p.name for p in convo.participants]
                    sx, sy = speaker.position
                    for other_id, other in self.agents.items():
                        if any(p.id == other_id for p in convo.participants):
                            continue
                        ox, oy = other.position
                        dist = abs(sx - ox) + abs(sy - oy)
                        if dist <= CONVERSATION_RANGE + 1:
                            overhearing_system.process(other, speaker_names, speech, dist, is_argument=(convo.interaction_type == "argument"))

            # End: consequences for all remaining participants
            all_names = [a.name for a in self.agents.values()]
            final_participants = list(convo.participants)
            for agent in final_participants:
                others = [p.name for p in final_participants if p.id != agent.id]
                if others:
                    process_conversation_consequences(agent, others, convo, tick=self.tick, day=self.time_manager.day, all_agent_names=all_names)
            await self._synthesize_conversation_models(convo, final_participants)
            if convo.structured_commitments:
                description = convo.structured_commitments[-1]["description"]
                self._add_story_highlight("new_goal", f"{final_participants[0].name} wants to: {description}", final_participants[0].id, final_participants[0].name)
        except Exception as e:
            logger.error("Conversation error: %s", e)
        finally:
            for p in list(convo.participants):
                p.is_in_conversation = False
                p.current_conversation_id = None
                p.talking_until_tick = max(p.talking_until_tick, self.tick + 6)
                p.conversation_cooldown = 30
            self._live_conversations.pop(convo.id, None)

    async def _process_inner_monologue_background(self):
        """Per-agent inner monologue. Each agent thinks every 3-5 ticks (staggered)."""
        try:
            from agents.cognition.inner_monologue import process_agent_thought
            thought_events = []
            for agent in list(self.agents.values()):
                thought = await process_agent_thought(agent, self.tick, self.time_manager.time_of_day)
                if thought:
                    thought_events.append({"type": "agent_thought", "agentId": agent.id, "thought": thought})
            if thought_events and self._broadcast:
                await self._broadcast({"type": "tick", "data": {"tick": self.tick, "time": self.time_manager.to_dict(), "events": thought_events, "agents": [a.to_dict() for a in self.agents.values()]}})
        except Exception as e:
            logger.error("Inner monologue error: %s", e)

    async def _run_daily_morning(self):
        from agents.cognition.daily_cycle import morning_plan
        locations = ", ".join(self.world.get_all_location_ids())
        for agent in list(self.agents.values()):
            try:
                await morning_plan(agent, self.time_manager.day, self.tick, locations)
            except Exception as e:
                logger.error("Morning plan error for %s: %s", agent.name, e)
        logger.info("Morning planning complete for day %s", self.time_manager.day)

    async def _run_daily_evening(self):
        from agents.cognition.daily_cycle import evening_reflection
        for agent in list(self.agents.values()):
            try:
                await evening_reflection(agent, self.time_manager.day, self.tick)
            except Exception as e:
                logger.error("Evening reflection error for %s: %s", agent.name, e)
        logger.info("Evening reflection complete for day %s", self.time_manager.day)

    async def _generate_day_recap(self, day: int):
        if self.day_recaps and self.day_recaps[-1].get("day") == day:
            return
        top_events = []
        for event in self.story_highlights[-5:]:
            if event.get("text"):
                top_events.append(event["text"])
        if not top_events:
            top_events = [f"The settlers kept exploring on day {day}."]
        self.day_recaps.append({"day": day, "summary": " ".join(top_events[:3]), "tick": self.tick})
        self.day_recaps = self.day_recaps[-30:]

    def _serialize_world_objects(self) -> list[dict]:
        return [obj.to_dict() for obj in self.world.world_objects.values()]

    def _serialize_innovations(self) -> list[dict]:
        return list(self.world.innovation_registry[-100:])

    def _serialize_patterns(self) -> list[dict]:
        patterns = getattr(self.world.constitution, "detected_patterns", [])
        return [
            {
                "type": pattern.get("category", "social"),
                "name": pattern.get("name", pattern.get("text", "Pattern")),
                "description": pattern.get("description", ""),
                "emerged_on": pattern.get("emerged_on", 0),
            }
            for pattern in patterns[-100:]
        ]

    def _serialize_timeline_events(self) -> list[dict]:
        return [
            {
                "tick": entry.get("tick", 0),
                "day": entry.get("day", self.time_manager.day),
                "type": entry.get("type", "world_event"),
                "title": entry.get("title", entry.get("type", "World Event").replace("_", " ").title()),
                "description": entry.get("description", ""),
                "agents_involved": entry.get("agents_involved", []),
            }
            for entry in self.world.constitution.change_history[-200:]
        ]

    async def _broadcast_message(self, message_type: str, data: dict):
        if not self._broadcast:
            return
        await self._broadcast({"type": message_type, "data": data})

    def _record_timeline_event(self, event_type: str, title: str, description: str, agents_involved: list[str] | None = None):
        self.world.constitution.change_history.append({
            "tick": self.tick,
            "day": self.time_manager.day,
            "type": event_type,
            "title": title,
            "description": description,
            "agents_involved": agents_involved or [],
        })
        self.world.constitution.change_history = self.world.constitution.change_history[-200:]

    def _make_action_result_event(self, agent: Agent, action_desc: str, result) -> dict:
        outcome_desc = getattr(result.outcome, "description", "") or result.evaluation.why_not or "No visible outcome"
        objects_created = []
        if getattr(result.success, "__bool__", lambda: bool(result.success))():
            objects_created = [obj.name for obj in getattr(result.outcome, "objects_created", [])]
        return {
            "agent_name": agent.name,
            "action_description": action_desc,
            "success": result.success,
            "outcome_description": outcome_desc,
            "objects_created": objects_created,
            "tick": self.tick,
        }

    def _record_innovation_from_result(self, agent: Agent, action_desc: str, result) -> dict | None:
        if not result.success:
            return None
        objects_created = getattr(result.outcome, "objects_created", [])
        if not objects_created and not result.evaluation.unlocks:
            return None

        primary_name = objects_created[0].name if objects_created else action_desc[:80]
        key = f"{primary_name.lower()}::{result.intent.description[:80].lower()}"
        existing = next((entry for entry in self.world.innovation_registry if entry.get("key") == key), None)
        if existing:
            if agent.name != existing.get("inventor") and agent.name not in existing.get("adopters", []):
                existing.setdefault("adopters", []).append(agent.name)
                existing["adoption_rate"] = round(len(existing["adopters"]) / max(len(self.agents), 1), 3)
            return existing

        innovation = {
            "id": f"innovation_{len(self.world.innovation_registry) + 1}",
            "key": key,
            "name": primary_name,
            "description": getattr(result.outcome, "description", action_desc),
            "inventor": agent.name,
            "invented_on": self.tick,
            "adoption_rate": 0.0,
            "adopters": [],
            "parent_id": None,
        }
        self.world.innovation_registry.append(innovation)
        self.world.innovation_registry = self.world.innovation_registry[-100:]
        return innovation

    async def _execute_open_ended_action(self, agent: Agent, action_desc: str):
        from systems.action_interpreter import ActionInterpreter
        from systems.consequence_engine import consequence_engine
        from systems.pattern_detector import pattern_detector

        interpreter = ActionInterpreter()
        interpreter._agents = self.agents
        before_objects = {
            obj_id: obj.to_dict()
            for obj_id, obj in self.world.world_objects.items()
        }

        result = await interpreter.evaluate_action(agent, action_desc, self.world)
        result.tick_completed = self.tick

        if result.evaluation.feasible:
            consequence_engine.apply(
                result,
                agent,
                self.world,
                self.agents,
                tick=self.tick,
                day=self.time_manager.day,
            )

        after_ids = set(self.world.world_objects.keys())
        before_ids = set(before_objects.keys())
        created = [self.world.world_objects[obj_id].to_dict() for obj_id in sorted(after_ids - before_ids)]
        updated = [
            self.world.world_objects[obj_id].to_dict()
            for obj_id in sorted(after_ids & before_ids)
            if self.world.world_objects[obj_id].to_dict() != before_objects[obj_id]
        ]

        outcome = result.outcome
        pattern_type = getattr(outcome, "skill_practiced", "") or (
            getattr(outcome, "objects_created", [None])[0].category
            if getattr(outcome, "objects_created", None)
            else "deliberate_action"
        )
        pattern_detector.record_action(agent.name, {
            "type": pattern_type,
            "location": agent.current_location,
            "description": result.intent.description,
        }, self.tick)

        action_event = self._make_action_result_event(agent, action_desc, result)
        timeline_title = "Action Succeeded" if result.success else "Action Failed"
        self._record_timeline_event(
            "action_result",
            timeline_title,
            f"{agent.name}: {action_event['outcome_description']}",
            [agent.name],
        )
        innovation = self._record_innovation_from_result(agent, action_desc, result)
        if innovation and innovation.get("inventor") == agent.name and not innovation.get("adopters"):
            self._record_timeline_event(
                "innovation",
                "Innovation",
                f"{agent.name} introduced {innovation['name']}.",
                [agent.name],
            )
        self._world_state_dirty = True

        if created or updated:
            await self._broadcast_message("world_object_delta", {
                "created": created,
                "updated": updated,
                "destroyed": [],
            })
        await self._broadcast_message("action_result", action_event)
        if innovation:
            await self._broadcast_message("innovation_event", innovation)
        await self._broadcast_message("timeline_event", self._serialize_timeline_events()[-1])

    async def _process_novelty_decisions(self):
        from agents.cognition.decision import decide

        world_state = {
            "agents": self.agents,
            "hour": self.time_manager.hour,
            "time_of_day": self.time_manager.time_of_day,
        }

        for agent in list(self.agents.values()):
            try:
                action_desc = await decide(agent, world_state, self.tick)
                if not action_desc:
                    continue

                await self._execute_open_ended_action(agent, action_desc)
            except Exception as e:
                logger.error("Novelty decision error for %s: %s", agent.name, e)

    def get_world_state(self) -> dict:
        return {
            "tick": self.tick,
            "time": self.time_manager.to_dict(),
            "agents": [a.to_dict() for a in self.agents.values()],
            "weather": self.time_manager.weather,
            "speed": self.speed,
            "buildings": self.world.get_buildings_list(),
            "tileGrid": self.world.get_tile_grid(),
            "worldSummary": self.world.get_world_summary(),
            "worldObjects": self._serialize_world_objects(),
            "innovations": self._serialize_innovations(),
            "patterns": self._serialize_patterns(),
            "timelineEvents": self._serialize_timeline_events(),
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
            "constitution": self.world.constitution.to_dict(),
            "storyHighlights": self.story_highlights[-50:],
            "dayRecaps": self.day_recaps[-30:],
            "resources": self.world.resources,
            "activeProposals": self.world.active_proposals[-30:],
            "meetings": self.world.meetings[-30:],
            "coalitions": self.world.coalitions[-20:],
            "activeNorms": self.world.constitution.social_norms[-20:],
            "normViolations": self.world.norm_violations[-40:],
            "institutions": self.world.constitution.institutions[-20:],
            "projects": self.world.projects[-20:],
            "patterns": self._serialize_patterns(),
            "innovations": self._serialize_innovations(),
            "timelineEvents": self._serialize_timeline_events(),
            "worldObjects": self._serialize_world_objects(),
            "worldSummary": self.world.get_world_summary(),
            "debugEvents": self.debug_events[-30:],
            "townStats": {
                "population": len(self.agents),
                "avgMood": round(sum((a.emotional_state.valence + 1) / 2 for a in self.agents.values()) / max(len(self.agents), 1), 2),
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
            context,
            temperature=0.9,
            max_tokens=300,
        )
        return result or "I'm still finding my way..."

    def handle_god_command(self, command: str, params: dict):
        logger.info("God command: %s params=%s", command, params)
        if command == "whisper":
            agent = self.agents.get(params.get("agent_id"))
            thought = params.get("thought", "")
            if agent and thought:
                agent.inner_thought = thought
                agent.working_memory.push(thought)
                agent.episodic_memory.add_simple(f"A strange thought came to me: {thought}", self.tick, self.time_manager.day, self.time_manager.time_of_day, agent.current_location, category="reflection", intensity=0.6, emotion="uneasy")
                self._record_debug_event("whisper", f"Whispered to {agent.name}: {thought}")
        elif command == "world_edit" and params.get("action") == "build":
            col = params.get("col")
            row = params.get("row")
            if params.get("auto_place"):
                spot = self.world.find_empty_space(params.get("width", 2), params.get("height", 2))
                if spot:
                    col, row = spot
            if col is not None and row is not None:
                bid = self.world.build_structure(col, row, params.get("width", 2), params.get("height", 2), params.get("label", "New Structure"), builder="god_mode", purpose=params.get("structure_type", "debug"))
                if bid:
                    self._world_state_dirty = True
                    self._record_debug_event("world_edit", f"Built {params.get('label', 'New Structure')} via God Mode")
        elif command == "inject_event":
            event_type = params.get("event_type", "event")
            description = params.get("params", {}).get("secret") or params.get("params", {}).get("item") or event_type.replace("_", " ")
            self._record_debug_event(event_type, str(description))
            self._add_story_highlight("crisis", f"God Mode triggered: {event_type.replace('_', ' ')}", None, None)
