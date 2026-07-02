"""Simulation orchestrator — bridges the pure-domain simulation loop with
the persistence layer (async DB reads) and the strategy-runner report format.
"""

from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import HoldingProjection, SimulationReport, StrategyProfile
from db.models import HoldingFinancials, PortfolioHolding
from domain.reactions.models import ReactionVector
from domain.simulation.loop import run_simulation
from domain.simulation.models import (
    CohortState,
    InvestorTrace,
    PropertyState,
    SimConfig,
    SimResult,
    SimSeed,
)

logger = structlog.get_logger(__name__)


async def build_sim_seed_from_holding(
    db: AsyncSession,
    holding_id: str,
) -> SimSeed | None:
    """Load a holding + financials from DB and build an initial SimSeed.

    Returns None if the holding or its financials cannot be found.
    """
    result = await db.execute(
        select(PortfolioHolding).where(PortfolioHolding.id == holding_id)
    )
    holding = result.scalar_one_or_none()
    if holding is None:
        logger.warning("sim_seed.holding_not_found", holding_id=holding_id)
        return None

    fin_result = await db.execute(
        select(HoldingFinancials).where(HoldingFinancials.holding_id == holding_id)
    )
    fin = fin_result.scalar_one_or_none()

    monthly_rent = fin.monthly_rent if fin and fin.monthly_rent else 80000.0
    vacancy = fin.vacancy_rate if fin and fin.vacancy_rate is not None else 0.05
    monthly_opex = fin.monthly_opex_estimate if fin and fin.monthly_opex_estimate else 15000.0
    current_value = fin.current_value_estimate if fin and fin.current_value_estimate else 10000000.0
    loan_balance = fin.loan_balance if fin and fin.loan_balance else 0.0

    occupancy = 1.0 - vacancy
    gross_annual = monthly_rent * 12 * occupancy
    annual_opex = monthly_opex * 12
    noi = gross_annual - annual_opex
    annual_debt_service = (fin.monthly_piti or 0.0) * 12
    dscr = noi / annual_debt_service if annual_debt_service > 0 else 0.0
    cap_rate = noi / current_value if current_value > 0 else 0.0

    initial_property = PropertyState(
        occupancy_rate=round(occupancy, 4),
        effective_monthly_rent=round(monthly_rent, 0),
        monthly_opex=round(monthly_opex, 0),
        annual_noi=round(noi, 0),
        dscr=round(dscr, 4),
        cap_rate=round(cap_rate, 6),
        assessed_value=round(current_value, 0),
    )

    default_cohort = CohortState(
        cohort_label=f"tenants_{holding.zip_code or 'unknown'}",
        size=10,
        reaction=ReactionVector(),
        churn_probability=vacancy,
        affordability_pressure_avg=0.0,
    )

    initial_investor = InvestorTrace(
        reaction=ReactionVector(investor_optimism=0.3),
        recommendation="HOLD",
        recommendation_score=0.7,
        rationale="initial seed",
    )

    return SimSeed(
        initial_property=initial_property,
        initial_cohorts=(default_cohort,),
        initial_investor=initial_investor,
    )


def sim_result_to_simulation_report(
    result: SimResult,
    portfolio_id: str,
    holding_id: str,
    address: str,
) -> SimulationReport:
    """Map a SimResult into the existing SimulationReport schema.

    This allows the unified simulation output to plug into
    ``reconcile_unified_report()`` seamlessly.
    """
    final = result.final_property
    projection = HoldingProjection(
        holding_id=holding_id,
        address=address,
        horizon_years=result.config.max_rounds,
        projected_value=final.assessed_value,
        projected_annual_noi=final.annual_noi,
        projected_cap_rate=final.cap_rate,
        projected_monthly_cash_flow=final.effective_monthly_rent * final.occupancy_rate - final.monthly_opex,
        projected_recommendation=result.final_investor.recommendation,
    )

    notes: list[str] = []
    if result.converged:
        notes.append(f"Converged at round {result.converged_at_round}")
    notes.append(f"Final recommendation: {result.final_investor.recommendation}")
    notes.append(f"Final DSCR: {final.dscr:.2f}")

    return SimulationReport(
        portfolio_id=portfolio_id,
        horizon_years=result.config.max_rounds,
        per_holding=[projection],
        aggregate_value_projection=final.assessed_value,
        aggregate_annual_noi_projection=final.annual_noi,
        aggregate_cap_rate_projection=final.cap_rate,
        notes=notes,
    )
