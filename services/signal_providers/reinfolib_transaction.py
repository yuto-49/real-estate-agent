"""MLIT REINFOLIB XIT001 → median transaction prices per municipality.

Source: Real Estate Transaction Price Information API (不動産取引価格情報)
https://www.reinfolib.mlit.go.jp/help/apiManual/

Endpoint **XIT001** returns individual real estate transactions for a given
municipality, year, and quarter.  This provider aggregates them into two
signals per city code:

- ``median_sale_price`` — median of ``TradePrice`` across all transactions
- ``median_unit_price`` — median of ``UnitPrice`` (price per m²)

Signals are emitted with ``subject_type="neighborhood"`` and
``subject_id=<5-digit municipality code>``.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Final

import httpx

from services.signal_providers.base import ExternalSignal
from services.signal_providers.reinfolib_base import (
    TOKYO_23_CITY_CODES,
    reinfolib_get,
)

_ENDPOINT: Final[str] = "XIT001"
_PRICE_CLASSIFICATION: Final[str] = "01"  # transactions only


def _current_quarter(now: datetime) -> tuple[int, int]:
    """Return ``(year, quarter)`` for *now*."""
    return now.year, (now.month - 1) // 3 + 1


def _previous_quarter(year: int, quarter: int) -> tuple[int, int]:
    """Return the quarter immediately before ``(year, quarter)``."""
    return (year - 1, 4) if quarter == 1 else (year, quarter - 1)


# MLIT publishes XIT001 with a lag of several quarters, so the current quarter
# is always empty. Walk back this many quarters looking for published data
# before giving up (2 years — comfortably beyond the observed lag).
_MAX_QUARTER_LOOKBACK: Final[int] = 8


def _extract_numeric(records: Sequence[dict[str, Any]], key: str) -> list[float]:
    """Pull numeric values for *key* from transaction records, skipping blanks."""
    values: list[float] = []
    for rec in records:
        raw = rec.get(key)
        if raw is None or raw == "":
            continue
        try:
            values.append(float(raw))
        except (TypeError, ValueError):
            continue
    return values


class ReinfolibTransactionProvider:
    """Fetches real estate transaction prices from REINFOLIB XIT001."""

    name: Final[str] = "reinfolib_transaction"

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        api_key: str | None = None,
    ) -> None:
        if not api_key:
            raise ValueError(
                "ReinfolibTransactionProvider requires api_key "
                "(set REINFOLIB_API_KEY env)"
            )
        self._client = client
        self._api_key = api_key

    async def fetch(
        self,
        *,
        year: int | None = None,
        quarter: int | None = None,
        city_codes: Sequence[str] | None = None,
        observed_at: datetime | None = None,
        **_: Any,
    ) -> Sequence[ExternalSignal]:
        """Fetch median transaction prices for the given municipalities.

        Parameters
        ----------
        year:
            Calendar year (YYYY).  Defaults to the current year.
        quarter:
            Quarter (1-4).  Defaults to the current quarter.
        city_codes:
            5-digit municipality codes.  Defaults to the Tokyo 23 wards.
        observed_at:
            Timestamp to stamp on signals.  Defaults to now (UTC).
        """
        when = observed_at or datetime.now(UTC)
        codes = city_codes or TOKYO_23_CITY_CODES

        client = self._client or httpx.AsyncClient(timeout=30.0)
        owns = self._client is None

        try:
            explicit = year is not None and quarter is not None
            if not explicit:
                resolved = await self._resolve_published_quarter(client, codes[0], when)
                if resolved is None:
                    return ()
                year, quarter = resolved

            results: list[ExternalSignal] = []
            for code in codes:
                signals = await self._fetch_city(client, code, year, quarter, when)
                results.extend(signals)
            return tuple(results)
        finally:
            if owns:
                await client.aclose()

    async def _resolve_published_quarter(
        self,
        client: httpx.AsyncClient,
        probe_city: str,
        when: datetime,
    ) -> tuple[int, int] | None:
        """Find the newest quarter MLIT has actually published.

        Probes a single municipality walking backwards from the current quarter,
        so the cost is paid once and the resolved quarter is reused for the rest
        of the batch. Returns ``None`` when nothing is published in range.
        """
        year, quarter = _current_quarter(when)
        for _ in range(_MAX_QUARTER_LOOKBACK):
            body = await reinfolib_get(
                client,
                _ENDPOINT,
                self._api_key,
                {
                    "year": str(year),
                    "quarter": str(quarter),
                    "city": probe_city,
                    "priceClassification": _PRICE_CLASSIFICATION,
                },
            )
            if body and body.get("data"):
                return year, quarter
            year, quarter = _previous_quarter(year, quarter)
        return None

    async def _fetch_city(
        self,
        client: httpx.AsyncClient,
        city_code: str,
        year: int,
        quarter: int,
        when: datetime,
    ) -> list[ExternalSignal]:
        """Fetch and aggregate transactions for a single municipality."""
        params: dict[str, str] = {
            "year": str(year),
            "quarter": str(quarter),
            "city": city_code,
            "priceClassification": _PRICE_CLASSIFICATION,
        }

        body = await reinfolib_get(client, _ENDPOINT, self._api_key, params)
        if body is None:
            return []  # 404 — no data for this city/period

        records: list[dict[str, Any]] = body.get("data", [])
        if not records:
            return []

        payload_base: dict[str, Any] = {
            "source": "reinfolib",
            "endpoint": _ENDPOINT,
            "year": year,
            "quarter": quarter,
            "sample_size": len(records),
        }

        signals: list[ExternalSignal] = []

        trade_prices = _extract_numeric(records, "TradePrice")
        if trade_prices:
            signals.append(
                ExternalSignal(
                    signal_type="median_sale_price",
                    subject_type="neighborhood",
                    subject_id=city_code,
                    observed_at=when,
                    value=statistics.median(trade_prices),
                    payload=payload_base,
                )
            )

        unit_prices = _extract_numeric(records, "UnitPrice")
        if unit_prices:
            signals.append(
                ExternalSignal(
                    signal_type="median_unit_price",
                    subject_type="neighborhood",
                    subject_id=city_code,
                    observed_at=when,
                    value=statistics.median(unit_prices),
                    payload=payload_base,
                )
            )

        return signals

    async def fetch_individual_transactions(
        self,
        *,
        city_code: str,
        year: int | None = None,
        quarter: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return individual transaction records (not aggregated) for satei comp grid.

        Each dict has keys from the REINFOLIB XIT001 response:
        TradePrice, UnitPrice, Area, BuildingYear, Structure,
        TimeToNearestStation, FloorPlan, CityCode, etc.
        """
        when = datetime.now(UTC)
        if year is None or quarter is None:
            default_year, default_quarter = _current_quarter(when)
            year = year or default_year
            quarter = quarter or default_quarter

        client = self._client or httpx.AsyncClient(timeout=30.0)
        owns = self._client is None
        try:
            params: dict[str, str] = {
                "year": str(year),
                "quarter": str(quarter),
                "city": city_code,
                "priceClassification": _PRICE_CLASSIFICATION,
            }
            body = await reinfolib_get(client, _ENDPOINT, self._api_key, params)
            if body is None:
                return []
            return body.get("data", [])
        finally:
            if owns:
                await client.aclose()


__all__ = ["ReinfolibTransactionProvider"]
