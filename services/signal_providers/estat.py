"""e-Stat (Japan) → population, households, density, rent signals per municipality.

Source: Japan's e-Stat API v3.0 (https://api.e-stat.go.jp/).
Requires a free application ID (``ESTAT_APP_ID`` env var; register at
https://www.e-stat.go.jp/en/mypage/login).

Statistical tables used:

- **0003445099** — 令和2年国勢調査 (2020 Census): population, household count,
  population density, area by municipality.
- **0003356438** — 平成30年住宅・土地統計調査 (2018 Housing & Land Survey): average
  rent per tatami-mat (畳) by area.

Signals emitted (``subject_type="neighborhood"``, ``subject_id=<area_code>``):

- ``population`` — total population
- ``household_count`` — total households
- ``population_density`` — persons per km²
- ``rent_per_tatami`` — monthly rent per tatami mat (¥)

Area codes are 5-digit Japanese municipality codes (全国地方公共団体コード),
e.g. ``"13101"`` = 千代田区. The provider stores them as ``subject_id`` so
downstream consumers can match by municipality code.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Final

import httpx

from services.signal_providers.base import ExternalSignal

ESTAT_ENDPOINT: Final[str] = (
    "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData"
)

# --- Census 2020 table ---
CENSUS_TABLE_ID: Final[str] = "0003445099"
# Tab codes within this table
TAB_POPULATION: Final[str] = "2020_03"
TAB_HOUSEHOLDS: Final[str] = "2020_15"
TAB_DENSITY: Final[str] = "2020_48"

# --- Housing & Land Survey 2018 table ---
RENT_TABLE_ID: Final[str] = "0003356438"
# We want the "total" row: all move-in periods, all construction periods,
# all housing types (cat01=00, cat02=00, cat03=0).
RENT_TAB: Final[str] = "41-2018"

# Signal-type mapping for census tab codes
_CENSUS_SIGNAL_MAP: Final[dict[str, str]] = {
    TAB_POPULATION: "population",
    TAB_HOUSEHOLDS: "household_count",
    TAB_DENSITY: "population_density",
}

# Maximum rows per API call (e-Stat cap is 100_000)
_API_LIMIT: Final[int] = 100_000


class EStatProvider:
    """Fetches Japanese government statistics from e-Stat API v3."""

    name: Final[str] = "estat"

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        app_id: str | None = None,
    ) -> None:
        if not app_id:
            raise ValueError(
                "EStatProvider requires app_id (set ESTAT_APP_ID env)"
            )
        self._client = client
        self._app_id = app_id

    async def fetch(
        self,
        *,
        area_codes: Sequence[str] | None = None,
        observed_at: datetime | None = None,
        **_: Any,
    ) -> Sequence[ExternalSignal]:
        """Fetch census + rent signals for the given municipality codes.

        Parameters
        ----------
        area_codes:
            5-digit municipality codes (e.g. ``["13101", "13102"]``).
            If *None*, fetches all municipalities (can be large).
        observed_at:
            Timestamp to stamp on the signals. Defaults to now.
        """
        when = observed_at or datetime.now(UTC)
        client = self._client or httpx.AsyncClient(timeout=30.0)
        owns = self._client is None

        try:
            results: list[ExternalSignal] = []
            results.extend(
                await self._fetch_census(client, area_codes, when)
            )
            results.extend(
                await self._fetch_rent(client, area_codes, when)
            )
            return tuple(results)
        finally:
            if owns:
                await client.aclose()

    # ------------------------------------------------------------------
    # Census 2020: population, households, density
    # ------------------------------------------------------------------

    async def _fetch_census(
        self,
        client: httpx.AsyncClient,
        area_codes: Sequence[str] | None,
        when: datetime,
    ) -> list[ExternalSignal]:
        params: dict[str, str] = {
            "appId": self._app_id,
            "statsDataId": CENSUS_TABLE_ID,
            "lang": "J",
            "limit": str(_API_LIMIT),
            "metaGetFlg": "N",
        }
        if area_codes:
            params["cdArea"] = ",".join(area_codes)

        resp = await client.get(ESTAT_ENDPOINT, params=params)
        resp.raise_for_status()
        body = resp.json()

        values = _extract_values(body)
        signals: list[ExternalSignal] = []

        for entry in values:
            tab = entry.get("@tab", "")
            signal_type = _CENSUS_SIGNAL_MAP.get(tab)
            if signal_type is None:
                continue
            area = entry.get("@area", "")
            if not area or area == "00000":
                continue  # skip national total
            raw = entry.get("$")
            num = _to_float(raw)
            if num is None:
                continue
            signals.append(
                ExternalSignal(
                    signal_type=signal_type,
                    subject_type="neighborhood",
                    subject_id=area,
                    observed_at=when,
                    value=num,
                    payload={"source": "estat", "table": CENSUS_TABLE_ID},
                )
            )
        return signals

    # ------------------------------------------------------------------
    # Housing & Land Survey 2018: rent per tatami
    # ------------------------------------------------------------------

    async def _fetch_rent(
        self,
        client: httpx.AsyncClient,
        area_codes: Sequence[str] | None,
        when: datetime,
    ) -> list[ExternalSignal]:
        params: dict[str, str] = {
            "appId": self._app_id,
            "statsDataId": RENT_TABLE_ID,
            "lang": "J",
            "limit": str(_API_LIMIT),
            "metaGetFlg": "N",
            # Filter to "total" aggregates only
            "cdCat01": "00",  # all move-in periods
            "cdCat02": "00",  # all construction periods
            "cdCat03": "0",   # all housing types
        }
        if area_codes:
            params["cdArea"] = ",".join(area_codes)

        resp = await client.get(ESTAT_ENDPOINT, params=params)
        resp.raise_for_status()
        body = resp.json()

        values = _extract_values(body)
        signals: list[ExternalSignal] = []

        for entry in values:
            area = entry.get("@area", "")
            if not area or area == "00000":
                continue
            raw = entry.get("$")
            num = _to_float(raw)
            if num is None:
                continue
            signals.append(
                ExternalSignal(
                    signal_type="rent_per_tatami",
                    subject_type="neighborhood",
                    subject_id=area,
                    observed_at=when,
                    value=num,
                    payload={
                        "source": "estat",
                        "table": RENT_TABLE_ID,
                        "unit": "yen",
                    },
                )
            )
        return signals


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _extract_values(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Navigate e-Stat JSON envelope to the VALUE list."""
    try:
        data_inf = (
            body["GET_STATS_DATA"]["STATISTICAL_DATA"]["DATA_INF"]
        )
    except (KeyError, TypeError):
        return []
    value = data_inf.get("VALUE")
    if value is None:
        return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return value
    return []


def _to_float(raw: Any) -> float | None:
    if raw in (None, "", "-", "***", "\u2026", "x", "X"):
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    return v


__all__ = ["EStatProvider"]
