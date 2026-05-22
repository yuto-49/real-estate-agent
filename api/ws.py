"""WebSocket endpoint with typed event dispatch and connection management."""

import asyncio
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
from services.redis import get_redis
from services.strategy_runner import get_strategy_run

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
                report_id = message.get("report_id")

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
                        report_id=report_id,
                    )

                # Send agent response
                agent_event = AgentResponseEvent(
                    agent_type=role,
                    response=result.get("response", ""),
                    tool_calls=result.get("tool_calls", []),
                )

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


@router.websocket("/strategy/{run_id}")
async def strategy_run_ws(websocket: WebSocket, run_id: str):
    """Live trace stream for a strategy run.

    On connect, replays any step events already on the record (so a client
    that connects mid-run doesn't miss the early events), then subscribes
    to the ``strategy:{run_id}`` Redis channel and forwards new events until
    either the run completes/fails or the client disconnects.

    Falls back to polling-only behavior if Redis is unavailable: we still
    send the replayed steps and any terminal status changes detected via
    the in-memory store.
    """
    await websocket.accept()

    # Replay durable trace first.
    record = await get_strategy_run(run_id)
    if record is None:
        await websocket.send_json(
            {"type": "error", "payload": {"detail": "run_not_found"}}
        )
        await websocket.close()
        return

    for step in record.steps:
        await websocket.send_json(
            {
                "type": step.type,
                "payload": {
                    "label": step.label,
                    "detail": step.detail,
                    "at": step.at.isoformat(),
                },
            }
        )

    if record.status in ("completed", "failed"):
        await websocket.send_json({"type": "stream.closed", "payload": {"status": record.status}})
        await websocket.close()
        return

    # Subscribe to live events.
    channel = f"strategy:{run_id}"
    try:
        redis_client = await get_redis()
    except Exception:
        redis_client = None

    if redis_client is None:
        await websocket.send_json(
            {"type": "stream.degraded", "payload": {"reason": "redis_unavailable"}}
        )
        await _poll_until_done(websocket, run_id)
        return

    pubsub = redis_client.pubsub()
    await pubsub.subscribe(channel)
    try:
        while True:
            message_task = asyncio.create_task(pubsub.get_message(ignore_subscribe_messages=True, timeout=15.0))
            recv_task = asyncio.create_task(websocket.receive_text())
            done, pending = await asyncio.wait(
                {message_task, recv_task}, return_when=asyncio.FIRST_COMPLETED
            )
            for t in pending:
                t.cancel()

            if recv_task in done:
                # Client closed or sent something — we ignore inbound payloads.
                try:
                    recv_task.result()
                except Exception:
                    break
                continue

            message = message_task.result()
            if message is None:
                # Heartbeat: check terminal state via the store.
                current = await get_strategy_run(run_id)
                if current is not None and current.status in ("completed", "failed"):
                    await websocket.send_json(
                        {"type": "stream.closed", "payload": {"status": current.status}}
                    )
                    break
                continue

            data = message.get("data")
            if isinstance(data, bytes):
                data = data.decode()
            try:
                payload = json.loads(data) if isinstance(data, str) else data
            except json.JSONDecodeError:
                continue
            await websocket.send_json(payload)
            if isinstance(payload, dict) and payload.get("type") in (
                "run.completed",
                "run.failed",
            ):
                await websocket.send_json(
                    {"type": "stream.closed", "payload": {"status": payload["type"]}}
                )
                break
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("ws.strategy.error", error=str(e), run_id=run_id)
    finally:
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
        except Exception:
            pass
        try:
            await websocket.close()
        except Exception:
            pass


async def _poll_until_done(websocket: WebSocket, run_id: str) -> None:
    """Fallback when Redis is offline — poll the in-memory store."""
    seen_indices = 0
    try:
        for _ in range(120):  # ~2 minutes of polling at 1s
            record = await get_strategy_run(run_id)
            if record is None:
                break
            for step in record.steps[seen_indices:]:
                await websocket.send_json(
                    {
                        "type": step.type,
                        "payload": {
                            "label": step.label,
                            "detail": step.detail,
                            "at": step.at.isoformat(),
                        },
                    }
                )
            seen_indices = len(record.steps)
            if record.status in ("completed", "failed"):
                await websocket.send_json(
                    {"type": "stream.closed", "payload": {"status": record.status}}
                )
                break
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
