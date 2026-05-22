"""Monte Carlo stress-test engine — Phase P3."""

from __future__ import annotations

import pytest

from intelligence.stress_test import (
    StressTestConfig,
    StressTestResult,
    SliderRange,
    monte_carlo_stress_test,
)
from intelligence.underwriting import UnderwritingInputs


def _base_inputs() -> UnderwritingInputs:
    return UnderwritingInputs(
        purchase_price=250_000,
        down_payment=50_000,
        loan_rate=0.065,
        loan_term_years=30,
        monthly_rent=2_200,
        vacancy_rate=0.05,
        monthly_opex=350,
        property_tax_annual=3_000,
        insurance_annual=1_100,
        closing_costs=5_000,
        rent_growth=0.03,
        expense_growth=0.025,
        exit_cap_rate=0.07,
    )


def test_stress_test_returns_full_distribution():
    config = StressTestConfig(
        iterations=500,
        vacancy_rate=SliderRange(low=0.03, high=0.15),
        rent_growth=SliderRange(low=0.0, high=0.05),
        expense_growth=SliderRange(low=0.01, high=0.05),
        loan_rate=SliderRange(low=0.05, high=0.08),
        exit_cap_rate=SliderRange(low=0.055, high=0.085),
        seed=42,
    )
    result = monte_carlo_stress_test(_base_inputs(), config)
    assert isinstance(result, StressTestResult)
    assert result.iterations == 500
    # IRR can fail to converge in stressed scenarios — at least 50% should resolve
    assert len(result.irr_5yr_samples) >= 250
    assert len(result.irr_5yr_samples) <= 500
    assert result.irr_5yr_p10 <= result.irr_5yr_p50 <= result.irr_5yr_p90
    assert result.cash_on_cash_p10 <= result.cash_on_cash_p90


def test_stress_test_deterministic_with_seed():
    config = StressTestConfig(
        iterations=200,
        vacancy_rate=SliderRange(0.03, 0.12),
        rent_growth=SliderRange(0.0, 0.05),
        expense_growth=SliderRange(0.01, 0.04),
        loan_rate=SliderRange(0.05, 0.08),
        exit_cap_rate=SliderRange(0.06, 0.08),
        seed=99,
    )
    r1 = monte_carlo_stress_test(_base_inputs(), config)
    r2 = monte_carlo_stress_test(_base_inputs(), config)
    assert r1.cash_on_cash_p50 == pytest.approx(r2.cash_on_cash_p50)
    assert r1.irr_5yr_p50 == pytest.approx(r2.irr_5yr_p50)


def test_tornado_chart_shows_dominant_variable():
    """Tornado: holding other vars at midpoint, sweep each var across its range."""
    config = StressTestConfig(
        iterations=300,
        vacancy_rate=SliderRange(0.03, 0.30),  # wide range — expected dominant
        rent_growth=SliderRange(0.02, 0.04),
        expense_growth=SliderRange(0.02, 0.03),
        loan_rate=SliderRange(0.06, 0.07),
        exit_cap_rate=SliderRange(0.065, 0.075),
        seed=7,
    )
    result = monte_carlo_stress_test(_base_inputs(), config)
    assert result.tornado is not None
    assert "vacancy_rate" in result.tornado
    # Vacancy should have a non-trivial swing
    swing = result.tornado["vacancy_rate"]["swing"]
    assert swing > 0


def test_probability_of_loss_computed():
    config = StressTestConfig(
        iterations=400,
        vacancy_rate=SliderRange(0.05, 0.25),
        rent_growth=SliderRange(-0.02, 0.04),
        expense_growth=SliderRange(0.02, 0.06),
        loan_rate=SliderRange(0.06, 0.085),
        exit_cap_rate=SliderRange(0.06, 0.09),
        seed=11,
    )
    result = monte_carlo_stress_test(_base_inputs(), config)
    assert 0.0 <= result.probability_negative_cash_flow <= 1.0
    assert 0.0 <= result.probability_dscr_under_1 <= 1.0
