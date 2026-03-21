"""Event store tests."""

import pytest

from services.event_store import EventStore


@pytest.mark.asyncio
async def test_append_event(db):
    store = EventStore(db)
    event = await store.append(
        event_type="offer.created",
        aggregate_type="negotiation",
        aggregate_id="neg-123",
        payload={"offer_price": 300000},
        actor_type="agent",
        actor_id="buyer-agent-1",
        correlation_id="corr-abc",
    )
    assert event.id is not None
    assert event.sequence == 1
    assert event.event_type == "offer.created"
    await db.commit()


@pytest.mark.asyncio
async def test_sequence_increments(db):
    store = EventStore(db)
    e1 = await store.append(
        event_type="offer.created",
        aggregate_type="negotiation",
        aggregate_id="neg-456",
        payload={"offer_price": 300000},
    )
    e2 = await store.append(
        event_type="offer.countered",
        aggregate_type="negotiation",
        aggregate_id="neg-456",
        payload={"counter_price": 320000},
    )
    assert e1.sequence == 1
    assert e2.sequence == 2
    await db.commit()


@pytest.mark.asyncio
async def test_get_events(db):
    store = EventStore(db)
    await store.append(
        event_type="offer.created",
        aggregate_type="negotiation",
        aggregate_id="neg-789",
        payload={"price": 100},
    )
    await store.append(
        event_type="offer.accepted",
        aggregate_type="negotiation",
        aggregate_id="neg-789",
        payload={"price": 100},
    )
    await db.commit()

    events = await store.get_events("negotiation", "neg-789")
    assert len(events) == 2
    assert events[0].event_type == "offer.created"
    assert events[1].event_type == "offer.accepted"


@pytest.mark.asyncio
async def test_get_by_correlation(db):
    store = EventStore(db)
    await store.append(
        event_type="offer.created",
        aggregate_type="negotiation",
        aggregate_id="neg-aaa",
        payload={},
        correlation_id="corr-xyz",
    )
    await store.append(
        event_type="agent.decision",
        aggregate_type="agent",
        aggregate_id="agent-1",
        payload={},
        correlation_id="corr-xyz",
    )
    await db.commit()

    events = await store.get_by_correlation("corr-xyz")
    assert len(events) == 2


@pytest.mark.asyncio
async def test_replay_aggregate(db):
    store = EventStore(db)
    await store.append(
        event_type="offer.created",
        aggregate_type="negotiation",
        aggregate_id="neg-replay",
        payload={"price": 300000},
        actor_type="user",
        actor_id="user-1",
    )
    await db.commit()

    replay = await store.replay_aggregate("negotiation", "neg-replay")
    assert len(replay) == 1
    assert replay[0]["event_type"] == "offer.created"
    assert replay[0]["payload"]["price"] == 300000
