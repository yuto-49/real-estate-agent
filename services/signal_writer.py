"""Shared idempotent writer for the ``market_signals`` table.

Both the in-DB backfill (``scripts/backfill_market_signals.py``) and the
external-source fetcher (``scripts/fetch_external_signals.py``) write through
this helper so the same-day upsert semantics stay in one place.

Day-keyed idempotency rule: re-running with the same calendar day for a given
``(signal_type, subject_type, subject_id)`` triple updates the existing row
rather than inserting a duplicate. A different day produces a new row so the
column reads as a time series.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import MarketSignal


async def upsert_signal(
    db: AsyncSession,
    *,
    signal_type: str,
    subject_type: str,
    subject_id: str,
    observed_at: datetime,
    value: float | None = None,
    payload: dict | None = None,
    source: str | None = None,
) -> MarketSignal:
    """Insert or update the signal row for ``(type, subject, day)``.

    Returns the row that was written. Caller is responsible for committing.
    """
    day_start = datetime(observed_at.year, observed_at.month, observed_at.day)
    day_end = datetime(
        observed_at.year, observed_at.month, observed_at.day, 23, 59, 59, 999999
    )

    existing = (
        await db.execute(
            select(MarketSignal).where(
                MarketSignal.signal_type == signal_type,
                MarketSignal.subject_type == subject_type,
                MarketSignal.subject_id == subject_id,
                MarketSignal.observed_at >= day_start,
                MarketSignal.observed_at <= day_end,
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        existing.value = value
        existing.payload = payload or {}
        existing.observed_at = observed_at
        if source is not None:
            existing.source = source
        return existing

    row = MarketSignal(
        signal_type=signal_type,
        subject_type=subject_type,
        subject_id=subject_id,
        value=value,
        payload=payload or {},
        source=source,
        observed_at=observed_at,
    )
    db.add(row)
    return row


__all__ = ["upsert_signal"]
