"""Strategy runner — Phase S6.

Chains the analysis stage (portfolio summary parametrized by the user's
profile) into a simulation stage that projects each holding forward under
the profile's assumptions. Runs as a background job; callers poll for
status and fetch the result.

State lives in a module-level dict guarded by an ``asyncio.Lock`` —
matches the pattern used by ``services/batch_simulator.py``. Tests can
inspect or reset the store via the helpers at the bottom of this module.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from typing import Protocol

from api.schemas import (
    HoldingProjection,
    PortfolioSummaryReport,
    SimulationReport,
    StrategyProfile,
    StrategyRunRecord,
    StrategyRunStep,
)
from db.models import ConstructionType
from intelligence.depreciation_jp import project_depreciation
from services.event_store import EventStore
from services.portfolio_summary import build_portfolio_summary


class StrategyEventSink(Protocol):
    """Anything that can absorb a strategy step event.

    Production: a wrapper over ``EventBus.publish_strategy_step``. Tests pass
    a list-recording stub. ``None`` is also accepted by the runner — passes
    through silently.
    """

    async def publish_strategy_step(
        self, run_id: str, event_type: str, payload: dict
    ) -> int: ...

# Investor-facing action labels (mirrors services.holding_decision).
_HOLD = "HOLD"
_RAISE_RENT = "RAISE_RENT"
_REFI = "REFI"
_SELL = "SELL"
_IMPROVE = "IMPROVE"

# In-memory store. Production would use Redis; tests reset between runs.
_store: dict[str, StrategyRunRecord] = {}
_lock = asyncio.Lock()


# ── projection logic ─────────────────────────────────────────────────


def _market_outlook_modifier(outlook: str) -> float:
    """Per-year appreciation tilt driven by the user's market thesis."""
    return {"bullish": 0.02, "bearish": -0.015}.get(outlook, 0.0)


def _project_depreciation_shield(
    summary_row: dict[str, object],
    profile: StrategyProfile,
) -> tuple[float | None, float | None, int | None, bool]:
    """Run the depreciation engine when construction info is present.

    Returns ``(annual_shield_within_horizon, total_shield, expires_year,
    expired_in_horizon)``. ``annual_shield_within_horizon`` is the average
    yen-of-shield per year over the hold period (zero after expiry), so
    callers can fold it directly into projected cash flow.
    """
    construction = summary_row.get("construction_type")
    basis = summary_row.get("building_basis_yen")
    age = summary_row.get("building_age_years")
    if not isinstance(construction, str) or not isinstance(basis, (int, float)):
        return (None, None, None, False)
    if not isinstance(age, int) or basis <= 0:
        return (None, None, None, False)
    try:
        ctype = ConstructionType(construction)
    except ValueError:
        return (None, None, None, False)

    horizon = profile.assumptions.hold_period_years
    schedule = project_depreciation(
        construction=ctype,
        building_basis_yen=float(basis),
        building_age_years=age,
        marginal_tax_rate=profile.assumptions.marginal_tax_rate,
        horizon_years=horizon,
    )
    shield_in_horizon = sum(y.tax_shield_yen for y in schedule.years)
    avg_annual_in_horizon = shield_in_horizon / horizon if horizon > 0 else 0.0
    expired = schedule.shield_expires_year <= horizon
    return (
        avg_annual_in_horizon,
        schedule.total_shield_yen,
        schedule.shield_expires_year,
        expired,
    )


