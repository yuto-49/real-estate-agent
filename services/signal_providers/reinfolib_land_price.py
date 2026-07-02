"""MLIT REINFOLIB XPT002 → land price per sqm signals (tile-based GeoJSON).

Source: REINFOLIB External API, endpoint ``XPT002``
(https://www.reinfolib.mlit.go.jp/help/apiManual/).

The XPT002 endpoint returns a GeoJSON FeatureCollection of land-price survey
points within a given map tile.  Each Feature carries price-per-sqm, zoning,
FAR/BCR, station distance, YoY change rate, and other appraisal metadata.

Signals emitted (``subject_type="neighborhood"``, ``subject_id=<point_id>``):

- ``land_price_psm`` — assessed land price per square metre (¥/m²)
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Final

import httpx

from services.signal_providers.base import ExternalSignal
from services.signal_providers.reinfolib_base import (
    TOKYO_23_BBOX,
    reinfolib_get,
    tiles_covering_bbox,
)

logger = logging.getLogger(__name__)

_ENDPOINT: Final[str] = "XPT002"
_MAX_TILES: Final[int] = 50


class ReinfolibLandPriceProvider:
    """Fetches land-price survey points from REINFOLIB XPT002 (tile GeoJSON)."""

    name: Final[str] = "reinfolib_land_price"

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        api_key: str | None = None,
    ) -> None:
        if not api_key:
            raise ValueError(
                "ReinfolibLandPriceProvider requires api_key "
                "(set REINFOLIB_API_KEY env)"
            )
        self._client = client
        self._api_key = api_key

    async def fetch(
        self,
        *,
        year: int | None = None,
        bbox: tuple[float, float, float, float] | None = None,
        zoom: int = 14,
        observed_at: datetime | None = None,
        **_: Any,
    ) -> Sequence[ExternalSignal]:
        """Fetch land-price signals for tiles covering *bbox*.

        Parameters
        ----------
        year:
            Survey year (NNNN).  Defaults to the current year.
        bbox:
            ``(min_lat, min_lng, max_lat, max_lng)``.  Defaults to
            :data:`TOKYO_23_BBOX`.
        zoom:
            Tile zoom level.  Defaults to 14.
        observed_at:
            Timestamp to stamp on emitted signals.  Defaults to now (UTC).
        """
        resolved_year = year or datetime.now(UTC).year
        resolved_bbox = bbox or TOKYO_23_BBOX
        when = observed_at or datetime.now(UTC)

        tiles = tiles_covering_bbox(*resolved_bbox, zoom)

        if len(tiles) > _MAX_TILES:
            logger.warning(
                "reinfolib_land_price: %d tiles exceed limit of %d — truncating",
                len(tiles),
                _MAX_TILES,
            )
            tiles = tiles[:_MAX_TILES]

        client = self._client or httpx.AsyncClient(timeout=30.0)
        owns = self._client is None

        try:
            results: list[ExternalSignal] = []
            for x, y in tiles:
                signals = await self._fetch_tile(
                    client, x, y, zoom, resolved_year, when,
                )
                results.extend(signals)
            return tuple(results)
        finally:
            if owns:
                await client.aclose()

    async def _fetch_tile(
        self,
        client: httpx.AsyncClient,
        x: int,
        y: int,
        zoom: int,
        year: int,
        when: datetime,
    ) -> list[ExternalSignal]:
        params: dict[str, str] = {
            "response_format": "geojson",
            "z": str(zoom),
            "x": str(x),
            "y": str(y),
            "year": str(year),
        }

        body = await reinfolib_get(client, _ENDPOINT, self._api_key, params)
        if body is None:
            return []

        features: list[dict[str, Any]] = body.get("features") or []
        signals: list[ExternalSignal] = []

        for feature in features:
            props: dict[str, Any] = feature.get("properties") or {}
            price = _to_float(props.get("price"))
            if price is None:
                continue

            point_id = props.get("point_id") or props.get("location") or ""
            if not point_id:
                continue

            coords = _extract_coords(feature)

            signals.append(
                ExternalSignal(
                    signal_type="land_price_psm",
                    subject_type="neighborhood",
                    subject_id=str(point_id),
                    observed_at=when,
                    value=price,
                    payload={
                        "source": "reinfolib",
                        "endpoint": _ENDPOINT,
                        "year": year,
                        "use_category": props.get("use_category_name"),
                        "floor_area_ratio": _to_float(
                            props.get("floor_area_ratio"),
                        ),
                        "building_coverage_ratio": _to_float(
                            props.get("building_coverage_ratio"),
                        ),
                        "change_rate_yoy": _to_float(
                            props.get("change_rate"),
                        ),
                        "distance_station_m": _to_float(
                            props.get("distance_station"),
                        ),
                        "front_road_width_m": _to_float(
                            props.get("front_road_width"),
                        ),
                        "coordinates": coords,
                    },
                )
            )

        return signals


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _to_float(raw: Any) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _extract_coords(feature: dict[str, Any]) -> list[float] | None:
    """Return ``[lat, lng]`` from a GeoJSON Point feature, or *None*."""
    geometry = feature.get("geometry") or {}
    coords = geometry.get("coordinates")
    if not isinstance(coords, (list, tuple)) or len(coords) < 2:
        return None
    # GeoJSON is [lng, lat]; return as [lat, lng] for consistency
    return [coords[1], coords[0]]


__all__ = ["ReinfolibLandPriceProvider"]
