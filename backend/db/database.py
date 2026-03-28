"""SQLite persistence — saves/loads full cognitive state."""

import json
import logging
import os

import aiosqlite

from config import settings

logger = logging.getLogger("agentica.db")

DB_PATH = settings.db_path


async def init_db():
    """Create tables if they don't exist."""
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS world_state_v2 (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                tick INTEGER,
                day INTEGER,
                tick_in_day INTEGER,
                speed INTEGER DEFAULT 1,
                world_json TEXT DEFAULT '{}',
                story_highlights_json TEXT DEFAULT '[]',
                day_recaps_json TEXT DEFAULT '[]',
                debug_events_json TEXT DEFAULT '[]',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS agent_state_v2 (
                agent_id TEXT PRIMARY KEY,
                name TEXT,
                position_json TEXT,
                current_location TEXT,
                current_action TEXT,
                inner_thought TEXT,
                daily_plan TEXT,
                daily_schedule_json TEXT DEFAULT '[]',
                current_plan_step_json TEXT DEFAULT 'null',
                long_term_goals_json TEXT DEFAULT '[]',
                active_intentions_json TEXT DEFAULT '[]',
                current_plan_json TEXT DEFAULT 'null',
                fallback_plan_json TEXT DEFAULT 'null',
                blocked_reasons_json TEXT DEFAULT '[]',
                decision_rationale_json TEXT DEFAULT '{}',
                life_events_json TEXT DEFAULT '[]',
                reciprocity_ledger_json TEXT DEFAULT '{}',
                proposal_stances_json TEXT DEFAULT '{}',
                project_roles_json TEXT DEFAULT '[]',
                current_institution_roles_json TEXT DEFAULT '[]',
                active_conflicts_json TEXT DEFAULT '[]',
                plan_mode TEXT DEFAULT 'improvising',
                plan_deviation_reason TEXT DEFAULT '',
                self_concept TEXT,
                emotion TEXT,
                emotions_json TEXT DEFAULT '{}',
                drives_json TEXT DEFAULT '{}',
                episodic_memory_json TEXT DEFAULT '[]',
                working_memory_json TEXT DEFAULT '{}',
                beliefs_json TEXT DEFAULT '[]',
                mental_models_json TEXT DEFAULT '{}',
                skills_json TEXT DEFAULT '{}',
                world_model_json TEXT DEFAULT '{}',
                relationships_json TEXT DEFAULT '{}',
                active_goals_json TEXT DEFAULT '[]',
                social_commitments_json TEXT DEFAULT '[]',
                inventory_json TEXT DEFAULT '[]',
                secrets_json TEXT DEFAULT '[]',
                opinions_json TEXT DEFAULT '{}'
            )
        """)
        await _ensure_columns(db, "world_state_v2", {"debug_events_json": "TEXT DEFAULT '[]'"})
        await _ensure_columns(db, "agent_state_v2", {
            "social_commitments_json": "TEXT DEFAULT '[]'",
            "daily_schedule_json": "TEXT DEFAULT '[]'",
            "current_plan_step_json": "TEXT DEFAULT 'null'",
            "long_term_goals_json": "TEXT DEFAULT '[]'",
            "active_intentions_json": "TEXT DEFAULT '[]'",
            "current_plan_json": "TEXT DEFAULT 'null'",
            "fallback_plan_json": "TEXT DEFAULT 'null'",
            "blocked_reasons_json": "TEXT DEFAULT '[]'",
            "decision_rationale_json": "TEXT DEFAULT '{}'",
            "life_events_json": "TEXT DEFAULT '[]'",
            "reciprocity_ledger_json": "TEXT DEFAULT '{}'",
            "proposal_stances_json": "TEXT DEFAULT '{}'",
            "project_roles_json": "TEXT DEFAULT '[]'",
            "current_institution_roles_json": "TEXT DEFAULT '[]'",
            "active_conflicts_json": "TEXT DEFAULT '[]'",
            "plan_mode": "TEXT DEFAULT 'improvising'",
            "plan_deviation_reason": "TEXT DEFAULT ''",
        })
        await db.commit()
    logger.info(f"Database initialized at {DB_PATH}")


async def _ensure_columns(db, table: str, columns: dict[str, str]):
    cursor = await db.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in await cursor.fetchall()}
    for name, definition in columns.items():
        if name not in existing:
            await db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


async def save_world_state(engine) -> None:
    """Save full simulation state."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            world_json = json.dumps(engine.world.to_save_dict())
            await db.execute("""
                INSERT OR REPLACE INTO world_state_v2
                (id, tick, day, tick_in_day, speed, world_json, story_highlights_json, day_recaps_json, debug_events_json)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                engine.tick,
                engine.time_manager.day,
                engine.time_manager.tick_in_day,
                engine.speed,
                world_json,
                json.dumps(engine.story_highlights[-50:]),
                json.dumps(engine.day_recaps[-30:]),
                json.dumps(getattr(engine, "debug_events", [])[-50:]),
            ))

            for agent in engine.agents.values():
                await db.execute("""
                    INSERT OR REPLACE INTO agent_state_v2
                    (agent_id, name, position_json, current_location, current_action,
                     inner_thought, daily_plan, daily_schedule_json, current_plan_step_json, long_term_goals_json, active_intentions_json,
                     current_plan_json, fallback_plan_json, blocked_reasons_json, decision_rationale_json, life_events_json,
                     reciprocity_ledger_json, proposal_stances_json, project_roles_json, current_institution_roles_json, active_conflicts_json,
                     plan_mode, plan_deviation_reason, self_concept, emotion,
                     emotions_json, drives_json, episodic_memory_json, working_memory_json,
                     beliefs_json, mental_models_json, skills_json, world_model_json,
                     relationships_json, active_goals_json, social_commitments_json, inventory_json, secrets_json, opinions_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    agent.id,
                    agent.name,
                    json.dumps(list(agent.position)),
                    agent.current_location,
                    agent.current_action.value,
                    agent.inner_thought,
                    agent.daily_plan,
                    json.dumps(agent.daily_schedule),
                    json.dumps(agent.current_plan_step),
                    json.dumps(agent.long_term_goals),
                    json.dumps(agent.active_intentions),
                    json.dumps(agent.current_plan),
                    json.dumps(agent.fallback_plan),
                    json.dumps(agent.blocked_reasons),
                    json.dumps(agent.decision_rationale),
                    json.dumps(agent.life_events),
                    json.dumps(agent.reciprocity_ledger),
                    json.dumps(agent.proposal_stances),
                    json.dumps(agent.project_roles),
                    json.dumps(agent.current_institution_roles),
                    json.dumps(agent.active_conflicts),
                    agent.plan_mode,
                    agent.plan_deviation_reason,
                    agent.self_concept,
                    agent.emotion,
                    json.dumps(agent.emotional_state.to_dict()),
                    json.dumps(agent.drives.to_dict()),
                    json.dumps(agent.episodic_memory.to_list(200)),
                    json.dumps(agent.working_memory.to_dict()),
                    json.dumps(agent.belief_system.to_list()),
                    json.dumps(agent.mental_models.to_dict()),
                    json.dumps(agent.skill_memory.to_dict()),
                    json.dumps(agent.world_model.to_dict()),
                    json.dumps(agent.relationships),
                    json.dumps(agent.active_goals),
                    json.dumps(agent.social_commitments),
                    json.dumps(agent.inventory),
                    json.dumps(agent.secrets),
                    json.dumps(agent.opinions),
                ))

            await db.commit()
        logger.info(f"Saved state at tick {engine.tick}, day {engine.time_manager.day}")
    except Exception as e:
        logger.error(f"Failed to save state: {e}", exc_info=True)


async def load_world_state() -> dict | None:
    """Load saved state. Returns None if no save exists."""
    if not os.path.exists(DB_PATH):
        return None

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # Check if table exists
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='world_state_v2'"
            )
            if not await cursor.fetchone():
                return None

            cursor = await db.execute("SELECT * FROM world_state_v2 WHERE id = 1")
            cols = [desc[0] for desc in cursor.description]
            row = await cursor.fetchone()
            if not row:
                return None
            data = dict(zip(cols, row))

            result = {
                "tick": data.get("tick", 0),
                "day": data.get("day", 0),
                "tick_in_day": data.get("tick_in_day", 0),
                "speed": data.get("speed", 1) or 1,
                "world": json.loads(data["world_json"]) if data.get("world_json") else {},
                "story_highlights": json.loads(data["story_highlights_json"]) if data.get("story_highlights_json") else [],
                "day_recaps": json.loads(data["day_recaps_json"]) if data.get("day_recaps_json") else [],
                "debug_events": json.loads(data["debug_events_json"]) if data.get("debug_events_json") else [],
                "agents": {},
            }

            cursor = await db.execute("SELECT * FROM agent_state_v2")
            cols = [desc[0] for desc in cursor.description]
            rows = await cursor.fetchall()
            for arow in rows:
                d = dict(zip(cols, arow))
                agent_id = d["agent_id"]
                result["agents"][agent_id] = {
                    "agent_id": agent_id,
                    "name": d["name"],
                    "position": json.loads(d["position_json"]) if d["position_json"] else None,
                    "current_location": d["current_location"] or "clearing",
                    "current_action": d["current_action"] or "idle",
                    "inner_thought": d["inner_thought"] or "",
                    "daily_plan": d["daily_plan"] or "",
                    "daily_schedule": json.loads(d["daily_schedule_json"]) if d.get("daily_schedule_json") else [],
                    "current_plan_step": json.loads(d["current_plan_step_json"]) if d.get("current_plan_step_json") else None,
                    "long_term_goals": json.loads(d["long_term_goals_json"]) if d.get("long_term_goals_json") else [],
                    "active_intentions": json.loads(d["active_intentions_json"]) if d.get("active_intentions_json") else [],
                    "current_plan": json.loads(d["current_plan_json"]) if d.get("current_plan_json") else None,
                    "fallback_plan": json.loads(d["fallback_plan_json"]) if d.get("fallback_plan_json") else None,
                    "blocked_reasons": json.loads(d["blocked_reasons_json"]) if d.get("blocked_reasons_json") else [],
                    "decision_rationale": json.loads(d["decision_rationale_json"]) if d.get("decision_rationale_json") else {},
                    "life_events": json.loads(d["life_events_json"]) if d.get("life_events_json") else [],
                    "reciprocity_ledger": json.loads(d["reciprocity_ledger_json"]) if d.get("reciprocity_ledger_json") else {},
                    "proposal_stances": json.loads(d["proposal_stances_json"]) if d.get("proposal_stances_json") else {},
                    "project_roles": json.loads(d["project_roles_json"]) if d.get("project_roles_json") else [],
                    "current_institution_roles": json.loads(d["current_institution_roles_json"]) if d.get("current_institution_roles_json") else [],
                    "active_conflicts": json.loads(d["active_conflicts_json"]) if d.get("active_conflicts_json") else [],
                    "plan_mode": d.get("plan_mode") or "improvising",
                    "plan_deviation_reason": d.get("plan_deviation_reason") or "",
                    "self_concept": d["self_concept"],
                    "emotion": d["emotion"] or "neutral",
                    "emotions": json.loads(d["emotions_json"]) if d["emotions_json"] else {},
                    "drives": json.loads(d["drives_json"]) if d["drives_json"] else {},
                    "episodic_memory": json.loads(d["episodic_memory_json"]) if d["episodic_memory_json"] else [],
                    "working_memory": json.loads(d["working_memory_json"]) if d["working_memory_json"] else {},
                    "beliefs": json.loads(d["beliefs_json"]) if d["beliefs_json"] else [],
                    "mental_models": json.loads(d["mental_models_json"]) if d["mental_models_json"] else {},
                    "skills": json.loads(d["skills_json"]) if d["skills_json"] else {},
                    "world_model": json.loads(d["world_model_json"]) if d["world_model_json"] else {},
                    "relationships": json.loads(d["relationships_json"]) if d["relationships_json"] else {},
                    "active_goals": json.loads(d["active_goals_json"]) if d["active_goals_json"] else [],
                    "social_commitments": json.loads(d["social_commitments_json"]) if d.get("social_commitments_json") else [],
                    "inventory": json.loads(d["inventory_json"]) if d["inventory_json"] else [],
                    "secrets": json.loads(d["secrets_json"]) if d["secrets_json"] else [],
                    "opinions": json.loads(d["opinions_json"]) if d["opinions_json"] else {},
                }

            world = result.get("world", {})
            if world.get("version") != 2:
                logger.info("Ignoring pre-v2.1 save because the world version is incompatible")
                return None

            logger.info(f"Loaded save: tick {result['tick']}, day {result['day']}, {len(result['agents'])} agents")
            return result
    except Exception as e:
        logger.error(f"Failed to load state: {e}", exc_info=True)
        return None
