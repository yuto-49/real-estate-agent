"""Broker orchestrator — generates disclosure-aware reports for 宅建業法 compliance."""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from domain.simulation.loop import run_simulation
from domain.simulation.models import SimConfig
from services.broker_report import BrokerDisclosureItem, BrokerReport
from services.sim_orchestrator import build_sim_seed_from_holding

logger = structlog.get_logger(__name__)

# In-memory store for broker reports
_reports: dict[str, BrokerReport] = {}


def _build_disclosure_checklist(
    sim_result,
) -> tuple[BrokerDisclosureItem, ...]:
    """Generate disclosure items based on simulation results."""
    items: list[BrokerDisclosureItem] = []

    final = sim_result.final_property

    # 重要事項説明 items
    items.append(
        BrokerDisclosureItem(
            category="重要事項説明",
            item="収益性予測の開示",
            status="confirmed",
            source="unified_simulation",
            note=f"NOI: ¥{final.annual_noi:,.0f}, Cap Rate: {final.cap_rate:.2%}",
        )
    )

    if final.dscr < 1.0:
        items.append(
            BrokerDisclosureItem(
                category="告知事項",
                item="債務返済能力リスク",
                status="flagged",
                source="unified_simulation",
                note=f"DSCR {final.dscr:.2f} — below 1.0 coverage threshold",
            )
        )

    if final.occupancy_rate < 0.85:
        items.append(
            BrokerDisclosureItem(
                category="告知事項",
                item="空室率リスク",
                status="flagged",
                source="unified_simulation",
                note=f"Projected occupancy {final.occupancy_rate:.0%}",
            )
        )

    # Check for severe shocks in simulation
    rec = sim_result.final_investor.recommendation
    if rec == "SELL":
        items.append(
            BrokerDisclosureItem(
                category="特約条件",
                item="シミュレーション結果: 売却推奨",
                status="flagged",
                source="unified_simulation",
                note=sim_result.final_investor.rationale,
            )
        )

    items.append(
        BrokerDisclosureItem(
            category="重要事項説明",
            item="シミュレーション前提条件",
            status="confirmed",
            source="unified_simulation",
            note=f"Rounds: {len(sim_result.rounds)}, Converged: {sim_result.converged}",
        )
    )

    return tuple(items)


async def generate_broker_report(
    db: AsyncSession,
    holding_id: str,
    listing_id: str,
    sim_config: SimConfig | None = None,
) -> BrokerReport | None:
    """Generate a broker report for a holding.

    Runs the unified simulation and produces a disclosure checklist
    for 宅建業法 compliance.
    """
    seed = await build_sim_seed_from_holding(db, holding_id)
    if seed is None:
        logger.warning("broker.holding_not_found", holding_id=holding_id)
        return None

    config = sim_config or SimConfig(max_rounds=20)
    sim_result = run_simulation(config, seed)

    checklist = _build_disclosure_checklist(sim_result)

    # Compute investor match score from simulation outcome
    final = sim_result.final_property
    match_score = min(1.0, max(0.0, (final.dscr / 2.0 + final.cap_rate * 5)))

    # Build ranked recommendations
    recs: list[str] = []
    recs.append(sim_result.final_investor.recommendation)
    if final.dscr < 1.2:
        recs.append("REFI")
    if final.occupancy_rate < 0.90:
        recs.append("IMPROVE")

    # Generate audit event ID
    audit_id = str(uuid.uuid4())

    warnings: list[str] = []
    flagged = [d for d in checklist if d.status == "flagged"]
    if flagged:
        warnings.append(f"{len(flagged)} disclosure item(s) flagged for review")
    if not sim_result.converged:
        warnings.append("Simulation did not converge within max rounds")

    report = BrokerReport(
        listing_id=listing_id,
        investor_match_score=round(match_score, 4),
        sim_result=sim_result,
        analyst_score=seed.analyst_score,
        disclosure_checklist=checklist,
        ranked_recommendations=tuple(dict.fromkeys(recs)),  # deduplicate, preserve order
        audit_event_ids=(audit_id,),
        warnings=tuple(warnings),
    )

    _reports[audit_id] = report
    return report


def get_broker_report(report_id: str) -> BrokerReport | None:
    """Retrieve a stored broker report by its audit ID."""
    return _reports.get(report_id)
