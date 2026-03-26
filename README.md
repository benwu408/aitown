# Agentica — AI Civilization Simulator

A browser-based AI civilization simulator with 15 LLM-powered autonomous agents who live, work, socialize, trade, and make decisions in a persistent isometric micro-town.

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env with your LLM API key and endpoint

# 2. Run with Docker Compose
docker compose up

# 3. Open browser
open http://localhost:5173
```

## Tech Stack

- **Frontend:** React + TypeScript + PixiJS (2D isometric) + Zustand + TailwindCSS
- **Backend:** FastAPI (Python) + WebSocket + SQLite
- **LLM:** Any OpenAI-compatible API endpoint

## Features

- **15 autonomous agents** with unique personalities, jobs, goals, and daily schedules
- **2D isometric town** with 12+ buildings, paths, trees, and decorations
- **LLM-powered conversations** — agents talk when they meet at social locations
- **Cognitive architecture** — memory, reflection, daily planning
- **Economic system** — production, trade, supply/demand pricing
- **Inspector panel** — click any agent to see thoughts, memories, relationships
- **Live feed** — scrolling event log of everything happening in town
- **God mode** — inject events (drought, festival, illness), whisper thoughts to agents
- **Day/night cycle** with weather effects
- **Auto-save** to SQLite every ~100 seconds

## Configuration

All settings in `.env`:

| Variable | Description | Default |
|---|---|---|
| `LLM_API_KEY` | API key for LLM endpoint | required |
| `LLM_BASE_URL` | OpenAI-compatible base URL | `https://api.openai.com/v1` |
| `LLM_MODEL_NAME` | Model to use | `gpt-4o-mini` |
| `TICK_DURATION_MS` | Real-time ms per tick | `2000` |
| `TICKS_PER_DAY` | Simulation ticks per day | `144` |

## Architecture

The frontend is a **dumb renderer** — it receives action events via WebSocket and maps them to sprites/animations. The backend owns all simulation logic, agent cognition, and economics. LLM calls are async and batched (max 5/tick). Rule-based behavior keeps agents moving even without LLM responses.

## License

MIT
