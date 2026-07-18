"""Name → factory registry for ``MarketSignalProvider`` implementations.

Adding a new provider:

1. Implement the class with ``name: str`` and ``async fetch(...)``.
2. Register a factory in ``_FACTORIES`` keyed by the provider's ``name``.

The CLI (``scripts/fetch_external_signals.py``) calls
:func:`get_provider` to resolve ``--source`` flags.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Final

from config import settings
from services.signal_providers.base import MarketSignalProvider
from services.signal_providers.chicago_crime import ChicagoCrimeProvider
from services.signal_providers.census_acs import CensusAcsProvider
from services.signal_providers.fema_nfhl import FemaNfhlProvider
from services.signal_providers.fred import FredMortgageRateProvider
from services.signal_providers.hud_fmr import HudFmrProvider
from services.signal_providers.mock import MockSignalProvider
from services.signal_providers.reinfolib_appraisal import ReinfolibAppraisalProvider
from services.signal_providers.reinfolib_hazard import ReinfolibHazardProvider
from services.signal_providers.reinfolib_land_price import ReinfolibLandPriceProvider
from services.signal_providers.reinfolib_transaction import ReinfolibTransactionProvider


def _hud_fmr_factory() -> MarketSignalProvider:
    return HudFmrProvider(api_token=os.environ.get("HUD_FMR_API_TOKEN"))


def _fred_factory() -> MarketSignalProvider:
    return FredMortgageRateProvider(api_key=os.environ.get("FRED_API_KEY"))


def _census_acs_factory() -> MarketSignalProvider:
    return CensusAcsProvider(api_key=os.environ.get("CENSUS_API_KEY"))


def _fema_nfhl_factory() -> MarketSignalProvider:
    return FemaNfhlProvider()


def _reinfolib_api_key() -> str | None:
    """Resolve the MLIT key from ``.env`` (via settings), falling back to the
    process environment so ``REINFOLIB_API_KEY=... python ...`` still works.
    """
    return settings.reinfolib_api_key or os.environ.get("REINFOLIB_API_KEY")


def _reinfolib_transaction_factory() -> MarketSignalProvider:
    return ReinfolibTransactionProvider(api_key=_reinfolib_api_key())


def _reinfolib_land_price_factory() -> MarketSignalProvider:
    return ReinfolibLandPriceProvider(api_key=_reinfolib_api_key())


def _reinfolib_appraisal_factory() -> MarketSignalProvider:
    return ReinfolibAppraisalProvider(api_key=_reinfolib_api_key())


def _reinfolib_hazard_factory() -> MarketSignalProvider:
    return ReinfolibHazardProvider(api_key=_reinfolib_api_key())


_FACTORIES: Final[dict[str, Callable[[], MarketSignalProvider]]] = {
    MockSignalProvider.name: MockSignalProvider,
    ChicagoCrimeProvider.name: ChicagoCrimeProvider,
    HudFmrProvider.name: _hud_fmr_factory,
    FredMortgageRateProvider.name: _fred_factory,
    CensusAcsProvider.name: _census_acs_factory,
    FemaNfhlProvider.name: _fema_nfhl_factory,
    ReinfolibTransactionProvider.name: _reinfolib_transaction_factory,
    ReinfolibLandPriceProvider.name: _reinfolib_land_price_factory,
    ReinfolibAppraisalProvider.name: _reinfolib_appraisal_factory,
    ReinfolibHazardProvider.name: _reinfolib_hazard_factory,
}

PROVIDERS: Final[tuple[str, ...]] = tuple(sorted(_FACTORIES))


def get_provider(name: str) -> MarketSignalProvider:
    """Return a fresh provider instance by name. Raises ``KeyError`` if unknown."""
    factory = _FACTORIES.get(name)
    if factory is None:
        raise KeyError(
            f"Unknown signal provider {name!r}. Known: {', '.join(PROVIDERS)}"
        )
    return factory()


__all__ = ["PROVIDERS", "get_provider"]
