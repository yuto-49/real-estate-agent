from domain.reactions.models import ReactionVector
from domain.simulation.models import (
    CohortState,
    InvestorTrace,
    PolicyShock,
    PropertyState,
    SimConfig,
    SimSeed,
)
from domain.simulation.loop import run_simulation


def _make_seed() -> SimSeed:
    return SimSeed(
        initial_property=PropertyState(0.95, 85000, 15000, 840000, 1.4, 0.065, 13000000),
        initial_cohorts=(CohortState("1K_板橋", 30, ReactionVector(), 0.03, 0.1),),
        initial_investor=InvestorTrace(
            ReactionVector(investor_optimism=0.3), "HOLD", 0.8, "stable"
        ),
        depreciation_annual_shield=500000,
        shield_expires_round=8,
    )


def test_simulation_runs_to_completion():
    result = run_simulation(SimConfig(max_rounds=5), _make_seed())
    assert len(result.rounds) == 5
    assert result.final_property.occupancy_rate > 0


def test_simulation_with_rent_decline_shock():
    shock = PolicyShock(
        round_num=2, shock_type="rent_decline", magnitude=-0.10, label="家賃下落10%"
    )
    config = SimConfig(max_rounds=5, shocks=(shock,))
    result = run_simulation(config, _make_seed())
    round1_noi = result.rounds[0].property_state.annual_noi
    round3_noi = result.rounds[2].property_state.annual_noi
    assert round3_noi < round1_noi


def test_simulation_shield_expiry():
    result = run_simulation(SimConfig(max_rounds=10), _make_seed())
    round7_noi = result.rounds[6].property_state.annual_noi
    round9_noi = result.rounds[8].property_state.annual_noi
    # Shield expires at round 8 -- NOI should drop after
    assert round9_noi < round7_noi


def test_simulation_produces_replay_frames():
    result = run_simulation(SimConfig(max_rounds=3), _make_seed())
    for rnd in result.rounds:
        assert rnd.replay_frame is not None
        assert rnd.replay_frame.step == rnd.round_num
