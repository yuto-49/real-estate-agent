"""Tests for broker report generation."""

from domain.reactions.models import ReactionVector
from domain.simulation.loop import run_simulation
from domain.simulation.models import (
    CohortState,
    InvestorTrace,
    PropertyState,
    SimConfig,
    SimSeed,
)
from services.broker_report import BrokerDisclosureItem, BrokerReport


def _make_seed() -> SimSeed:
    return SimSeed(
        initial_property=PropertyState(0.95, 85000, 15000, 840000, 1.4, 0.065, 13000000),
        initial_cohorts=(CohortState("test", 30, ReactionVector(), 0.03, 0.1),),
        initial_investor=InvestorTrace(
            ReactionVector(investor_optimism=0.3), "HOLD", 0.8, "stable"
        ),
    )


def test_broker_disclosure_has_required_items():
    result = run_simulation(SimConfig(max_rounds=5), _make_seed())
    from services.broker_orchestrator import _build_disclosure_checklist

    checklist = _build_disclosure_checklist(result)
    categories = {d.category for d in checklist}
    assert "重要事項説明" in categories


def test_broker_report_frozen():
    result = run_simulation(SimConfig(max_rounds=3), _make_seed())
    report = BrokerReport(
        listing_id="test-listing",
        investor_match_score=0.75,
        sim_result=result,
        analyst_score=None,
        disclosure_checklist=(),
        ranked_recommendations=("HOLD",),
        audit_event_ids=("test-audit-1",),
    )
    assert report.listing_id == "test-listing"
    assert report.investor_match_score == 0.75


def test_flagged_items_for_low_dscr():
    # Use a seed that will produce low DSCR
    seed = SimSeed(
        initial_property=PropertyState(0.60, 50000, 30000, 0, 0.5, 0.01, 5000000),
        initial_cohorts=(
            CohortState(
                "stressed",
                10,
                ReactionVector(affordability_pressure=0.5),
                0.15,
                0.5,
            ),
        ),
        initial_investor=InvestorTrace(
            ReactionVector(investor_optimism=-0.3), "SELL", 0.3, "distressed"
        ),
    )
    result = run_simulation(SimConfig(max_rounds=5), seed)
    from services.broker_orchestrator import _build_disclosure_checklist

    checklist = _build_disclosure_checklist(result)
    flagged = [d for d in checklist if d.status == "flagged"]
    assert len(flagged) > 0
