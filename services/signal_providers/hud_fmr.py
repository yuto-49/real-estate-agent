"""HUD Fair Market Rent → ``median_rent`` provider.

Source: HUD User API (https://www.huduser.gov/portal/dataset/fmr-api.html).
Requires a free API token (``HUD_FMR_API_TOKEN`` env var).

Emits one signal per zip:
- ``signal_type=median_rent`` with the 2-bedroom FMR as the headline value
- Per-bedroom breakdown stored in ``payload`` (efficiency / 1BR / 2BR / 3BR / 4BR)

The default headline is 2BR FMR because it's the most-used proxy for "median
rent" in single-family / small multi underwriting.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, Final

import httpx

from services.signal_providers.base import ExternalSignal


HUD_FMR_ENDPOINT: Final[str] = (
    "https://www.huduser.gov/hudapi/public/fmr/data/{zip_code}"
)


class HudFmrProvider:
    """Fetches Fair Market Rent per zip from HUD User."""

    name: Final[str] = "hud_fmr"

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        api_token: str | None = None,
        bedroom_headline: str = "Two-Bedroom",
    ) -> None:
        if not api_token:
            raise ValueError(
                "HudFmrProvider requires api_token (set HUD_FMR_API_TOKEN env)"
            )
        self._client = client
        self._token = api_token
        self._headline = bedroom_headline

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
            headers = {"Authorization": f"Bearer {self._token}"}
            results: list[ExternalSignal] = []
            for zip_code in zips:
                url = HUD_FMR_ENDPOINT.format(zip_code=zip_code)
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                rows = (resp.json().get("data", {}) or {}).get("basicdata", [])
                if not rows:
                    continue
                row = rows[0]
                headline_rent = _to_float(row.get(self._headline))
                if headline_rent is None:
                    continue
                results.append(
                    ExternalSignal(
                        signal_type="median_rent",
                        subject_type="neighborhood",
                        subject_id=zip_code,
                        observed_at=when,
                        value=headline_rent,
                        payload={
                            "source": "hud_fmr",
                            "efficiency": _to_float(row.get("Efficiency")),
                            "one_bedroom": _to_float(row.get("One-Bedroom")),
                            "two_bedroom": _to_float(row.get("Two-Bedroom")),
                            "three_bedroom": _to_float(row.get("Three-Bedroom")),
                            "four_bedroom": _to_float(row.get("Four-Bedroom")),
                        },
                    )
                )
            return tuple(results)
        finally:
            if owns:
                await client.aclose()


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = ["HudFmrProvider"]
