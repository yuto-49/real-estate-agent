from domain.simulation.models import PropertyState
from domain.simulation.property_step import update_property


def test_occupancy_drop_reduces_noi():
    prev = PropertyState(0.95, 85000, 15000, 840000, 1.4, 0.065, 13000000)
    common = dict(
        rent_delta=0.0,
        expense_delta=0.0,
        appreciation_delta=0.0,
        shield_active=True,
        shield_annual=500000,
        annual_debt_service=600000,
    )
    baseline = update_property(prev, churn_rate=0.0, **common)
    updated = update_property(prev, churn_rate=0.10, **common)
    assert updated.occupancy_rate < prev.occupancy_rate
    assert updated.annual_noi < baseline.annual_noi


def test_rent_increase_raises_noi():
    prev = PropertyState(0.95, 85000, 15000, 840000, 1.4, 0.065, 13000000)
    updated = update_property(
        prev,
        churn_rate=0.0,
        rent_delta=0.05,
        expense_delta=0.0,
        appreciation_delta=0.0,
        shield_active=True,
        shield_annual=500000,
        annual_debt_service=600000,
    )
    assert updated.effective_monthly_rent > prev.effective_monthly_rent
    assert updated.annual_noi > prev.annual_noi
