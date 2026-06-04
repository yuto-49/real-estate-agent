"""Phase 4 — Aparuto thesis end-to-end through the strategy runner.

The deterministic depreciation engine is unit-tested in
``test_depreciation_jp.py``. This module asserts the *integration*: that
``_project_holding`` calls ``project_depreciation`` correctly, folds the
shield into projected cash flow, and that the recommendation flips toward
SELL when the shield expires inside the hold horizon and cash flow is
shield-dependent.
"""

from __future__ import annotations

import pytest

from api.schemas import (
    StrategyAssumptions,
    StrategyPolicyConfig,
    StrategyProfile,
    StrategyThesis,
)
from services.strategy_runner import _project_holding


def _profile(
    *,
    hold_period_years: int = 10,
    marginal_tax_rate: float = 0.33,
    rent_growth: float = 0.03,
    expense_growth: float = 0.025,
) -> StrategyProfile:
    return StrategyProfile(
        assumptions=StrategyAssumptions(
            hold_period_years=hold_period_years,
            marginal_tax_rate=marginal_tax_rate,
            rent_growth=rent_growth,
            expense_growth=expense_growth,
        ),
        policy_config=StrategyPolicyConfig(),
        thesis=StrategyThesis(),
    )


def _summary_row(
    *,
    construction_type: str | None = None,
    building_basis_yen: float | None = None,
    building_age_years: int | None = None,
    current_value: float = 40_000_000.0,
    cap_rate: float = 0.07,
    monthly_cash_flow: float = 60_000.0,
) -> dict[str, object]:
    return {
        "holding_id": "h-test",
        "address": "東京都江戸川区テスト",
        "current_value": current_value,
        "cap_rate": cap_rate,
        "monthly_cash_flow": monthly_cash_flow,
        "construction_type": construction_type,
        "building_basis_yen": building_basis_yen,
        "building_age_years": building_age_years,
    }


class TestShieldComputation:
    def test_aparuto_wood_shield_populated(self):
        # 10-year-old wood, 25M basis, 33% rate, 10-yr hold
        # residual = (22-10) + 10×0.20 = 14 years → shield runs full horizon
        projection = _project_holding(
            _summary_row(
                construction_type="wood",
                building_basis_yen=25_000_000.0,
                building_age_years=10,
            ),
            _profile(hold_period_years=10),
        )
        assert projection.total_tax_shield_yen is not None
        assert projection.total_tax_shield_yen > 0
        assert projection.shield_expires_year == 14
        assert projection.shield_expired_in_horizon is False
        assert projection.annual_tax_shield_yen is not None
        # 25M / 14 × 0.33 ≈ 589,285
        assert projection.annual_tax_shield_yen == pytest.approx(
            (25_000_000 / 14) * 0.33, rel=0.01
        )

    def test_shield_skipped_when_construction_missing(self):
        projection = _project_holding(
            _summary_row(
                construction_type=None,
                building_basis_yen=25_000_000.0,
                building_age_years=10,
            ),
            _profile(),
        )
        assert projection.annual_tax_shield_yen is None
        assert projection.total_tax_shield_yen is None
        assert projection.shield_expires_year is None
        assert projection.shield_expired_in_horizon is False

    def test_shield_skipped_when_basis_missing(self):
        projection = _project_holding(
            _summary_row(
                construction_type="wood",
                building_basis_yen=None,
                building_age_years=10,
            ),
            _profile(),
        )
        assert projection.annual_tax_shield_yen is None

    def test_shield_skipped_when_age_missing(self):
        projection = _project_holding(
            _summary_row(
                construction_type="wood",
                building_basis_yen=25_000_000.0,
                building_age_years=None,
            ),
            _profile(),
        )
        assert projection.annual_tax_shield_yen is None


class TestShieldFoldedIntoCashFlow:
    def test_wood_shield_lifts_projected_cash_flow(self):
        # Same row, with and without construction info — shield should add to CF.
        row_with = _summary_row(
            construction_type="wood",
            building_basis_yen=25_000_000.0,
            building_age_years=10,
            monthly_cash_flow=60_000.0,
        )
        row_without = _summary_row(
            construction_type=None,
            building_basis_yen=None,
            building_age_years=None,
            monthly_cash_flow=60_000.0,
        )
        with_shield = _project_holding(row_with, _profile(hold_period_years=10))
        without_shield = _project_holding(row_without, _profile(hold_period_years=10))
        assert with_shield.projected_monthly_cash_flow is not None
        assert without_shield.projected_monthly_cash_flow is not None
        delta = (
            with_shield.projected_monthly_cash_flow
            - without_shield.projected_monthly_cash_flow
        )
        # Monthly shield ≈ annual_shield / 12 ≈ 589,285 / 12 ≈ 49,107
        assert delta == pytest.approx((25_000_000 / 14) * 0.33 / 12.0, rel=0.01)


class TestAparutoThesisFlip:
    def test_recommendation_flips_to_sell_when_shield_expires_and_cf_thin(self):
        # 20-year-old wood, 5M basis (small building), 15-yr hold
        # residual = (22-20) + 20×0.20 = 6 years → expires in horizon
        # Tiny monthly CF (5,000 yen) — shield is the whole story
        projection = _project_holding(
            _summary_row(
                construction_type="wood",
                building_basis_yen=5_000_000.0,
                building_age_years=20,
                monthly_cash_flow=5_000.0,
            ),
            _profile(hold_period_years=15),
        )
        assert projection.shield_expired_in_horizon is True
        # Even though shield adds to CF during years 1-6, the rule flips when
        # post-shield CF would be ≤ 50,000 monthly. We're well under that.
        assert projection.projected_recommendation == "SELL"

    def test_recommendation_holds_when_cf_survives_shield_expiry(self):
        # Same wood + age, but with strong organic CF that survives expiry
        projection = _project_holding(
            _summary_row(
                construction_type="wood",
                building_basis_yen=5_000_000.0,
                building_age_years=20,
                monthly_cash_flow=200_000.0,  # robust CF independent of shield
            ),
            _profile(hold_period_years=15),
        )
        assert projection.shield_expired_in_horizon is True
        # Cash flow comfortably above the 50,000 threshold post-shield
        assert projection.projected_recommendation == "HOLD"


class TestAparutoVsRcThesis:
    def test_wood_yields_higher_annual_shield_than_rc(self):
        # Same basis (50M), same age (10), same rate (33%), same 10-yr hold
        # Wood: residual 14 yrs → 50M/14 × 0.33 ≈ 1,178,571/yr (full horizon)
        # RC: residual = (47-10) + 10×0.20 = 39 yrs → 50M/39 × 0.33 ≈ 423,077/yr
        wood_proj = _project_holding(
            _summary_row(
                construction_type="wood",
                building_basis_yen=50_000_000.0,
                building_age_years=10,
            ),
            _profile(hold_period_years=10),
        )
        rc_proj = _project_holding(
            _summary_row(
                construction_type="rc",
                building_basis_yen=50_000_000.0,
                building_age_years=10,
            ),
            _profile(hold_period_years=10),
        )
        assert wood_proj.annual_tax_shield_yen is not None
        assert rc_proj.annual_tax_shield_yen is not None
        # Wood shield is materially larger per year — this is the Aparuto pitch.
        assert wood_proj.annual_tax_shield_yen > rc_proj.annual_tax_shield_yen * 2.5
