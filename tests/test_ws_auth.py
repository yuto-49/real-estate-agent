"""WebSocket auth guard tests."""

from __future__ import annotations

from fastapi import HTTPException
import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from main import app


def test_ws_rejects_missing_access_token():
    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws/negotiation/test-negotiation-id"):
            pass
    assert exc.value.code == 4401


def test_ws_rejects_invalid_access_token(monkeypatch):
    async def _reject_token(_websocket):
        raise HTTPException(status_code=401, detail="Invalid access token")

    monkeypatch.setattr("api.ws.get_auth_user_from_ws_token", _reject_token)
    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws/negotiation/test-negotiation-id?access_token=invalid"):
            pass
    assert exc.value.code == 4401
