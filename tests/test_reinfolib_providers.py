"""REINFOLIB signal provider tests — transaction, land price, appraisal, hazard."""

from __future__ import annotations

import httpx
import pytest

from services.signal_providers.reinfolib_base import (
    lat_lng_to_tile,
    tile_bounds,
    tiles_covering_bbox,
)
from services.signal_providers.reinfolib_transaction import ReinfolibTransactionProvider
from services.signal_providers.reinfolib_land_price import ReinfolibLandPriceProvider
from services.signal_providers.reinfolib_appraisal import ReinfolibAppraisalProvider
from services.signal_providers.reinfolib_hazard import (
    ENDPOINT_FLOOD,
    ENDPOINT_LANDSLIDE,
    ENDPOINT_LIQUEFACTION,
    ReinfolibHazardProvider,
)


# ── Tile math tests ──────────────────────────────────────────────────────


def test_lat_lng_to_tile_tokyo():
    """Tokyo Station at zoom 14 should land in a known tile range."""
    x, y = lat_lng_to_tile(35.6812, 139.7671, 14)
    assert 14000 < x < 15000
    assert 6000 < y < 7000


def test_tile_bounds_round_trip():
    """Converting a tile's center back to a tile should give the same tile."""
    x, y, z = 14552, 6451, 14
    min_lat, min_lng, max_lat, max_lng = tile_bounds(x, y, z)
    cx, cy = lat_lng_to_tile((min_lat + max_lat) / 2, (min_lng + max_lng) / 2, z)
    assert (cx, cy) == (x, y)


def test_tiles_covering_bbox():
    """Small bbox should produce a reasonable tile count."""
    tiles = tiles_covering_bbox(35.65, 139.70, 35.70, 139.75, 14)
    assert len(tiles) > 0
    assert len(tiles) < 100


# ── Transaction provider (XIT001) ────────────────────────────────────────

_XIT001_RESPONSE = {
    "data": [
        {"TradePrice": "50000000", "UnitPrice": "350000", "Area": "100"},
        {"TradePrice": "60000000", "UnitPrice": "400000", "Area": "120"},
        {"TradePrice": "55000000", "UnitPrice": "380000", "Area": "110"},
        {"TradePrice": "", "UnitPrice": None},  # missing — should be skipped
    ]
}


def _xit001_handler(request: httpx.Request) -> httpx.Response:
    if "XIT001" in str(request.url):
        return httpx.Response(200, json=_XIT001_RESPONSE)
    return httpx.Response(404)


def test_transaction_requires_api_key():
    with pytest.raises(ValueError, match="api_key"):
        ReinfolibTransactionProvider(api_key=None)


@pytest.mark.asyncio
async def test_transaction_median_signals():
    transport = httpx.MockTransport(_xit001_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = ReinfolibTransactionProvider(client=client, api_key="test-key")
        signals = await provider.fetch(
            year=2025, quarter=1, city_codes=["13101"],
        )

    by_type = {s.signal_type: s for s in signals}
    assert "median_sale_price" in by_type
    assert "median_unit_price" in by_type

    sale = by_type["median_sale_price"]
    assert sale.subject_type == "neighborhood"
    assert sale.subject_id == "13101"
    assert sale.value == 55000000.0  # median of 50M, 55M, 60M
    assert sale.payload["source"] == "reinfolib"

    unit = by_type["median_unit_price"]
    assert unit.value == 380000.0  # median of 350k, 380k, 400k


@pytest.mark.asyncio
async def test_transaction_404_returns_empty():
    transport = httpx.MockTransport(lambda _: httpx.Response(404))
    async with httpx.AsyncClient(transport=transport) as client:
        provider = ReinfolibTransactionProvider(client=client, api_key="test-key")
        signals = await provider.fetch(year=2025, quarter=1, city_codes=["99999"])

    assert len(signals) == 0


# ── Land price provider (XPT002) ─────────────────────────────────────────

_XPT002_RESPONSE = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [139.75, 35.68]},
            "properties": {
                "point_id": "T-13-00001",
                "price": "500000",
                "use_category_name": "住宅",
                "floor_area_ratio": "200",
                "building_coverage_ratio": "60",
                "change_rate": "1.5",
                "distance_station": "800",
                "front_road_width": "6.0",
            },
        },
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [139.76, 35.69]},
            "properties": {
                "point_id": "",  # empty — should be skipped
                "price": "600000",
            },
        },
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [139.77, 35.70]},
            "properties": {
                "point_id": "T-13-00002",
                "price": None,  # missing price — should be skipped
            },
        },
    ],
}


