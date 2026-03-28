import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from simulation.engine_v2 import SimulationEngineV2 as SimulationEngine

logger = logging.getLogger("agentica")
logging.basicConfig(level=logging.INFO)


class ConnectionManager:
    def __init__(self):
        self.connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)
        logger.info(f"Client connected. Total: {len(self.connections)}")

    def disconnect(self, ws: WebSocket):
        self.connections.remove(ws)
        logger.info(f"Client disconnected. Total: {len(self.connections)}")

    async def broadcast(self, message: dict):
        data = json.dumps(message)
        disconnected = []
        for ws in self.connections:
            try:
                await ws.send_text(data)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.connections.remove(ws)


manager = ConnectionManager()
engine = SimulationEngine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine.set_broadcast(manager.broadcast)
    asyncio.create_task(engine.run())
    logger.info("Simulation engine started")
    yield
    engine.stop()
    # Give the save task a moment to complete
    await asyncio.sleep(0.5)
    logger.info("Simulation engine stopped")


app = FastAPI(title="Agentica", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "tick": engine.tick}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        # Send full world state on connect
        state = engine.get_world_state()
        await ws.send_text(json.dumps({"type": "world_state", "data": state}))

        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type")

            if msg_type == "set_speed":
                engine.set_speed(msg.get("speed", 1))
            elif msg_type == "inspect_agent":
                agent_id = msg.get("agentId")
                detail = engine.get_agent_detail(agent_id)
                await ws.send_text(json.dumps({"type": "agent_detail", "data": detail}))
            elif msg_type == "request_dashboard":
                data = engine.get_dashboard_data()
                await ws.send_text(json.dumps({"type": "dashboard_data", "data": data}))
            elif msg_type == "request_autobiography":
                agent_id = msg.get("agentId")
                text = await engine.generate_autobiography(agent_id)
                await ws.send_text(json.dumps({"type": "autobiography", "data": {"agentId": agent_id, "text": text}}))
            elif msg_type == "god_command":
                engine.handle_god_command(msg.get("command"), msg.get("params", {}))
            else:
                logger.warning(f"Unknown message type: {msg_type}")

    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(ws)
