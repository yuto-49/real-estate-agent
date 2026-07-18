"""Market-layer state snapshots."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class MarketContextSnapshot:
    """Normalized market context consumed by actor, reaction, and decision code."""

    property_id: str | None = None
    neighborhood_id: str | None = None
    zip_code: str | None = None
    jurisdiction: str | None = None
    zoning_code: str | None = None
    transit_score: float | None = None
    school_score: float | None = None
    safety_score: float | None = None
    median_rent: float | None = None
    median_sale_price: float | None = None
    inventory_pressure: float | None = None
    # JP (MLIT REINFOLIB) scalars. Yen per square metre unless noted.
    median_unit_price: float | None = None
    land_price_psm: float | None = None
    appraised_value_psm: float | None = None
    hazard_flags: Mapping[str, Any] = field(default_factory=dict)
