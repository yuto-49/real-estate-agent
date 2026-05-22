"""Public runtime configuration and SPA serving tests."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from config import settings
from main import app


@pytest.mark.asyncio
async def test_public_runtime_config_exposes_only_browser_safe_fields(monkeypatch):
    monkeypatch.setattr(settings, "environment", "staging")
    monkeypatch.setattr(settings, "public_api_base_url", "/api")
    monkeypatch.setattr(settings, "public_ws_base_url", "/ws")
    monkeypatch.setattr(settings, "vite_supabase_url", "https://example.supabase.co")
    monkeypatch.setattr(settings, "vite_supabase_publishable_key", "public-anon-key")
    monkeypatch.setattr(settings, "public_map_style_url", "https://maps.example/style.json")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/config/public")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "environment": "staging",
        "api_base_url": "/api",
        "ws_base_url": "/ws",
        "supabase_url": "https://example.supabase.co",
        "supabase_publishable_key": "public-anon-key",
        "map_style_url": "https://maps.example/style.json",
    }
    assert "tomtom_api_key" not in body


@pytest.mark.asyncio
async def test_frontend_deep_link_serves_spa_html():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/simulation/visualize/example-property")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert '<div id="root">' in response.text
