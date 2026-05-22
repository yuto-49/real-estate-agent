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
from services.signal_providers.chicago_crime import ChicagoCrimeProvider
from services.signal_providers.fred import FredMortgageRateProvider
from services.signal_providers.hud_fmr import HudFmrProvider
from services.signal_providers.mock import MockSignalProvider
from services.signal_providers.registry import PROVIDERS, get_provider

__all__ = [
    "ChicagoCrimeProvider",
    "ExternalSignal",
    "FredMortgageRateProvider",
    "HudFmrProvider",
    "MarketSignalProvider",
    "MockSignalProvider",
    "PROVIDERS",
    "get_provider",
]
