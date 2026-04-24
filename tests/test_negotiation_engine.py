"""Negotiation engine integration tests with mocked DB — no Claude API calls."""

import pytest
from sqlalchemy import select

from agent.tools.broker_tools import mediate_negotiation
from db.models import Offer, UserProfile, Property, Negotiation, NegotiationStatus
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
async def test_offer_ledger_persists_negotiation_actor_and_parent_chain(db):
    """Offer rows created by the engine should be authoritative negotiation ledger entries."""
    buyer = UserProfile(name="Ledger Buyer", email="ledger_buyer@test.com", role="buyer")
    seller = UserProfile(name="Ledger Seller", email="ledger_seller@test.com", role="seller")
    db.add_all([buyer, seller])
    await db.flush()

    prop = Property(
        seller_id=seller.id,
        address="555 Ledger Ln, Chicago, IL 60601",
        asking_price=410000,
    )
    db.add(prop)
    await db.flush()

    negotiation = Negotiation(
        property_id=prop.id,
        buyer_id=buyer.id,
        seller_id=seller.id,
        status=NegotiationStatus.IDLE,
    )
    db.add(negotiation)
    await db.commit()

    event_store = EventStore(db)
    engine = NegotiationEngine(db=db, event_store=event_store)

    await engine.process_offer(
        negotiation_id=negotiation.id,
        offer_price=385000,
        from_role="buyer",
        message="Buyer opening move",
    )
    await engine.process_offer(
        negotiation_id=negotiation.id,
        offer_price=398000,
        from_role="seller",
        message="Seller counter move",
    )

    result = await db.execute(
        select(Offer)
        .where(Offer.negotiation_id == negotiation.id)
        .order_by(Offer.created_at.asc())
    )
    offers = list(result.scalars().all())

    assert len(offers) == 2
    assert offers[0].negotiation_id == negotiation.id
    assert offers[0].actor_role == "buyer"
    assert offers[0].actor_user_id == buyer.id
    assert offers[0].message == "Buyer opening move"
    assert offers[0].parent_offer_id is None

    assert offers[1].negotiation_id == negotiation.id
    assert offers[1].actor_role == "seller"
    assert offers[1].actor_user_id == seller.id
    assert offers[1].message == "Seller counter move"
    assert offers[1].parent_offer_id == offers[0].id


@pytest.mark.asyncio
async def test_negotiation_state_isolated_to_negotiation_ledger(db):
    """Session projection should only include offers for the requested negotiation."""
    buyer_one = UserProfile(name="Buyer One", email="buyer_one@test.com", role="buyer")
    buyer_two = UserProfile(name="Buyer Two", email="buyer_two@test.com", role="buyer")
    seller = UserProfile(name="Shared Seller", email="shared_seller@test.com", role="seller")
    db.add_all([buyer_one, buyer_two, seller])
    await db.flush()

    prop = Property(
        seller_id=seller.id,
        address="444 Isolation Ave, Chicago, IL 60601",
        asking_price=450000,
    )
    db.add(prop)
    await db.flush()

    first_negotiation = Negotiation(
        property_id=prop.id,
        buyer_id=buyer_one.id,
        seller_id=seller.id,
        status=NegotiationStatus.IDLE,
    )
    second_negotiation = Negotiation(
        property_id=prop.id,
        buyer_id=buyer_two.id,
        seller_id=seller.id,
        status=NegotiationStatus.IDLE,
    )
    db.add_all([first_negotiation, second_negotiation])
    await db.commit()

    event_store = EventStore(db)
    engine = NegotiationEngine(db=db, event_store=event_store)

    await engine.process_offer(
        negotiation_id=first_negotiation.id,
        offer_price=420000,
        from_role="buyer",
        message="First negotiation offer",
    )
    await engine.process_offer(
        negotiation_id=second_negotiation.id,
        offer_price=435000,
        from_role="buyer",
        message="Second negotiation offer",
    )

    first_state = await engine.get_negotiation_state(first_negotiation.id)
    second_state = await engine.get_negotiation_state(second_negotiation.id)

    assert first_state is not None
    assert second_state is not None
    assert len(first_state["offer_history"]) == 1
    assert first_state["offer_history"][0]["message"] == "First negotiation offer"
    assert first_state["offer_history"][0]["actor_user_id"] == buyer_one.id

    assert len(second_state["offer_history"]) == 1
    assert second_state["offer_history"][0]["message"] == "Second negotiation offer"
    assert second_state["offer_history"][0]["actor_user_id"] == buyer_two.id


@pytest.mark.asyncio
async def test_broker_mediation_reads_negotiation_scoped_actor_prices(db):
    """Broker mediation should use negotiation-scoped offer ledger rows, not property-wide bleed-through."""
    buyer_one = UserProfile(name="Broker Buyer 1", email="broker_buyer1@test.com", role="buyer")
    buyer_two = UserProfile(name="Broker Buyer 2", email="broker_buyer2@test.com", role="buyer")
    seller = UserProfile(name="Broker Seller", email="broker_seller@test.com", role="seller")
    db.add_all([buyer_one, buyer_two, seller])
    await db.flush()

    prop = Property(
        seller_id=seller.id,
        address="333 Mediation Pl, Chicago, IL 60601",
        asking_price=500000,
    )
    db.add(prop)
    await db.flush()

    target_negotiation = Negotiation(
        property_id=prop.id,
        buyer_id=buyer_one.id,
        seller_id=seller.id,
        status=NegotiationStatus.IDLE,
    )
    other_negotiation = Negotiation(
        property_id=prop.id,
        buyer_id=buyer_two.id,
        seller_id=seller.id,
        status=NegotiationStatus.IDLE,
    )
    db.add_all([target_negotiation, other_negotiation])
    await db.commit()

    event_store = EventStore(db)
    engine = NegotiationEngine(db=db, event_store=event_store)

    await engine.process_offer(
        negotiation_id=target_negotiation.id,
        offer_price=470000,
        from_role="buyer",
        message="Target buyer offer",
    )
    await engine.process_offer(
        negotiation_id=target_negotiation.id,
        offer_price=488000,
        from_role="seller",
        message="Target seller counter",
    )
    await engine.process_offer(
        negotiation_id=other_negotiation.id,
        offer_price=499000,
        from_role="buyer",
        message="Other buyer offer that should not bleed",
    )

    result = await mediate_negotiation(
        db=db,
        event_store=event_store,
        negotiation_id=target_negotiation.id,
    )

    assert result["buyer_latest_price"] == 470000
    assert result["seller_latest_price"] == 488000


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
