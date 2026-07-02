from domain.simulation.models import PolicyShock, SimConfig, PropertyState, SimSeed, SimResult, InvestorTrace, CohortState
from domain.reactions.models import ReactionVector


def test_policy_shock_frozen():
    shock = PolicyShock(round_num=3, shock_type="rent_decline", magnitude=-0.05, label="家賃下落5%")
    assert shock.round_num == 3
    assert shock.magnitude == -0.05


def test_sim_config_defaults():
    cfg = SimConfig()
    assert cfg.max_rounds == 20
    assert cfg.convergence_threshold == 0.02
    assert cfg.shocks == ()
    assert cfg.base_rent_growth_annual == 0.01


def test_property_state_frozen():
    ps = PropertyState(occupancy_rate=0.95, effective_monthly_rent=85000,
                       monthly_opex=15000, annual_noi=840000, dscr=1.4,
                       cap_rate=0.065, assessed_value=13000000)
    assert ps.annual_noi == 840000


def test_sim_result_immutable():
    seed = SimSeed(
        initial_property=PropertyState(0.95, 85000, 15000, 840000, 1.4, 0.065, 13000000),
        initial_cohorts=(),
        initial_investor=InvestorTrace(ReactionVector(), "HOLD", 0.8, "stable"),
    )
    result = SimResult(
        config=SimConfig(), seed=seed, rounds=(), converged=False,
        final_property=seed.initial_property,
        final_investor=seed.initial_investor, final_cohorts=(),
    )
    assert result.converged is False
