"""FEMA NFHL → property hazard signal.

Source: FEMA National Flood Hazard Layer ArcGIS service (public, no key).
For each property (lat/lng), we query the flood-hazard polygon layer and
emit a ``hazard`` signal with the flood zone code and SFHA flag.

NFHL zone codes (subset):
- ``A``, ``AE``, ``AH``, ``AO``, ``AR``, ``V``, ``VE`` → Special Flood Hazard Area
- ``X`` (shaded or unshaded) → minimal risk
- Missing feature → assumed Zone X (no mapped flood risk)
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, Final

import httpx

from services.signal_providers.base import ExternalSignal


NFHL_QUERY_ENDPOINT: Final[str] = (
    "https://hazards.fema.gov/gis/nfhl/rest/services/public/NFHL/MapServer/28/query"
)

SFHA_ZONES: Final[frozenset[str]] = frozenset(
    {"A", "AE", "AH", "AO", "AR", "A99", "V", "VE"}
)


class FemaNfhlProvider:
    """Pulls flood-zone classification per property."""

    name: Final[str] = "fema_nfhl"

    def __init__(self, *, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def fetch(
        self,
        *,
        properties: Sequence[Mapping[str, Any]] | None = None,
        observed_at: datetime | None = None,
        **_: Any,
    ) -> Sequence[ExternalSignal]:
        if not properties:
            return ()
        client = self._client or httpx.AsyncClient(timeout=15.0)
        owns = self._client is None
        when = observed_at or datetime.utcnow()

        try:
            results: list[ExternalSignal] = []
            for prop in properties:
                pid = prop.get("id")
                lat, lng = prop.get("latitude"), prop.get("longitude")
                if not pid or lat is None or lng is None:
                    continue
                zone, subtype = await self._lookup_zone(client, float(lat), float(lng))
                in_sfha = zone in SFHA_ZONES
                # Numeric value: higher = riskier (0..10 scale)
                hazard_score = 7.0 if in_sfha else (3.0 if zone.startswith("X") else 0.5)
                results.append(
                    ExternalSignal(
                        signal_type="hazard",
                        subject_type="property",
                        subject_id=str(pid),
                        observed_at=when,
                        value=hazard_score,
                        payload={
                            "flood_zone": zone,
                            "zone_subtype": subtype,
                            "in_special_flood_hazard_area": in_sfha,
                            "source": "fema_nfhl",
                        },
                    )
                )
            return tuple(results)
        finally:
            if owns:
                await client.aclose()

    async def _lookup_zone(
        self, client: httpx.AsyncClient, lat: float, lng: float
    ) -> tuple[str, str | None]:
        params = {
            "f": "json",
            "geometry": f"{lng},{lat}",
            "geometryType": "esriGeometryPoint",
            "inSR": "4326",
            "outFields": "FLD_ZONE,ZONE_SUBTY,SFHA_TF",
            "returnGeometry": "false",
        }
        resp = await client.get(NFHL_QUERY_ENDPOINT, params=params)
        resp.raise_for_status()
        features = resp.json().get("features") or []
        if not features:
            return "X", None
        attrs = features[0].get("attributes", {})
        zone = str(attrs.get("FLD_ZONE") or "X")
        subtype = attrs.get("ZONE_SUBTY")
        return zone, subtype


__all__ = ["FemaNfhlProvider", "SFHA_ZONES"]
