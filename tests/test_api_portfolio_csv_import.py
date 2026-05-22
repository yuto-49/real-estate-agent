"""CSV bulk-import endpoint tests — Phase P2."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db.models import HoldingFinancials, InvestorPortfolio, PortfolioHolding, UserProfile


def _factory(db_engine):
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


async def _seed_user(db_engine, email: str = "import@test.com") -> str:
    async with _factory(db_engine)() as s:
        user = UserProfile(name="Importer", email=email)
        s.add(user)
        await s.commit()
        await s.refresh(user)
        return user.id


async def _client(db_engine):
    from db.database import get_db
    from main import app

    factory = _factory(db_engine)

    async def override():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_db] = override
    transport = ASGITransport(app=app)
    return app, AsyncClient(transport=transport, base_url="http://test")


def _payload(user_id: str, *, address: str = "123 Main St 60601", rent: float = 2400.0):
    return {
        "user_id": user_id,
        "portfolio_name": "Wizard Import",
        "investment_strategy": "buy_hold",
        "holdings": [
            {
                "address": address,
                "asset_class": "sfr",
                "status": "held",
                "zip_code": "60601",
                "financials": {
                    "cost_basis": 350000,
                    "current_value_estimate": 420000,
                    "loan_balance": 240000,
                    "monthly_rent": rent,
                    "monthly_piti": 1850,
                },
            }
        ],
    }


@pytest.mark.asyncio
async def test_import_csv_creates_portfolio_and_holding(db_engine):
    user_id = await _seed_user(db_engine)
    app, ac = await _client(db_engine)
    async with ac:
        r = await ac.post("/api/portfolio/import/csv", json=_payload(user_id))
    app.dependency_overrides.clear()

    assert r.status_code == 201, r.text
    body = r.json()
    assert body["inserted_count"] == 1
    assert body["updated_count"] == 0
    assert body["portfolio_id"]

    async with _factory(db_engine)() as s:
        holdings = (await s.execute(select(PortfolioHolding))).scalars().all()
        assert len(holdings) == 1
        assert holdings[0].address == "123 Main St 60601"
        fin = (
            await s.execute(
                select(HoldingFinancials).where(
                    HoldingFinancials.holding_id == holdings[0].id
                )
            )
        ).scalar_one()
        assert fin.monthly_rent == 2400.0


@pytest.mark.asyncio
async def test_import_csv_is_idempotent_on_address(db_engine):
    user_id = await _seed_user(db_engine)
    app, ac = await _client(db_engine)
    async with ac:
        r1 = await ac.post("/api/portfolio/import/csv", json=_payload(user_id))
        assert r1.status_code == 201, r1.text

        # Re-import with a different rent on the same address
        r2 = await ac.post(
            "/api/portfolio/import/csv", json=_payload(user_id, rent=2600.0)
        )
    app.dependency_overrides.clear()

    assert r2.status_code == 201, r2.text
    body = r2.json()
    assert body["inserted_count"] == 0
    assert body["updated_count"] == 1

    async with _factory(db_engine)() as s:
        holdings = (await s.execute(select(PortfolioHolding))).scalars().all()
        assert len(holdings) == 1, "no duplicate holding rows"

        portfolios = (await s.execute(select(InvestorPortfolio))).scalars().all()
        assert len(portfolios) == 1, "no duplicate portfolio rows"

        fin = (await s.execute(select(HoldingFinancials))).scalar_one()
        assert fin.monthly_rent == 2600.0


@pytest.mark.asyncio
async def test_import_csv_rejects_empty_holdings(db_engine):
    user_id = await _seed_user(db_engine)
    app, ac = await _client(db_engine)
    async with ac:
        r = await ac.post(
            "/api/portfolio/import/csv",
            json={
                "user_id": user_id,
                "portfolio_name": "Empty",
                "investment_strategy": "buy_hold",
                "holdings": [],
            },
        )
    app.dependency_overrides.clear()
    assert r.status_code == 400
    assert r.json()["detail"] == "no_holdings_provided"


@pytest.mark.asyncio
async def test_import_csv_rejects_unknown_user(db_engine):
    app, ac = await _client(db_engine)
    async with ac:
        r = await ac.post(
            "/api/portfolio/import/csv",
            json=_payload("00000000-0000-0000-0000-000000000000"),
        )
    app.dependency_overrides.clear()
    assert r.status_code == 404
    assert r.json()["detail"] == "user_not_found"


@pytest.mark.asyncio
async def test_import_csv_skips_blank_address(db_engine):
    user_id = await _seed_user(db_engine)
    payload = {
        "user_id": user_id,
        "portfolio_name": "Mixed",
        "investment_strategy": "buy_hold",
        "holdings": [
            {"address": "", "asset_class": "sfr", "status": "held"},
            {"address": "456 Oak Ave 60602", "asset_class": "sfr", "status": "held"},
        ],
    }
    app, ac = await _client(db_engine)
    async with ac:
        r = await ac.post("/api/portfolio/import/csv", json=payload)
    app.dependency_overrides.clear()

    assert r.status_code == 201, r.text
    body = r.json()
    assert body["inserted_count"] == 1
    assert body["skipped"] == ["<missing address>"]


@pytest.mark.asyncio
async def test_csv_template_endpoint(db_engine):
    app, ac = await _client(db_engine)
    async with ac:
        r = await ac.get("/api/portfolio/import/csv/template")
    app.dependency_overrides.clear()

    assert r.status_code == 200
    body = r.json()
    assert "address" in body["columns"]
    assert "monthly_rent" in body["columns"]
    assert body["csv"].startswith("address,zip_code,asset_class")
    assert body["csv"].count("\n") >= 2  # header + at least one example
