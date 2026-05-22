"""POST /api/underwrite/stress-test — Phase P3."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession


@pytest.mark.asyncio
async def test_stress_test_endpoint_returns_distribution(db_engine):
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
            "/api/underwrite/stress-test",
            json={
                "base_inputs": {
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
                "config": {
                    "iterations": 200,
                    "seed": 42,
                    "vacancy_rate": {"low": 0.03, "high": 0.15},
                    "rent_growth": {"low": 0.0, "high": 0.05},
                    "expense_growth": {"low": 0.01, "high": 0.04},
                    "loan_rate": {"low": 0.055, "high": 0.08},
                    "exit_cap_rate": {"low": 0.06, "high": 0.08},
                },
            },
        )
    app.dependency_overrides.clear()

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["iterations"] == 200
    assert "irr_5yr_p10" in body
    assert "irr_5yr_p50" in body
    assert "irr_5yr_p90" in body
    assert "tornado" in body
    assert body["probability_negative_cash_flow"] >= 0
