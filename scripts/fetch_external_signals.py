"""Fetch market signals from external providers and upsert into ``market_signals``.

Picks one provider by ``--source`` (``mock``, ``chicago_crime``, ...), runs its
async ``fetch()``, and writes results through
:func:`services.signal_writer.upsert_signal` — same idempotent-per-day
semantics as the in-DB backfill.

Usage::

    python scripts/fetch_external_signals.py --source mock
    python scripts/fetch_external_signals.py --source chicago_crime
    python scripts/fetch_external_signals.py --source chicago_crime --dry-run
    python scripts/fetch_external_signals.py --list

See ``doc/market-signal-sources.md`` for the source catalog.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy.ext.asyncio import AsyncSession

from db.database import async_session
from services.signal_providers import PROVIDERS, get_provider
from services.signal_providers.base import MarketSignalProvider
from services.signal_writer import upsert_signal


async def fetch_and_persist(
    db: AsyncSession,
    provider: MarketSignalProvider,
    **fetch_kwargs: object,
) -> dict[str, int]:
    """Run a provider and upsert each signal it emits.

    ``fetch_kwargs`` are forwarded to the provider; the Protocol requires
    implementations to ignore ones they don't understand.

    Returns a counter ``{signal_type: rows_written}``.
    """
    signals = await provider.fetch(**fetch_kwargs)
    counts: Counter[str] = Counter()

    for signal in signals:
        await upsert_signal(
            db,
            signal_type=signal.signal_type,
            subject_type=signal.subject_type,
            subject_id=signal.subject_id,
            value=signal.value,
            payload=dict(signal.payload),
            observed_at=signal.observed_at,
            source=provider.name,
        )
        counts[signal.signal_type] += 1

    await db.commit()
    return dict(counts)


async def _main(source: str, dry_run: bool, **fetch_kwargs: object) -> None:
    provider = get_provider(source)
    async with async_session() as db:
        if dry_run:
            counts = await fetch_and_persist(db, provider, **fetch_kwargs)
            await db.rollback()
            print(f"[dry-run] {source}: would write {counts}")
            return
        counts = await fetch_and_persist(db, provider, **fetch_kwargs)
        if not counts:
            print(f"{source}: wrote nothing — no data published for that period")
            return
        print(f"{source}: wrote {counts}")


def _cli() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        help=f"Provider name. One of: {', '.join(PROVIDERS)}",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List registered providers and exit.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Roll back the transaction; report what would be written.",
    )
    parser.add_argument(
        "--year",
        type=int,
        help=(
            "Calendar year (JP providers). Omit to auto-resolve the newest "
            "quarter MLIT has published — the current quarter is always empty."
        ),
    )
    parser.add_argument(
        "--quarter",
        type=int,
        choices=(1, 2, 3, 4),
        help="Quarter 1-4 (JP providers). Omit to auto-resolve.",
    )
    args = parser.parse_args()

    if args.list:
        for name in PROVIDERS:
            print(name)
        return

    if not args.source:
        parser.error("--source is required (or pass --list)")

    fetch_kwargs: dict[str, object] = {}
    if args.year is not None:
        fetch_kwargs["year"] = args.year
    if args.quarter is not None:
        fetch_kwargs["quarter"] = args.quarter

    asyncio.run(_main(args.source, args.dry_run, **fetch_kwargs))


if __name__ == "__main__":
    _cli()
