"""Deterministic mock signal provider — no network, useful for dev + tests.

Mirrors the shape of a real provider so wiring code can be tested without
touching the network. Numbers are hand-picked plausible values for Chicago
zips already present in the seed data.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, Final

from services.signal_providers.base import ExternalSignal


_FIXTURE: Final[dict[str, dict[str, float]]] = {
    "60601": {"transit_score": 88.0, "school_score": 7.5, "safety_score": 6.2, "median_rent": 2250.0},
    "60610": {"transit_score": 82.0, "school_score": 7.0, "safety_score": 6.5, "median_rent": 2400.0},
    "60614": {"transit_score": 79.0, "school_score": 8.5, "safety_score": 7.4, "median_rent": 2700.0},
    "60622": {"transit_score": 76.0, "school_score": 7.2, "safety_score": 6.9, "median_rent": 2350.0},
    "60640": {"transit_score": 74.0, "school_score": 6.4, "safety_score": 5.8, "median_rent": 1850.0},
    "60647": {"transit_score": 78.0, "school_score": 7.0, "safety_score": 6.6, "median_rent": 2300.0},
}


class MockSignalProvider:
    """Returns deterministic fixture signals for a fixed set of zips."""

    name: Final[str] = "mock"

    def __init__(self, zips: Sequence[str] | None = None) -> None:
        self._zips = tuple(zips) if zips is not None else tuple(_FIXTURE)

    async def fetch(
        self,
        *,
        observed_at: datetime | None = None,
        **_: Any,
    ) -> Sequence[ExternalSignal]:
        when = observed_at or datetime.utcnow()
        out: list[ExternalSignal] = []
        for zip_code in self._zips:
            scalars = _FIXTURE.get(zip_code)
            if scalars is None:
                continue
            for signal_type, value in scalars.items():
                out.append(
                    ExternalSignal(
                        signal_type=signal_type,
                        subject_type="neighborhood",
                        subject_id=zip_code,
                        observed_at=when,
                        value=float(value),
                    )
                )
        return tuple(out)


__all__ = ["MockSignalProvider"]
