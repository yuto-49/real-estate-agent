"""MLIT REINFOLIB XCT001 — appraised valuation (assessment prices) per parcel.

Source: REINFOLIB API ``XCT001`` (parameter-based, non-tile).
Requires ``REINFOLIB_API_KEY`` (``Ocp-Apim-Subscription-Key``).

Parameters accepted by the endpoint:

- ``year``     — survey year (YYYY)
- ``area``     — comma-separated 2-digit prefecture codes
- ``division`` — land-use division (00 = residential, 05 = commercial, etc.)

Signals emitted (``subject_type="neighborhood"``):

- ``appraised_value_psm`` — appraised valuation per square metre (yen)

Each record carries a rich ``payload`` with zoning, road-access, utility,
transit, and coordinate metadata extracted from the ~60-field MLIT response.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Final

import httpx

from services.signal_providers.base import ExternalSignal
from services.signal_providers.reinfolib_base import reinfolib_get

ENDPOINT: Final[str] = "XCT001"

# Default prefecture: 13 = Tokyo
DEFAULT_PREFECTURES: Final[Sequence[str]] = ("13",)

# Default land-use divisions: residential + commercial
DEFAULT_DIVISIONS: Final[Sequence[str]] = ("00", "05")


class ReinfolibAppraisalProvider:
    """Fetches appraised-valuation signals from MLIT REINFOLIB XCT001."""

    name: Final[str] = "reinfolib_appraisal"

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        api_key: str | None = None,
    ) -> None:
        if not api_key:
            raise ValueError(
                "ReinfolibAppraisalProvider requires api_key "
                "(set REINFOLIB_API_KEY env)"
            )
        self._client = client
        self._api_key = api_key

    async def fetch(
        self,
        *,
        year: int | None = None,
        prefecture_codes: Sequence[str] | None = None,
        divisions: Sequence[str] | None = None,
        observed_at: datetime | None = None,
        **_: Any,
    ) -> Sequence[ExternalSignal]:
        """Fetch appraised-valuation signals for the given prefectures.

        Parameters
        ----------
        year:
            Survey year (YYYY). Defaults to the current year.
        prefecture_codes:
            2-digit prefecture codes (e.g. ``["13", "14"]``).
            Defaults to ``["13"]`` (Tokyo).
        divisions:
            Land-use division codes (e.g. ``["00", "05"]``).
            Defaults to residential + commercial.
        observed_at:
            Timestamp to stamp on the signals. Defaults to now (UTC).
        """
        when = observed_at or datetime.now(UTC)
        resolved_year = year or datetime.now(UTC).year
        prefectures = prefecture_codes or DEFAULT_PREFECTURES
        divs = divisions or DEFAULT_DIVISIONS
        area_param = ",".join(prefectures)

        client = self._client or httpx.AsyncClient(timeout=30.0)
        owns = self._client is None

        try:
            results: list[ExternalSignal] = []
            for division in divs:
                params: dict[str, str] = {
                    "year": str(resolved_year),
                    "area": area_param,
                    "division": division,
                }
                body = await reinfolib_get(
                    client, ENDPOINT, self._api_key, params=params,
                )
                if body is None:
                    continue
                results.extend(
                    _parse_records(body, division, resolved_year, when)
                )
            return tuple(results)
        finally:
            if owns:
                await client.aclose()


# ------------------------------------------------------------------
# Parsing helpers
# ------------------------------------------------------------------

def _parse_records(
    body: dict[str, Any],
    division: str,
    year: int,
    when: datetime,
) -> list[ExternalSignal]:
    """Extract ``ExternalSignal`` records from an XCT001 response body."""
    data: list[dict[str, Any]] = body.get("data", [])
    if not isinstance(data, list):
        return []

    signals: list[ExternalSignal] = []
    for record in data:
        signal = _record_to_signal(record, division, year, when)
        if signal is not None:
            signals.append(signal)
    return signals


def _record_to_signal(
    record: dict[str, Any],
    division: str,
    year: int,
    when: datetime,
) -> ExternalSignal | None:
    """Convert a single XCT001 record to an ``ExternalSignal``.

    Returns ``None`` when the record lacks a usable valuation or identifier.
    """
    value_raw = record.get("L01_006")  # per-sqm appraised price
    value = _to_float(value_raw)
    if value is None:
        return None

    # Build a subject identifier from address or coordinates
    subject_id = _subject_id_from(record)
    if not subject_id:
        return None

    payload: dict[str, Any] = {
        "source": "reinfolib",
        "endpoint": ENDPOINT,
        "year": year,
        "division": division,
    }

    # Zoning
    _put_if(payload, "use_category", record.get("L01_025"))
    _put_if(payload, "floor_area_ratio", _to_float(record.get("L01_024")))
    _put_if(payload, "building_coverage_ratio", _to_float(record.get("L01_023")))

    # Road access
    _put_if(payload, "road_access", record.get("L01_026"))

    # Utilities
    _put_if(payload, "water", record.get("L01_028"))
    _put_if(payload, "gas", record.get("L01_029"))
    _put_if(payload, "sewer", record.get("L01_030"))

    # Transit
    _put_if(payload, "station_distance", _to_float(record.get("L01_034")))

    # Coordinates
    lat = _to_float(record.get("lat"))
    lng = _to_float(record.get("lng"))
    if lat is not None and lng is not None:
        payload["coordinates"] = {"lat": lat, "lng": lng}

    return ExternalSignal(
        signal_type="appraised_value_psm",
        subject_type="neighborhood",
        subject_id=subject_id,
        observed_at=when,
        value=value,
        payload=payload,
    )


def _subject_id_from(record: dict[str, Any]) -> str:
    """Derive a subject identifier from the record.

    Prefers the address field; falls back to ``lat,lng`` point string.
    """
    address = record.get("L01_021") or record.get("L01_019")
    if address:
        return str(address).strip()
    lat = record.get("lat")
    lng = record.get("lng")
    if lat is not None and lng is not None:
        return f"{lat},{lng}"
    return ""


def _to_float(raw: Any) -> float | None:
    """Coerce to float, returning ``None`` on failure or sentinel values."""
    if raw in (None, "", "-", "***", "x", "X"):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _put_if(d: dict[str, Any], key: str, val: Any) -> None:
    """Add *val* to *d* under *key* only when *val* is not ``None``."""
    if val is not None:
        d[key] = val


__all__ = ["ReinfolibAppraisalProvider"]
