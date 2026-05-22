"""Chat-based portfolio import tests — Phase P3.

The Anthropic client is faked end-to-end so the suite stays offline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db.models import HoldingFinancials, PortfolioHolding, UserProfile


# ── fakes ───────────────────────────────────────────────────────────────


@dataclass
class _FakeBlock:
    type: str
    text: str | None = None
    name: str | None = None
    input: dict[str, Any] | None = None


@dataclass
class _FakeResponse:
    content: list[_FakeBlock]


class _FakeMessages:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> _FakeResponse:
        self.calls.append(kwargs)
        if not self._responses:
            return _FakeResponse(content=[])
        return self._responses.pop(0)


class _FakeAnthropic:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self.messages = _FakeMessages(responses)


def _tool_use_block(holdings: list[dict[str, Any]]) -> _FakeBlock:
    return _FakeBlock(
        type="tool_use",
        name="record_portfolio_holdings",
        input={"holdings": holdings},
    )


# ── fixtures + helpers ──────────────────────────────────────────────────


def _factory(db_engine):
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


async def _seed_user(db_engine, email: str = "chat@test.com") -> str:
    async with _factory(db_engine)() as s:
        user = UserProfile(name="Chatter", email=email)
        s.add(user)
        await s.commit()
        await s.refresh(user)
        return user.id


async def _client(db_engine, *, fake_anthropic: _FakeAnthropic | None = None):
    from api.portfolio import get_chat_client
    from db.database import get_db
    from main import app

    factory = _factory(db_engine)

    async def db_override():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_db] = db_override
    if fake_anthropic is not None:
        app.dependency_overrides[get_chat_client] = lambda: fake_anthropic

    transport = ASGITransport(app=app)
    return app, AsyncClient(transport=transport, base_url="http://test")


# ── tests ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_chat_extract_returns_structured_holdings(db_engine):
    fake = _FakeAnthropic(
        responses=[
            _FakeResponse(
                content=[
                    _FakeBlock(type="text", text="Got it, recording your holding."),
                    _tool_use_block(
                        [
                            {
                                "address": "789 Lakeview Dr 60615",
                                "asset_class": "sfr",
                                "zip_code": "60615",
                                "monthly_rent": 2600,
                            }
                        ]
                    ),
                ]
            )
        ]
    )
    app, ac = await _client(db_engine, fake_anthropic=fake)
    async with ac:
        r = await ac.post(
            "/api/portfolio/import/chat",
            json={
                "messages": [
                    {
                        "role": "user",
                        "content": "I own 789 Lakeview Drive in Chicago, rents for $2600/mo.",
                    }
                ]
            },
        )
    app.dependency_overrides.clear()

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["narration"].startswith("Got it")
    assert len(body["holdings"]) == 1
    assert body["holdings"][0]["address"] == "789 Lakeview Dr 60615"
    assert body["holdings"][0]["financials"]["monthly_rent"] == 2600
    # The fake also recorded the call — verify the system prompt + tool got through
    assert fake.messages.calls[0]["tools"][0]["name"] == "record_portfolio_holdings"


@pytest.mark.asyncio
async def test_chat_extract_handles_no_tool_use(db_engine):
    """If Claude only asks a clarifying question, we return an empty list."""
    fake = _FakeAnthropic(
        responses=[
            _FakeResponse(
                content=[
                    _FakeBlock(type="text", text="What's the address?"),
                ]
            )
        ]
    )
    app, ac = await _client(db_engine, fake_anthropic=fake)
    async with ac:
        r = await ac.post(
            "/api/portfolio/import/chat",
            json={"messages": [{"role": "user", "content": "I have a place."}]},
        )
    app.dependency_overrides.clear()

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["holdings"] == []
    assert body["narration"] == "What's the address?"


@pytest.mark.asyncio
async def test_chat_extract_rejects_empty_messages(db_engine):
    fake = _FakeAnthropic(responses=[])
    app, ac = await _client(db_engine, fake_anthropic=fake)
    async with ac:
        r = await ac.post("/api/portfolio/import/chat", json={"messages": []})
    app.dependency_overrides.clear()

    assert r.status_code == 400
    assert r.json()["detail"] == "no_messages_provided"


@pytest.mark.asyncio
async def test_chat_confirm_commits_holdings(db_engine):
    user_id = await _seed_user(db_engine)
    app, ac = await _client(db_engine)
    async with ac:
        r = await ac.post(
            "/api/portfolio/import/chat/confirm",
            json={
                "user_id": user_id,
                "portfolio_name": "Chat Import",
                "investment_strategy": "buy_hold",
                "holdings": [
                    {
                        "address": "100 River Rd 60601",
                        "asset_class": "sfr",
                        "status": "held",
                        "zip_code": "60601",
                        "financials": {"monthly_rent": 2200},
                    }
                ],
            },
        )
    app.dependency_overrides.clear()

    assert r.status_code == 201, r.text
    assert r.json()["inserted_count"] == 1

    async with _factory(db_engine)() as s:
        holdings = (await s.execute(select(PortfolioHolding))).scalars().all()
        assert len(holdings) == 1
        fin = (await s.execute(select(HoldingFinancials))).scalar_one()
        assert fin.monthly_rent == 2200


@pytest.mark.asyncio
async def test_chat_confirm_is_idempotent_with_csv_import(db_engine):
    """Confirming the same address twice (CSV then chat) updates rather than dupes."""
    user_id = await _seed_user(db_engine)
    payload_csv = {
        "user_id": user_id,
        "portfolio_name": "Mixed",
        "investment_strategy": "buy_hold",
        "holdings": [
            {
                "address": "55 Pier Pl 60602",
                "asset_class": "sfr",
                "status": "held",
                "financials": {"monthly_rent": 2000},
            }
        ],
    }
    app, ac = await _client(db_engine)
    async with ac:
        r1 = await ac.post("/api/portfolio/import/csv", json=payload_csv)
        assert r1.status_code == 201
        r2 = await ac.post(
            "/api/portfolio/import/chat/confirm",
            json={
                "user_id": user_id,
                "portfolio_name": "Mixed",
                "investment_strategy": "buy_hold",
                "holdings": [
                    {
                        "address": "55 Pier Pl 60602",
                        "asset_class": "sfr",
                        "status": "held",
                        "financials": {"monthly_rent": 2300},
                    }
                ],
            },
        )
    app.dependency_overrides.clear()

    assert r2.status_code == 201, r2.text
    assert r2.json()["updated_count"] == 1
    assert r2.json()["inserted_count"] == 0

    async with _factory(db_engine)() as s:
        holdings = (await s.execute(select(PortfolioHolding))).scalars().all()
        assert len(holdings) == 1
        fin = (await s.execute(select(HoldingFinancials))).scalar_one()
        assert fin.monthly_rent == 2300
