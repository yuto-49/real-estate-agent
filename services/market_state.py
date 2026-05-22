"""Phase B market-state snapshot builder.

Reads ``MarketSignal`` rows + ``Property`` columns and produces a
:class:`MarketContextSnapshot` consumable by actor, reaction, and decision
layers. Lenient by design: missing signals leave snapshot fields as ``None``
rather than failing the build.

Signal-type → snapshot-field mapping is intentionally explicit so the schema
is discoverable from one place.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import MarketSignal, Property
from domain.market.models import MarketContextSnapshot


SUBJECT_PROPERTY: Final[str] = "property"
SUBJECT_NEIGHBORHOOD: Final[str] = "neighborhood"
SUBJECT_JURISDICTION: Final[str] = "jurisdiction"


# Maps signal_type → MarketContextSnapshot field name. Numeric scalars only.
_SCALAR_SIGNAL_FIELDS: Final[dict[str, str]] = {
    "transit_score": "transit_score",
    "school_score": "school_score",
    "safety_score": "safety_score",
    "median_rent": "median_rent",
    "median_sale_price": "median_sale_price",
    "inventory_pressure": "inventory_pressure",
}


async def _latest_signals_for(
    db: AsyncSession,
    *,
    subject_type: str,
    subject_id: str,
) -> list[MarketSignal]:
    """Return the most recent signal per signal_type for a subject."""
    stmt = (
        select(MarketSignal)
        .where(MarketSignal.subject_type == subject_type)
        .where(MarketSignal.subject_id == subject_id)
        .order_by(MarketSignal.observed_at.desc())
    )
    result = await db.execute(stmt)
    rows: list[MarketSignal] = list(result.scalars().all())

    # Keep first row per signal_type (already sorted desc by observed_at).
    seen: set[str] = set()
    deduped: list[MarketSignal] = []
    for row in rows:
        if row.signal_type in seen:
            continue
        seen.add(row.signal_type)
        deduped.append(row)
    return deduped


def _aggregate(
    snapshot_kwargs: dict[str, object],
    signals: Iterable[MarketSignal],
) -> dict[str, object]:
    """Fold signals into the kwargs dict that builds the snapshot."""
    hazard_flags: dict[str, object] = dict(snapshot_kwargs.get("hazard_flags") or {})

    for signal in signals:
        field = _SCALAR_SIGNAL_FIELDS.get(signal.signal_type)
        if field is not None and signal.value is not None:
            snapshot_kwargs[field] = float(signal.value)
            continue

        if signal.signal_type == "zoning":
            payload = dict(signal.payload or {})
            zoning_code = payload.get("code") or payload.get("zoning_code")
            if zoning_code is not None:
                snapshot_kwargs["zoning_code"] = str(zoning_code)
            continue

        if signal.signal_type == "hazard":
            payload = dict(signal.payload or {})
            hazard_flags.update(payload)
            continue

    snapshot_kwargs["hazard_flags"] = hazard_flags
    return snapshot_kwargs


async def build_snapshot(
    db: AsyncSession,
    property_id: str,
) -> MarketContextSnapshot | None:
    """Compose a :class:`MarketContextSnapshot` for ``property_id``.

    Returns ``None`` if the property does not exist. Otherwise returns a
    snapshot whose unresolved fields stay ``None`` (lenient — callers downstream
    decide how to handle missing signals).
    """
    prop_result = await db.execute(select(Property).where(Property.id == property_id))
    prop: Property | None = prop_result.scalar_one_or_none()
    if prop is None:
        return None

    neighborhood_data = dict(prop.neighborhood_data or {})
    neighborhood_id = neighborhood_data.get("neighborhood_id") or neighborhood_data.get("id")
    zip_code = neighborhood_data.get("zip_code") or neighborhood_data.get("zip")

    snapshot_kwargs: dict[str, object] = {
        "property_id": prop.id,
        "neighborhood_id": str(neighborhood_id) if neighborhood_id else None,
        "zip_code": str(zip_code) if zip_code else None,
        "jurisdiction": prop.jurisdiction,
        "zoning_code": prop.youto_chiiki,
        "hazard_flags": dict(prop.hazard_flags or {}),
    }

    property_signals = await _latest_signals_for(
        db, subject_type=SUBJECT_PROPERTY, subject_id=prop.id
    )
    snapshot_kwargs = _aggregate(snapshot_kwargs, property_signals)

    # Neighborhood-level signals can be keyed by either an explicit
    # neighborhood_id or by zip_code (the convention used by the backfill).
    # Property signals win over both; between the two neighborhood keys we
    # take whichever resolves first per signal_type.
    neighborhood_keys: list[str] = []
    if neighborhood_id:
        neighborhood_keys.append(str(neighborhood_id))
    if zip_code and str(zip_code) not in neighborhood_keys:
        neighborhood_keys.append(str(zip_code))

    for key in neighborhood_keys:
        neighborhood_signals = await _latest_signals_for(
            db, subject_type=SUBJECT_NEIGHBORHOOD, subject_id=key
        )
        for signal in neighborhood_signals:
            field = _SCALAR_SIGNAL_FIELDS.get(signal.signal_type)
            if (
                field is not None
                and snapshot_kwargs.get(field) is None
                and signal.value is not None
            ):
                snapshot_kwargs[field] = float(signal.value)

    return MarketContextSnapshot(**snapshot_kwargs)


__all__ = ["build_snapshot", "SUBJECT_PROPERTY", "SUBJECT_NEIGHBORHOOD", "SUBJECT_JURISDICTION"]
