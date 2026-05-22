"""Tests for InvestorPortfolio, PortfolioHolding, HoldingFinancials, UnderwritingScenario.

Phase P1 — model invariants only. CRUD round-trips covered in test_api_portfolio.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from db.models import (
    HoldingFinancials,
    InvestorPortfolio,
    InvestmentStrategy,
    HoldingStatus,
    AssetClass,
    PortfolioHolding,
    PortfolioMode,
    UnderwritingScenario,
    UserProfile,
)


@pytest.mark.asyncio
async def test_user_profile_has_preferred_mode_default(db):
    """UserProfile.preferred_mode defaults to INSTITUTIONAL."""
    user = UserProfile(name="Test", email="t@test.com")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    assert user.preferred_mode == PortfolioMode.INSTITUTIONAL


@pytest.mark.asyncio
async def test_user_profile_can_set_individual_mode(db):
    user = UserProfile(
        name="Indie", email="indie@test.com", preferred_mode=PortfolioMode.INDIVIDUAL
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    assert user.preferred_mode == PortfolioMode.INDIVIDUAL


@pytest.mark.asyncio
async def test_create_investor_portfolio(db):
    user = UserProfile(name="Alice", email="alice@test.com")
    db.add(user)
    await db.flush()

    portfolio = InvestorPortfolio(
        user_id=user.id,
        name="Chicago BRRRR",
        investment_strategy=InvestmentStrategy.BRRRR,
    )
    db.add(portfolio)
    await db.commit()
    await db.refresh(portfolio)

    assert portfolio.id is not None
    assert portfolio.user_id == user.id
    assert portfolio.investment_strategy == InvestmentStrategy.BRRRR
    assert portfolio.created_at is not None


@pytest.mark.asyncio
async def test_portfolio_holding_supports_off_platform_address(db):
    """A holding can exist without a property_id (off-platform property)."""
    user = UserProfile(name="Bob", email="bob@test.com")
    db.add(user)
    await db.flush()
    portfolio = InvestorPortfolio(
        user_id=user.id, name="Mixed", investment_strategy=InvestmentStrategy.MIXED
    )
    db.add(portfolio)
    await db.flush()

    holding = PortfolioHolding(
        portfolio_id=portfolio.id,
        property_id=None,
        address="900 Off-Platform St, Chicago, IL 60601",
        asset_class=AssetClass.SFR,
        status=HoldingStatus.HELD,
    )
    db.add(holding)
    await db.commit()
    await db.refresh(holding)

    assert holding.id is not None
    assert holding.property_id is None
    assert holding.asset_class == AssetClass.SFR


@pytest.mark.asyncio
async def test_holding_financials_stores_money_fields(db):
    user = UserProfile(name="C", email="c@test.com")
    db.add(user)
    await db.flush()
    portfolio = InvestorPortfolio(user_id=user.id, name="P")
    db.add(portfolio)
    await db.flush()
    holding = PortfolioHolding(
        portfolio_id=portfolio.id,
        address="1 Main",
        asset_class=AssetClass.MF_2_4,
    )
    db.add(holding)
    await db.flush()

    fin = HoldingFinancials(
        holding_id=holding.id,
        cost_basis=300_000,
        current_value_estimate=350_000,
        loan_balance=240_000,
        interest_rate=0.065,
        monthly_piti=2100,
        monthly_rent=2800,
        vacancy_rate=0.05,
        monthly_opex_estimate=600,
        property_tax_annual=4200,
        insurance_annual=1400,
    )
    db.add(fin)
    await db.commit()
    await db.refresh(fin)

    assert fin.id is not None
    assert fin.holding_id == holding.id
    assert fin.cost_basis == 300_000
    assert fin.interest_rate == pytest.approx(0.065)


@pytest.mark.asyncio
async def test_underwriting_scenario_persists_jsonb_blobs(db):
    """UnderwritingScenario stores arbitrary inputs/outputs as JSONB."""
    scenario = UnderwritingScenario(
        holding_id=None,
        inputs={"vacancy_rate": 0.05, "rent_growth": 0.03},
        outputs={"cap_rate": 0.062, "cash_on_cash": 0.084, "irr_5yr": 0.12},
        hazard_signals={"flood_zone": "X", "crime_score": 0.42},
    )
    db.add(scenario)
    await db.commit()
    await db.refresh(scenario)

    assert scenario.id is not None
    assert scenario.inputs["vacancy_rate"] == 0.05
    assert scenario.outputs["cap_rate"] == 0.062
    assert scenario.hazard_signals["flood_zone"] == "X"


@pytest.mark.asyncio
async def test_portfolio_to_holdings_relationship(db):
    """Querying holdings by portfolio_id works."""
    user = UserProfile(name="D", email="d@test.com")
    db.add(user)
    await db.flush()
    portfolio = InvestorPortfolio(user_id=user.id, name="Multi")
    db.add(portfolio)
    await db.flush()

    for i in range(3):
        db.add(
            PortfolioHolding(
                portfolio_id=portfolio.id,
                address=f"{i} Holding Ave",
                asset_class=AssetClass.SFR,
            )
        )
    await db.commit()

    result = await db.execute(
        select(PortfolioHolding).where(PortfolioHolding.portfolio_id == portfolio.id)
    )
    rows = list(result.scalars().all())
    assert len(rows) == 3
