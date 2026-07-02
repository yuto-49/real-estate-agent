"""Shared utilities for MLIT REINFOLIB API providers.

All REINFOLIB endpoints require an ``Ocp-Apim-Subscription-Key`` header and
return gzip-encoded JSON.  The tile-based endpoints (XPT/XKT) use the XYZ
tile coordinate system — helpers here convert lat/lng → tile x/y.

See https://www.reinfolib.mlit.go.jp/help/apiManual/ for full docs.
"""

from __future__ import annotations

import math
from typing import Any, Final

import httpx

REINFOLIB_BASE: Final[str] = "https://www.reinfolib.mlit.go.jp/ex-api/external"


async def reinfolib_get(
    client: httpx.AsyncClient,
    endpoint: str,
    api_key: str,
    params: dict[str, str] | None = None,
) -> Any:
    """GET a REINFOLIB endpoint, returning parsed JSON.

    Raises ``httpx.HTTPStatusError`` on 4xx/5xx **except** 404 which returns
    ``None`` (REINFOLIB uses 404 for "no data found").
    """
    url = f"{REINFOLIB_BASE}/{endpoint}"
    headers = {"Ocp-Apim-Subscription-Key": api_key}
    resp = await client.get(url, params=params, headers=headers)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# XYZ tile coordinate math (Web Mercator / EPSG:3857)
# ---------------------------------------------------------------------------

def lat_lng_to_tile(lat: float, lng: float, zoom: int) -> tuple[int, int]:
    """Convert latitude/longitude to XYZ tile coordinates at *zoom* level.

    Returns ``(x, y)`` tile indices.
    """
    n = 2 ** zoom
    x = int((lng + 180.0) / 360.0 * n)
    lat_rad = math.radians(lat)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def tile_bounds(x: int, y: int, zoom: int) -> tuple[float, float, float, float]:
    """Return (min_lat, min_lng, max_lat, max_lng) for a given tile."""
    n = 2 ** zoom
    min_lng = x / n * 360.0 - 180.0
    max_lng = (x + 1) / n * 360.0 - 180.0
    max_lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    min_lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
    return min_lat, min_lng, max_lat, max_lng


def tiles_covering_bbox(
    min_lat: float,
    min_lng: float,
    max_lat: float,
    max_lng: float,
    zoom: int,
) -> list[tuple[int, int]]:
    """Return all tile (x, y) tuples that cover a bounding box at *zoom*."""
    x_min, y_min = lat_lng_to_tile(max_lat, min_lng, zoom)  # top-left
    x_max, y_max = lat_lng_to_tile(min_lat, max_lng, zoom)  # bottom-right
    tiles: list[tuple[int, int]] = []
    for x in range(x_min, x_max + 1):
        for y in range(y_min, y_max + 1):
            tiles.append((x, y))
    return tiles


# Tokyo 23-ward bounding box (approximate)
TOKYO_23_BBOX: Final[tuple[float, float, float, float]] = (
    35.53,   # min_lat  (south — Ota-ku)
    139.56,  # min_lng  (west  — Suginami-ku)
    35.82,   # max_lat  (north — Adachi-ku)
    139.92,  # max_lng  (east  — Edogawa-ku)
)

# Tokyo 23-ward 5-digit municipality codes
TOKYO_23_CITY_CODES: Final[tuple[str, ...]] = (
    "13101", "13102", "13103", "13104", "13105", "13106", "13107",
    "13108", "13109", "13110", "13111", "13112", "13113", "13114",
    "13115", "13116", "13117", "13118", "13119", "13120", "13121",
    "13122", "13123",
)


__all__ = [
    "REINFOLIB_BASE",
    "TOKYO_23_BBOX",
    "TOKYO_23_CITY_CODES",
    "lat_lng_to_tile",
    "reinfolib_get",
    "tile_bounds",
    "tiles_covering_bbox",
]
