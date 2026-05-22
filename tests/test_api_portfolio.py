"""Portfolio CRUD API tests — Phase P1."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from db.models import UserProfile


async def _make_user(db_engine, email: str = "owner@test.com") -> str:
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        user = UserProfile(name="Owner", email=email)
        s.add(user)
        await s.commit()
        await s.refresh(user)
        return user.id


@pytest.mark.asyncio
async def test_create_portfolio(db_engine):
    from db.database import get_db
    from main import app

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_db] = override
    user_id = await _make_user(db_engine)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/api/portfolio/",
            json={"user_id": user_id, "name": "Chi-BRRRR", "investment_strategy": "brrrr"},
        )
    app.dependency_overrides.clear()

    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "Chi-BRRRR"
    assert body["investment_strategy"] == "brrrr"
    assert body["user_id"] == user_id


@pytest.mark.asyncio
async def test_list_portfolios_for_user(db_engine):
    from db.database import get_db
    from main import app

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_db] = override
    user_id = await _make_user(db_engine, "list@test.com")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        for i in range(2):
            await ac.post(
                "/api/portfolio/",
                json={
                    "user_id": user_id,
                    "name": f"P{i}",
                    "investment_strategy": "buy_hold",
                },
            )
        r = await ac.get(f"/api/portfolio/?user_id={user_id}")
    app.dependency_overrides.clear()

    assert r.status_code == 200
    items = r.json()
    assert len(items) == 2
    assert {item["name"] for item in items} == {"P0", "P1"}


@pytest.mark.asyncio
async def test_add_holding_to_portfolio(db_engine):
    from db.database import get_db
    from main import app

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_db] = override
    user_id = await _make_user(db_engine, "h@test.com")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        p = await ac.post(
            "/api/portfolio/",
            json={"user_id": user_id, "name": "H", "investment_strategy": "buy_hold"},
        )
        pid = p.json()["id"]
        r = await ac.post(
            f"/api/portfolio/{pid}/holdings",
            json={
                "address": "10 Investor Way",
                "asset_class": "sfr",
                "status": "held",
                "financials": {
                    "cost_basis": 200_000,
                    "current_value_estimate": 250_000,
                    "loan_balance": 160_000,
                    "interest_rate": 0.067,
                    "monthly_piti": 1500,
                    "monthly_rent": 2200,
                    "vacancy_rate": 0.05,
                    "monthly_opex_estimate": 450,
                    "property_tax_annual": 3000,
                    "insurance_annual": 1100,
                },
            },
        )
    app.dependency_overrides.clear()

    assert r.status_code == 201, r.text
    body = r.json()
    assert body["address"] == "10 Investor Way"
    assert body["asset_class"] == "sfr"
    assert body["financials"]["monthly_rent"] == 2200


@pytest.mark.asyncio
async def test_list_holdings_for_portfolio(db_engine):
    from db.database import get_db
    from main import app

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_db] = override
    user_id = await _make_user(db_engine, "lh@test.com")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        p = await ac.post(
            "/api/portfolio/",
            json={"user_id": user_id, "name": "LH", "investment_strategy": "mixed"},
        )
        pid = p.json()["id"]
        for i in range(3):
            await ac.post(
                f"/api/portfolio/{pid}/holdings",
                json={"address": f"{i} Way", "asset_class": "sfr"},
            )
        r = await ac.get(f"/api/portfolio/{pid}/holdings")
    app.dependency_overrides.clear()

    assert r.status_code == 200
    assert len(r.json()) == 3


@pytest.mark.asyncio
async def test_delete_holding(db_engine):
    from db.database import get_db
    from main import app

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_db] = override
    user_id = await _make_user(db_engine, "del@test.com")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        p = await ac.post(
            "/api/portfolio/",
            json={"user_id": user_id, "name": "D", "investment_strategy": "buy_hold"},
        )
        pid = p.json()["id"]
        h = await ac.post(
            f"/api/portfolio/{pid}/holdings", json={"address": "1 Del St", "asset_class": "sfr"}
        )
        hid = h.json()["id"]
        r = await ac.delete(f"/api/portfolio/{pid}/holdings/{hid}")
        listed = await ac.get(f"/api/portfolio/{pid}/holdings")
    app.dependency_overrides.clear()

    assert r.status_code == 204
    assert listed.json() == []


@pytest.mark.asyncio
async def test_portfolio_aggregate_metrics(db_engine):
    """Aggregate endpoint returns blended cap rate and geographic concentration."""
    from db.database import get_db
    from main import app

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_db] = override
    user_id = await _make_user(db_engine, "agg@test.com")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        p = await ac.post(
            "/api/portfolio/",
            json={"user_id": user_id, "name": "Agg", "investment_strategy": "buy_hold"},
        )
        pid = p.json()["id"]
        # Two holdings, same zip
        for rent, opex, value in [(2400, 500, 280_000), (3000, 700, 360_000)]:
            await ac.post(
                f"/api/portfolio/{pid}/holdings",
                json={
                    "address": f"{rent} Chicago St, Chicago, IL 60601",
                    "asset_class": "sfr",
                    "status": "held",
                    "financials": {
                        "cost_basis": value - 30_000,
                        "current_value_estimate": value,
                        "loan_balance": value * 0.7,
                        "interest_rate": 0.065,
                        "monthly_piti": 1500,
                        "monthly_rent": rent,
                        "vacancy_rate": 0.05,
                        "monthly_opex_estimate": opex,
                        "property_tax_annual": 3500,
                        "insurance_annual": 1200,
                    },
                },
            )
        r = await ac.get(f"/api/portfolio/{pid}/aggregate")
    app.dependency_overrides.clear()

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["holding_count"] == 2
    assert body["total_value"] == 640_000
    assert body["total_loan_balance"] == pytest.approx(448_000)
    assert body["total_equity"] == pytest.approx(192_000)
    assert 0 < body["blended_cap_rate"] < 0.20
    assert "concentration" in body
