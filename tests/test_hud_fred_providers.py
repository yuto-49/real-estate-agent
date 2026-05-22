"""HUD FMR + FRED provider tests — Phase P2.

Uses ``httpx.MockTransport`` so no real network calls happen.
"""

from __future__ import annotations

import json
from datetime import datetime

import httpx
import pytest

from services.signal_providers.fred import FredMortgageRateProvider
from services.signal_providers.hud_fmr import HudFmrProvider


# ── HUD FMR ─────────────────────────────────────────────────────────────


def _hud_handler(request: httpx.Request) -> httpx.Response:
    # HUD User API returns nested JSON with FMR by bedroom count.
    # Match on the metro/zip code in the URL.
    payload = {
        "data": {
            "year": 2026,
            "basicdata": [
                {
                    "zip_code": "60601",
                    "Efficiency": 1200,
                    "One-Bedroom": 1400,
                    "Two-Bedroom": 1700,
                    "Three-Bedroom": 2200,
                    "Four-Bedroom": 2700,
                }
            ],
        }
    }
    return httpx.Response(200, json=payload)


@pytest.mark.asyncio
async def test_hud_fmr_provider_emits_rent_estimate():
    transport = httpx.MockTransport(_hud_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = HudFmrProvider(client=client, api_token="fake-token")
        signals = await provider.fetch(zips=["60601"])

    assert len(signals) >= 1
    by_type = {s.signal_type for s in signals}
    assert "median_rent" in by_type
    rent_signal = next(s for s in signals if s.signal_type == "median_rent")
    assert rent_signal.subject_type == "neighborhood"
    assert rent_signal.subject_id == "60601"
    assert rent_signal.value == pytest.approx(1700)  # 2BR default
    assert "two_bedroom" in rent_signal.payload


@pytest.mark.asyncio
async def test_hud_fmr_provider_requires_token():
    with pytest.raises(ValueError):
        HudFmrProvider(api_token=None)


# ── FRED ────────────────────────────────────────────────────────────────


def _fred_handler(request: httpx.Request) -> httpx.Response:
    payload = {
        "observations": [
            {"date": "2026-05-08", "value": "6.85"},
            {"date": "2026-05-01", "value": "6.79"},
        ]
    }
    return httpx.Response(200, json=payload)


@pytest.mark.asyncio
async def test_fred_provider_emits_mortgage_rate_signal():
    transport = httpx.MockTransport(_fred_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = FredMortgageRateProvider(client=client, api_key="fake-key")
        signals = await provider.fetch()

    assert len(signals) == 1
    sig = signals[0]
    assert sig.signal_type == "mortgage_rate_30yr"
    assert sig.subject_type == "jurisdiction"
    assert sig.subject_id == "US"
    assert sig.value == pytest.approx(6.85)
    assert "series_id" in sig.payload


@pytest.mark.asyncio
async def test_fred_provider_requires_api_key():
    with pytest.raises(ValueError):
        FredMortgageRateProvider(api_key=None)
