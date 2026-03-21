"""Negotiation timeout tests."""

from datetime import datetime, timedelta

import pytest

from agent.negotiation import (
    NegotiationState,
    NegotiationTimer,
    TIMEOUT_HOURS,
)


def test_offer_pending_timeout():
    hours = NegotiationTimer.get_timeout_hours(NegotiationState.OFFER_PENDING)
    assert hours == 48


def test_counter_pending_timeout():
    hours = NegotiationTimer.get_timeout_hours(NegotiationState.COUNTER_PENDING)
    assert hours == 48


def test_inspection_timeout():
    hours = NegotiationTimer.get_timeout_hours(NegotiationState.INSPECTION)
    assert hours == 240  # 10 days


def test_idle_no_timeout():
    hours = NegotiationTimer.get_timeout_hours(NegotiationState.IDLE)
    assert hours is None


def test_deadline_calculation():
    now = datetime(2026, 3, 17, 12, 0, 0)
    deadline = NegotiationTimer.get_deadline(NegotiationState.OFFER_PENDING, now)
    expected = now + timedelta(hours=48)
    assert deadline == expected


def test_no_deadline_for_idle():
    now = datetime(2026, 3, 17, 12, 0, 0)
    deadline = NegotiationTimer.get_deadline(NegotiationState.IDLE, now)
    assert deadline is None


@pytest.mark.asyncio
async def test_check_expired_negotiations(db):
    """Test that expired negotiations are transitioned."""
    from db.models import Negotiation, NegotiationStatus, UserProfile, Property

    # Create test data
    user = UserProfile(name="Test Buyer", email="buyer@test.com", role="buyer")
    seller = UserProfile(name="Test Seller", email="seller@test.com", role="seller")
    db.add_all([user, seller])
    await db.flush()

    prop = Property(address="123 Test St", asking_price=300000)
    db.add(prop)
    await db.flush()

    # Create a negotiation that's past its deadline
    neg = Negotiation(
        property_id=prop.id,
        buyer_id=user.id,
        seller_id=seller.id,
        status=NegotiationStatus.OFFER_PENDING,
        deadline_at=datetime.utcnow() - timedelta(hours=1),
        state_entered_at=datetime.utcnow() - timedelta(hours=49),
    )
    db.add(neg)
    await db.commit()

    from services.timeout_checker import check_expired_negotiations
    expired = await check_expired_negotiations(db)
    assert neg.id in expired
