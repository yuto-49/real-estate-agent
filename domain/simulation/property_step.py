from __future__ import annotations

from domain.simulation.models import PropertyState


def update_property(
    prev: PropertyState,
    churn_rate: float,
    rent_delta: float,
    expense_delta: float,
    appreciation_delta: float,
    shield_active: bool,
    shield_annual: float,
    annual_debt_service: float,
) -> PropertyState:
    new_occupancy = max(0.0, min(1.0, prev.occupancy_rate * (1 - churn_rate)))
    new_rent = prev.effective_monthly_rent * (1 + rent_delta)
    new_opex = prev.monthly_opex * (1 + expense_delta)
    new_value = prev.assessed_value * (1 + appreciation_delta)

    gross_annual = new_rent * 12 * new_occupancy
    annual_opex = new_opex * 12
    noi = gross_annual - annual_opex

    if shield_active:
        noi += shield_annual

    dscr = noi / annual_debt_service if annual_debt_service > 0 else 0.0
    cap_rate = noi / new_value if new_value > 0 else 0.0

    return PropertyState(
        occupancy_rate=round(new_occupancy, 4),
        effective_monthly_rent=round(new_rent, 0),
        monthly_opex=round(new_opex, 0),
        annual_noi=round(noi, 0),
        dscr=round(dscr, 4),
        cap_rate=round(cap_rate, 6),
        assessed_value=round(new_value, 0),
    )