def _xpt002_handler(request: httpx.Request) -> httpx.Response:
    if "XPT002" in str(request.url):
        return httpx.Response(200, json=_XPT002_RESPONSE)
    return httpx.Response(404)


def test_land_price_requires_api_key():
    with pytest.raises(ValueError, match="api_key"):
        ReinfolibLandPriceProvider(api_key="")


@pytest.mark.asyncio
async def test_land_price_signals():
    transport = httpx.MockTransport(_xpt002_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = ReinfolibLandPriceProvider(client=client, api_key="test-key")
        signals = await provider.fetch(
            year=2025, bbox=(35.68, 139.75, 35.69, 139.76), zoom=14,
        )

    assert len(signals) == 1  # only T-13-00001 has both point_id and price
    sig = signals[0]
    assert sig.signal_type == "land_price_psm"
    assert sig.subject_id == "T-13-00001"
    assert sig.value == 500000.0
    assert sig.payload["use_category"] == "住宅"
    assert sig.payload["floor_area_ratio"] == 200.0
    assert sig.payload["coordinates"] == [35.68, 139.75]  # [lat, lng]


# ── Appraisal provider (XCT001) ─────────────────────────────────────────

_XCT001_RESPONSE = {
    "data": [
        {
            "L01_006": "450000",
            "L01_021": "東京都千代田区丸の内1-1",
            "L01_023": "80",
            "L01_024": "400",
            "L01_025": "商業地域",
            "L01_026": "南8.0m",
            "L01_028": "水道",
            "L01_029": "ガス",
            "L01_030": "下水",
            "L01_034": "200",
            "lat": "35.6812",
            "lng": "139.7671",
        },
        {
            "L01_006": None,  # no valuation — skip
            "L01_021": "東京都中央区銀座",
        },
    ]
}


def _xct001_handler(request: httpx.Request) -> httpx.Response:
    if "XCT001" in str(request.url):
        return httpx.Response(200, json=_XCT001_RESPONSE)
    return httpx.Response(404)


def test_appraisal_requires_api_key():
    with pytest.raises(ValueError, match="api_key"):
        ReinfolibAppraisalProvider(api_key="")


@pytest.mark.asyncio
async def test_appraisal_signals():
    transport = httpx.MockTransport(_xct001_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = ReinfolibAppraisalProvider(client=client, api_key="test-key")
        signals = await provider.fetch(
            year=2025, prefecture_codes=["13"], divisions=["05"],
        )

    assert len(signals) == 1
    sig = signals[0]
    assert sig.signal_type == "appraised_value_psm"
    assert sig.subject_id == "東京都千代田区丸の内1-1"
    assert sig.value == 450000.0
    assert sig.payload["division"] == "05"
    assert sig.payload["use_category"] == "商業地域"
    assert sig.payload["floor_area_ratio"] == 400.0
    assert sig.payload["building_coverage_ratio"] == 80.0
    assert sig.payload["coordinates"] == {"lat": 35.6812, "lng": 139.7671}


@pytest.mark.asyncio
async def test_appraisal_404_returns_empty():
    transport = httpx.MockTransport(lambda _: httpx.Response(404))
    async with httpx.AsyncClient(transport=transport) as client:
        provider = ReinfolibAppraisalProvider(client=client, api_key="test-key")
        signals = await provider.fetch(year=2025)
    assert len(signals) == 0


# ── Hazard provider (XKT025/026/029) ────────────────────────────────────

_LIQUEFACTION_RESPONSE = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [139.75, 35.68]},
            "properties": {
                "mesh_code": "533935",
                "liquefaction_tendency_level": "4",
            },
        },
    ],
}

