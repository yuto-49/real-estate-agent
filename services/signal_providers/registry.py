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

from services.signal_providers.base import MarketSignalProvider
from services.signal_providers.estat import EStatProvider
from services.signal_providers.reinfolib_appraisal import ReinfolibAppraisalProvider
from services.signal_providers.reinfolib_hazard import ReinfolibHazardProvider
from services.signal_providers.reinfolib_land_price import ReinfolibLandPriceProvider
from services.signal_providers.reinfolib_transaction import ReinfolibTransactionProvider


def _estat_factory() -> MarketSignalProvider:
    return EStatProvider(app_id=os.environ.get("ESTAT_APP_ID"))


def _reinfolib_transaction_factory() -> MarketSignalProvider:
    return ReinfolibTransactionProvider(api_key=os.environ.get("REINFOLIB_API_KEY"))


def _reinfolib_land_price_factory() -> MarketSignalProvider:
    return ReinfolibLandPriceProvider(api_key=os.environ.get("REINFOLIB_API_KEY"))


def _reinfolib_appraisal_factory() -> MarketSignalProvider:
    return ReinfolibAppraisalProvider(api_key=os.environ.get("REINFOLIB_API_KEY"))


def _reinfolib_hazard_factory() -> MarketSignalProvider:
    return ReinfolibHazardProvider(api_key=os.environ.get("REINFOLIB_API_KEY"))


_FACTORIES: Final[dict[str, Callable[[], MarketSignalProvider]]] = {
    EStatProvider.name: _estat_factory,
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
