"""External market-signal providers.

Each provider implements :class:`MarketSignalProvider` and yields
:class:`ExternalSignal` records that the CLI fetcher upserts via
:func:`services.signal_writer.upsert_signal`.

See ``doc/market-signal-sources.md`` for the source catalog.
"""

from services.signal_providers.base import (
    ExternalSignal,
    MarketSignalProvider,
)
from services.signal_providers.registry import PROVIDERS, get_provider

__all__ = [
    "ExternalSignal",
    "MarketSignalProvider",
    "PROVIDERS",
    "get_provider",
]