def _project_holding(
    summary_row: dict[str, object],
    profile: StrategyProfile,
) -> HoldingProjection:
    """Project one holding's metrics forward by the profile's hold period.

    ``summary_row`` is a dict of the relevant ``HoldingSummaryEntry`` fields —
    keeping this projection pure (no Pydantic dep) helps tests.
    """
    horizon = profile.assumptions.hold_period_years
    rent_growth = profile.assumptions.rent_growth
    expense_growth = profile.assumptions.expense_growth
    exit_cap = profile.assumptions.exit_cap_rate
    outlook_tilt = _market_outlook_modifier(profile.thesis.market_outlook)

    current_value = summary_row.get("current_value")
    today_cap = summary_row.get("cap_rate")
    today_cf = summary_row.get("monthly_cash_flow")

    # NOI grows with rent - expenses, weighted 50/50 toward each.
    noi_growth_factor = (1.0 + rent_growth - expense_growth) ** horizon
    appreciation_factor = (1.0 + 0.03 + outlook_tilt) ** horizon

    projected_value = (
        current_value * appreciation_factor
        if isinstance(current_value, (int, float)) and current_value > 0
        else None
    )

    if today_cap is not None and current_value is not None:
        today_noi = today_cap * current_value
        projected_noi: float | None = today_noi * noi_growth_factor
    else:
        projected_noi = None

    projected_cap = (
        projected_noi / projected_value
        if projected_noi is not None and projected_value and projected_value > 0
        else None
    )

    # Monthly cash flow scales with NOI growth (debt service approximately flat).
    if isinstance(today_cf, (int, float)):
        projected_cf: float | None = today_cf * noi_growth_factor
    else:
        projected_cf = None

    # Fold in the JP depreciation tax shield (Phase 4): annual shield ÷ 12
    # added to monthly cash flow. When the shield expires inside the horizon,
    # ``annual_shield_in_horizon`` already averages in the post-expiry zeros.
    annual_shield_in_horizon, total_shield, expires_year, expired_in_horizon = (
        _project_depreciation_shield(summary_row, profile)
    )
    if projected_cf is not None and annual_shield_in_horizon is not None:
        projected_cf = projected_cf + annual_shield_in_horizon / 12.0

    today_noi = (
        today_cap * current_value
        if isinstance(today_cap, (int, float)) and isinstance(current_value, (int, float))
        else None
    )
    projected_action = _project_recommendation(
        today_cap=today_cap if isinstance(today_cap, (int, float)) else None,
        projected_cap=projected_cap,
        today_noi=today_noi,
        projected_noi=projected_noi,
        projected_cf=projected_cf,
        exit_cap=exit_cap,
        profile=profile,
        shield_expired_in_horizon=expired_in_horizon,
    )

    return HoldingProjection(
        holding_id=str(summary_row["holding_id"]),
        address=str(summary_row["address"]),
        horizon_years=horizon,
        projected_value=projected_value,
        projected_annual_noi=projected_noi,
        projected_cap_rate=projected_cap,
        projected_monthly_cash_flow=projected_cf,
        projected_recommendation=projected_action,
        annual_tax_shield_yen=annual_shield_in_horizon,
        total_tax_shield_yen=total_shield,
        shield_expires_year=expires_year,
        shield_expired_in_horizon=expired_in_horizon,
    )


def _project_recommendation(
    *,
    today_cap: float | None,
    projected_cap: float | None,
    today_noi: float | None,
    projected_noi: float | None,
    projected_cf: float | None,
    exit_cap: float,
    profile: StrategyProfile,
    shield_expired_in_horizon: bool = False,
) -> str:
    """Pick the recommended action for a holding under the projection.

    Rule order is deliberate — checked top to bottom, first match wins.
    """
    # 1. Cash flow goes negative under projection — strongest sell signal.
    if projected_cf is not None and projected_cf < 0:
        return _SELL
    # 2. NOI declines meaningfully in nominal terms — sell signal.
    if (
        today_noi is not None
        and projected_noi is not None
        and projected_noi < today_noi * 0.9
    ):
        return _SELL
    # 2b. Aparuto thesis check: shield expires before hold horizon ends AND
    # cash flow is razor-thin (≤ 0.5× the pre-shield daily-equivalent) — the
    # cash-flow story is largely shield-driven and won't survive expiry.
    if shield_expired_in_horizon and (projected_cf is None or projected_cf < 50_000):
        return _SELL
    # 3. Refinance lever — explicit loan-rate outlook above the threshold.
    if (
        profile.assumptions.loan_rate_outlook is not None
        and profile.assumptions.loan_rate_outlook > profile.policy_config.refi_rate_threshold
    ):
        return _REFI
    # 4. Tenant protection — reinvest when cap rate rises, otherwise hold.
    if profile.policy_config.tenant_protection:
        if (
            today_cap is not None
            and projected_cap is not None
            and projected_cap > today_cap
        ):
            return _IMPROVE
        return _HOLD
    # 5. User explicitly biased toward pushing rents.
    if profile.policy_config.raise_rent_bias > 0.2:
        return _RAISE_RENT
    # 6. Severe cap-rate collapse (yields evaporate) — last sell trigger.
    if projected_cap is not None and projected_cap < exit_cap * 0.4:
        return _SELL
    return _HOLD


