"""Basic US tax modeling for individual investors.

Scope:
- Straight-line depreciation (27.5y residential default)
- Long-term / short-term capital gains
- After-tax sale proceeds

Out of scope (deferred to v2):
- 1031 exchanges
- Cost segregation
- Opportunity zones
- Depreciation recapture nuances (assumed flat)
- State-level taxes
"""

from __future__ import annotations

from typing import Final

RESIDENTIAL_USEFUL_LIFE_YEARS: Final[float] = 27.5
DEFAULT_LONG_TERM_RATE: Final[float] = 0.15
DEFAULT_SHORT_TERM_RATE: Final[float] = 0.32


def annual_depreciation(
    building_value: float, useful_life_years: float = RESIDENTIAL_USEFUL_LIFE_YEARS
) -> float:
    """Straight-line annual depreciation deduction.

    Land is NOT depreciable — pass only the building portion of cost basis.
    """
    if building_value <= 0 or useful_life_years <= 0:
        return 0.0
    return building_value / useful_life_years


def capital_gains_tax(
    sale_price: float,
    adjusted_basis: float,
    *,
    long_term: bool = True,
    long_term_rate: float = DEFAULT_LONG_TERM_RATE,
    short_term_rate: float = DEFAULT_SHORT_TERM_RATE,
) -> float:
    """Capital gains tax on the sale of a property.

    Negative gains (losses) → tax = 0.
    """
    gain = sale_price - adjusted_basis
    if gain <= 0:
        return 0.0
    rate = long_term_rate if long_term else short_term_rate
    return gain * rate


def after_tax_sale_proceeds(
    sale_price: float,
    loan_balance: float,
    adjusted_basis: float,
    *,
    selling_costs_pct: float = 0.06,
    long_term: bool = True,
    long_term_rate: float = DEFAULT_LONG_TERM_RATE,
    short_term_rate: float = DEFAULT_SHORT_TERM_RATE,
) -> float:
    """Net proceeds to the seller after costs, loan payoff, and taxes.

    Selling-costs (agent fees, transfer tax) are deducted from the sale price
    before computing the taxable gain (matches IRS convention).
    """
    selling_costs = sale_price * selling_costs_pct
    amount_realized = sale_price - selling_costs
    gain = max(amount_realized - adjusted_basis, 0.0)
    rate = long_term_rate if long_term else short_term_rate
    tax = gain * rate
    return amount_realized - loan_balance - tax


__all__ = [
    "RESIDENTIAL_USEFUL_LIFE_YEARS",
    "annual_depreciation",
    "capital_gains_tax",
    "after_tax_sale_proceeds",
]
