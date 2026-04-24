"""Market-layer event primitives."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Mapping


MARKET_EVENT_NAMESPACE = "market"


def market_event(name: str) -> str:
    """Build a canonical market-layer event name."""
    return f"{MARKET_EVENT_NAMESPACE}.{name}"


@dataclass(frozen=True, slots=True)
class MarketShock:
    """A market event that changes shared spatial or pricing context."""

    event_type: str
    subject_id: str
    narrative: str = ""
    payload: Mapping[str, Any] = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
