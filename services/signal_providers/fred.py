"""FRED → ``mortgage_rate_30yr`` provider.

Source: Federal Reserve Economic Data, series ``MORTGAGE30US`` (30-year
fixed mortgage average, weekly). Requires a free API key
(``FRED_API_KEY`` env var).

Emits a single jurisdiction-scoped signal:
- ``signal_type=mortgage_rate_30yr``
- ``subject_type=jurisdiction``, ``subject_id="US"``
- ``value`` = latest observation in percent (e.g. 6.85)
- ``payload`` includes ``series_id`` and the observation date

Used by the investor underwriting page to default the loan rate.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, Final

import httpx

from services.signal_providers.base import ExternalSignal


FRED_ENDPOINT: Final[str] = "https://api.stlouisfed.org/fred/series/observations"
DEFAULT_SERIES: Final[str] = "MORTGAGE30US"


class FredMortgageRateProvider:
    """Latest 30y fixed mortgage rate observation from FRED."""

    name: Final[str] = "fred_mortgage_rate"

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        api_key: str | None = None,
        series_id: str = DEFAULT_SERIES,
    ) -> None:
        if not api_key:
            raise ValueError(
                "FredMortgageRateProvider requires api_key (set FRED_API_KEY env)"
            )
        self._client = client
        self._key = api_key
        self._series = series_id

    async def fetch(
        self,
        *,
        observed_at: datetime | None = None,
        **_: Any,
    ) -> Sequence[ExternalSignal]:
        client = self._client or httpx.AsyncClient(timeout=15.0)
        owns = self._client is None
        try:
            params = {
                "series_id": self._series,
                "api_key": self._key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": "1",
            }
            resp = await client.get(FRED_ENDPOINT, params=params)
            resp.raise_for_status()
            payload = resp.json()
            observations = payload.get("observations") or []
            if not observations:
                return ()
            latest = observations[0]
            try:
                value = float(latest["value"])
            except (KeyError, TypeError, ValueError):
                return ()
            when = observed_at or datetime.utcnow()
            return (
                ExternalSignal(
                    signal_type="mortgage_rate_30yr",
                    subject_type="jurisdiction",
                    subject_id="US",
                    observed_at=when,
                    value=value,
                    payload={
                        "series_id": self._series,
                        "observation_date": latest.get("date"),
                        "source": "fred",
                    },
                ),
            )
        finally:
            if owns:
                await client.aclose()


__all__ = ["FredMortgageRateProvider"]
