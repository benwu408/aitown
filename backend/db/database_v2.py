"""SQLite persistence for V2 simulation — saves/loads full cognitive state."""

import json
import logging
import os

import aiosqlite

from config import settings

logger = logging.getLogger("agentica.db_v2")

DB_PATH = settings.db_path


async def init_db_v2():
    """Create V2 tables if they don't exist."""
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
                inventory_json TEXT DEFAULT '[]',
                secrets_json TEXT DEFAULT '[]',
                opinions_json TEXT DEFAULT '{}'
            )
        """)
        await db.commit()
    logger.info(f"V2 database initialized at {DB_PATH}")


async def save_world_state_v2(engine) -> None:
    """Save full V2 simulation state."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            world_json = json.dumps(engine.world.to_save_dict())
            await db.execute("""
                INSERT OR REPLACE INTO world_state_v2
                (id, tick, day, tick_in_day, speed, world_json, story_highlights_json, day_recaps_json)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?)
            """, (
                engine.tick,
                engine.time_manager.day,
                engine.time_manager.tick_in_day,
                engine.speed,
                world_json,
                json.dumps(engine.story_highlights[-50:]),
                json.dumps(engine.day_recaps[-30:]),
            ))

            for agent in engine.agents.values():
                await db.execute("""
                    INSERT OR REPLACE INTO agent_state_v2
                    (agent_id, name, position_json, current_location, current_action,
                     inner_thought, daily_plan, self_concept, emotion,
                     emotions_json, drives_json, episodic_memory_json, working_memory_json,
                     beliefs_json, mental_models_json, skills_json, world_model_json,
                     relationships_json, active_goals_json, inventory_json, secrets_json, opinions_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    agent.id,
                    agent.name,
                    json.dumps(list(agent.position)),
                    agent.current_location,
                    agent.current_action.value,
                    agent.inner_thought,
                    agent.daily_plan,
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
                    json.dumps(agent.inventory),
                    json.dumps(agent.secrets),
                    json.dumps(agent.opinions),
                ))

            await db.commit()
        logger.info(f"Saved V2 state at tick {engine.tick}, day {engine.time_manager.day}")
    except Exception as e:
        logger.error(f"Failed to save V2 state: {e}", exc_info=True)


async def load_world_state_v2() -> dict | None:
    """Load saved V2 state. Returns None if no save exists."""
    if not os.path.exists(DB_PATH):
        return None

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # Check if V2 table exists
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='world_state_v2'"
            )
            if not await cursor.fetchone():
                return None

            cursor = await db.execute("SELECT * FROM world_state_v2 WHERE id = 1")
            row = await cursor.fetchone()
            if not row:
                return None

            result = {
                "tick": row[1],
                "day": row[2],
                "tick_in_day": row[3],
                "speed": row[4] or 1,
                "world": json.loads(row[5]) if row[5] else {},
                "story_highlights": json.loads(row[6]) if row[6] else [],
                "day_recaps": json.loads(row[7]) if row[7] else [],
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
                    "inventory": json.loads(d["inventory_json"]) if d["inventory_json"] else [],
                    "secrets": json.loads(d["secrets_json"]) if d["secrets_json"] else [],
                    "opinions": json.loads(d["opinions_json"]) if d["opinions_json"] else {},
                }

            logger.info(f"Loaded V2 save: tick {result['tick']}, day {result['day']}, {len(result['agents'])} agents")
            return result
    except Exception as e:
        logger.error(f"Failed to load V2 state: {e}", exc_info=True)
        return None
