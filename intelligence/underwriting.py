"""Single-property underwriting engine for individual investors.

Pure-function module. All money in USD; rates as decimal fractions.

Inputs:
- Purchase price, down payment, loan terms (rate, term years)
- Operating: monthly rent, vacancy, opex, taxes, insurance, closing costs
- Growth: rent growth, expense growth, appreciation, exit cap (for IRR)

Outputs (UnderwritingResult, frozen dataclass):
- monthly_piti, annual_debt_service
- effective_gross_income, annual_noi
- cap_rate, cash_on_cash, dscr
- breakeven_occupancy
- irr_5yr, irr_10yr (None when loan terms make IRR ill-defined)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

# Optional dependency — pure-Python IRR fallback if numpy missing
try:
    import numpy as _np  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover
    _np = None


MONTHS_PER_YEAR: Final[int] = 12


@dataclass(frozen=True, slots=True)
class UnderwritingInputs:
    purchase_price: float
    down_payment: float
    loan_rate: float = 0.0  # annual decimal, e.g. 0.065
    loan_term_years: int = 30
    monthly_rent: float = 0.0
    vacancy_rate: float = 0.05
    monthly_opex: float = 0.0
    property_tax_annual: float = 0.0
    insurance_annual: float = 0.0
    closing_costs: float = 0.0
    rent_growth: float = 0.03
    expense_growth: float = 0.025
    appreciation: float = 0.03
    exit_cap_rate: float = 0.07
    selling_costs_pct: float = 0.06


@dataclass(frozen=True, slots=True)
class UnderwritingResult:
    monthly_piti: float
    annual_debt_service: float
    effective_gross_income: float
    annual_noi: float
    cap_rate: float
    cash_on_cash: float
    dscr: float
    breakeven_occupancy: float
    initial_equity: float
    irr_5yr: float | None
    irr_10yr: float | None
    cash_flow_path: tuple[float, ...] = field(default_factory=tuple)


# ── helpers ──────────────────────────────────────────────────────────────


def _monthly_mortgage_payment(
    principal: float, annual_rate: float, term_years: int
) -> float:
    """Standard amortizing payment formula. Returns 0 when no loan."""
    if principal <= 0:
        return 0.0
    if annual_rate <= 0:
        return principal / (term_years * MONTHS_PER_YEAR)
    r = annual_rate / MONTHS_PER_YEAR
    n = term_years * MONTHS_PER_YEAR
    return principal * (r * (1 + r) ** n) / ((1 + r) ** n - 1)


def _npv(cash_flows: list[float], rate: float) -> float:
    total = 0.0
    for t, cf in enumerate(cash_flows):
        try:
            total += cf / ((1.0 + rate) ** t)
        except (OverflowError, ZeroDivisionError):
            return float("inf") if cf > 0 else float("-inf")
    return total


def _irr(cash_flows: list[float]) -> float | None:
    """Compute IRR for a cash-flow series via bisection.

    Search range [-0.99, 10.0]. Returns None when:
    - All flows have the same sign (no IRR exists)
    - Bisection fails to bracket a sign change
    """
    if not cash_flows:
        return None
    pos = any(cf > 0 for cf in cash_flows)
    neg = any(cf < 0 for cf in cash_flows)
    if not (pos and neg):
        return None

    low, high = -0.99, 10.0
    f_low = _npv(cash_flows, low)
    f_high = _npv(cash_flows, high)
    if f_low == 0:
        return low
    if f_high == 0:
        return high
    # If both have same sign, scan for a bracket
    if f_low * f_high > 0:
        bracket: tuple[float, float] | None = None
        prev_rate = low
        prev_val = f_low
        for step in range(1, 1000):
            r = low + step * (high - low) / 1000.0
            v = _npv(cash_flows, r)
            if v == 0:
                return r
            if v * prev_val < 0:
                bracket = (prev_rate, r)
                break
            prev_rate, prev_val = r, v
        if bracket is None:
            return None
        low, high = bracket
        f_low = _npv(cash_flows, low)
        f_high = _npv(cash_flows, high)

    for _ in range(200):
        mid = (low + high) / 2.0
        f_mid = _npv(cash_flows, mid)
        if abs(f_mid) < 1e-6 or (high - low) < 1e-7:
            return mid
        if f_mid * f_low < 0:
            high, f_high = mid, f_mid
        else:
            low, f_low = mid, f_mid
    return (low + high) / 2.0


# ── main entry point ────────────────────────────────────────────────────


def underwrite(inputs: UnderwritingInputs) -> UnderwritingResult:
    """Project core underwriting metrics from inputs.

    Operating numbers reflect year-1 stabilized. IRR is computed over a hold
    period assuming straight-line growth and a sale at exit cap on year-N NOI.
    """
    loan_principal = max(inputs.purchase_price - inputs.down_payment, 0.0)
    monthly_piti = _monthly_mortgage_payment(
        loan_principal, inputs.loan_rate, inputs.loan_term_years
    )
    annual_debt_service = monthly_piti * MONTHS_PER_YEAR

    gross_rent = inputs.monthly_rent * MONTHS_PER_YEAR
    vacancy_loss = gross_rent * inputs.vacancy_rate
    egi = gross_rent - vacancy_loss

    opex_annual = (
        inputs.monthly_opex * MONTHS_PER_YEAR
        + inputs.property_tax_annual
        + inputs.insurance_annual
    )
    annual_noi = egi - opex_annual

    cap_rate = (annual_noi / inputs.purchase_price) if inputs.purchase_price > 0 else 0.0

    initial_cash = inputs.down_payment + inputs.closing_costs
    annual_cf = annual_noi - annual_debt_service
    cash_on_cash = (annual_cf / initial_cash) if initial_cash > 0 else 0.0

    dscr = (
        (annual_noi / annual_debt_service)
        if annual_debt_service > 0
        else float("inf")
    )

    # Breakeven occupancy = (opex + DS) / gross_rent
    breakeven_occupancy = (
        (opex_annual + annual_debt_service) / gross_rent
        if gross_rent > 0
        else 0.0
    )

    # IRR — project N years of cash flow + sale proceeds at exit cap
    irr_5 = _project_irr(inputs, hold_years=5, initial_cash=initial_cash, loan_principal=loan_principal, annual_ds=annual_debt_service)
    irr_10 = _project_irr(inputs, hold_years=10, initial_cash=initial_cash, loan_principal=loan_principal, annual_ds=annual_debt_service)

    return UnderwritingResult(
        monthly_piti=monthly_piti,
        annual_debt_service=annual_debt_service,
        effective_gross_income=egi,
        annual_noi=annual_noi,
        cap_rate=cap_rate,
        cash_on_cash=cash_on_cash,
        dscr=dscr,
        breakeven_occupancy=breakeven_occupancy,
        initial_equity=initial_cash,
        irr_5yr=irr_5,
        irr_10yr=irr_10,
    )


def _project_irr(
    inp: UnderwritingInputs,
    *,
    hold_years: int,
    initial_cash: float,
    loan_principal: float,
    annual_ds: float,
) -> float | None:
    """Project IRR over hold period assuming straight-line growth + sale."""
    if initial_cash <= 0:
        return None

    rent_y1 = inp.monthly_rent * MONTHS_PER_YEAR
    opex_y1 = (
        inp.monthly_opex * MONTHS_PER_YEAR
        + inp.property_tax_annual
        + inp.insurance_annual
    )

    cash_flows: list[float] = [-initial_cash]
    for year in range(1, hold_years + 1):
        rent_y = rent_y1 * ((1 + inp.rent_growth) ** (year - 1))
        opex_y = opex_y1 * ((1 + inp.expense_growth) ** (year - 1))
        noi_y = rent_y * (1 - inp.vacancy_rate) - opex_y
        cf = noi_y - annual_ds
        if year < hold_years:
            cash_flows.append(cf)
        else:
            # exit: NOI(year+1) / exit cap, less selling costs and remaining loan
            future_noi = (
                (rent_y * (1 + inp.rent_growth)) * (1 - inp.vacancy_rate)
                - (opex_y * (1 + inp.expense_growth))
            )
            exit_value = (
                (future_noi / inp.exit_cap_rate)
                if inp.exit_cap_rate > 0
                else inp.purchase_price * ((1 + inp.appreciation) ** hold_years)
            )
            selling_costs = exit_value * inp.selling_costs_pct
            # Approximate remaining loan: simplified — assume interest-only treatment
            # for IRR signal purposes (good enough for an investor preview).
            net_sale = exit_value - selling_costs - loan_principal
            cash_flows.append(cf + net_sale)

    return _irr(cash_flows)


__all__ = ["UnderwritingInputs", "UnderwritingResult", "underwrite"]
