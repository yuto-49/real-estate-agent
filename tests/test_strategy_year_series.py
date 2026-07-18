"""The simulation must expose a year-by-year series, not just an endpoint.

``SimulationReport`` historically carried only horizon-end values, so the
Simulation tab had nothing to plot over time. ``project_year_series`` walks the
same compound-growth factors ``_project_holding`` uses, evaluated at each year,
so the curve and the endpoint can never disagree.
"""

from __future__ import annotations

import pytest

from api.schemas import (
    HoldingSummaryEntry,
    MarketCoverage,
    PortfolioSummaryAggregates,
    PortfolioSummaryReport,
    StrategyAssumptions,
    StrategyProfile,
)
from services.strategy_runner import project_simulation, project_year_series

_HORIZON = 5


def _aggregates() -> PortfolioSummaryAggregates:
    """Aggregates are not what these tests exercise — the per_holding rows are."""
    return PortfolioSummaryAggregates(
        total_value=0.0,
        total_loan_balance=0.0,
        total_equity=0.0,
        monthly_gross_rent=0.0,
        monthly_net_operating_income=0.0,
        monthly_cash_flow=0.0,
        annual_noi=0.0,
        blended_cap_rate=0.0,
    )


def _analysis() -> PortfolioSummaryReport:
    from datetime import datetime, timezone

    row = HoldingSummaryEntry(
        holding_id="h1",
        address="東京都 港区 六本木六丁目",
        zip_code="13103",
        asset_class="CONDO",
        current_value=200_000_000.0,
        cap_rate=0.04,
        monthly_cash_flow=200_000.0,
        recommendation="HOLD",
        recommendation_score=0.7,
        recommendation_rationale="安定したキャッシュフロー",
        market_context_available=True,
    )
    return PortfolioSummaryReport(
        portfolio_id="p1",
        generated_at=datetime.now(timezone.utc),
        holding_count=1,
        aggregates=_aggregates(),
        per_holding=[row],
        attention=[],
        market_coverage=MarketCoverage(total=1, with_signals=1),
    )


def _profile() -> StrategyProfile:
    """A 5-year hold; every other assumption stays at its default."""
    return StrategyProfile(
        assumptions=StrategyAssumptions(hold_period_years=_HORIZON)
    )


def test_series_covers_year_zero_through_horizon():
    series = project_year_series(_analysis(), _profile())
    assert [p.year for p in series] == list(range(0, _HORIZON + 1))


def test_year_zero_is_today_not_projected():
    """Year 0 must be the present value — the curve starts where the portfolio is."""
    series = project_year_series(_analysis(), _profile())
    assert series[0].portfolio_value == pytest.approx(200_000_000.0)


def test_final_year_matches_the_endpoint_report_exactly():
    """The curve's last point must equal the endpoint the report already ships.

    If these ever diverge, the chart is lying about the number beside it.
    """
    analysis, profile = _analysis(), _profile()
    series = project_year_series(analysis, profile)
    report = project_simulation(analysis, profile)

    assert series[-1].portfolio_value == pytest.approx(
        report.aggregate_value_projection
    )
    assert series[-1].annual_noi == pytest.approx(
        report.aggregate_annual_noi_projection
    )


def test_value_grows_monotonically_under_positive_appreciation():
    series = project_year_series(_analysis(), _profile())
    values = [p.portfolio_value for p in series]
    assert values == sorted(values)


def test_report_exposes_the_series():
    report = project_simulation(_analysis(), _profile())
    assert report.per_year, "SimulationReport must carry the per-year series"
    assert len(report.per_year) == _HORIZON + 1


def test_empty_portfolio_yields_a_flat_zero_series_not_a_crash():
    """Lenient by design: no holdings must not raise."""
    from datetime import datetime, timezone

    empty = PortfolioSummaryReport(
        portfolio_id="p0",
        generated_at=datetime.now(timezone.utc),
        holding_count=0,
        aggregates=_aggregates(),
        per_holding=[],
        attention=[],
        market_coverage=MarketCoverage(total=0, with_signals=0),
    )
    series = project_year_series(empty, _profile())
    assert len(series) == _HORIZON + 1
    assert all(p.portfolio_value == 0.0 for p in series)
