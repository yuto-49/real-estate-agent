"""POST /api/underwrite and POST /api/listing/parse — Phase P2."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession


@pytest.mark.asyncio
async def test_underwrite_endpoint_returns_metrics(db_engine):
    from db.database import get_db
    from main import app

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_db] = override

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/api/underwrite",
            json={
                "purchase_price": 250_000,
                "down_payment": 50_000,
                "loan_rate": 0.065,
                "loan_term_years": 30,
                "monthly_rent": 2_200,
                "vacancy_rate": 0.05,
                "monthly_opex": 350,
                "property_tax_annual": 3_000,
                "insurance_annual": 1_100,
                "closing_costs": 5_000,
            },
        )
    app.dependency_overrides.clear()

    assert r.status_code == 200, r.text
    body = r.json()
    assert "cap_rate" in body
    assert "cash_on_cash" in body
    assert "dscr" in body
    assert "monthly_piti" in body
    assert body["annual_noi"] > 0


@pytest.mark.asyncio
async def test_listing_parse_endpoint_suumo(db_engine):
    from db.database import get_db
    from main import app

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_db] = override

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/api/listing/parse",
            json={
                "url": "https://suumo.jp/ms/chuko/tokyo/sc_minatoku/nc_12345678/"
            },
        )
    app.dependency_overrides.clear()

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["property_id"] == "12345678"
    assert body["prefecture"] == "東京都"
    assert body["source"] == "suumo"


@pytest.mark.asyncio
async def test_listing_parse_endpoint_rejects_unsupported(db_engine):
    from db.database import get_db
    from main import app

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_db] = override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/api/listing/parse",
            json={"url": "https://www.zillow.com/homedetails/123-Main-St-Chicago-IL-60601/12345678_zpid/"},
        )
    app.dependency_overrides.clear()
    assert r.status_code == 400