def project_simulation(
    analysis: PortfolioSummaryReport, profile: StrategyProfile
) -> SimulationReport:
    """Pure simulation projection — testable without a database."""
    horizon = profile.assumptions.hold_period_years

    projections: list[HoldingProjection] = []
    total_projected_value = 0.0
    total_projected_noi = 0.0
    for row in analysis.per_holding:
        proj = _project_holding(row.model_dump(), profile)
        projections.append(proj)
        if proj.projected_value:
            total_projected_value += proj.projected_value
        if proj.projected_annual_noi:
            total_projected_noi += proj.projected_annual_noi

    aggregate_cap = (
        total_projected_noi / total_projected_value
        if total_projected_value > 0
        else None
    )

    notes: list[str] = []
    if profile.thesis.trajectory != "none":
        notes.append(
            f"thesis trajectory '{profile.thesis.trajectory}' applied to neighborhood reactions"
        )
    if profile.policy_config.tenant_protection:
        notes.append("tenant protection on — RAISE_RENT actions suppressed")
    if profile.assumptions.loan_rate_outlook is not None:
        notes.append(
            f"loan rate outlook {profile.assumptions.loan_rate_outlook:.3f} vs "
            f"refi threshold {profile.policy_config.refi_rate_threshold:.3f}"
        )

    return SimulationReport(
        portfolio_id=analysis.portfolio_id,
        horizon_years=horizon,
        per_holding=projections,
        aggregate_value_projection=total_projected_value,
        aggregate_annual_noi_projection=total_projected_noi,
        aggregate_cap_rate_projection=aggregate_cap,
        notes=notes,
    )


# ── run orchestration + store ────────────────────────────────────────


async def _set(record: StrategyRunRecord) -> None:
    async with _lock:
        _store[record.run_id] = record


async def get_strategy_run(run_id: str) -> StrategyRunRecord | None:
    async with _lock:
        return _store.get(run_id)


async def list_strategy_runs() -> list[StrategyRunRecord]:
    async with _lock:
        return list(_store.values())


async def reset_strategy_runs() -> None:
    """Test helper — empty the in-memory store."""
    async with _lock:
        _store.clear()


def _make_pending(run_id: str, portfolio_id: str, profile: StrategyProfile) -> StrategyRunRecord:
    return StrategyRunRecord(
        run_id=run_id,
        portfolio_id=portfolio_id,
        status="pending",
        profile=profile,
        started_at=datetime.now(timezone.utc),
    )


async def _emit_step(
    run_id: str,
    steps: list[StrategyRunStep],
    sink: StrategyEventSink | None,
    *,
    event_type: str,
    label: str,
    detail: str | None = None,
) -> StrategyRunStep:
    """Append a step to the trace and (best-effort) publish over pub/sub.

    Pub/sub failures never break the run — the trace remains durable on the
    record itself for HTTP polling clients.
    """
    step = StrategyRunStep(
        type=event_type,
        label=label,
        detail=detail,
        at=datetime.now(timezone.utc),
    )
    steps.append(step)
    if sink is not None:
        try:
            await sink.publish_strategy_step(
                run_id,
                event_type,
                {"label": label, "detail": detail, "at": step.at.isoformat()},
            )
        except Exception:
            # Pub/sub is fire-and-forget for the trace; ignore broker errors.
            pass
    return step