_FLOOD_RESPONSE = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [[[139.7, 35.6]]]},
            "properties": {"depth_category": "3m~5m"},
        },
    ],
}

_LANDSLIDE_RESPONSE = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [[[139.7, 35.6]]]},
            "properties": {
                "zone_classification": "警戒区域",
                "phenomenon_type": "土石流",
            },
        },
    ],
}

_EMPTY_GEOJSON = {"type": "FeatureCollection", "features": []}


def _hazard_handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if ENDPOINT_LIQUEFACTION in url:
        return httpx.Response(200, json=_LIQUEFACTION_RESPONSE)
    if ENDPOINT_FLOOD in url:
        return httpx.Response(200, json=_FLOOD_RESPONSE)
    if ENDPOINT_LANDSLIDE in url:
        return httpx.Response(200, json=_LANDSLIDE_RESPONSE)
    return httpx.Response(404)


def test_hazard_requires_api_key():
    with pytest.raises(ValueError, match="api_key"):
        ReinfolibHazardProvider(api_key=None)


@pytest.mark.asyncio
async def test_hazard_liquefaction_signal():
    transport = httpx.MockTransport(_hazard_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = ReinfolibHazardProvider(client=client, api_key="test-key")
        signals = await provider.fetch(
            lat=35.68, lng=139.75, radius_tiles=0, zoom=14,
        )

    liq = [s for s in signals if s.signal_type == "hazard_liquefaction"]
    assert len(liq) == 1
    assert liq[0].subject_id == "533935"
    assert liq[0].value == 7.0  # level "4" → score 7


@pytest.mark.asyncio
async def test_hazard_flood_signal():
    transport = httpx.MockTransport(_hazard_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = ReinfolibHazardProvider(client=client, api_key="test-key")
        signals = await provider.fetch(
            lat=35.68, lng=139.75, radius_tiles=0, zoom=14,
        )

    flood = [s for s in signals if s.signal_type == "hazard_flood"]
    assert len(flood) == 1
    assert flood[0].value == 6.0  # "3m~5m" → score 6


@pytest.mark.asyncio
async def test_hazard_landslide_signal():
    transport = httpx.MockTransport(_hazard_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = ReinfolibHazardProvider(client=client, api_key="test-key")
        signals = await provider.fetch(
            lat=35.68, lng=139.75, radius_tiles=0, zoom=14,
        )

    slide = [s for s in signals if s.signal_type == "hazard_landslide"]
    assert len(slide) == 1
    assert slide[0].value == 8.0  # features present → score 8
    assert slide[0].payload["zone_classification"] == "警戒区域"


@pytest.mark.asyncio
async def test_hazard_empty_tiles():
    """All endpoints return empty features → landslide gets score 0."""
    transport = httpx.MockTransport(
        lambda _: httpx.Response(200, json=_EMPTY_GEOJSON)
    )
    async with httpx.AsyncClient(transport=transport) as client:
        provider = ReinfolibHazardProvider(client=client, api_key="test-key")
        signals = await provider.fetch(
            lat=35.68, lng=139.75, radius_tiles=0, zoom=14,
        )

    slide = [s for s in signals if s.signal_type == "hazard_landslide"]
    assert len(slide) == 1
    assert slide[0].value == 0.0


@pytest.mark.asyncio
async def test_hazard_404_returns_empty():
    transport = httpx.MockTransport(lambda _: httpx.Response(404))
    async with httpx.AsyncClient(transport=transport) as client:
        provider = ReinfolibHazardProvider(client=client, api_key="test-key")
        signals = await provider.fetch(
            lat=35.68, lng=139.75, radius_tiles=0, zoom=14,
        )
    assert len(signals) == 0
