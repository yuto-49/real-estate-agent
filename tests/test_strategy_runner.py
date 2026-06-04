"""StrategyRunner + UnifiedReport tests — Phases S6/S7."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.schemas import (
    HoldingSummaryEntry,
    MarketCoverage,
    PortfolioSummaryAggregates,
    PortfolioSummaryReport,
    StrategyAssumptions,
    StrategyPolicyConfig,
    StrategyProfile,
    StrategyThesis,
)
from db.models import (
    HoldingFinancials,
    InvestorPortfolio,
    MarketSignal,
    PortfolioHolding,
    UserProfile,
)
from services.strategy_runner import (
    execute_strategy_run,
    project_simulation,
    reset_strategy_runs,
    start_strategy_run,
)
from services.unified_report import reconcile_unified_report


def _factory(db_engine):
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


def _make_analysis(rows: list[HoldingSummaryEntry]) -> PortfolioSummaryReport:
    return PortfolioSummaryReport(
        portfolio_id="p1",
        generated_at=datetime.now(timezone.utc),
        holding_count=len(rows),
        aggregates=PortfolioSummaryAggregates(
            total_value=sum((r.current_value or 0) for r in rows),
            total_loan_balance=0.0,
            total_equity=sum((r.current_value or 0) for r in rows),
            monthly_gross_rent=0.0,
            monthly_net_operating_income=0.0,
            monthly_cash_flow=sum((r.monthly_cash_flow or 0) for r in rows),
            annual_noi=0.0,
            blended_cap_rate=0.05,
            weighted_dscr=None,
        ),
        per_holding=rows,
        attention=[],
        market_coverage=MarketCoverage(total=len(rows), with_signals=len(rows)),
    )


def _row(
    *,
    holding_id: str = "h1",
    recommendation: str = "HOLD",
    cap_rate: float = 0.05,
    current_value: float = 400_000.0,
    monthly_cash_flow: float = 100.0,
) -> HoldingSummaryEntry:
    return HoldingSummaryEntry(
        holding_id=holding_id,
        address=f"{holding_id} Test St",
        zip_code="60601",
        asset_class="sfr",
        current_value=current_value,
        monthly_cash_flow=monthly_cash_flow,
        cap_rate=cap_rate,
        dscr=1.0,
        cash_on_cash=0.05,
        recommendation=recommendation,
        recommendation_score=0.5,
        recommendation_rationale="seed",
        market_context_available=True,
    )


# ── pure projection tests ──────────────────────────────────────────────


def test_projection_grows_noi_with_rent_growth():
    analysis = _make_analysis([_row(cap_rate=0.05, current_value=400_000.0)])
    profile = StrategyProfile(
        assumptions=StrategyAssumptions(
            rent_growth=0.05,
            expense_growth=0.02,
            hold_period_years=5,
            exit_cap_rate=0.06,
        ),
    )
    sim = project_simulation(analysis, profile)
    assert sim.horizon_years == 5
    assert len(sim.per_holding) == 1
    proj = sim.per_holding[0]
    today_noi = 0.05 * 400_000.0  # 20_000
    assert proj.projected_annual_noi is not None
    assert proj.projected_annual_noi > today_noi
    assert proj.projected_value is not None and proj.projected_value > 400_000.0


def test_projection_flags_sell_when_cap_collapses():
    analysis = _make_analysis([_row(cap_rate=0.05)])
    profile = StrategyProfile(
        assumptions=StrategyAssumptions(
            rent_growth=-0.05,
            expense_growth=0.05,
            hold_period_years=10,
            exit_cap_rate=0.07,
        ),
        thesis=StrategyThesis(market_outlook="bearish"),
    )
    sim = project_simulation(analysis, profile)
    proj = sim.per_holding[0]
    assert proj.projected_recommendation == "SELL"


def test_projection_flags_refi_for_high_loan_outlook():
    analysis = _make_analysis([_row()])
    profile = StrategyProfile(
        assumptions=StrategyAssumptions(loan_rate_outlook=0.09),
    )
    sim = project_simulation(analysis, profile)
    assert sim.per_holding[0].projected_recommendation == "REFI"


def test_projection_respects_tenant_protection_flag():
    analysis = _make_analysis([_row()])
    profile = StrategyProfile(
        policy_config=StrategyPolicyConfig(
            raise_rent_bias=0.5,
            tenant_protection=True,
        ),
        assumptions=StrategyAssumptions(rent_growth=0.04, expense_growth=0.02),
    )
    sim = project_simulation(analysis, profile)
    # tenant_protection + rising cap rate → IMPROVE, not RAISE_RENT
    assert sim.per_holding[0].projected_recommendation in {"IMPROVE", "HOLD"}


# ── unified reconciliation ────────────────────────────────────────────


def test_unified_report_flags_flips():
    analysis = _make_analysis([
        _row(holding_id="h1", recommendation="HOLD", cap_rate=0.05),
        _row(holding_id="h2", recommendation="HOLD", cap_rate=0.05),
    ])
    profile = StrategyProfile(
        assumptions=StrategyAssumptions(
            rent_growth=-0.05, expense_growth=0.05, exit_cap_rate=0.07,
        ),
        thesis=StrategyThesis(market_outlook="bearish"),
    )
    sim = project_simulation(analysis, profile)
    unified = reconcile_unified_report(analysis, sim, profile)
    assert unified.horizon_years == profile.assumptions.hold_period_years
    assert any(r.flipped for r in unified.reconciliations)
    assert unified.survives is False


def test_unified_report_survives_when_recommendations_stable():
    analysis = _make_analysis([_row(holding_id="h1", recommendation="HOLD")])
    profile = StrategyProfile()  # all defaults — stable conditions
    sim = project_simulation(analysis, profile)
    unified = reconcile_unified_report(analysis, sim, profile)
    assert unified.survives is True
    assert unified.confidence >= 0.5


# ── end-to-end via execute_strategy_run ───────────────────────────────


async def _seed_portfolio(db_engine, *, tag: str) -> str:
    factory = _factory(db_engine)
    async with factory() as s:
        user = UserProfile(name="Investor", email=f"runner-{tag}@t.com")
        s.add(user)
        await s.flush()
        portfolio = InvestorPortfolio(user_id=user.id, name=tag)
        s.add(portfolio)
        await s.flush()
        holding = PortfolioHolding(
            portfolio_id=portfolio.id,
            address="1 End To End St",
            zip_code="60601",
        )
        s.add(holding)
        await s.flush()
        s.add(
            HoldingFinancials(
                holding_id=holding.id,
                current_value_estimate=400_000.0,
                loan_balance=200_000.0,
                interest_rate=0.04,
                monthly_piti=1_400.0,
                monthly_rent=2_400.0,
                vacancy_rate=0.05,
                monthly_opex_estimate=200.0,
                property_tax_annual=6_000.0,
                insurance_annual=1_200.0,
            )
        )
        s.add(
            MarketSignal(
                signal_type="inventory_pressure",
                subject_type="neighborhood",
                subject_id="60601",
                value=0.2,
            )
        )
        await s.commit()
        return portfolio.id


@pytest.mark.asyncio
async def test_execute_strategy_run_end_to_end(db_engine):
    await reset_strategy_runs()
    portfolio_id = await _seed_portfolio(db_engine, tag="end2end")
    profile = StrategyProfile()
    record = await start_strategy_run(portfolio_id, profile)

    factory = _factory(db_engine)
    async with factory() as s:
        completed = await execute_strategy_run(s, record.run_id, portfolio_id, profile)

    assert completed.status == "completed"
    assert completed.analysis is not None
    assert completed.simulation is not None
    assert completed.unified is not None
    assert completed.completed_at is not None
    assert len(completed.simulation.per_holding) == 1


@pytest.mark.asyncio
async def test_execute_strategy_run_fails_for_missing_portfolio(db_engine):
    await reset_strategy_runs()
    profile = StrategyProfile()
    record = await start_strategy_run("missing", profile)

    factory = _factory(db_engine)
    async with factory() as s:
        result = await execute_strategy_run(s, record.run_id, "missing", profile)

    assert result.status == "failed"
    assert result.error == "portfolio_not_found"


# ── HTTP surface ──────────────────────────────────────────────────────


def _override_db(db_engine):
    from db.database import get_db
    from main import app

    factory = _factory(db_engine)

    async def override():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_db] = override
    return app


@pytest.mark.asyncio
async def test_extract_endpoint_seeds_profile():
    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/api/strategy/extract",
            json={"portfolio_id": "any", "text": "Buy and hold, low risk, 5% rent growth."},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["profile"]["policy_config"]["risk_tolerance"] == "low"
    assert body["profile"]["assumptions"]["rent_growth"] == pytest.approx(0.05)


@pytest.mark.skip(reason="background-task race hangs against ASGITransport — pre-existing")
@pytest.mark.asyncio
async def test_strategy_run_via_http(db_engine):
    await reset_strategy_runs()
    portfolio_id = await _seed_portfolio(db_engine, tag="http")
    app = _override_db(db_engine)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/api/strategy/run",
            json={"portfolio_id": portfolio_id, "text": "long-term buy and hold"},
        )
        assert r.status_code == 202, r.text
        run_id = r.json()["run_id"]

        result = await ac.get(f"/api/strategy/{run_id}/result")
        assert result.status_code == 200, result.text
        body = result.json()
        assert body["status"] == "completed"
        assert body["analysis"]["portfolio_id"] == portfolio_id
        assert body["unified"]["portfolio_id"] == portfolio_id
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_strategy_run_status_404_for_unknown():
    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/strategy/does-not-exist/status")
    assert r.status_code == 404
