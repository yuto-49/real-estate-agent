"""MLIT REINFOLIB hazard endpoints → liquefaction, flood, landslide signals.

Wraps three tile-based GeoJSON endpoints from the REINFOLIB API:

- **XKT025** — Liquefaction risk (mesh-level, zoom 11-15)
- **XKT026** — Flood inundation zones (zoom 14-15)
- **XKT029** — Landslide disaster warning zones (zoom 11-15)

Signals emitted (``subject_type="neighborhood"``):

- ``hazard_liquefaction`` — 0-10 score from 6-level liquefaction tendency
  (``subject_id=<mesh_code>``)
- ``hazard_flood`` — 0-10 score from inundation depth category
  (``subject_id="<z>/<x>/<y>"``)
- ``hazard_landslide`` — 8 if features present in tile, else 0
  (``subject_id="<z>/<x>/<y>"``)

Requires ``REINFOLIB_API_KEY`` (Ocp-Apim-Subscription-Key).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Final

import httpx

from services.signal_providers.base import ExternalSignal
from services.signal_providers.reinfolib_base import lat_lng_to_tile, reinfolib_get

# ---------------------------------------------------------------------------
# Endpoint identifiers
# ---------------------------------------------------------------------------

ENDPOINT_LIQUEFACTION: Final[str] = "XKT025"
ENDPOINT_FLOOD: Final[str] = "XKT026"
ENDPOINT_LANDSLIDE: Final[str] = "XKT029"

# ---------------------------------------------------------------------------
# Default coordinates (Tokyo center)
# ---------------------------------------------------------------------------

DEFAULT_LAT: Final[float] = 35.6762
DEFAULT_LNG: Final[float] = 139.6503

# ---------------------------------------------------------------------------
# Score mappings
# ---------------------------------------------------------------------------

# XKT025: liquefaction_tendency_level text → 0-10 score
_LIQUEFACTION_SCORE: Final[dict[str, int]] = {
    "1": 1,
    "2": 3,
    "3": 5,
    "4": 7,
    "5": 8,
    "6": 10,
}

# XKT026: flood depth category (Japanese) → 0-10 score
_FLOOD_DEPTH_SCORE: Final[dict[str, int]] = {
    "0.5m未満": 2,
    "0.5m~3m": 4,
    "3m~5m": 6,
    "5m~10m": 8,
    "10m以上": 10,
}


class ReinfolibHazardProvider:
    """Fetches hazard risk signals from MLIT REINFOLIB tile endpoints."""

    name: Final[str] = "reinfolib_hazard"

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        api_key: str | None = None,
    ) -> None:
        if not api_key:
            raise ValueError(
                "ReinfolibHazardProvider requires api_key "
                "(set REINFOLIB_API_KEY env)"
            )
        self._client = client
        self._api_key = api_key

    async def fetch(
        self,
        *,
        lat: float | None = None,
        lng: float | None = None,
        radius_tiles: int = 1,
        zoom: int = 14,
        observed_at: datetime | None = None,
        **_: Any,
    ) -> Sequence[ExternalSignal]:
        """Fetch hazard signals for tiles around *lat*/*lng*.

        Parameters
        ----------
        lat, lng:
            Center point. Defaults to Tokyo center (35.6762, 139.6503).
        radius_tiles:
            Number of tiles to expand in each direction from center.
        zoom:
            Tile zoom level (11-15 for most endpoints).
        observed_at:
            Timestamp to stamp on signals. Defaults to now (UTC).
        """
        lat = lat if lat is not None else DEFAULT_LAT
        lng = lng if lng is not None else DEFAULT_LNG
        when = observed_at or datetime.now(UTC)

        client = self._client or httpx.AsyncClient(timeout=30.0)
        owns = self._client is None

        try:
            cx, cy = lat_lng_to_tile(lat, lng, zoom)
            tiles = [
                (x, y)
                for x in range(cx - radius_tiles, cx + radius_tiles + 1)
                for y in range(cy - radius_tiles, cy + radius_tiles + 1)
            ]

            results: list[ExternalSignal] = []
            for tx, ty in tiles:
                results.extend(
                    await self._fetch_liquefaction(client, zoom, tx, ty, when)
                )
                results.extend(
                    await self._fetch_flood(client, zoom, tx, ty, when)
                )
                results.extend(
                    await self._fetch_landslide(client, zoom, tx, ty, when)
                )
            return tuple(results)
        finally:
            if owns:
                await client.aclose()

    # ------------------------------------------------------------------
    # XKT025 — Liquefaction risk
    # ------------------------------------------------------------------

    async def _fetch_liquefaction(
        self,
        client: httpx.AsyncClient,
        z: int,
        x: int,
        y: int,
        when: datetime,
    ) -> list[ExternalSignal]:
        params = {"response_format": "geojson", "z": str(z), "x": str(x), "y": str(y)}
        body = await reinfolib_get(client, ENDPOINT_LIQUEFACTION, self._api_key, params)
        if body is None:
            return []

        features = _extract_features(body)
        signals: list[ExternalSignal] = []
        for feat in features:
            props = feat.get("properties") or {}
            mesh_code = props.get("mesh_code", "")
            if not mesh_code:
                continue
            level_text = str(props.get("liquefaction_tendency_level", ""))
            # Extract leading digit for lookup
            level_key = level_text.strip()[:1] if level_text.strip() else ""
            score = _LIQUEFACTION_SCORE.get(level_key, 0)
            signals.append(
                ExternalSignal(
                    signal_type="hazard_liquefaction",
                    subject_type="neighborhood",
                    subject_id=str(mesh_code),
                    observed_at=when,
                    value=float(score),
                    payload={
                        "source": "reinfolib",
                        "endpoint": ENDPOINT_LIQUEFACTION,
                        "liquefaction_tendency_level": level_text,
                        "coordinates": _feature_coords(feat),
                    },
                )
            )
        return signals

    # ------------------------------------------------------------------
    # XKT026 — Flood inundation
    # ------------------------------------------------------------------

    async def _fetch_flood(
        self,
        client: httpx.AsyncClient,
        z: int,
        x: int,
        y: int,
        when: datetime,
    ) -> list[ExternalSignal]:
        params = {"response_format": "geojson", "z": str(z), "x": str(x), "y": str(y)}
        body = await reinfolib_get(client, ENDPOINT_FLOOD, self._api_key, params)
        if body is None:
            return []

        tile_key = f"{z}/{x}/{y}"
        features = _extract_features(body)
        signals: list[ExternalSignal] = []
        for feat in features:
            props = feat.get("properties") or {}
            depth_text = _resolve_flood_depth(props)
            score = _FLOOD_DEPTH_SCORE.get(depth_text, 0)
            signals.append(
                ExternalSignal(
                    signal_type="hazard_flood",
                    subject_type="neighborhood",
                    subject_id=tile_key,
                    observed_at=when,
                    value=float(score),
                    payload={
                        "source": "reinfolib",
                        "endpoint": ENDPOINT_FLOOD,
                        "flood_depth_category": depth_text,
                        "coordinates": _feature_coords(feat),
                    },
                )
            )
        return signals

    # ------------------------------------------------------------------
    # XKT029 — Landslide disaster warning zones
    # ------------------------------------------------------------------

    async def _fetch_landslide(
        self,
        client: httpx.AsyncClient,
        z: int,
        x: int,
        y: int,
        when: datetime,
    ) -> list[ExternalSignal]:
        params = {"response_format": "geojson", "z": str(z), "x": str(x), "y": str(y)}
        body = await reinfolib_get(client, ENDPOINT_LANDSLIDE, self._api_key, params)
        if body is None:
            return []

        tile_key = f"{z}/{x}/{y}"
        features = _extract_features(body)
        score = 8.0 if features else 0.0

        if not features:
            return [
                ExternalSignal(
                    signal_type="hazard_landslide",
                    subject_type="neighborhood",
                    subject_id=tile_key,
                    observed_at=when,
                    value=score,
                    payload={
                        "source": "reinfolib",
                        "endpoint": ENDPOINT_LANDSLIDE,
                        "zone_classification": None,
                        "phenomenon_type": None,
                        "coordinates": None,
                    },
                )
            ]

        signals: list[ExternalSignal] = []
        for feat in features:
            props = feat.get("properties") or {}
            signals.append(
                ExternalSignal(
                    signal_type="hazard_landslide",
                    subject_type="neighborhood",
                    subject_id=tile_key,
                    observed_at=when,
                    value=score,
                    payload={
                        "source": "reinfolib",
                        "endpoint": ENDPOINT_LANDSLIDE,
                        "zone_classification": props.get("zone_classification"),
                        "phenomenon_type": props.get("phenomenon_type"),
                        "coordinates": _feature_coords(feat),
                    },
                )
            )
        return signals


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _extract_features(body: Any) -> list[dict[str, Any]]:
    """Safely extract the ``features`` list from a GeoJSON response."""
    if not isinstance(body, dict):
        return []
    features = body.get("features")
    if not isinstance(features, list):
        return []
    return features


def _feature_coords(feat: dict[str, Any]) -> Any:
    """Return the geometry coordinates from a GeoJSON feature, or None."""
    geom = feat.get("geometry")
    if isinstance(geom, dict):
        return geom.get("coordinates")
    return None


def _resolve_flood_depth(props: dict[str, Any]) -> str:
    """Extract the flood depth category string from feature properties.

    REINFOLIB XKT026 may encode depth under various property names.
    We look through common candidates and return the first match found
    in the known depth-score map, falling back to empty string.
    """
    candidates = (
        "depth_category",
        "flood_depth",
        "depth",
        "rank",
        "classification",
    )
    for key in candidates:
        val = props.get(key)
        if isinstance(val, str) and val in _FLOOD_DEPTH_SCORE:
            return val
    # Fallback: check all string values for a known depth category
    for val in props.values():
        if isinstance(val, str) and val in _FLOOD_DEPTH_SCORE:
            return val
    return ""


__all__ = ["ReinfolibHazardProvider"]
