# Agentica — Polis V2 Emergent Settlement Simulator

A browser-based AI settlement simulator where 15 LLM-powered agents wake up in untouched wilderness, discover resources, talk, make plans, and slowly build a town together.

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env

# 2. Start services
docker compose up

# 3. Open the app
open http://localhost:5173
```

Docker rebuilds keep simulation state. The backend stores its SQLite save in the named Docker volume `backend-data` at `/app/data/agentica.db`, so `docker compose up --build` will preserve agents, memories, built structures, and world state unless you explicitly remove the volume.

## What It Does

- Starts from a zero-building wilderness map with a central clearing
- Simulates 15 autonomous agents with drives, emotions, memories, beliefs, and emerging roles
- Lets agents discover resource zones, gather food and wood, and build structures over time
- Runs live conversations that can create follow-up commitments and future actions
- Persists world state, structures, memories, and agent cognition to SQLite
- Exposes inspector, dashboard, story highlights, and debug-oriented God Mode tools in the UI

## Tech Stack

- Frontend: React + TypeScript + PixiJS + Zustand + TailwindCSS
- Backend: FastAPI + WebSocket + SQLite
- LLM: OpenAI-compatible chat completion endpoint

## Configuration

Important environment variables:

| Variable | Description | Default |
|---|---|---|
| `LLM_API_KEY` | API key for the configured LLM endpoint | required for conversations/thoughts |
| `LLM_BASE_URL` | OpenAI-compatible base URL | `https://api.openai.com/v1` |
| `LLM_MODEL_NAME` | Chat model used for thoughts and conversations | `gpt-4o-mini` |
| `LLM_MAX_CONCURRENT_REQUESTS` | Max concurrent LLM calls | `15` |
| `BACKEND_PORT` | FastAPI port | `8000` |
| `DB_PATH` | SQLite save path | `data/agentica.db` |

Under Docker Compose, `DB_PATH` is explicitly set to `/app/data/agentica.db` so persistence survives backend container rebuilds.

Simulation timing is currently controlled in backend config for the active `v2` runtime.

## Runtime Notes

- The active product runtime is `SimulationEngineV2`
- Fresh compatible saves start from wilderness with no buildings
- Older pre-refactor `v2` saves are intentionally ignored
- God Mode is available as a debug/observer tool, not as the core governing model of the simulation

## License

MIT
