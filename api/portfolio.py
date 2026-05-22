"""Investor portfolio CRUD API.

Phase P1 surface — list/create portfolios, add/list/delete holdings, compute
portfolio aggregates. Underwriting + stress tests + decision recommendations
are layered on in P2–P4.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import (
    ChatImportConfirm,
    ChatImportRequest,
    ChatImportResponse,
    CsvImportRequest,
    CsvImportResponse,
    HoldingFinancialsResponse,
    InvestorPortfolioCreate,
    InvestorPortfolioResponse,
    PortfolioAggregateResponse,
    PortfolioFromPropertyRequest,
    PortfolioHoldingCreate,
    PortfolioHoldingResponse,
    PortfolioSummaryReport,
)
from services.portfolio_chat_extractor import (
    ChatLike,
    extract_holdings_from_chat,
)
from services.user_resolve import resolve_user_id
from db.database import get_db
from db.models import (
    AssetClass,
    HoldingFinancials,
    HoldingStatus,
    InvestmentStrategy,
    InvestorPortfolio,
    PortfolioHolding,
    Property,
    UserProfile,
)
from services.portfolio_summary import build_portfolio_summary

router = APIRouter()


# ── helpers ─────────────────────────────────────────────────────────────


async def _load_holding_with_financials(
    db: AsyncSession, holding: PortfolioHolding
) -> PortfolioHoldingResponse:
    fin_row = (
        await db.execute(
            select(HoldingFinancials).where(
                HoldingFinancials.holding_id == holding.id
            )
        )
    ).scalar_one_or_none()

    fin_resp = HoldingFinancialsResponse.model_validate(fin_row) if fin_row else None
    return PortfolioHoldingResponse(
        id=holding.id,
        portfolio_id=holding.portfolio_id,
        property_id=holding.property_id,
        address=holding.address,
        latitude=holding.latitude,
        longitude=holding.longitude,
        zip_code=holding.zip_code,
        asset_class=holding.asset_class.value
        if hasattr(holding.asset_class, "value")
        else holding.asset_class,
        status=holding.status.value
        if hasattr(holding.status, "value")
        else holding.status,
        acquisition_date=holding.acquisition_date,
        financials=fin_resp,
        created_at=holding.created_at,
    )


def _coerce_enum(value: str, enum_cls: type) -> Any:
    try:
        return enum_cls(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _zip_from_address(address: str | None, explicit_zip: str | None) -> str | None:
    if explicit_zip:
        return explicit_zip
    if not address:
        return None
    # Best-effort: take the last 5-digit token, if any
    for token in reversed(address.replace(",", " ").split()):
        if len(token) == 5 and token.isdigit():
            return token
    return None


# ── portfolio CRUD ──────────────────────────────────────────────────────


@router.post(
    "/", response_model=InvestorPortfolioResponse, status_code=201
)
async def create_portfolio(
    data: InvestorPortfolioCreate, db: AsyncSession = Depends(get_db)
):
    """Create an InvestorPortfolio for an existing UserProfile."""
    user = (
        await db.execute(select(UserProfile).where(UserProfile.id == data.user_id))
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    strategy = _coerce_enum(data.investment_strategy, InvestmentStrategy)
    portfolio = InvestorPortfolio(
        user_id=data.user_id,
        name=data.name,
        investment_strategy=strategy,
        notes=data.notes,
    )
    db.add(portfolio)
    await db.commit()
    await db.refresh(portfolio)
    return InvestorPortfolioResponse(
        id=portfolio.id,
        user_id=portfolio.user_id,
        name=portfolio.name,
        investment_strategy=portfolio.investment_strategy.value,
        notes=portfolio.notes,
        created_at=portfolio.created_at,
    )


@router.get("/", response_model=list[InvestorPortfolioResponse])
async def list_portfolios(
    user_id: str = Query(...), db: AsyncSession = Depends(get_db)
):
    """List all portfolios belonging to a user."""
    rows = (
        await db.execute(
            select(InvestorPortfolio)
            .where(InvestorPortfolio.user_id == user_id)
            .order_by(InvestorPortfolio.created_at.asc())
        )
    ).scalars().all()
    return [
        InvestorPortfolioResponse(
            id=p.id,
            user_id=p.user_id,
            name=p.name,
            investment_strategy=p.investment_strategy.value,
            notes=p.notes,
            created_at=p.created_at,
        )
        for p in rows
    ]


@router.get("/{portfolio_id}", response_model=InvestorPortfolioResponse)
async def get_portfolio(portfolio_id: str, db: AsyncSession = Depends(get_db)):
    p = (
        await db.execute(
            select(InvestorPortfolio).where(InvestorPortfolio.id == portfolio_id)
        )
    ).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="portfolio_not_found")
    return InvestorPortfolioResponse(
        id=p.id,
        user_id=p.user_id,
        name=p.name,
        investment_strategy=p.investment_strategy.value,
        notes=p.notes,
        created_at=p.created_at,
    )


@router.delete("/{portfolio_id}", status_code=204)
async def delete_portfolio(portfolio_id: str, db: AsyncSession = Depends(get_db)):
    p = (
        await db.execute(
            select(InvestorPortfolio).where(InvestorPortfolio.id == portfolio_id)
        )
    ).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="portfolio_not_found")
    # Cascade by hand — kept explicit so SQLite tests don't need ON DELETE
    holdings = (
        await db.execute(
            select(PortfolioHolding).where(
                PortfolioHolding.portfolio_id == portfolio_id
            )
        )
    ).scalars().all()
    for h in holdings:
        fins = (
            await db.execute(
                select(HoldingFinancials).where(
                    HoldingFinancials.holding_id == h.id
                )
            )
        ).scalars().all()
        for f in fins:
            await db.delete(f)
        await db.delete(h)
    await db.delete(p)
    await db.commit()


# ── holdings CRUD ───────────────────────────────────────────────────────


@router.post(
    "/{portfolio_id}/holdings",
    response_model=PortfolioHoldingResponse,
    status_code=201,
)
async def add_holding(
    portfolio_id: str,
    data: PortfolioHoldingCreate,
    db: AsyncSession = Depends(get_db),
):
    portfolio = (
        await db.execute(
            select(InvestorPortfolio).where(InvestorPortfolio.id == portfolio_id)
        )
    ).scalar_one_or_none()
    if not portfolio:
        raise HTTPException(status_code=404, detail="portfolio_not_found")

    asset_class = _coerce_enum(data.asset_class, AssetClass)
    status = _coerce_enum(data.status, HoldingStatus)

    holding = PortfolioHolding(
        portfolio_id=portfolio_id,
        property_id=data.property_id,
        address=data.address,
        latitude=data.latitude,
        longitude=data.longitude,
        zip_code=_zip_from_address(data.address, data.zip_code),
        asset_class=asset_class,
        status=status,
        acquisition_date=data.acquisition_date,
    )
    db.add(holding)
    await db.flush()

    if data.financials is not None:
        fin = HoldingFinancials(
            holding_id=holding.id,
            **data.financials.model_dump(exclude_none=True),
        )
        db.add(fin)

    await db.commit()
    await db.refresh(holding)
    return await _load_holding_with_financials(db, holding)


@router.get(
    "/{portfolio_id}/holdings",
    response_model=list[PortfolioHoldingResponse],
)
async def list_holdings(
    portfolio_id: str, db: AsyncSession = Depends(get_db)
):
    rows = (
        await db.execute(
            select(PortfolioHolding)
            .where(PortfolioHolding.portfolio_id == portfolio_id)
            .order_by(PortfolioHolding.created_at.asc())
        )
    ).scalars().all()
    return [await _load_holding_with_financials(db, h) for h in rows]


@router.get(
    "/{portfolio_id}/holdings/{holding_id}",
    response_model=PortfolioHoldingResponse,
)
async def get_holding(
    portfolio_id: str, holding_id: str, db: AsyncSession = Depends(get_db)
):
    h = (
        await db.execute(
            select(PortfolioHolding).where(
                PortfolioHolding.id == holding_id,
                PortfolioHolding.portfolio_id == portfolio_id,
            )
        )
    ).scalar_one_or_none()
    if not h:
        raise HTTPException(status_code=404, detail="holding_not_found")
    return await _load_holding_with_financials(db, h)


@router.delete(
    "/{portfolio_id}/holdings/{holding_id}", status_code=204
)
async def delete_holding(
    portfolio_id: str, holding_id: str, db: AsyncSession = Depends(get_db)
):
    h = (
        await db.execute(
            select(PortfolioHolding).where(
                PortfolioHolding.id == holding_id,
                PortfolioHolding.portfolio_id == portfolio_id,
            )
        )
    ).scalar_one_or_none()
    if not h:
        raise HTTPException(status_code=404, detail="holding_not_found")
    fins = (
        await db.execute(
            select(HoldingFinancials).where(HoldingFinancials.holding_id == h.id)
        )
    ).scalars().all()
    for f in fins:
        await db.delete(f)
    await db.delete(h)
    await db.commit()


# ── bulk CSV import (onboarding wizard P2) ─────────────────────────────

CSV_TEMPLATE_COLUMNS = [
    "address",
    "zip_code",
    "asset_class",
    "cost_basis",
    "current_value_estimate",
    "loan_balance",
    "interest_rate",
    "monthly_rent",
    "monthly_piti",
]


@router.get("/import/csv/template")
async def csv_import_template() -> dict[str, Any]:
    """Return the canonical CSV header row + a one-line example.

    The wizard's CSV step downloads this so users always start from a known
    schema. Keeping the columns server-authoritative means a schema bump only
    requires a backend redeploy.
    """
    header = ",".join(CSV_TEMPLATE_COLUMNS)
    example = ",".join(
        [
            "123 Main St, Chicago IL 60601",
            "60601",
            "sfr",
            "350000",
            "420000",
            "240000",
            "0.0625",
            "2400",
            "1850",
        ]
    )
    return {"columns": CSV_TEMPLATE_COLUMNS, "csv": f"{header}\n{example}\n"}


@router.post(
    "/import/csv",
    response_model=CsvImportResponse,
    status_code=201,
)
async def import_csv(
    payload: CsvImportRequest,
    db: AsyncSession = Depends(get_db),
) -> CsvImportResponse:
    """Bulk-create a portfolio + holdings from parsed CSV rows.

    Idempotency rule: a holding is keyed on ``(portfolio.user_id, address)``.
    If a holding with the same address already exists in any of the user's
    portfolios, its financials are updated in place instead of duplicating.

    The whole operation is transactional — if any row blows up the entire
    import rolls back so the user can retry with a fixed file.
    """
    return await _bulk_import_holdings(
        db,
        user_id=payload.user_id,
        user_email=payload.user_email,
        user_name=payload.user_name,
        portfolio_name=payload.portfolio_name,
        investment_strategy=payload.investment_strategy,
        holdings=payload.holdings,
    )


async def _bulk_import_holdings(
    db: AsyncSession,
    *,
    user_id: str,
    user_email: str | None = None,
    user_name: str | None = None,
    portfolio_name: str,
    investment_strategy: str,
    holdings: list[PortfolioHoldingCreate],
) -> CsvImportResponse:
    """Shared idempotent commit path used by CSV and chat imports."""
    if not holdings:
        raise HTTPException(status_code=400, detail="no_holdings_provided")

    try:
        user_id = await resolve_user_id(
            db, user_id, email=user_email, name=user_name, auto_create=True
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="user_not_found")

    strategy = _coerce_enum(investment_strategy, InvestmentStrategy)

    existing_portfolios = (
        await db.execute(
            select(InvestorPortfolio).where(
                InvestorPortfolio.user_id == user_id
            )
        )
    ).scalars().all()

    portfolio: InvestorPortfolio | None
    if existing_portfolios:
        portfolio = existing_portfolios[0]
    else:
        portfolio = InvestorPortfolio(
            user_id=user_id,
            name=portfolio_name,
            investment_strategy=strategy,
        )
        db.add(portfolio)
        await db.flush()

    existing_holdings = (
        await db.execute(
            select(PortfolioHolding)
            .join(
                InvestorPortfolio,
                InvestorPortfolio.id == PortfolioHolding.portfolio_id,
            )
            .where(InvestorPortfolio.user_id == user_id)
        )
    ).scalars().all()
    by_address: dict[str, PortfolioHolding] = {
        h.address.strip().lower(): h for h in existing_holdings if h.address
    }

    inserted = 0
    updated = 0
    skipped: list[str] = []

    for row in holdings:
        addr = (row.address or "").strip()
        if not addr:
            skipped.append("<missing address>")
            continue

        asset_class = _coerce_enum(row.asset_class, AssetClass)
        status_enum = _coerce_enum(row.status, HoldingStatus)
        zip_code = _zip_from_address(addr, row.zip_code)

        match = by_address.get(addr.lower())
        if match is not None:
            match.asset_class = asset_class
            match.status = status_enum
            match.zip_code = zip_code or match.zip_code
            match.property_id = row.property_id or match.property_id
            match.latitude = row.latitude if row.latitude is not None else match.latitude
            match.longitude = (
                row.longitude if row.longitude is not None else match.longitude
            )
            if row.acquisition_date is not None:
                match.acquisition_date = row.acquisition_date
            if row.financials is not None:
                fin = (
                    await db.execute(
                        select(HoldingFinancials).where(
                            HoldingFinancials.holding_id == match.id
                        )
                    )
                ).scalar_one_or_none()
                fin_data = row.financials.model_dump(exclude_none=True)
                if fin is None:
                    db.add(HoldingFinancials(holding_id=match.id, **fin_data))
                else:
                    for key, value in fin_data.items():
                        setattr(fin, key, value)
            updated += 1
            continue

        holding = PortfolioHolding(
            portfolio_id=portfolio.id,
            property_id=row.property_id,
            address=addr,
            latitude=row.latitude,
            longitude=row.longitude,
            zip_code=zip_code,
            asset_class=asset_class,
            status=status_enum,
            acquisition_date=row.acquisition_date,
        )
        db.add(holding)
        await db.flush()
        if row.financials is not None:
            db.add(
                HoldingFinancials(
                    holding_id=holding.id,
                    **row.financials.model_dump(exclude_none=True),
                )
            )
        inserted += 1

    await db.commit()
    return CsvImportResponse(
        portfolio_id=portfolio.id,
        inserted_count=inserted,
        updated_count=updated,
        skipped=skipped,
    )


# ── chat-based import (onboarding wizard P3) ───────────────────────────


def get_chat_client() -> ChatLike:
    """FastAPI dependency: builds an Anthropic client per request.

    Overridable in tests by ``app.dependency_overrides[get_chat_client]``.
    """
    import anthropic

    from config import settings

    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


@router.post(
    "/import/chat",
    response_model=ChatImportResponse,
)
async def chat_extract(
    payload: ChatImportRequest,
    client: ChatLike = Depends(get_chat_client),
) -> ChatImportResponse:
    """Extract structured holdings from the conversation so far.

    Stateless: the frontend owns the conversation. We invoke Claude with a
    structured tool and return whatever holdings it inferred plus any text
    Claude wrote (a clarifying question, typically). Nothing is persisted —
    the user must POST the final list to ``/import/chat/confirm``.
    """
    if not payload.messages:
        raise HTTPException(status_code=400, detail="no_messages_provided")

    messages_payload = [
        {"role": m.role, "content": m.content} for m in payload.messages
    ]
    result = await extract_holdings_from_chat(client, messages=messages_payload)
    return ChatImportResponse(narration=result.narration, holdings=result.holdings)


@router.post(
    "/import/chat/confirm",
    response_model=CsvImportResponse,
    status_code=201,
)
async def chat_confirm(
    payload: ChatImportConfirm,
    db: AsyncSession = Depends(get_db),
) -> CsvImportResponse:
    """Commit the user-approved holdings via the shared idempotent path."""
    return await _bulk_import_holdings(
        db,
        user_id=payload.user_id,
        user_email=payload.user_email,
        user_name=payload.user_name,
        portfolio_name=payload.portfolio_name,
        investment_strategy=payload.investment_strategy,
        holdings=payload.holdings,
    )


# ── synthetic portfolio bridge (onboarding wizard P6) ──────────────────


@router.post(
    "/from-property",
    response_model=InvestorPortfolioResponse,
    status_code=201,
)
async def portfolio_from_property(
    payload: PortfolioFromPropertyRequest,
    db: AsyncSession = Depends(get_db),
) -> InvestorPortfolioResponse:
    """Wrap an existing ``Property`` in a single-holding portfolio.

    The no-portfolio onboarding branch ends on a property recommendation;
    the strategy runner needs a portfolio to operate against, so we
    synthesize one with this property as its sole holding. Idempotent:
    re-posting with the same ``(user_id, property_id)`` returns the existing
    portfolio rather than duplicating.
    """
    try:
        user_id = await resolve_user_id(
            db,
            payload.user_id,
            email=payload.user_email,
            name=payload.user_name,
            auto_create=True,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="user_not_found")

    prop = (
        await db.execute(select(Property).where(Property.id == payload.property_id))
    ).scalar_one_or_none()
    if prop is None:
        raise HTTPException(status_code=404, detail="property_not_found")

    # Reuse an existing portfolio that already holds this property.
    existing = (
        await db.execute(
            select(InvestorPortfolio)
            .join(PortfolioHolding, PortfolioHolding.portfolio_id == InvestorPortfolio.id)
            .where(
                InvestorPortfolio.user_id == user_id,
                PortfolioHolding.property_id == payload.property_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return InvestorPortfolioResponse(
            id=existing.id,
            user_id=existing.user_id,
            name=existing.name,
            investment_strategy=existing.investment_strategy.value
            if hasattr(existing.investment_strategy, "value")
            else existing.investment_strategy,
            notes=existing.notes,
            created_at=existing.created_at,
        )

    strategy = _coerce_enum(payload.investment_strategy, InvestmentStrategy)
    portfolio = InvestorPortfolio(
        user_id=user_id,
        name=payload.portfolio_name,
        investment_strategy=strategy,
    )
    db.add(portfolio)
    await db.flush()

    holding = PortfolioHolding(
        portfolio_id=portfolio.id,
        property_id=prop.id,
        address=prop.address,
        latitude=prop.latitude,
        longitude=prop.longitude,
        zip_code=_zip_from_address(prop.address, None),
        asset_class=AssetClass.SFR,
        status=HoldingStatus.HELD,
    )
    db.add(holding)
    await db.flush()

    # Seed financials from the listing — cost_basis = asking_price.
    db.add(
        HoldingFinancials(
            holding_id=holding.id,
            cost_basis=prop.asking_price,
            current_value_estimate=prop.asking_price,
            value_estimate_source="listing",
        )
    )
    await db.commit()
    await db.refresh(portfolio)

    return InvestorPortfolioResponse(
        id=portfolio.id,
        user_id=portfolio.user_id,
        name=portfolio.name,
        investment_strategy=portfolio.investment_strategy.value
        if hasattr(portfolio.investment_strategy, "value")
        else portfolio.investment_strategy,
        notes=portfolio.notes,
        created_at=portfolio.created_at,
    )


# ── aggregate metrics ──────────────────────────────────────────────────


@router.get(
    "/{portfolio_id}/aggregate", response_model=PortfolioAggregateResponse
)
async def portfolio_aggregate(
    portfolio_id: str, db: AsyncSession = Depends(get_db)
):
    portfolio = (
        await db.execute(
            select(InvestorPortfolio).where(InvestorPortfolio.id == portfolio_id)
        )
    ).scalar_one_or_none()
    if not portfolio:
        raise HTTPException(status_code=404, detail="portfolio_not_found")

    holdings = (
        await db.execute(
            select(PortfolioHolding).where(
                PortfolioHolding.portfolio_id == portfolio_id
            )
        )
    ).scalars().all()

    total_value = 0.0
    total_loan = 0.0
    total_cost_basis = 0.0
    monthly_gross_rent = 0.0
    monthly_noi = 0.0
    monthly_debt_service = 0.0
    annual_noi = 0.0
    dscr_components: list[tuple[float, float]] = []  # (noi, debt_service) per holding

    zip_counter: Counter[str] = Counter()
    asset_counter: Counter[str] = Counter()

    for h in holdings:
        zip_counter[h.zip_code or "unknown"] += 1
        asset_value = h.asset_class.value if hasattr(h.asset_class, "value") else str(h.asset_class)
        asset_counter[asset_value] += 1

        fin = (
            await db.execute(
                select(HoldingFinancials).where(
                    HoldingFinancials.holding_id == h.id
                )
            )
        ).scalar_one_or_none()
        if not fin:
            continue

        value = fin.current_value_estimate or 0.0
        total_value += value
        total_loan += fin.loan_balance or 0.0
        total_cost_basis += fin.cost_basis or 0.0

        rent = fin.monthly_rent or 0.0
        vacancy = fin.vacancy_rate or 0.0
        eff_rent = rent * (1.0 - vacancy)
        monthly_gross_rent += rent

        opex_m = fin.monthly_opex_estimate or 0.0
        tax_m = (fin.property_tax_annual or 0.0) / 12.0
        ins_m = (fin.insurance_annual or 0.0) / 12.0
        noi_m = eff_rent - opex_m - tax_m - ins_m
        monthly_noi += noi_m
        annual_noi += noi_m * 12.0

        piti = fin.monthly_piti or 0.0
        monthly_debt_service += piti
        if piti > 0:
            dscr_components.append((noi_m * 12.0, piti * 12.0))

    blended_cap_rate = (annual_noi / total_value) if total_value > 0 else 0.0
    weighted_dscr: float | None
    if dscr_components:
        total_noi = sum(noi for noi, _ in dscr_components)
        total_ds = sum(ds for _, ds in dscr_components)
        weighted_dscr = (total_noi / total_ds) if total_ds > 0 else None
    else:
        weighted_dscr = None

    return PortfolioAggregateResponse(
        portfolio_id=portfolio_id,
        holding_count=len(holdings),
        total_value=total_value,
        total_loan_balance=total_loan,
        total_equity=total_value - total_loan,
        total_cost_basis=total_cost_basis,
        monthly_gross_rent=monthly_gross_rent,
        monthly_net_operating_income=monthly_noi,
        monthly_cash_flow=monthly_noi - monthly_debt_service,
        blended_cap_rate=blended_cap_rate,
        weighted_dscr=weighted_dscr,
        concentration={"by_zip": dict(zip_counter)},
        asset_class_mix=dict(asset_counter),
        investment_strategy=portfolio.investment_strategy.value,
    )


# ── portfolio summary (Phase S3) ───────────────────────────────────────


@router.get(
    "/{portfolio_id}/summary", response_model=PortfolioSummaryReport
)
async def portfolio_summary(
    portfolio_id: str, db: AsyncSession = Depends(get_db)
):
    """One consolidated read-only report — analysis across every holding."""
    report = await build_portfolio_summary(db, portfolio_id)
    if report is None:
        raise HTTPException(status_code=404, detail="portfolio_not_found")
    return report
