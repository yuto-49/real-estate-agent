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
    # JP (MLIT REINFOLIB) scalars.
    "median_unit_price": "median_unit_price",
    "land_price_psm": "land_price_psm",
    "appraised_value_psm": "appraised_value_psm",
}

# REINFOLIB emits one signal_type per hazard kind; FEMA emitted a single
# generic ``hazard`` row carrying a payload. Both fold into ``hazard_flags``.
_HAZARD_SIGNAL_KINDS: Final[dict[str, str]] = {
    "hazard_flood": "flood",
    "hazard_landslide": "landslide",
    "hazard_liquefaction": "liquefaction",
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

        hazard_kind = _HAZARD_SIGNAL_KINDS.get(signal.signal_type)
        if hazard_kind is not None:
            # The scalar is the headline severity/depth; the payload carries the
            # provider's detail (rank, source layer) when present.
            if signal.value is not None:
                hazard_flags[hazard_kind] = float(signal.value)
            payload = dict(signal.payload or {})
            if payload:
                hazard_flags[f"{hazard_kind}_detail"] = payload
            continue

    snapshot_kwargs["hazard_flags"] = hazard_flags
    return snapshot_kwargs


async def _latest_signals_bulk(
    db: AsyncSession,
    *,
    subject_type: str,
    subject_ids: Iterable[str],
) -> dict[str, list[MarketSignal]]:
    """Latest signal per ``signal_type`` for many subjects in one query.

    Returns ``{subject_id: [latest MarketSignal per signal_type]}``. Subjects
    with no signals are simply absent from the map. One round-trip regardless of
    how many subjects are requested.
    """
    ids = [sid for sid in dict.fromkeys(subject_ids) if sid]
    if not ids:
        return {}

    stmt = (
        select(MarketSignal)
        .where(MarketSignal.subject_type == subject_type)
        .where(MarketSignal.subject_id.in_(ids))
        .order_by(MarketSignal.observed_at.desc())
    )
    rows: list[MarketSignal] = list((await db.execute(stmt)).scalars().all())

    by_subject: dict[str, dict[str, MarketSignal]] = {}
    for row in rows:
        per_type = by_subject.setdefault(row.subject_id, {})
        if row.signal_type not in per_type:  # rows are observed_at desc → first wins
            per_type[row.signal_type] = row
    return {sid: list(per_type.values()) for sid, per_type in by_subject.items()}


def _neighborhood_keys(prop: Property) -> tuple[list[str], str | None, str | None]:
    """Resolve a property's ordered neighborhood lookup keys + id/zip.

    Neighborhood-level signals can be keyed by an explicit ``neighborhood_id``,
    by ``zip_code`` (the US backfill convention), or by ``ward_code`` — the
    5-digit MLIT municipality code the REINFOLIB providers key their signals by.
    The id is tried first, then the zip, then the ward code.
    """
    neighborhood_data = dict(prop.neighborhood_data or {})
    neighborhood_id = neighborhood_data.get("neighborhood_id") or neighborhood_data.get("id")
    zip_code = neighborhood_data.get("zip_code") or neighborhood_data.get("zip")
    ward_code = getattr(prop, "ward_code", None)

    keys: list[str] = []
    if neighborhood_id:
        keys.append(str(neighborhood_id))
    if zip_code and str(zip_code) not in keys:
        keys.append(str(zip_code))
    if ward_code and str(ward_code) not in keys:
        keys.append(str(ward_code))
    return (
        keys,
        str(neighborhood_id) if neighborhood_id else None,
        str(zip_code) if zip_code else None,
    )


def _compose_snapshot(
    prop: Property,
    property_signals: Iterable[MarketSignal],
    neighborhood_signals_by_key: dict[str, list[MarketSignal]],
) -> MarketContextSnapshot:
    """Fold a property's preloaded signals into a snapshot (pure, no I/O).

    Property-level signals win; neighborhood keys then fill any still-unresolved
    scalar field in key order. Shared by :func:`build_snapshot` (single) and
    :func:`build_snapshots` (batched) so both compose identically.
    """
    keys, neighborhood_id, zip_code = _neighborhood_keys(prop)

    snapshot_kwargs: dict[str, object] = {
        "property_id": prop.id,
        "neighborhood_id": neighborhood_id,
        "zip_code": zip_code,
        "jurisdiction": prop.jurisdiction,
        "zoning_code": prop.youto_chiiki,
        "hazard_flags": dict(prop.hazard_flags or {}),
    }
    snapshot_kwargs = _aggregate(snapshot_kwargs, property_signals)

    hazard_flags: dict[str, object] = dict(snapshot_kwargs.get("hazard_flags") or {})
    for key in keys:
        for signal in neighborhood_signals_by_key.get(key, []):
            field = _SCALAR_SIGNAL_FIELDS.get(signal.signal_type)
            if (
                field is not None
                and snapshot_kwargs.get(field) is None
                and signal.value is not None
            ):
                snapshot_kwargs[field] = float(signal.value)
                continue

            # Neighborhood-level hazard (REINFOLIB keys hazard by municipality).
            # Property-level flags already present win, so only fill gaps.
            hazard_kind = _HAZARD_SIGNAL_KINDS.get(signal.signal_type)
            if hazard_kind is not None and hazard_kind not in hazard_flags:
                if signal.value is not None:
                    hazard_flags[hazard_kind] = float(signal.value)
                payload = dict(signal.payload or {})
                if payload:
                    hazard_flags[f"{hazard_kind}_detail"] = payload

    snapshot_kwargs["hazard_flags"] = hazard_flags
    return MarketContextSnapshot(**snapshot_kwargs)


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

    keys, _, _ = _neighborhood_keys(prop)
    property_signals = await _latest_signals_for(
        db, subject_type=SUBJECT_PROPERTY, subject_id=prop.id
    )
    neighborhood_signals_by_key = {
        key: await _latest_signals_for(
            db, subject_type=SUBJECT_NEIGHBORHOOD, subject_id=key
        )
        for key in keys
    }
    return _compose_snapshot(prop, property_signals, neighborhood_signals_by_key)


async def build_snapshots(
    db: AsyncSession,
    properties: Iterable[Property],
) -> dict[str, MarketContextSnapshot]:
    """Batched :func:`build_snapshot` — one snapshot per preloaded property.

    Issues exactly two signal queries (property-level + neighborhood-level)
    regardless of how many properties are passed, instead of the per-property
    fan-out. The caller supplies already-loaded ``Property`` rows so no
    redundant property query is made. Returns ``{property_id: snapshot}``.
    """
    props = list(properties)
    if not props:
        return {}

    property_signals_by_subject = await _latest_signals_bulk(
        db, subject_type=SUBJECT_PROPERTY, subject_ids=[p.id for p in props]
    )

    all_keys: list[str] = []
    seen: set[str] = set()
    for prop in props:
        keys, _, _ = _neighborhood_keys(prop)
        for key in keys:
            if key not in seen:
                seen.add(key)
                all_keys.append(key)

    neighborhood_signals_by_key = await _latest_signals_bulk(
        db, subject_type=SUBJECT_NEIGHBORHOOD, subject_ids=all_keys
    )

    return {
        prop.id: _compose_snapshot(
            prop,
            property_signals_by_subject.get(prop.id, []),
            neighborhood_signals_by_key,
        )
        for prop in props
    }


async def neighborhood_snapshots(
    db: AsyncSession,
    zip_codes: Iterable[str],
) -> dict[str, MarketContextSnapshot]:
    """Batched neighborhood-only snapshots keyed by zip — one query for all zips.

    For off-platform holdings with no linked property: build a minimal snapshot
    from neighborhood scalar signals. Mirrors the single-zip fallback used by the
    holding-decision service. Returns ``{zip_code: snapshot}`` for every requested
    zip (fields stay ``None`` when no signal resolves).
    """
    zips = [z for z in dict.fromkeys(zip_codes) if z]
    if not zips:
        return {}

    signals_by_zip = await _latest_signals_bulk(
        db, subject_type=SUBJECT_NEIGHBORHOOD, subject_ids=zips
    )

    snapshots: dict[str, MarketContextSnapshot] = {}
    for zip_code in zips:
        kwargs: dict[str, object] = {"zip_code": zip_code}
        for signal in signals_by_zip.get(zip_code, []):
            field = _SCALAR_SIGNAL_FIELDS.get(signal.signal_type)
            if field is not None and signal.value is not None:
                kwargs[field] = float(signal.value)
        snapshots[zip_code] = MarketContextSnapshot(**kwargs)
    return snapshots


__all__ = [
    "build_snapshot",
    "build_snapshots",
    "neighborhood_snapshots",
    "SUBJECT_PROPERTY",
    "SUBJECT_NEIGHBORHOOD",
    "SUBJECT_JURISDICTION",
]
