"""Negotiation engine integration tests with mocked DB — no Claude API calls."""

import pytest

from db.models import UserProfile, Property, Negotiation, NegotiationStatus
from agent.negotiation_engine import NegotiationEngine
from services.event_store import EventStore


@pytest.mark.asyncio
async def test_full_negotiation_flow(db):
    """Test a complete negotiation from offer to acceptance."""
    # Setup test data
    buyer = UserProfile(name="Flow Buyer", email="flow_buyer@test.com", role="buyer", budget_max=500000)
    seller = UserProfile(name="Flow Seller", email="flow_seller@test.com", role="seller")
    db.add_all([buyer, seller])
    await db.flush()

    prop = Property(
        seller_id=seller.id,
        address="999 Negotiation St, Chicago, IL 60601",
        asking_price=400000,
    )
    db.add(prop)
    await db.flush()

    # Create negotiation
    neg = Negotiation(
        property_id=prop.id,
        buyer_id=buyer.id,
        seller_id=seller.id,
        status=NegotiationStatus.IDLE,
    )
    db.add(neg)
    await db.commit()

    event_store = EventStore(db)
    engine = NegotiationEngine(db=db, event_store=event_store)

    # Round 1: Buyer places offer
    result = await engine.process_offer(
        negotiation_id=neg.id,
        offer_price=370000,
        from_role="buyer",
        message="Starting offer at 370K",
    )
    assert result["new_status"] == "offer_pending"
    assert result["round"] == 1

    # Round 2: Seller counters
    result = await engine.process_offer(
        negotiation_id=neg.id,
        offer_price=390000,
        from_role="seller",
        message="Counter at 390K",
    )
    assert result["new_status"] == "counter_pending"
    assert result["round"] == 2

    # Round 3: Buyer counters again
    result = await engine.process_offer(
        negotiation_id=neg.id,
        offer_price=380000,
        from_role="buyer",
        message="Meeting in the middle at 380K",
    )
    assert result["new_status"] == "offer_pending"
    assert result["round"] == 3

    # Seller accepts
    result = await engine.accept_offer(
        negotiation_id=neg.id,
        from_role="seller",
        final_price=380000,
    )
    assert result["status"] == "accepted"
    assert result["final_price"] == 380000


@pytest.mark.asyncio
async def test_negotiation_state_retrieval(db):
    """Test getting full negotiation state with events."""
    buyer = UserProfile(name="State Buyer", email="state_buyer@test.com", role="buyer")
    seller = UserProfile(name="State Seller", email="state_seller@test.com", role="seller")
    db.add_all([buyer, seller])
    await db.flush()

    prop = Property(
        seller_id=seller.id,
        address="888 State St, Chicago, IL 60601",
        asking_price=350000,
    )
    db.add(prop)
    await db.flush()

    neg = Negotiation(
        property_id=prop.id,
        buyer_id=buyer.id,
        seller_id=seller.id,
        status=NegotiationStatus.IDLE,
    )
    db.add(neg)
    await db.commit()

    event_store = EventStore(db)
    engine = NegotiationEngine(db=db, event_store=event_store)

    await engine.process_offer(neg.id, 320000, "buyer")

    state = await engine.get_negotiation_state(neg.id)
    assert state is not None
    assert state["status"] == "offer_pending"
    assert len(state["events"]) >= 1


@pytest.mark.asyncio
async def test_expired_negotiation_rejected(db):
    """Test that offers on expired negotiations are rejected."""
    from datetime import datetime, timedelta

    buyer = UserProfile(name="Expired Buyer", email="expired_buyer@test.com", role="buyer")
    seller = UserProfile(name="Expired Seller", email="expired_seller@test.com", role="seller")
    db.add_all([buyer, seller])
    await db.flush()

    prop = Property(address="777 Expired St", asking_price=300000)
    db.add(prop)
    await db.flush()

    neg = Negotiation(
        property_id=prop.id,
        buyer_id=buyer.id,
        seller_id=seller.id,
        status=NegotiationStatus.OFFER_PENDING,
        deadline_at=datetime.utcnow() - timedelta(hours=1),
    )
    db.add(neg)
    await db.commit()

    event_store = EventStore(db)
    engine = NegotiationEngine(db=db, event_store=event_store)

    result = await engine.process_offer(neg.id, 280000, "seller")
    assert "error" in result
    assert result.get("expired") is True
