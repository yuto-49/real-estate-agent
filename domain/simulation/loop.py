"""Unified simulation loop.

Composes shock translation, cohort reaction, property update, and investor
trace into a deterministic round-based pipeline.  Pure Python, no I/O.
"""

from __future__ import annotations

from datetime import datetime, timezone

from domain.reports.models import ReplayFrame
from domain.simulation.cohort_step import update_cohorts
from domain.simulation.investor_step import update_investor
from domain.simulation.models import (
    PolicyShock,
    SimConfig,
    SimResult,
    SimRound,
    SimSeed,
)
from domain.simulation.property_step import update_property
from domain.simulation.shocks import translate_shock


def _aggregate_churn(cohorts: tuple) -> float:
    """Weighted-average churn across cohorts."""
    if not cohorts:
        return 0.0
    total_size = sum(c.size for c in cohorts)
    if total_size == 0:
        return 0.0
    return sum(c.churn_probability * c.size for c in cohorts) / total_size


def _build_replay_frame(
    round_num: int,
    shocks: tuple[PolicyShock, ...],
    investor,
    prop,
) -> ReplayFrame:
    topic = shocks[0].shock_type if shocks else "tick"
    return ReplayFrame(
        step=round_num,
        occurred_at=datetime.now(timezone.utc),
        actor_id="investor",
        event_topic=topic,
        event_variable="annual_noi",
        event_delta=None,
        actor_vector=investor.reaction,
        aggregate_sentiment=round(investor.reaction.investor_optimism, 4),
        metadata={
            "recommendation": investor.recommendation,
            "noi": prop.annual_noi,
            "occupancy": prop.occupancy_rate,
            "dscr": prop.dscr,
            "cap_rate": prop.cap_rate,
        },
    )


def run_simulation(config: SimConfig, seed: SimSeed) -> SimResult:
    """Execute the unified simulation loop.

    Returns a :class:`SimResult` with one :class:`SimRound` per round.
    Convergence is detected when relative NOI change is below
    ``config.convergence_threshold`` for two consecutive rounds.
    """
    rounds: list[SimRound] = []
    prev_prop = seed.initial_property
    prev_investor = seed.initial_investor
    cohorts = seed.initial_cohorts
    converged = False
    converged_at: int | None = None
    consecutive_stable = 0

    per_round_rent = config.base_rent_growth_annual / config.max_rounds
    per_round_expense = config.base_expense_growth_annual / config.max_rounds
    per_round_appreciation = config.base_appreciation_annual / config.max_rounds

    for r in range(1, config.max_rounds + 1):
        # 1. Collect shocks for this round
        round_shocks = tuple(s for s in config.shocks if s.round_num == r)

        # Auto-inject shield_expiry if applicable
        if (
            seed.shield_expires_round is not None
            and r == seed.shield_expires_round
            and not any(s.shock_type == "shield_expiry" for s in round_shocks)
        ):
            round_shocks = round_shocks + (
                PolicyShock(
                    round_num=r,
                    shock_type="shield_expiry",
                    magnitude=0,
                    label="減価償却シールド期限切れ",
                ),
            )

        # 2. Translate shocks -> ReactionEvents
        all_events: list = []
        for shock in round_shocks:
            all_events.extend(translate_shock(shock))
        events_tuple = tuple(all_events)

        # 3. Update cohorts
        cohorts = update_cohorts(cohorts, events_tuple)

        # 4. Aggregate churn -> occupancy impact
        avg_churn = _aggregate_churn(cohorts)

        # 5. Compute deltas
        rent_delta = per_round_rent
        expense_delta = per_round_expense
        appreciation_delta = per_round_appreciation

        # Shock overrides on rent
        for shock in round_shocks:
            if shock.shock_type == "rent_decline":
                rent_delta += shock.magnitude
            elif shock.shock_type == "expense_spike":
                expense_delta += abs(shock.magnitude)

        # 6. Shield status
        shield_active = (
            seed.shield_expires_round is None or r < seed.shield_expires_round
        )
        shield_annual = seed.depreciation_annual_shield or 0.0

        # 7. Update property
        new_prop = update_property(
            prev=prev_prop,
            churn_rate=avg_churn,
            rent_delta=rent_delta,
            expense_delta=expense_delta,
            appreciation_delta=appreciation_delta,
            shield_active=shield_active,
            shield_annual=shield_annual,
            annual_debt_service=600000,
        )

        # 8. Update investor
        new_investor = update_investor(
            prev=prev_investor,
            prev_prop=prev_prop,
            new_prop=new_prop,
            events=events_tuple,
        )

        # 9. Build replay frame
        frame = _build_replay_frame(r, round_shocks, new_investor, new_prop)

        # 10. Record round
        rounds.append(
            SimRound(
                round_num=r,
                shocks_applied=round_shocks,
                property_state=new_prop,
                cohorts=cohorts,
                investor_trace=new_investor,
                replay_frame=frame,
            )
        )

        # 11. Convergence check
        if prev_prop.annual_noi != 0:
            rel_change = abs(new_prop.annual_noi - prev_prop.annual_noi) / abs(
                prev_prop.annual_noi
            )
            if rel_change < config.convergence_threshold:
                consecutive_stable += 1
            else:
                consecutive_stable = 0
            if consecutive_stable >= 2:
                converged = True
                converged_at = r
                break
        else:
            consecutive_stable = 0

        prev_prop = new_prop
        prev_investor = new_investor

    final_prop = rounds[-1].property_state if rounds else seed.initial_property
    final_inv = rounds[-1].investor_trace if rounds else seed.initial_investor
    final_cohorts = rounds[-1].cohorts if rounds else seed.initial_cohorts

    return SimResult(
        config=config,
        seed=seed,
        rounds=tuple(rounds),
        converged=converged,
        final_property=final_prop,
        final_investor=final_inv,
        final_cohorts=final_cohorts,
        converged_at_round=converged_at,
    )
