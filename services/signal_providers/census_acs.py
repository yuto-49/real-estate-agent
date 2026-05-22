"""Census ACS 5-year → ``median_rent`` and ``median_home_value`` per zip.

Source: U.S. Census Bureau ACS 5-Year Data API. Requires a free API key
(``CENSUS_API_KEY`` env var; obtain at https://api.census.gov/data/key_signup.html).

We emit two signals per zip:
- ``median_rent`` from variable ``B25064_001E`` (median gross rent)
- ``median_home_value`` from variable ``B25077_001E``

ZIP Code Tabulation Areas (ZCTAs) are the geography Census uses, which
approximate USPS zip codes.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, Final

import httpx

from services.signal_providers.base import ExternalSignal


# Default year — ACS releases publish ~18 months after the reference year.
DEFAULT_ACS_YEAR: Final[int] = 2022
ACS_ENDPOINT: Final[str] = "https://api.census.gov/data/{year}/acs/acs5"

# Variables we pull
RENT_VAR: Final[str] = "B25064_001E"
VALUE_VAR: Final[str] = "B25077_001E"


class CensusAcsProvider:
    """Census ACS 5-year provider."""

    name: Final[str] = "census_acs"

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        api_key: str | None = None,
        year: int = DEFAULT_ACS_YEAR,
    ) -> None:
        if not api_key:
            raise ValueError(
                "CensusAcsProvider requires api_key (set CENSUS_API_KEY env)"
            )
        self._client = client
        self._key = api_key
        self._year = year

    async def fetch(
        self,
        *,
        zips: Sequence[str] | None = None,
        observed_at: datetime | None = None,
        **_: Any,
    ) -> Sequence[ExternalSignal]:
        if not zips:
            return ()
        when = observed_at or datetime.utcnow()
        client = self._client or httpx.AsyncClient(timeout=15.0)
        owns = self._client is None

        try:
            params = {
                "get": f"NAME,{RENT_VAR},{VALUE_VAR}",
                "for": f"zip code tabulation area:{','.join(zips)}",
                "key": self._key,
            }
            resp = await client.get(
                ACS_ENDPOINT.format(year=self._year), params=params
            )
            resp.raise_for_status()
            rows = resp.json()
            if not rows or len(rows) < 2:
                return ()
            header, *data = rows
            try:
                rent_idx = header.index(RENT_VAR)
                value_idx = header.index(VALUE_VAR)
                zip_idx = header.index("zip code tabulation area")
            except ValueError:
                return ()

            results: list[ExternalSignal] = []
            for row in data:
                zip_code = row[zip_idx]
                rent_val = _to_float(row[rent_idx])
                value_val = _to_float(row[value_idx])
                if rent_val is not None:
                    results.append(
                        ExternalSignal(
                            signal_type="median_rent",
                            subject_type="neighborhood",
                            subject_id=zip_code,
                            observed_at=when,
                            value=rent_val,
                            payload={
                                "source": "census_acs",
                                "year": self._year,
                                "variable": RENT_VAR,
                            },
                        )
                    )
                if value_val is not None:
                    results.append(
                        ExternalSignal(
                            signal_type="median_home_value",
                            subject_type="neighborhood",
                            subject_id=zip_code,
                            observed_at=when,
                            value=value_val,
                            payload={
                                "source": "census_acs",
                                "year": self._year,
                                "variable": VALUE_VAR,
                            },
                        )
                    )
            return tuple(results)
        finally:
            if owns:
                await client.aclose()


def _to_float(value: Any) -> float | None:
    if value in (None, "", "-", "null"):
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    # Census uses negative codes for missing/suppressed data
    if v < 0:
        return None
    return v


__all__ = ["CensusAcsProvider"]
