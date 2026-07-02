"""Tests for services.sim_orchestrator — seed builder and report mapper."""

import pytest
from domain.reactions.models import ReactionVector
from domain.simulation.loop import run_simulation
from domain.simulation.models import (
    CohortState,
    InvestorTrace,
    PropertyState,
    SimConfig,
    SimSeed,
)
from services.sim_orchestrator import sim_result_to_simulation_report


def _make_seed() -> SimSeed:
    return SimSeed(
        initial_property=PropertyState(0.95, 85000, 15000, 840000, 1.4, 0.065, 13000000),
        initial_cohorts=(CohortState("test", 30, ReactionVector(), 0.03, 0.1),),
        initial_investor=InvestorTrace(ReactionVector(investor_optimism=0.3), "HOLD", 0.8, "stable"),
    )


def test_sim_result_to_report_basic():
    result = run_simulation(SimConfig(max_rounds=5), _make_seed())
    report = sim_result_to_simulation_report(result, "port-1", "hold-1", "Test Address")
    assert report.portfolio_id == "port-1"
    assert len(report.per_holding) == 1
    assert report.per_holding[0].holding_id == "hold-1"
    assert report.per_holding[0].projected_recommendation in {"HOLD", "SELL", "REFI", "IMPROVE"}


def test_sim_result_preserves_horizon():
    result = run_simulation(SimConfig(max_rounds=8), _make_seed())
    report = sim_result_to_simulation_report(result, "port-2", "hold-2", "addr-2")
    assert report.horizon_years == 8
