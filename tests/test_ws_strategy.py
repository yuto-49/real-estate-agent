"""WebSocket strategy-run stream replays + closes properly — Phase P5."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.schemas import StrategyProfile
from db.models import (
    AssetClass,
    HoldingFinancials,
    HoldingStatus,
    InvestmentStrategy,
    InvestorPortfolio,
    PortfolioHolding,
    UserProfile,
)
from services.strategy_runner import (
    execute_strategy_run,
    reset_strategy_runs,
    start_strategy_run,
)


def _factory(db_engine):
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


async def _seed_portfolio(db_engine) -> str:
    factory = _factory(db_engine)
    async with factory() as s:
        u = UserProfile(name="WS Owner", email="ws@test.com")
        s.add(u)
        await s.flush()
        p = InvestorPortfolio(
            user_id=u.id,
            name="WS",
            investment_strategy=InvestmentStrategy.BUY_HOLD,
        )
        s.add(p)
        await s.flush()
        h = PortfolioHolding(
            portfolio_id=p.id,
            address="200 WS Way 60601",
            asset_class=AssetClass.SFR,
            status=HoldingStatus.HELD,
        )
        s.add(h)
        await s.flush()
        s.add(
            HoldingFinancials(
                holding_id=h.id,
                cost_basis=300_000,
                current_value_estimate=350_000,
                monthly_rent=2_400,
            )
        )
        await s.commit()
        return p.id


@pytest.mark.asyncio
async def test_ws_replays_steps_for_completed_run(db_engine):
    """Once the run is in the store with steps, the ws replays + closes."""
    await reset_strategy_runs()
    portfolio_id = await _seed_portfolio(db_engine)
    profile = StrategyProfile()
    rec = await start_strategy_run(portfolio_id, profile)

    async with _factory(db_engine)() as s:
        completed = await execute_strategy_run(s, rec.run_id, portfolio_id, profile)
    assert completed.status == "completed"

    from db.database import get_db
    from main import app

    factory = _factory(db_engine)

    async def override():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_db] = override
    client = TestClient(app)
    received: list[dict] = []
    try:
        with client.websocket_connect(f"/ws/strategy/{rec.run_id}") as ws:
            while True:
                msg = ws.receive_json()
                received.append(msg)
                if msg.get("type") == "stream.closed":
                    break
    finally:
        app.dependency_overrides.clear()

    types = [m["type"] for m in received]
    assert "run.started" in types
    assert "run.completed" in types
    assert types[-1] == "stream.closed"
    assert received[-1]["payload"]["status"] == "completed"


@pytest.mark.asyncio
async def test_ws_rejects_unknown_run_id(db_engine):
    from main import app

    client = TestClient(app)
    received: list[dict] = []
    with client.websocket_connect("/ws/strategy/not-a-real-run") as ws:
        try:
            while True:
                received.append(ws.receive_json())
        except Exception:
            pass

    assert any(m.get("type") == "error" for m in received)
