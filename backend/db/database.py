"""SQLite persistence — save/load world state."""

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
            CREATE TABLE IF NOT EXISTS world_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                tick INTEGER,
                day INTEGER,
                season TEXT,
                weather TEXT,
                economy_json TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                world_json TEXT DEFAULT '{}'
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS agent_state (
                agent_id TEXT PRIMARY KEY,
                name TEXT,
                position_json TEXT,
                state_json TEXT,
                memories_json TEXT,
                relationships_json TEXT,
                inner_thought TEXT,
                daily_plan TEXT,
                emotion TEXT,
                current_location TEXT,
                current_action TEXT,
                transactions_json TEXT DEFAULT '[]'
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tick INTEGER,
                buyer TEXT,
                seller TEXT,
                item TEXT,
                price REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Migrate world_state table
        try:
            await db.execute("SELECT world_json FROM world_state LIMIT 1")
        except Exception:
            await db.execute("ALTER TABLE world_state ADD COLUMN world_json TEXT DEFAULT '{}'")

        # Migrations: add columns if missing
        for col, default in [
            ("transactions_json", "'[]'"),
            ("secrets_json", "'[]'"),
            ("goals_json", "'[]'"),
            ("opinions_json", "'{}'"),
        ]:
            try:
                await db.execute(f"SELECT {col} FROM agent_state LIMIT 1")
            except Exception:
                await db.execute(f"ALTER TABLE agent_state ADD COLUMN {col} TEXT DEFAULT {default}")

        await db.commit()
    logger.info(f"Database initialized at {DB_PATH}")


async def save_world_state(engine) -> None:
    """Save full simulation state to SQLite."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            economy_json = json.dumps(engine.economy.to_dict()) if hasattr(engine, "economy") else "{}"
            world_json = json.dumps(engine.world.to_save_dict()) if hasattr(engine, "world") else "{}"
            await db.execute("""
                INSERT OR REPLACE INTO world_state (id, tick, day, season, weather, economy_json, world_json)
                VALUES (1, ?, ?, ?, ?, ?, ?)
            """, (
                engine.tick,
                engine.time_manager.day,
                engine.time_manager.season,
                engine.time_manager.weather,
                economy_json,
                world_json,
            ))

            for agent in engine.agents.values():
                await db.execute("""
                    INSERT OR REPLACE INTO agent_state
                    (agent_id, name, position_json, state_json, memories_json,
                     relationships_json, inner_thought, daily_plan, emotion,
                     current_location, current_action, transactions_json,
                     secrets_json, goals_json, opinions_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    agent.id,
                    agent.name,
                    json.dumps(list(agent.position)),
                    json.dumps({
                        "energy": agent.state.energy,
                        "hunger": agent.state.hunger,
                        "mood": agent.state.mood,
                        "wealth": agent.state.wealth,
                    }),
                    json.dumps(agent.memory.to_list(200)),
                    json.dumps(agent.relationships),
                    agent.inner_thought,
                    agent.daily_plan,
                    agent.emotion,
                    agent.current_location,
                    agent.current_action.value,
                    json.dumps(agent.transactions[-50:]),
                    json.dumps(agent.secrets),
                    json.dumps(agent.active_goals),
                    json.dumps(agent.opinions),
                ))

            await db.commit()
        logger.info(f"Saved world state at tick {engine.tick}")
    except Exception as e:
        logger.error(f"Failed to save world state: {e}")


async def load_world_state() -> dict | None:
    """Load saved world state + all agent states. Returns None if no save exists."""
    if not os.path.exists(DB_PATH):
        return None

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # Load world state
            cursor = await db.execute("SELECT * FROM world_state WHERE id = 1")
            row = await cursor.fetchone()
            if not row:
                return None

            result = {
                "tick": row[1],
                "day": row[2],
                "season": row[3],
                "weather": row[4],
                "economy": json.loads(row[5]) if row[5] else {},
                "agents": {},
            }
            # world_json may be at different index depending on migration
            for i in range(6, len(row)):
                val = row[i]
                if isinstance(val, str) and val.startswith('{') and len(val) > 5:
                    try:
                        parsed = json.loads(val)
                        if "tiles" in parsed or "buildings" in parsed:
                            result["world"] = parsed
                            break
                    except json.JSONDecodeError:
                        pass

            # Load all agent states
            cursor = await db.execute("SELECT * FROM agent_state")
            rows = await cursor.fetchall()
            for arow in rows:
                agent_id = arow[0]
                result["agents"][agent_id] = {
                    "agent_id": agent_id,
                    "name": arow[1],
                    "position": json.loads(arow[2]) if arow[2] else None,
                    "state": json.loads(arow[3]) if arow[3] else None,
                    "memories": json.loads(arow[4]) if arow[4] else [],
                    "relationships": json.loads(arow[5]) if arow[5] else {},
                    "inner_thought": arow[6] or "",
                    "daily_plan": arow[7] or "",
                    "emotion": arow[8] or "neutral",
                    "current_location": arow[9] or "",
                    "current_action": arow[10] or "idle",
                    "transactions": json.loads(arow[11]) if len(arow) > 11 and arow[11] else [],
                    "secrets": json.loads(arow[12]) if len(arow) > 12 and arow[12] else [],
                    "active_goals": json.loads(arow[13]) if len(arow) > 13 and arow[13] else [],
                    "opinions": json.loads(arow[14]) if len(arow) > 14 and arow[14] else {},
                }

            logger.info(f"Loaded save: tick {result['tick']}, day {result['day']}, {len(result['agents'])} agents")
            return result
    except Exception as e:
        logger.error(f"Failed to load world state: {e}")
        return None
