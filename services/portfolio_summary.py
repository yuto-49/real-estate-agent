"""Portfolio summary aggregator — Phase S2.

Fans out per-holding analysis (underwrite + decision) across an entire
portfolio and returns one ``PortfolioSummaryReport``. Pure composition over
existing services — no new domain logic.

The shape returned here is also the analysis seed consumed by the strategy
pipeline (Phase S6). Keep it stable.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import (
    HoldingSummaryEntry,
    MarketCoverage,
    PortfolioAttentionItem,
    PortfolioSummaryAggregates,
    PortfolioSummaryReport,
)
from db.models import (
    HoldingFinancials,
    InvestorPortfolio,
    PortfolioHolding,
)
from services.holding_decision import HOLD, compute_holding_decision

# Non-HOLD actions surface in the "attention" list.
_ATTENTION_ACTIONS: frozenset[str] = frozenset(
    {"SELL", "REFI", "IMPROVE", "RAISE_RENT"}
)


def _enum_value(value: object) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _per_holding_metrics(fin: HoldingFinancials | None) -> dict[str, float | None]:
    """Compute the per-holding metrics surfaced in the summary row.

    Mirrors the math in ``api/portfolio.py::portfolio_aggregate`` so the
    holdings tab and the overview tab agree.
    """
    if fin is None:
        return {
            "current_value": None,
            "monthly_noi": None,
            "monthly_cash_flow": None,
            "cap_rate": None,
            "dscr": None,
            "cash_on_cash": None,
        }

    value = fin.current_value_estimate
    rent = fin.monthly_rent or 0.0
    vacancy = fin.vacancy_rate or 0.0
    eff_rent = rent * (1.0 - vacancy)
    opex_m = fin.monthly_opex_estimate or 0.0
    tax_m = (fin.property_tax_annual or 0.0) / 12.0
    ins_m = (fin.insurance_annual or 0.0) / 12.0
    noi_m = eff_rent - opex_m - tax_m - ins_m
    annual_noi = noi_m * 12.0

    piti = fin.monthly_piti or 0.0
    monthly_cf = noi_m - piti
    annual_ds = piti * 12.0

    cap = annual_noi / value if value and value > 0 else None
    dscr = annual_noi / annual_ds if annual_ds > 0 else None
    equity = (value or 0.0) - (fin.loan_balance or 0.0)
    coc = (monthly_cf * 12.0) / equity if equity > 0 else None

    return {
        "current_value": value,
        "monthly_noi": noi_m,
        "monthly_cash_flow": monthly_cf,
        "cap_rate": cap,
        "dscr": dscr,
        "cash_on_cash": coc,
    }


async def _load_financials(
    db: AsyncSession, holding_id: str
) -> HoldingFinancials | None:
    return (
        await db.execute(
            select(HoldingFinancials).where(HoldingFinancials.holding_id == holding_id)
        )
    ).scalar_one_or_none()


async def build_portfolio_summary(
    db: AsyncSession, portfolio_id: str
) -> PortfolioSummaryReport | None:
    """Build a ``PortfolioSummaryReport`` for one portfolio, or ``None`` if missing."""
    portfolio = (
        await db.execute(
            select(InvestorPortfolio).where(InvestorPortfolio.id == portfolio_id)
        )
    ).scalar_one_or_none()
    if portfolio is None:
        return None

    holdings = (
        await db.execute(
            select(PortfolioHolding)
            .where(PortfolioHolding.portfolio_id == portfolio_id)
            .order_by(PortfolioHolding.created_at.asc())
        )
    ).scalars().all()

    per_holding: list[HoldingSummaryEntry] = []
    attention: list[PortfolioAttentionItem] = []

    total_value = 0.0
    total_loan = 0.0
    monthly_gross_rent = 0.0
    monthly_noi_total = 0.0
    monthly_cf_total = 0.0
    dscr_components: list[tuple[float, float]] = []  # (annual_noi, annual_ds)
    coverage_with_signals = 0

    for h in holdings:
        fin = await _load_financials(db, h.id)
        metrics = _per_holding_metrics(fin)
        decision = await compute_holding_decision(db, h, fin)

        if decision.market_context_available:
            coverage_with_signals += 1

        per_holding.append(
            HoldingSummaryEntry(
                holding_id=h.id,
                address=h.address,
                zip_code=h.zip_code,
                asset_class=_enum_value(h.asset_class),
                current_value=metrics["current_value"],
                monthly_cash_flow=metrics["monthly_cash_flow"],
                cap_rate=metrics["cap_rate"],
                dscr=metrics["dscr"],
                cash_on_cash=metrics["cash_on_cash"],
                recommendation=decision.recommendation,
                recommendation_score=decision.score,
                recommendation_rationale=decision.rationale,
                market_context_available=decision.market_context_available,
            )
        )

        if decision.recommendation in _ATTENTION_ACTIONS:
            attention.append(
                PortfolioAttentionItem(
                    holding_id=h.id,
                    address=h.address,
                    action=decision.recommendation,
                    score=decision.score,
                    rationale=decision.rationale,
                )
            )

        if fin is not None:
            total_value += fin.current_value_estimate or 0.0
            total_loan += fin.loan_balance or 0.0
            monthly_gross_rent += fin.monthly_rent or 0.0
            monthly_noi_total += metrics["monthly_noi"] or 0.0
            monthly_cf_total += metrics["monthly_cash_flow"] or 0.0
            piti = fin.monthly_piti or 0.0
            if piti > 0:
                dscr_components.append(
                    (
                        (metrics["monthly_noi"] or 0.0) * 12.0,
                        piti * 12.0,
                    )
                )

    annual_noi = monthly_noi_total * 12.0
    blended_cap = annual_noi / total_value if total_value > 0 else 0.0
    if dscr_components:
        sum_noi = sum(n for n, _ in dscr_components)
        sum_ds = sum(d for _, d in dscr_components)
        weighted_dscr: float | None = sum_noi / sum_ds if sum_ds > 0 else None
    else:
        weighted_dscr = None

    attention.sort(key=lambda a: a.score, reverse=True)

    return PortfolioSummaryReport(
        portfolio_id=portfolio_id,
        generated_at=datetime.now(timezone.utc),
        holding_count=len(holdings),
        aggregates=PortfolioSummaryAggregates(
            total_value=total_value,
            total_loan_balance=total_loan,
            total_equity=total_value - total_loan,
            monthly_gross_rent=monthly_gross_rent,
            monthly_net_operating_income=monthly_noi_total,
            monthly_cash_flow=monthly_cf_total,
            annual_noi=annual_noi,
            blended_cap_rate=blended_cap,
            weighted_dscr=weighted_dscr,
        ),
        per_holding=per_holding,
        attention=attention,
        market_coverage=MarketCoverage(
            total=len(holdings),
            with_signals=coverage_with_signals,
        ),
    )
