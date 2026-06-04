"""JP statutory depreciation engine — 法定耐用年数 + tax-shield projection.

Drives the Aparuto thesis: a 25-year-old 木造 building has only 4 years of
residual useful life under the simplified rule, so an investor in the
45% marginal bracket gets a steep but short tax shield. This module is
pure: no DB I/O, no Pydantic schemas — callers wrap the dataclass result.

References:
- 国税庁 耐用年数(建物・建物附属設備) (令和5年)
- 中古資産の耐用年数 (簡便法) — 法令解釈通達 1-5-1
"""

from __future__ import annotations

from dataclasses import dataclass

from db.models import ConstructionType


# ── Statutory useful life (法定耐用年数, residential use) ─────────────


STATUTORY_LIFE_YEARS: dict[ConstructionType, int] = {
    ConstructionType.WOOD: 22,
    ConstructionType.LIGHT_STEEL: 27,
    ConstructionType.STEEL: 34,
    ConstructionType.RC: 47,
    ConstructionType.SRC: 47,
}


def statutory_life(construction: ConstructionType) -> int:
    """Statutory useful life in years (新築)."""
    return STATUTORY_LIFE_YEARS[construction]


# ── Used-asset simplified rule (簡便法) ─────────────────────────────────


def residual_life_used(construction: ConstructionType, building_age_years: int) -> int:
    """Residual useful life for a used building under 簡便法.

    - If ``age >= statutory_life``: residual = statutory_life × 0.20
    - Else:                         residual = (statutory_life − age) + age × 0.20

    Floors at 2 years (the statute does not allow fractional sub-2 schedules).
    """
    if building_age_years < 0:
        raise ValueError("building_age_years must be non-negative")

    life = statutory_life(construction)
    if building_age_years >= life:
        residual = life * 0.20
    else:
        residual = (life - building_age_years) + building_age_years * 0.20

    return max(2, int(residual))


# ── Straight-line schedule + tax shield ────────────────────────────────


@dataclass(frozen=True)
class DepreciationYear:
    year_index: int            # 1-based, 1 = first year of ownership
    depreciation_yen: float    # building portion only
    tax_shield_yen: float      # depreciation × marginal_tax_rate
    cumulative_shield_yen: float


@dataclass(frozen=True)
class DepreciationSchedule:
    construction: ConstructionType
    building_basis_yen: float       # building portion of cost basis
    residual_life_years: int
    annual_depreciation_yen: float
    marginal_tax_rate: float
    years: tuple[DepreciationYear, ...]

    @property
    def total_shield_yen(self) -> float:
        return self.years[-1].cumulative_shield_yen if self.years else 0.0

    @property
    def shield_expires_year(self) -> int:
        """Year-of-ownership the shield runs out (= residual_life_years)."""
        return self.residual_life_years


def project_depreciation(
    *,
    construction: ConstructionType,
    building_basis_yen: float,
    building_age_years: int,
    marginal_tax_rate: float,
    horizon_years: int | None = None,
) -> DepreciationSchedule:
    """Straight-line depreciation schedule + tax shield projection.

    ``building_basis_yen`` is the **building** portion only — land is not
    depreciable in Japan. Callers should split cost basis using the assessed
    land/building ratio (固定資産税評価額) before invoking this.
    """
    if building_basis_yen < 0:
        raise ValueError("building_basis_yen must be non-negative")
    if not 0 <= marginal_tax_rate <= 1:
        raise ValueError("marginal_tax_rate must be in [0, 1]")

    residual = residual_life_used(construction, building_age_years)
    annual_dep = building_basis_yen / residual if residual > 0 else 0.0
    horizon = horizon_years if horizon_years is not None else residual

    cumulative_shield = 0.0
    rows: list[DepreciationYear] = []
    for y in range(1, horizon + 1):
        if y <= residual:
            dep = annual_dep
            shield = dep * marginal_tax_rate
        else:
            dep = 0.0
            shield = 0.0
        cumulative_shield += shield
        rows.append(
            DepreciationYear(
                year_index=y,
                depreciation_yen=dep,
                tax_shield_yen=shield,
                cumulative_shield_yen=cumulative_shield,
            )
        )

    return DepreciationSchedule(
        construction=construction,
        building_basis_yen=building_basis_yen,
        residual_life_years=residual,
        annual_depreciation_yen=annual_dep,
        marginal_tax_rate=marginal_tax_rate,
        years=tuple(rows),
    )


__all__ = [
    "STATUTORY_LIFE_YEARS",
    "statutory_life",
    "residual_life_used",
    "DepreciationYear",
    "DepreciationSchedule",
    "project_depreciation",
]
