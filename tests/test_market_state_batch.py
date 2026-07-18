"""Parity + batching tests for the batched market-state builders.

``build_snapshots`` / ``neighborhood_snapshots`` must produce snapshots
*identical* to the per-subject ``build_snapshot`` path, while collapsing the
per-property fan-out into a constant number of queries.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db.models import MarketSignal, Property
from services.market_state import (
    build_snapshot,
    build_snapshots,
    neighborhood_snapshots,
)


def _factory(db_engine):
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


async def _seed_properties(db_engine, n: int) -> list[str]:
    """N properties, each with a property-level + neighborhood-level signal."""
    zips = ("60614", "60601")
    ids: list[str] = []
    async with _factory(db_engine)() as s:
        for i in range(n):
            zip_code = zips[i % len(zips)]
            prop = Property(
                address=f"{i} Parity Ave",
                asking_price=500_000,
                neighborhood_data={"zip_code": zip_code},
                hazard_flags={"flood": False},
                jurisdiction="us",
            )
            s.add(prop)
            await s.flush()
            ids.append(prop.id)
            s.add_all(
                [
                    MarketSignal(
                        signal_type="transit_score",
                        subject_type="property",
                        subject_id=prop.id,
                        value=70.0 + i,
                        observed_at=datetime.utcnow(),
                    ),
                    MarketSignal(
                        signal_type="median_rent",
                        subject_type="neighborhood",
                        subject_id=zip_code,
                        value=2_000.0,
                        observed_at=datetime.utcnow(),
                    ),
                ]
            )
        await s.commit()
    return ids


@pytest.mark.asyncio
async def test_build_snapshots_matches_build_snapshot(db_engine):
    ids = await _seed_properties(db_engine, 3)

    async with _factory(db_engine)() as s:
        props = [
            await s.get(Property, pid) for pid in ids
        ]
        batched = await build_snapshots(s, props)
        singles = {pid: await build_snapshot(s, pid) for pid in ids}

    assert set(batched) == set(singles)
    for pid in ids:
        assert batched[pid] == singles[pid], f"snapshot mismatch for {pid}"
        # spot-check the folded fields actually populated
        assert batched[pid].transit_score is not None
        assert batched[pid].median_rent == 2_000.0


@pytest.mark.asyncio
async def test_build_snapshots_query_count_constant(db_engine):
    """build_snapshots issues the same number of queries for 2 vs 8 properties."""
    few = await _seed_properties(db_engine, 2)
    many = await _seed_properties(db_engine, 8)

    async def _count(ids: list[str]) -> int:
        seen: list[str] = []

        def _on_exec(conn, cursor, statement, params, context, executemany):
            if statement.lstrip()[:6].upper() == "SELECT":
                seen.append(statement)

        event.listen(db_engine.sync_engine, "after_cursor_execute", _on_exec)
        try:
            async with _factory(db_engine)() as s:
                props = [await s.get(Property, pid) for pid in ids]
                # reset: count only the build_snapshots round-trips
                seen.clear()
                await build_snapshots(s, props)
        finally:
            event.remove(db_engine.sync_engine, "after_cursor_execute", _on_exec)
        return len(seen)

    assert await _count(few) == await _count(many)


@pytest.mark.asyncio
async def test_neighborhood_snapshots_returns_entry_per_zip(db_engine):
    await _seed_properties(db_engine, 1)  # seeds zip 60614 with median_rent

    async with _factory(db_engine)() as s:
        snaps = await neighborhood_snapshots(s, ["60614", "99999", "60614"])

    # one entry per distinct requested zip; unknown zip still present (fields None)
    assert set(snaps) == {"60614", "99999"}
    assert snaps["60614"].zip_code == "60614"
    assert snaps["60614"].median_rent == 2_000.0
    assert snaps["99999"].median_rent is None


@pytest.mark.asyncio
async def test_build_snapshots_empty_input(db_engine):
    async with _factory(db_engine)() as s:
        assert await build_snapshots(s, []) == {}
        assert await neighborhood_snapshots(s, []) == {}
