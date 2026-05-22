"""Unified report builder — Phase S7.

Reconciles the analysis-stage ``PortfolioSummaryReport`` against the
simulation-stage ``SimulationReport`` to answer one question:

    *does this strategy survive its own projection?*

Pure: no I/O, no Pydantic-side construction beyond schema validation.
"""

from __future__ import annotations

from api.schemas import (
    HoldingReconciliation,
    PortfolioSummaryReport,
    SimulationReport,
    StrategyProfile,
    UnifiedReport,
)


def _flip_note(today: str, projected: str) -> str | None:
    if today == projected:
        return None
    pairs = {
        ("HOLD", "SELL"): "projection turns this holding into a sell candidate",
        ("HOLD", "REFI"): "projection makes refinancing the dominant move",
        ("HOLD", "RAISE_RENT"): "rent growth assumption now favors pushing rent",
        ("HOLD", "IMPROVE"): "tenant protection thesis flips this to reinvest",
        ("REFI", "HOLD"): "loan-rate outlook removes the refi case",
        ("RAISE_RENT", "IMPROVE"): "tenant protection overrides the rent push",
        ("RAISE_RENT", "HOLD"): "projection no longer supports raising rent",
        ("SELL", "HOLD"): "projection stabilizes the holding",
        ("IMPROVE", "HOLD"): "projection no longer requires reinvestment",
    }
    return pairs.get((today, projected), f"recommendation flips: {today} → {projected}")


def reconcile_unified_report(
    analysis: PortfolioSummaryReport,
    simulation: SimulationReport,
    profile: StrategyProfile,
) -> UnifiedReport:
    """Build the unified report from one analysis + simulation pair."""
    today_by_id = {row.holding_id: row for row in analysis.per_holding}
    projection_by_id = {p.holding_id: p for p in simulation.per_holding}

    reconciliations: list[HoldingReconciliation] = []
    flips = 0
    for holding_id, today_row in today_by_id.items():
        proj = projection_by_id.get(holding_id)
        if proj is None:
            continue
        flipped = today_row.recommendation != proj.projected_recommendation
        if flipped:
            flips += 1
        reconciliations.append(
            HoldingReconciliation(
                holding_id=holding_id,
                address=today_row.address,
                today_action=today_row.recommendation,
                projected_action=proj.projected_recommendation,
                flipped=flipped,
                note=_flip_note(today_row.recommendation, proj.projected_recommendation),
            )
        )

    total = len(reconciliations)
    agreements: list[str] = []
    divergences: list[str] = []

    if total == 0:
        agreements.append("no holdings to reconcile")
    else:
        stable = total - flips
        agreements.append(
            f"{stable} of {total} holdings keep the same recommendation under projection"
        )
        if flips:
            divergences.append(
                f"{flips} of {total} holdings flip recommendation under projection"
            )

    if analysis.aggregates.blended_cap_rate > 0:
        agg_proj = simulation.aggregate_cap_rate_projection or 0.0
        if agg_proj > analysis.aggregates.blended_cap_rate:
            agreements.append(
                f"blended cap rate projects upward "
                f"({analysis.aggregates.blended_cap_rate:.3f} → {agg_proj:.3f})"
            )
        elif agg_proj < analysis.aggregates.blended_cap_rate * 0.85:
            divergences.append(
                f"blended cap rate compresses under projection "
                f"({analysis.aggregates.blended_cap_rate:.3f} → {agg_proj:.3f})"
            )

    if profile.policy_config.tenant_protection:
        agreements.append("tenant protection honored — RAISE_RENT actions suppressed")

    survives = flips <= max(1, total // 3) and not any(
        r.projected_action == "SELL" and r.today_action != "SELL"
        for r in reconciliations
    )
    confidence = 1.0 - (flips / total if total > 0 else 0.0)

    summary = _summary_text(survives, flips, total, profile)

    return UnifiedReport(
        portfolio_id=analysis.portfolio_id,
        horizon_years=simulation.horizon_years,
        survives=survives,
        confidence=round(confidence, 3),
        agreements=agreements,
        divergences=divergences,
        reconciliations=reconciliations,
        summary=summary,
    )


def _summary_text(
    survives: bool, flips: int, total: int, profile: StrategyProfile
) -> str:
    if total == 0:
        return "Strategy run produced no per-holding projections — portfolio is empty."
    if survives:
        return (
            f"Strategy survives {profile.assumptions.hold_period_years}-year "
            f"projection: {total - flips} of {total} holdings stable, "
            f"{flips} flip."
        )
    return (
        f"Strategy does not survive cleanly: {flips} of {total} holdings "
        f"flip recommendation under projection — review attention items."
    )