async def execute_strategy_run(
    db: AsyncSession,
    run_id: str,
    portfolio_id: str,
    profile: StrategyProfile,
    event_sink: StrategyEventSink | None = None,
    correlation_id: str | None = None,
) -> StrategyRunRecord:
    """Run analysis → simulation for one strategy run.

    Updates the store throughout — callers can poll ``get_strategy_run``.
    Returns the final record so synchronous callers (and tests) can use it
    directly. When ``event_sink`` is provided, emits per-step events for live
    timelines; otherwise the trace is still persisted on the record.

    Every run is also audited to ``domain_events`` (started + terminal) with
    ``correlation_id`` — the durable, queryable record of the state change.
    """
    record = await get_strategy_run(run_id)
    if record is None:
        record = _make_pending(run_id, portfolio_id, profile)
    steps: list[StrategyRunStep] = list(record.steps)
    store = EventStore(db)

    await _emit_step(
        run_id, steps, event_sink,
        event_type="run.started",
        label="Run started",
        detail=f"Portfolio {portfolio_id}",
    )
    running = record.model_copy(update={"status": "running", "steps": steps})
    await _set(running)
    await store.append(
        event_type="strategy.run_started",
        aggregate_type="strategy_run",
        aggregate_id=run_id,
        payload={"portfolio_id": portfolio_id},
        actor_type="investor",
        correlation_id=correlation_id,
    )
    await db.commit()

    try:
        analysis = await build_portfolio_summary(db, portfolio_id)
        if analysis is None:
            await _emit_step(
                run_id, steps, event_sink,
                event_type="run.failed",
                label="Portfolio not found",
                detail=portfolio_id,
            )
            failed = running.model_copy(
                update={
                    "status": "failed",
                    "error": "portfolio_not_found",
                    "completed_at": datetime.now(timezone.utc),
                    "steps": steps,
                }
            )
            await _set(failed)
            await store.append(
                event_type="strategy.run_failed",
                aggregate_type="strategy_run",
                aggregate_id=run_id,
                payload={"error": "portfolio_not_found"},
                actor_type="investor",
                correlation_id=correlation_id,
            )
            await db.commit()
            return failed

        await _emit_step(
            run_id, steps, event_sink,
            event_type="step.analysis_built",
            label="Analysis built",
            detail=f"{analysis.holding_count} holding(s)",
        )
        await _set(running.model_copy(update={"analysis": analysis, "steps": list(steps)}))

        simulation = project_simulation(analysis, profile)
        await _emit_step(
            run_id, steps, event_sink,
            event_type="step.simulation_projected",
            label="Simulation projected",
            detail=f"{simulation.horizon_years}y horizon, {len(simulation.per_holding)} holding(s)",
        )
        await _set(running.model_copy(
            update={"analysis": analysis, "simulation": simulation, "steps": list(steps)}
        ))

        # Lazy import to avoid a hard module-level dependency before S7 lands.
        from services.unified_report import reconcile_unified_report

        unified = reconcile_unified_report(analysis, simulation, profile)
        await _emit_step(
            run_id, steps, event_sink,
            event_type="step.unified_reconciled",
            label="Unified report reconciled",
            detail=f"{len(unified.reconciliations)} reconciliation row(s)",
        )

        await _emit_step(
            run_id, steps, event_sink,
            event_type="run.completed",
            label="Run completed",
        )
        completed = running.model_copy(
            update={
                "status": "completed",
                "analysis": analysis,
                "simulation": simulation,
                "unified": unified,
                "completed_at": datetime.now(timezone.utc),
                "steps": steps,
            }
        )
        await _set(completed)
        await store.append(
            event_type="strategy.run_completed",
            aggregate_type="strategy_run",
            aggregate_id=run_id,
            payload={
                "survives": unified.survives,
                "confidence": unified.confidence,
                "holding_count": analysis.holding_count,
            },
            actor_type="investor",
            correlation_id=correlation_id,
        )
        await db.commit()
        return completed

    except Exception as exc:  # noqa: BLE001 — surface as failure on the record
        await _emit_step(
            run_id, steps, event_sink,
            event_type="run.failed",
            label="Run failed",
            detail=str(exc) or exc.__class__.__name__,
        )
        failed = running.model_copy(
            update={
                "status": "failed",
                "error": str(exc) or exc.__class__.__name__,
                "completed_at": datetime.now(timezone.utc),
                "steps": steps,
            }
        )
        await _set(failed)
        # The exception may have left the session dirty — roll back before the
        # audit write so the failure event still persists. (run_started was
        # already committed.)
        try:
            await db.rollback()
            await store.append(
                event_type="strategy.run_failed",
                aggregate_type="strategy_run",
                aggregate_id=run_id,
                payload={"error": str(exc) or exc.__class__.__name__},
                actor_type="investor",
                correlation_id=correlation_id,
            )
            await db.commit()
        except Exception:  # noqa: BLE001 — never let auditing mask the failure
            pass
        return failed


async def start_strategy_run(
    portfolio_id: str, profile: StrategyProfile
) -> StrategyRunRecord:
    """Register a new strategy run in PENDING state and return it.

    Callers schedule ``execute_strategy_run`` against a real DB session in
    a background task.
    """
    run_id = str(uuid.uuid4())
    record = _make_pending(run_id, portfolio_id, profile)
    await _set(record)
    return record
