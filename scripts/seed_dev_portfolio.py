"""Seed a local dev investor + Tokyo portfolio + holdings for no-login testing.

Companion to the ``VITE_DEV_BYPASS_AUTH`` frontend flag: that flag lets the UI
render without a Supabase session, and this script gives the (un-authed)
backend something to show — a user, a portfolio, and holdings with financials —
so the Portfolio page and the strategy simulation have real data to run on.

Holdings are **linked to seeded Tokyo properties by ``property_id``**. That link
is what carries ``Property.ward_code`` (the 5-digit MLIT municipality code) into
``market_state``, which is how live REINFOLIB signals reach the Analysis,
Simulation, and Portfolio surface. Run the Tokyo seed and the fetch first::

    python scripts/seed_tokyo.py
    python scripts/fetch_external_signals.py --source reinfolib_transaction
    python scripts/seed_dev_portfolio.py

Market context comes from real MLIT data via the fetch CLI above — this script
deliberately writes **no** synthetic market signals.

Pure local DB writes (no Supabase). Idempotent: re-running reuses the existing
dev user/portfolio instead of duplicating.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import func, select  # noqa: E402

from db.database import async_session  # noqa: E402
from db.models import (  # noqa: E402
    AssetClass,
    HoldingFinancials,
    HoldingStatus,
    InvestmentStrategy,
    InvestorPortfolio,
    PortfolioHolding,
    Property,
    UserProfile,
)

DEV_USER_ID = "dev-user-0001"
DEV_EMAIL = "dev@realestate.local"
DEV_PORTFOLIO_NAME = "デモ投資ポートフォリオ"

# Tokyo listing type → the portfolio's asset-class taxonomy.
_ASSET_CLASS_BY_TYPE = {
    "mansion": AssetClass.CONDO,
    "issenkodate": AssetClass.SFR,
    "shuueki": AssetClass.MF_5_PLUS,
}

# (gross_yield, interest_rate, ltv) per slot so the simulation surfaces
# different recommendations across the portfolio. Rates reflect the Japanese
# market (variable ~0.6%, fixed ~1.8%) rather than US benchmarks; the 1.8%
# holding is the deliberate REFI candidate.
_FINANCIAL_PROFILES = [
    (0.038, 0.006, 0.70),   # low-rate, healthy yield → HOLD
    (0.030, 0.018, 0.80),   # high-rate + thin yield → REFI / review
    (0.045, 0.012, 0.65),   # strong yield → HOLD
]


def _financials_for(asking_price: float, slot: int) -> dict[str, float]:
    """Derive plausible JPY financials from a listing price."""
    gross_yield, rate, ltv = _FINANCIAL_PROFILES[slot % len(_FINANCIAL_PROFILES)]
    monthly_rent = round(asking_price * gross_yield / 12, -3)
    loan = round(asking_price * ltv, -3)
    # 35-year annuity, the standard JP residential term.
    monthly_rate = rate / 12
    n = 35 * 12
    piti = (
        loan * monthly_rate / (1 - (1 + monthly_rate) ** -n)
        if monthly_rate
        else loan / n
    )
    return {
        "cost_basis": round(asking_price * 0.95, -3),
        "current_value_estimate": asking_price,
        "loan_balance": loan,
        "interest_rate": rate,
        "monthly_piti": round(piti, -2),
        "monthly_rent": monthly_rent,
        "vacancy_rate": 0.05,
        "monthly_opex_estimate": round(monthly_rent * 0.15, -2),
        # 固定資産税 ≈ 1.4% of assessed value (roughly 70% of market).
        "property_tax_annual": round(asking_price * 0.7 * 0.014, -3),
        "insurance_annual": round(asking_price * 0.0006, -3),
    }


async def _get_or_create_user(db) -> UserProfile:
    # Resolve by email first to avoid the unique-email constraint, then by the
    # fixed dev id, otherwise create with that id so it is stable across runs.
    by_email = (
        await db.execute(select(UserProfile).where(UserProfile.email == DEV_EMAIL))
    ).scalar_one_or_none()
    if by_email is not None:
        return by_email

    user = UserProfile(
        id=DEV_USER_ID,
        name="デモ投資家",
        email=DEV_EMAIL,
        role="investor",
    )
    db.add(user)
    await db.flush()
    return user


async def _get_or_create_portfolio(db, user: UserProfile) -> tuple[InvestorPortfolio, bool]:
    existing = (
        await db.execute(
            select(InvestorPortfolio).where(
                InvestorPortfolio.user_id == user.id,
                InvestorPortfolio.name == DEV_PORTFOLIO_NAME,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing, False

    portfolio = InvestorPortfolio(
        user_id=user.id,
        name=DEV_PORTFOLIO_NAME,
        investment_strategy=InvestmentStrategy.BUY_HOLD,
    )
    db.add(portfolio)
    await db.flush()
    return portfolio, True


async def _tokyo_properties(db, limit: int = 3) -> list[Property]:
    """Seeded Tokyo stock, priciest first. ``ward_code`` is the REINFOLIB join key."""
    return list(
        (
            await db.execute(
                select(Property)
                .where(Property.ward_code.isnot(None))
                .order_by(Property.asking_price.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )


async def main() -> None:
    async with async_session() as db:
        user = await _get_or_create_user(db)
        portfolio, created = await _get_or_create_portfolio(db, user)

        properties = await _tokyo_properties(db)
        if not properties:
            print(
                "No Tokyo properties with a ward_code found.\n"
                "Run `python scripts/seed_tokyo.py` first — without ward_code the\n"
                "REINFOLIB signals cannot resolve and the tabs stay empty."
            )
            return

        holding_count = (
            await db.execute(
                select(func.count(PortfolioHolding.id)).where(
                    PortfolioHolding.portfolio_id == portfolio.id
                )
            )
        ).scalar_one()

        if holding_count == 0:
            for slot, prop in enumerate(properties):
                holding = PortfolioHolding(
                    portfolio_id=portfolio.id,
                    property_id=prop.id,  # carries ward_code → REINFOLIB signals
                    address=prop.address,
                    zip_code=prop.ward_code,  # fallback key if the property link breaks
                    asset_class=_ASSET_CLASS_BY_TYPE.get(
                        prop.property_type, AssetClass.CONDO
                    ),
                    status=HoldingStatus.HELD,
                )
                db.add(holding)
                await db.flush()
                db.add(
                    HoldingFinancials(
                        holding_id=holding.id,
                        **_financials_for(float(prop.asking_price), slot),
                    )
                )
        else:
            print(f"  portfolio already has {holding_count} holdings — leaving them as-is")

        await db.commit()

        print("開発用ポートフォリオを作成しました / Dev portfolio seeded:")
        print(f"  user_id      : {user.id}  ({user.email})")
        print(f"  portfolio_id : {portfolio.id}  ({'created' if created else 'reused'})")
        print(f"  holdings     : {max(holding_count, len(properties))}")
        for prop in properties:
            print(f"    - [{prop.ward_code}] {prop.address}  ¥{prop.asking_price:,.0f}")
        print(
            "\n  Market context comes from real MLIT data. Load/refresh it with:\n"
            "    python scripts/fetch_external_signals.py --source reinfolib_transaction"
        )


if __name__ == "__main__":
    asyncio.run(main())
