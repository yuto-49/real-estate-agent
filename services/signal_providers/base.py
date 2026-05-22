"""Provider Protocol + DTO for external market-signal sources.

Providers are async-only, immutable, and side-effect free outside the HTTP
boundary they wrap. They yield :class:`ExternalSignal` records — write-ready
rows that the fetch CLI persists via :func:`services.signal_writer.upsert_signal`.

The DTO mirrors the columns of ``MarketSignal`` so the fetcher can pass it
through unchanged.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class ExternalSignal:
    """Write-ready market signal record from an external provider."""

    signal_type: str
    subject_type: str  # "property" | "neighborhood" | "jurisdiction"
    subject_id: str
    observed_at: datetime
    value: float | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class MarketSignalProvider(Protocol):
    """Async provider that fetches a batch of external market signals."""

    name: str

    async def fetch(self, **kwargs: Any) -> Sequence[ExternalSignal]:
        """Return a batch of write-ready signals.

        Implementations should accept (and ignore) unknown kwargs so the CLI
        can pass a uniform parameter set across providers.
        """
        ...


__all__ = ["ExternalSignal", "MarketSignalProvider"]
