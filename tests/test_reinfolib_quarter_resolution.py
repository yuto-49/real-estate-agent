"""The transaction provider must default to the latest *published* quarter.

MLIT publishes XIT001 with a multi-quarter lag: in 2026 Q3 the newest available
data is 2025 Q4. Defaulting to the current quarter makes ``fetch()`` return an
empty set and the CLI report success while writing nothing — so the provider
walks back until it finds a quarter with data.
"""

from __future__ import annotations

import httpx
import pytest

from services.signal_providers.reinfolib_transaction import ReinfolibTransactionProvider

_RECORD = {"Type": "中古マンション等", "TradePrice": "48000000", "Area": "40"}


def _transport(published: set[tuple[str, str]]) -> httpx.MockTransport:
    """Serve records only for quarters in *published*; empty otherwise."""

    def handler(request: httpx.Request) -> httpx.Response:
        year = request.url.params.get("year")
        quarter = request.url.params.get("quarter")
        if (year, quarter) in published:
            return httpx.Response(200, json={"status": "OK", "data": [_RECORD] * 3})
        return httpx.Response(200, json={"status": "OK", "data": []})

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_default_walks_back_to_latest_published_quarter():
    """With only 2025 Q4 published, a default fetch must still find data."""
    client = httpx.AsyncClient(transport=_transport({("2025", "4")}))
    provider = ReinfolibTransactionProvider(client=client, api_key="k")

    signals = await provider.fetch(city_codes=["13103"])

    assert signals, "provider defaulted to an unpublished quarter and found nothing"
    assert any(s.signal_type == "median_sale_price" for s in signals)


@pytest.mark.asyncio
async def test_explicit_year_quarter_is_respected_and_not_walked_back():
    """An explicit quarter must be honoured verbatim — no silent fallback."""
    seen: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(
            (request.url.params.get("year"), request.url.params.get("quarter"))
        )
        return httpx.Response(200, json={"status": "OK", "data": []})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ReinfolibTransactionProvider(client=client, api_key="k")

    await provider.fetch(year=2024, quarter=1, city_codes=["13103"])

    assert seen == [("2024", "1")], f"explicit quarter was not honoured: {seen}"


@pytest.mark.asyncio
async def test_gives_up_rather_than_walking_back_forever():
    """When nothing is published, fetch returns empty instead of looping."""
    client = httpx.AsyncClient(transport=_transport(set()))
    provider = ReinfolibTransactionProvider(client=client, api_key="k")

    signals = await provider.fetch(city_codes=["13103"])

    assert signals == [] or list(signals) == []
