"""e-Stat signal provider tests — census + rent signals."""

from __future__ import annotations

import httpx
import pytest

from services.signal_providers.estat import (
    CENSUS_TABLE_ID,
    EStatProvider,
    RENT_TABLE_ID,
)


# ── Fixtures ────────────────────────────────────────────────────────────

_CENSUS_RESPONSE = {
    "GET_STATS_DATA": {
        "RESULT": {"STATUS": 0, "ERROR_MSG": "正常に終了しました。"},
        "STATISTICAL_DATA": {
            "RESULT_INF": {"TOTAL_NUMBER": 4},
            "DATA_INF": {
                "VALUE": [
                    # population for Chiyoda-ku
                    {"@tab": "2020_03", "@area": "13101", "@time": "202010", "$": "67803"},
                    # households for Chiyoda-ku
                    {"@tab": "2020_15", "@area": "13101", "@time": "202010", "$": "36750"},
                    # density for Chiyoda-ku
                    {"@tab": "2020_48", "@area": "13101", "@time": "202010", "$": "5820.3"},
                    # national total — should be skipped
                    {"@tab": "2020_03", "@area": "00000", "@time": "202010", "$": "126226568"},
                    # suppressed data — should be skipped
                    {"@tab": "2020_03", "@area": "13102", "@time": "202010", "$": "-"},
                ]
            },
        },
    }
}

_RENT_RESPONSE = {
    "GET_STATS_DATA": {
        "RESULT": {"STATUS": 0, "ERROR_MSG": "正常に終了しました。"},
        "STATISTICAL_DATA": {
            "RESULT_INF": {"TOTAL_NUMBER": 2},
            "DATA_INF": {
                "VALUE": [
                    # rent per tatami for Tokyo
                    {
                        "@tab": "41-2018",
                        "@cat01": "00",
                        "@cat02": "00",
                        "@cat03": "0",
                        "@area": "13000",
                        "@time": "2018000000",
                        "$": "5094",
                    },
                    # national total — skipped
                    {
                        "@tab": "41-2018",
                        "@cat01": "00",
                        "@cat02": "00",
                        "@cat03": "0",
                        "@area": "00000",
                        "@time": "2018000000",
                        "$": "3064",
                    },
                ]
            },
        },
    }
}

_EMPTY_RESPONSE = {
    "GET_STATS_DATA": {
        "RESULT": {"STATUS": 1, "ERROR_MSG": "該当データはありません"},
        "STATISTICAL_DATA": {
            "RESULT_INF": {"TOTAL_NUMBER": 0},
            "DATA_INF": {},
        },
    }
}


def _make_handler(census_resp: dict, rent_resp: dict):
    """Return a mock transport handler that routes by statsDataId."""

    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if CENSUS_TABLE_ID in url_str:
            return httpx.Response(200, json=census_resp)
        if RENT_TABLE_ID in url_str:
            return httpx.Response(200, json=rent_resp)
        return httpx.Response(404, json={"error": "unknown table"})

    return handler


# ── Tests ───────────────────────────────────────────────────────────────


def test_estat_requires_app_id():
    with pytest.raises(ValueError, match="app_id"):
        EStatProvider(app_id=None)


@pytest.mark.asyncio
async def test_estat_census_signals():
    handler = _make_handler(_CENSUS_RESPONSE, _EMPTY_RESPONSE)
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = EStatProvider(client=client, app_id="test-key")
        signals = await provider.fetch(area_codes=["13101"])

    by_type = {s.signal_type: s for s in signals}
    assert "population" in by_type
    assert "household_count" in by_type
    assert "population_density" in by_type

    pop = by_type["population"]
    assert pop.subject_type == "neighborhood"
    assert pop.subject_id == "13101"
    assert pop.value == 67803.0
    assert pop.payload["source"] == "estat"

    hh = by_type["household_count"]
    assert hh.value == 36750.0

    density = by_type["population_density"]
    assert density.value == 5820.3


@pytest.mark.asyncio
async def test_estat_rent_signal():
    handler = _make_handler(_EMPTY_RESPONSE, _RENT_RESPONSE)
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = EStatProvider(client=client, app_id="test-key")
        signals = await provider.fetch()

    rent_signals = [s for s in signals if s.signal_type == "rent_per_tatami"]
    assert len(rent_signals) == 1
    rent = rent_signals[0]
    assert rent.subject_id == "13000"
    assert rent.value == 5094.0
    assert rent.payload["unit"] == "yen"


@pytest.mark.asyncio
async def test_estat_skips_national_total():
    handler = _make_handler(_CENSUS_RESPONSE, _RENT_RESPONSE)
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = EStatProvider(client=client, app_id="test-key")
        signals = await provider.fetch()

    area_ids = {s.subject_id for s in signals}
    assert "00000" not in area_ids


@pytest.mark.asyncio
async def test_estat_skips_suppressed_values():
    handler = _make_handler(_CENSUS_RESPONSE, _EMPTY_RESPONSE)
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = EStatProvider(client=client, app_id="test-key")
        signals = await provider.fetch()

    # "13102" had "-" value and should be excluded
    area_ids = {s.subject_id for s in signals}
    assert "13102" not in area_ids


@pytest.mark.asyncio
async def test_estat_empty_response():
    handler = _make_handler(_EMPTY_RESPONSE, _EMPTY_RESPONSE)
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = EStatProvider(client=client, app_id="test-key")
        signals = await provider.fetch(area_codes=["99999"])

    assert len(signals) == 0


@pytest.mark.asyncio
async def test_estat_combined_census_and_rent():
    handler = _make_handler(_CENSUS_RESPONSE, _RENT_RESPONSE)
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = EStatProvider(client=client, app_id="test-key")
        signals = await provider.fetch()

    types = {s.signal_type for s in signals}
    assert types == {"population", "household_count", "population_density", "rent_per_tatami"}
