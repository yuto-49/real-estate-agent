"""FEMA NFHL + Census ACS provider tests — Phase P3."""

from __future__ import annotations

import httpx
import pytest

from services.signal_providers.census_acs import CensusAcsProvider
from services.signal_providers.fema_nfhl import FemaNfhlProvider


# ── FEMA NFHL ────────────────────────────────────────────────────────────


def _fema_handler(request: httpx.Request) -> httpx.Response:
    payload = {
        "features": [
            {
                "attributes": {
                    "FLD_ZONE": "AE",
                    "ZONE_SUBTY": "FLOODWAY",
                    "SFHA_TF": "T",
                }
            }
        ]
    }
    return httpx.Response(200, json=payload)


@pytest.mark.asyncio
async def test_fema_nfhl_provider_emits_hazard():
    transport = httpx.MockTransport(_fema_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = FemaNfhlProvider(client=client)
        signals = await provider.fetch(
            properties=[
                {"id": "prop-1", "latitude": 41.88, "longitude": -87.63},
            ]
        )

    assert len(signals) == 1
    sig = signals[0]
    assert sig.signal_type == "hazard"
    assert sig.subject_type == "property"
    assert sig.subject_id == "prop-1"
    assert sig.payload["flood_zone"] == "AE"
    assert sig.payload["in_special_flood_hazard_area"] is True


def _fema_no_features_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"features": []})


@pytest.mark.asyncio
async def test_fema_nfhl_returns_zone_x_when_no_features():
    """Outside any mapped flood zone → Zone X (minimal risk)."""
    transport = httpx.MockTransport(_fema_no_features_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = FemaNfhlProvider(client=client)
        signals = await provider.fetch(
            properties=[{"id": "prop-2", "latitude": 41.0, "longitude": -88.0}]
        )

    assert len(signals) == 1
    assert signals[0].payload["flood_zone"] == "X"
    assert signals[0].payload["in_special_flood_hazard_area"] is False


# ── Census ACS ───────────────────────────────────────────────────────────


def _acs_handler(request: httpx.Request) -> httpx.Response:
    # Census API returns CSV-shaped JSON: [headers, ...rows]
    payload = [
        ["NAME", "B25064_001E", "B25077_001E", "zip code tabulation area"],
        ["ZCTA5 60601", "2150", "425000", "60601"],
    ]
    return httpx.Response(200, json=payload)


@pytest.mark.asyncio
async def test_census_acs_provider_emits_rent_and_value():
    transport = httpx.MockTransport(_acs_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = CensusAcsProvider(client=client, api_key="fake-key")
        signals = await provider.fetch(zips=["60601"])

    by_type = {s.signal_type: s for s in signals}
    assert "median_rent" in by_type
    assert "median_home_value" in by_type
    assert by_type["median_rent"].value == pytest.approx(2150)
    assert by_type["median_home_value"].value == pytest.approx(425_000)
    assert by_type["median_rent"].subject_id == "60601"


@pytest.mark.asyncio
async def test_census_acs_requires_api_key():
    with pytest.raises(ValueError):
        CensusAcsProvider(api_key=None)
