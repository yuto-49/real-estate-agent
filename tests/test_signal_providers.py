"""Tests for external market-signal providers + the fetch CLI integration.

Covers:
- MockSignalProvider: deterministic fixture data, observed_at threading
- ChicagoCrimeProvider: SODA query shape + safety_score formula via httpx.MockTransport
- registry: name-keyed lookup
- fetch_and_persist: idempotent same-day upsert through the shared writer
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import httpx
import pytest
from sqlalchemy import select

from db.models import MarketSignal
from scripts.fetch_external_signals import fetch_and_persist
from services.signal_providers import PROVIDERS, get_provider
from services.signal_providers.base import ExternalSignal, MarketSignalProvider
from services.signal_providers.chicago_crime import (
    ChicagoCrimeProvider,
    NORMAL_MAX_INCIDENTS_PER_1K,
    SODA_ENDPOINT,
    ZIP_LOOKUP,
)
from services.signal_providers.mock import MockSignalProvider


# ── MockSignalProvider ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mock_provider_yields_one_signal_per_zip_per_type():
    provider = MockSignalProvider(zips=["60601", "60614"])
    signals = await provider.fetch()

    by_zip = {(s.subject_id, s.signal_type): s for s in signals}
    assert ("60601", "transit_score") in by_zip
    assert ("60601", "school_score") in by_zip
    assert ("60601", "safety_score") in by_zip
    assert ("60601", "median_rent") in by_zip
    assert ("60614", "transit_score") in by_zip
    assert all(s.subject_type == "neighborhood" for s in signals)
    assert all(isinstance(s.value, float) for s in signals)


@pytest.mark.asyncio
async def test_mock_provider_threads_observed_at():
    when = datetime(2026, 5, 1, 9, 30)
    provider = MockSignalProvider(zips=["60601"])
    signals = await provider.fetch(observed_at=when)
    assert all(s.observed_at == when for s in signals)


@pytest.mark.asyncio
async def test_mock_provider_skips_unknown_zips():
    provider = MockSignalProvider(zips=["99999"])
    signals = await provider.fetch()
    assert signals == ()


# ── ChicagoCrimeProvider ───────────────────────────────────────────────────


def _soda_handler(incidents_by_community_area: dict[str, int]) -> httpx.MockTransport:
    """Mock the SODA ``count(*)`` endpoint deterministically."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/resource/ijzp-q8t2.json"
        where = request.url.params.get("$where", "")
        # Pull the community_area out of the SQL-ish $where clause.
        community_area = where.rsplit("'", 2)[-2] if "'" in where else ""
        count = incidents_by_community_area.get(community_area, 0)
        return httpx.Response(200, json=[{"incidents": str(count)}])

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_chicago_crime_provider_computes_safety_score():
    # 60601 (community_area=32, pop≈14k) with 0 incidents → score 10.0
    # 60614 (community_area=7, pop≈67k) with high incidents → low score
    transport = _soda_handler({"32": 0, "7": 1675})  # 1675/67k*1000 ≈ 25 → score ≈ 0
    async with httpx.AsyncClient(transport=transport) as client:
        provider = ChicagoCrimeProvider(client=client)
        signals = await provider.fetch(zips=["60601", "60614"])

    by_zip = {s.subject_id: s for s in signals}
    assert by_zip["60601"].value == pytest.approx(10.0)
    assert by_zip["60614"].value == pytest.approx(0.0, abs=0.05)
    # Payload threads incident metadata through for replay/audit.
    assert by_zip["60601"].payload["incidents"] == 0
    assert by_zip["60614"].payload["community_area"] == "7"
    assert by_zip["60614"].payload["lookback_days"] == 90
    # All rows are neighborhood-keyed safety_score signals.
    assert all(s.signal_type == "safety_score" for s in signals)
    assert all(s.subject_type == "neighborhood" for s in signals)


@pytest.mark.asyncio
async def test_chicago_crime_provider_clamps_to_zero_above_normal_max():
    # 5000 incidents / 14000 pop * 1000 ≈ 357 per 1k → far above NORMAL_MAX
    transport = _soda_handler({"32": 5000})
    async with httpx.AsyncClient(transport=transport) as client:
        provider = ChicagoCrimeProvider(client=client)
        signals = await provider.fetch(zips=["60601"])

    assert signals[0].value == 0.0


@pytest.mark.asyncio
async def test_chicago_crime_provider_skips_unknown_zip():
    transport = _soda_handler({})
    async with httpx.AsyncClient(transport=transport) as client:
        provider = ChicagoCrimeProvider(client=client)
        signals = await provider.fetch(zips=["99999"])
    assert signals == ()


@pytest.mark.asyncio
async def test_chicago_crime_provider_passes_app_token_when_set():
    seen_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update({k: v for k, v in request.headers.items()})
        return httpx.Response(200, json=[{"incidents": "0"}])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = ChicagoCrimeProvider(client=client, app_token="test-token")
        await provider.fetch(zips=["60601"])

    assert seen_headers.get("x-app-token") == "test-token"


# ── Registry ───────────────────────────────────────────────────────────────


def test_registry_lists_known_providers():
    assert "mock" in PROVIDERS
    assert "chicago_crime" in PROVIDERS


def test_registry_returns_provider_instance():
    provider = get_provider("mock")
    assert isinstance(provider, MarketSignalProvider)
    assert provider.name == "mock"


def test_registry_raises_on_unknown_provider():
    with pytest.raises(KeyError):
        get_provider("does-not-exist")


# ── fetch_and_persist (CLI integration) ────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_and_persist_writes_rows(db):
    provider = MockSignalProvider(zips=["60601"])
    counts = await fetch_and_persist(db, provider)

    rows = (await db.execute(select(MarketSignal))).scalars().all()
    assert {r.signal_type for r in rows} == {"transit_score", "school_score", "safety_score", "median_rent"}
    assert all(r.source == "mock" for r in rows)
    assert counts["transit_score"] == 1


@pytest.mark.asyncio
async def test_fetch_and_persist_is_idempotent_same_day(db):
    when = datetime(2026, 5, 9, 12, 0, 0)
    provider = MockSignalProvider(zips=["60601"])

    # Two runs same calendar day → row count stays put, values get updated.
    await fetch_and_persist(db, _PinnedTimeProvider(provider, when))
    await fetch_and_persist(db, _PinnedTimeProvider(provider, when))

    rows = (await db.execute(select(MarketSignal))).scalars().all()
    # 4 signal types × 1 zip = 4 rows.
    assert len(rows) == 4


class _PinnedTimeProvider:
    """Wrap a provider so its emitted signals carry a fixed observed_at."""

    name = "mock"

    def __init__(self, inner: MarketSignalProvider, when: datetime) -> None:
        self._inner = inner
        self._when = when

    async def fetch(self, **kwargs):
        signals = await self._inner.fetch(observed_at=self._when, **kwargs)
        return tuple(
            ExternalSignal(
                signal_type=s.signal_type,
                subject_type=s.subject_type,
                subject_id=s.subject_id,
                observed_at=self._when,
                value=s.value,
                payload=s.payload,
            )
            for s in signals
        )
