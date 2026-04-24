"""Compatibility wrapper for the negotiation domain state machine.

The source of truth now lives in ``domain.decisions.negotiation``. This module
exists to preserve current imports while the repo migrates gradually.
"""

from domain.decisions.negotiation import (
    NEGOTIATION_TIMEOUT_HOURS as TIMEOUT_HOURS,
    NegotiationAction,
    NegotiationState,
    NegotiationTimer,
    transition,
)

__all__ = [
    "NegotiationAction",
    "NegotiationState",
    "NegotiationTimer",
    "TIMEOUT_HOURS",
    "transition",
]
