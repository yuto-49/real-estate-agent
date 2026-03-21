"""WebSocket endpoint with typed event dispatch and connection management."""

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.ws_events import (
    AgentResponseEvent,
    ConnectionAckEvent,
    SystemErrorEvent,
    WSEvent,
)
from agent.orchestrator import AgentOrchestrator
from db.database import async_session
from services.maps import MapsService
from services.market_data import MarketDataService
from services.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


class ConnectionManager:
    """Manages WebSocket connections per negotiation."""

    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, negotiation_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        if negotiation_id not in self._connections:
            self._connections[negotiation_id] = []
        self._connections[negotiation_id].append(websocket)

    def disconnect(self, negotiation_id: str, websocket: WebSocket) -> None:
        if negotiation_id in self._connections:
            self._connections[negotiation_id] = [
                ws for ws in self._connections[negotiation_id] if ws is not websocket
            ]
            if not self._connections[negotiation_id]:
                del self._connections[negotiation_id]

    async def send_event(self, negotiation_id: str, event: WSEvent) -> None:
        """Send a typed event to all connections for a negotiation."""
        connections = self._connections.get(negotiation_id, [])
        dead = []
        for ws in connections:
            try:
                await ws.send_json(event.model_dump(mode="json"))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(negotiation_id, ws)

    async def broadcast(self, event: WSEvent) -> None:
        """Send an event to all connected clients."""
        for neg_id in list(self._connections.keys()):
            await self.send_event(neg_id, event)

    @property
    def active_connections(self) -> int:
        return sum(len(conns) for conns in self._connections.values())


manager = ConnectionManager()


@router.websocket("/negotiation/{negotiation_id}")
async def negotiation_ws(websocket: WebSocket, negotiation_id: str):
    """WebSocket endpoint for real-time negotiation updates with agent routing."""
    await manager.connect(negotiation_id, websocket)

    # Send connection acknowledgment
    ack = ConnectionAckEvent(
        negotiation_id=negotiation_id,
        current_status="connected",
    )
    await websocket.send_json(ack.model_dump(mode="json"))

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                msg_text = message.get("text", message.get("message", ""))
                user_id = message.get("user_id", "")
                role = message.get("role", "buyer")

                if not msg_text:
                    await websocket.send_json({
                        "type": "echo",
                        "negotiation_id": negotiation_id,
                        "data": message,
                    })
                    continue

                if not user_id:
                    error = SystemErrorEvent(
                        error="Missing user_id",
                        detail="Send {user_id, role, text} to route to an agent",
                    )
                    await websocket.send_json(error.model_dump(mode="json"))
                    continue

                # Route to agent via orchestrator
                async with async_session() as db:
                    maps = MapsService()
                    market_data = MarketDataService()
                    orchestrator = AgentOrchestrator(
                        db=db, maps=maps, market_data=market_data,
                    )
                    result = await orchestrator.route_message(
                        user_id=user_id,
                        role=role,
                        message=msg_text,
                    )

                # Send agent response
                agent_event = AgentResponseEvent(
                    agent_type=role,
                    response=result.get("response", ""),
                    tool_calls=[tc["tool"] for tc in result.get("tool_calls", [])],
                )
                await websocket.send_json(agent_event.model_dump(mode="json"))

                # Also broadcast to all connections on this negotiation
                await manager.send_event(negotiation_id, agent_event)

            except json.JSONDecodeError:
                error = SystemErrorEvent(error="Invalid JSON", detail=data[:100])
                await websocket.send_json(error.model_dump(mode="json"))
    except WebSocketDisconnect:
        manager.disconnect(negotiation_id, websocket)
    except Exception as e:
        logger.error("ws.error", error=str(e), negotiation_id=negotiation_id)
        manager.disconnect(negotiation_id, websocket)
