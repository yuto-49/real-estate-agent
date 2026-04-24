"""Core business-domain packages for the layered market knowledge system.

The domain layer holds business concepts and state transitions independent of
FastAPI transport, orchestration adapters, or external integrations.
"""

__all__ = [
    "actors",
    "decisions",
    "market",
    "outcomes",
    "reactions",
]
