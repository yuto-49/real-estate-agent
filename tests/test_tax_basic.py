"""Basic tax modeling tests — Phase P2."""

from __future__ import annotations

import pytest

from intelligence.tax_basic import (
    annual_depreciation,
    capital_gains_tax,
    after_tax_sale_proceeds,
)


def test_straight_line_depreciation_residential():
    """Residential: 27.5y straight-line on building value (land excluded)."""
    # Building value $220k, 80/20 split on $275k purchase, land $55k
    dep = annual_depreciation(building_value=220_000, useful_life_years=27.5)
    assert dep == pytest.approx(8_000)


def test_depreciation_zero_when_no_building_value():
    assert annual_depreciation(building_value=0) == 0.0


def test_capital_gains_tax_long_term():
    """Long-term cap gains @ 15% on $50k gain = $7,500."""
    tax = capital_gains_tax(
        sale_price=350_000,
        adjusted_basis=300_000,
        long_term=True,
        long_term_rate=0.15,
        short_term_rate=0.32,
    )
    assert tax == pytest.approx(7_500)


def test_capital_gains_tax_short_term_higher():
    short = capital_gains_tax(
        sale_price=350_000,
        adjusted_basis=300_000,
        long_term=False,
        long_term_rate=0.15,
        short_term_rate=0.32,
    )
    assert short == pytest.approx(16_000)


def test_capital_gains_tax_no_gain():
    """No gain → no tax."""
    tax = capital_gains_tax(
        sale_price=300_000, adjusted_basis=320_000, long_term=True
    )
    assert tax == 0.0


def test_after_tax_proceeds_subtracts_tax_and_costs():
    proceeds = after_tax_sale_proceeds(
        sale_price=400_000,
        loan_balance=200_000,
        adjusted_basis=300_000,
        selling_costs_pct=0.06,
        long_term=True,
    )
    # gross: 400k - 24k selling - 200k loan = 176k
    # gain: 400k - 24k - 300k = 76k → tax: 76k * 0.15 = 11.4k
    # net: 176k - 11.4k = 164.6k
    assert proceeds == pytest.approx(164_600)
