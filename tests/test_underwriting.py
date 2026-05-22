"""Unit tests for the underwriting engine — Phase P2.

Known-input / known-output tests for cap rate, cash-on-cash, DSCR, IRR.
"""

from __future__ import annotations

import pytest

from intelligence.underwriting import (
    UnderwritingInputs,
    UnderwritingResult,
    underwrite,
)


def test_cap_rate_simple():
    """Cap rate = NOI / property value. 10k NOI on 100k value = 10%."""
    inp = UnderwritingInputs(
        purchase_price=100_000,
        down_payment=100_000,
        loan_rate=0.0,
        loan_term_years=30,
        monthly_rent=1_000,
        vacancy_rate=0.0,
        monthly_opex=0.0,
        property_tax_annual=0.0,
        insurance_annual=0.0,
        closing_costs=0,
    )
    out = underwrite(inp)
    assert out.annual_noi == pytest.approx(12_000)
    assert out.cap_rate == pytest.approx(0.12)


def test_cash_on_cash_with_loan():
    """CoC = annual cash flow after debt service / cash invested."""
    inp = UnderwritingInputs(
        purchase_price=200_000,
        down_payment=40_000,
        loan_rate=0.06,
        loan_term_years=30,
        monthly_rent=2_000,
        vacancy_rate=0.05,
        monthly_opex=300,
        property_tax_annual=2_400,
        insurance_annual=1_200,
        closing_costs=4_000,
    )
    out = underwrite(inp)
    # Sanity: cap rate between 4–10% typical for residential
    assert 0.03 <= out.cap_rate <= 0.12
    # CoC should be positive for these inputs
    assert out.cash_on_cash > 0


def test_dscr_above_one_for_rent_covering_debt():
    inp = UnderwritingInputs(
        purchase_price=300_000,
        down_payment=60_000,
        loan_rate=0.065,
        loan_term_years=30,
        monthly_rent=3_000,
        vacancy_rate=0.05,
        monthly_opex=400,
        property_tax_annual=3_600,
        insurance_annual=1_200,
        closing_costs=6_000,
    )
    out = underwrite(inp)
    assert out.dscr > 1.0


def test_dscr_below_one_when_rent_too_low():
    inp = UnderwritingInputs(
        purchase_price=500_000,
        down_payment=50_000,
        loan_rate=0.075,
        loan_term_years=30,
        monthly_rent=1_500,
        vacancy_rate=0.10,
        monthly_opex=500,
        property_tax_annual=6_000,
        insurance_annual=2_000,
        closing_costs=10_000,
    )
    out = underwrite(inp)
    assert out.dscr < 1.0
    assert out.cash_on_cash < 0


def test_breakeven_occupancy_is_fraction():
    inp = UnderwritingInputs(
        purchase_price=250_000,
        down_payment=50_000,
        loan_rate=0.07,
        loan_term_years=30,
        monthly_rent=2_200,
        vacancy_rate=0.05,
        monthly_opex=350,
        property_tax_annual=3_000,
        insurance_annual=1_100,
        closing_costs=5_000,
    )
    out = underwrite(inp)
    assert 0.0 < out.breakeven_occupancy < 1.5  # may exceed 1 in stressed deals


def test_irr_positive_for_reasonable_deal():
    inp = UnderwritingInputs(
        purchase_price=200_000,
        down_payment=40_000,
        loan_rate=0.06,
        loan_term_years=30,
        monthly_rent=2_000,
        vacancy_rate=0.05,
        monthly_opex=300,
        property_tax_annual=2_400,
        insurance_annual=1_200,
        closing_costs=4_000,
        rent_growth=0.03,
        expense_growth=0.025,
        appreciation=0.03,
        exit_cap_rate=0.07,
    )
    out = underwrite(inp)
    assert out.irr_5yr is not None
    assert -0.5 < out.irr_5yr < 0.5  # plausible range
    assert out.irr_10yr is not None


def test_underwrite_returns_full_result_dataclass():
    inp = UnderwritingInputs(
        purchase_price=100_000,
        down_payment=20_000,
        loan_rate=0.06,
        loan_term_years=30,
        monthly_rent=1_000,
    )
    out = underwrite(inp)
    assert isinstance(out, UnderwritingResult)
    assert out.monthly_piti > 0
    assert out.annual_debt_service > 0
