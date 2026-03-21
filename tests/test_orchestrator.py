"""Orchestrator tests — uses DB fixtures, no Claude API calls."""

import pytest

from db.models import UserProfile, Property, NegotiationStatus


@pytest.mark.asyncio
async def test_start_negotiation(db):
    """Test starting a negotiation creates the correct DB state."""
    from agent.orchestrator import AgentOrchestrator

    buyer = UserProfile(name="Buyer", email="buyer_orch@test.com", role="buyer")
    seller = UserProfile(name="Seller", email="seller_orch@test.com", role="seller")
    db.add_all([buyer, seller])
    await db.flush()

    prop = Property(
        seller_id=seller.id,
        address="100 Orch St, Chicago, IL 60601",
        asking_price=400000,
    )
    db.add(prop)
    await db.flush()

    orchestrator = AgentOrchestrator(db=db)
    neg = await orchestrator.start_negotiation(prop.id, buyer.id, seller.id)

    assert neg.id is not None
    assert neg.property_id == prop.id
    status_val = neg.status.value if hasattr(neg.status, "value") else str(neg.status)
    assert status_val == "idle"


@pytest.mark.asyncio
async def test_negotiation_context(db):
    """Test that context is built from DB state."""
    from agent.orchestrator import AgentOrchestrator

    buyer = UserProfile(name="Buyer2", email="buyer_ctx@test.com", role="buyer")
    seller = UserProfile(name="Seller2", email="seller_ctx@test.com", role="seller")
    db.add_all([buyer, seller])
    await db.flush()

    prop = Property(
        seller_id=seller.id,
        address="200 Ctx St, Chicago, IL 60601",
        asking_price=500000,
    )
    db.add(prop)
    await db.flush()

    orchestrator = AgentOrchestrator(db=db)
    await orchestrator.start_negotiation(prop.id, buyer.id, seller.id)

    context = await orchestrator._get_negotiation_context(buyer.id)
    assert len(context["active_negotiations"]) == 1
    assert context["active_negotiations"][0]["property_id"] == prop.id
