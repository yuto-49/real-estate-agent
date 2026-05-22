"""Chicago Crime → ``safety_score`` provider.

Source: Chicago Open Data Portal, dataset ``ijzp-q8t2`` (Crimes 2001 → Present).
No API key is required for low-volume access; an optional ``$$app_token``
raises the per-hour rate limit.

The provider queries one community-area count at a time and maps each result
back to a representative zip. Incidents per 1k residents over the lookback
window normalize into a 0–10 safety score (higher = safer).

Algorithm
---------
1. ``incident_rate = incidents / population * 1000``  (incidents per 1k people)
2. ``stress = min(incident_rate / NORMAL_MAX, 1.0)``  where ``NORMAL_MAX = 25``
3. ``safety_score = round(10 * (1 - stress), 2)``

A zip with **0 incidents** ⇒ 10.0; a zip at the ``NORMAL_MAX`` rate ⇒ 0.0.
The ``NORMAL_MAX`` constant is a tunable; 25 incidents per 1k residents over
~90 days is roughly the upper end for Chicago community areas.

The httpx client is injectable so tests can use ``httpx.MockTransport``
without going over the network.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any, Final

import httpx

from services.signal_providers.base import ExternalSignal


SODA_ENDPOINT: Final[str] = "https://data.cityofchicago.org/resource/ijzp-q8t2.json"
DEFAULT_LOOKBACK_DAYS: Final[int] = 90
NORMAL_MAX_INCIDENTS_PER_1K: Final[float] = 25.0


# (zip, community_area_id, population_estimate). Population is the ACS 2022
# 5-year estimate for the zip, used only to normalize the incident rate.
# Easy to extend — new entries don't need code changes.
ZIP_LOOKUP: Final[dict[str, tuple[str, int]]] = {
    "60601": ("32", 14_000),   # Loop
    "60610": ("8", 33_000),    # Near North Side
    "60614": ("7", 67_000),    # Lincoln Park
    "60622": ("24", 53_000),   # West Town
    "60640": ("3", 65_000),    # Uptown
    "60647": ("22", 45_000),   # Logan Square
}


class ChicagoCrimeProvider:
    """Pulls Chicago crime counts → safety_score per zip."""

    name: Final[str] = "chicago_crime"

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        app_token: str | None = None,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    ) -> None:
        self._client = client
        self._app_token = app_token
        self._lookback_days = lookback_days

    async def fetch(
        self,
        *,
        observed_at: datetime | None = None,
        zips: Sequence[str] | None = None,
        **_: Any,
    ) -> Sequence[ExternalSignal]:
        when = observed_at or datetime.utcnow()
        cutoff = (when - timedelta(days=self._lookback_days)).strftime("%Y-%m-%dT00:00:00")
        targets = tuple(zips) if zips is not None else tuple(ZIP_LOOKUP)

        client = self._client or httpx.AsyncClient(timeout=15.0)
        owns_client = self._client is None

        try:
            results: list[ExternalSignal] = []
            for zip_code in targets:
                lookup = ZIP_LOOKUP.get(zip_code)
                if lookup is None:
                    continue
                community_area, population = lookup

                count = await self._fetch_count(client, community_area, cutoff)
                score = _safety_score(count, population)

                results.append(
                    ExternalSignal(
                        signal_type="safety_score",
                        subject_type="neighborhood",
                        subject_id=zip_code,
                        observed_at=when,
                        value=score,
                        payload={
                            "community_area": community_area,
                            "incidents": count,
                            "lookback_days": self._lookback_days,
                            "population_estimate": population,
                        },
                    )
                )
            return tuple(results)
        finally:
            if owns_client:
                await client.aclose()

    async def _fetch_count(
        self,
        client: httpx.AsyncClient,
        community_area: str,
        cutoff: str,
    ) -> int:
        params = {
            "$select": "count(*) AS incidents",
            "$where": f"date > '{cutoff}' AND community_area = '{community_area}'",
        }
        headers = {"X-App-Token": self._app_token} if self._app_token else None

        response = await client.get(SODA_ENDPOINT, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()

        if not data:
            return 0
        try:
            return int(data[0].get("incidents", 0))
        except (TypeError, ValueError):
            return 0


def _safety_score(incidents: int, population: int) -> float:
    if population <= 0:
        return 0.0
    rate_per_1k = (incidents / population) * 1000.0
    stress = min(rate_per_1k / NORMAL_MAX_INCIDENTS_PER_1K, 1.0)
    return round(10.0 * (1.0 - stress), 2)


__all__ = ["ChicagoCrimeProvider", "ZIP_LOOKUP", "NORMAL_MAX_INCIDENTS_PER_1K"]
