"""Tenant pool service — Phase P5.

For an individual investor evaluating a holding or a zip, the *tenant pool* is
the set of synthetic households that would plausibly rent or occupy the unit.
This module provides:

  * income-band aware filtering over ``HouseholdProfile`` rows, and
  * a small registry of *trajectory presets* — pre-bundled topic sets and
    round counts that drive a "where is this neighborhood heading" social
    simulation without the caller hand-picking topics.

``query_tenant_pool`` owns the DB I/O; ``summarize_pool`` is pure so it can be
unit-tested without a database.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import HouseholdProfile

# HouseholdProfile.income_band is free-text; these are the four canonical bands
# the seed data and social simulator use.
INCOME_BANDS: tuple[str, ...] = ("low", "moderate", "middle", "upper")


@dataclass(frozen=True, slots=True)
class TenantPoolFilter:
    """Immutable filter spec for ``query_tenant_pool``."""

    zip_code: str | None = None
    income_bands: tuple[str, ...] = ()
    housing_types: tuple[str, ...] = ()
    voucher_only: bool = False
    max_eviction_risk: float | None = None

    def validate(self) -> None:
        unknown = sorted(set(self.income_bands) - set(INCOME_BANDS))
        if unknown:
            raise ValueError(
                f"Unknown income band(s): {', '.join(unknown)}. "
                f"Expected one of {', '.join(INCOME_BANDS)}."
            )


@dataclass(frozen=True, slots=True)
class TenantPoolSummary:
    """Aggregate read-model over a tenant pool. Pure — no DB handle held."""

    total: int
    by_income_band: dict[str, int]
    by_housing_type: dict[str, int]
    voucher_holders: int
    avg_monthly_income: float
    avg_cost_burden: float  # housing cost / income, averaged over households with income
    avg_eviction_risk: float


@dataclass(frozen=True, slots=True)
class TrajectoryPreset:
    """A named social-simulation configuration for an investor scenario."""

    name: str
    topics: tuple[str, ...]
    max_rounds: int
    description: str
    income_bands: tuple[str, ...] = field(default_factory=tuple)


async def query_tenant_pool(
    db: AsyncSession, filt: TenantPoolFilter
) -> list[HouseholdProfile]:
    """Return households matching ``filt``. Raises ``ValueError`` on bad bands."""
    filt.validate()

    stmt = select(HouseholdProfile)
    if filt.zip_code:
        stmt = stmt.where(HouseholdProfile.zip_code == filt.zip_code)
    if filt.income_bands:
        stmt = stmt.where(HouseholdProfile.income_band.in_(filt.income_bands))
    if filt.housing_types:
        stmt = stmt.where(HouseholdProfile.housing_type.in_(filt.housing_types))
    if filt.voucher_only:
        stmt = stmt.where(HouseholdProfile.has_housing_voucher == 1)
    if filt.max_eviction_risk is not None:
        stmt = stmt.where(
            HouseholdProfile.eviction_risk <= filt.max_eviction_risk
        )

    result = await db.execute(stmt)
    return list(result.scalars().all())


def summarize_pool(households: Iterable[HouseholdProfile]) -> TenantPoolSummary:
    """Fold a tenant pool into an aggregate summary. Pure / side-effect free."""
    rows = list(households)
    if not rows:
        return TenantPoolSummary(
            total=0,
            by_income_band={},
            by_housing_type={},
            voucher_holders=0,
            avg_monthly_income=0.0,
            avg_cost_burden=0.0,
            avg_eviction_risk=0.0,
        )

    by_income_band: dict[str, int] = {}
    by_housing_type: dict[str, int] = {}
    voucher_holders = 0
    income_total = 0.0
    eviction_total = 0.0
    cost_burdens: list[float] = []

    for h in rows:
        by_income_band[h.income_band] = by_income_band.get(h.income_band, 0) + 1
        htype = h.housing_type or "unknown"
        by_housing_type[htype] = by_housing_type.get(htype, 0) + 1
        if h.has_housing_voucher:
            voucher_holders += 1

        income = h.monthly_income or 0.0
        income_total += income
        eviction_total += h.eviction_risk or 0.0
        if income > 0:
            cost_burdens.append((h.monthly_housing_cost or 0.0) / income)

    return TenantPoolSummary(
        total=len(rows),
        by_income_band=by_income_band,
        by_housing_type=by_housing_type,
        voucher_holders=voucher_holders,
        avg_monthly_income=income_total / len(rows),
        avg_cost_burden=(sum(cost_burdens) / len(cost_burdens)) if cost_burdens else 0.0,
        avg_eviction_risk=eviction_total / len(rows),
    )


# ── trajectory presets ──────────────────────────────────────────────────

_TRAJECTORY_PRESETS: dict[str, TrajectoryPreset] = {
    "neighborhood_trajectory": TrajectoryPreset(
        name="neighborhood_trajectory",
        topics=("market_prices", "eviction_policy", "neighborhood_safety"),
        max_rounds=12,
        description=(
            "Projects how the resident pool's stance and sentiment shift as a "
            "neighborhood's prices, tenant protections, and safety change — "
            "the 'where is this block heading' read for a buy-and-hold investor."
        ),
        income_bands=("low", "moderate", "middle"),
    ),
    "displacement_pressure": TrajectoryPreset(
        name="displacement_pressure",
        topics=("market_prices", "eviction_policy", "voucher_program"),
        max_rounds=10,
        description=(
            "Focuses on affordability and displacement risk for lower-income "
            "and voucher households — used to stress a value-add play against "
            "tenant-retention risk."
        ),
        income_bands=("low", "moderate"),
    ),
}


def get_trajectory_preset(name: str) -> TrajectoryPreset:
    """Return the named preset. Raises ``KeyError`` if unknown."""
    return _TRAJECTORY_PRESETS[name]


def list_trajectory_presets() -> list[TrajectoryPreset]:
    """Return all registered trajectory presets."""
    return list(_TRAJECTORY_PRESETS.values())


__all__ = [
    "INCOME_BANDS",
    "TenantPoolFilter",
    "TenantPoolSummary",
    "TrajectoryPreset",
    "query_tenant_pool",
    "summarize_pool",
    "get_trajectory_preset",
    "list_trajectory_presets",
]
