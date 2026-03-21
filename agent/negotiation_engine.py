"""Multi-turn negotiation orchestration engine.

Handles the full negotiation loop: buyer offers, seller counters,
broker mediates. Implements ZOPA detection (round 5+) and
auto-broker-mediation when spread is too wide.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.negotiation import (
    NegotiationState,
    NegotiationTimer,
    transition,
)
from db.models import (
    Negotiation,
    NegotiationStatus,
    Offer,
    AgentDecision,
)
from services.event_store import EventStore
from services.pubsub import EventBus
from services.logging import get_logger

logger = get_logger(__name__)


class NegotiationEngine:
    """Orchestrates multi-turn negotiations between buyer, seller, and broker agents."""

    ZOPA_THRESHOLD_ROUNDS = 5
    ZOPA_SPREAD_PERCENT = 3.0
    BROKER_MEDIATION_SPREAD = 10.0

    def __init__(
        self,
        db: AsyncSession,
        event_store: EventStore,
        event_bus: EventBus | None = None,
    ):
        self.db = db
        self.event_store = event_store
        self.event_bus = event_bus

    async def process_offer(
        self,
        negotiation_id: str,
        offer_price: float,
        from_role: str,  # "buyer" or "seller"
        message: str = "",
        correlation_id: str | None = None,
    ) -> dict:
        """Process an offer/counter-offer in a negotiation."""
        result = await self.db.execute(
            select(Negotiation).where(Negotiation.id == negotiation_id)
        )
        neg = result.scalar_one_or_none()
        if not neg:
            return {"error": "Negotiation not found"}

        now = datetime.utcnow()

        # Check deadline
        if neg.deadline_at and now > neg.deadline_at:
            return {"error": "Negotiation has expired", "expired": True}

        # Determine the action
        current_status = neg.status.value if hasattr(neg.status, "value") else str(neg.status)
        action = "place_offer" if current_status == "idle" else "counter"

        # Attempt state transition
        try:
            new_state = transition(
                NegotiationState(current_status),
                action,
                neg.round_count,
            )
        except ValueError as e:
            return {"error": str(e)}

        # Create the offer record
        from_id = neg.buyer_id if from_role == "buyer" else neg.seller_id
        offer = Offer(
            property_id=neg.property_id,
            buyer_id=neg.buyer_id,
            offer_price=offer_price,
            correlation_id=correlation_id,
        )
        self.db.add(offer)

        # Update negotiation state
        old_status = current_status
        neg.status = NegotiationStatus(new_state.value)
        neg.round_count += 1
        neg.state_entered_at = now
        neg.updated_at = now

        # Calculate new deadline
        deadline = NegotiationTimer.get_deadline(new_state, now)
        neg.deadline_at = deadline

        await self.db.flush()

        # Record domain event
        await self.event_store.append(
            event_type=f"negotiation.{action}",
            aggregate_type="negotiation",
            aggregate_id=negotiation_id,
            payload={
                "from_role": from_role,
                "offer_price": offer_price,
                "round": neg.round_count,
                "old_status": old_status,
                "new_status": new_state.value,
                "message": message[:500] if message else "",
            },
            actor_type="agent",
            actor_id=from_id,
            correlation_id=correlation_id,
        )

        # Record agent decision
        decision = AgentDecision(
            agent_type=from_role,
            negotiation_id=negotiation_id,
            user_id=from_id,
            action=action,
            reasoning=message,
            correlation_id=correlation_id,
        )
        self.db.add(decision)

        # Publish event
        if self.event_bus:
            await self.event_bus.publish_negotiation_event(
                negotiation_id,
                f"negotiation.{action}",
                {
                    "from_role": from_role,
                    "offer_price": offer_price,
                    "round": neg.round_count,
                    "new_status": new_state.value,
                },
            )

        await self.db.commit()

        # Check for ZOPA / broker mediation
        analysis = await self._analyze_negotiation(negotiation_id)

        return {
            "negotiation_id": negotiation_id,
            "new_status": new_state.value,
            "round": neg.round_count,
            "offer_price": offer_price,
            "deadline_at": deadline.isoformat() if deadline else None,
            "analysis": analysis,
        }

    async def accept_offer(
        self,
        negotiation_id: str,
        from_role: str,
        final_price: float,
        correlation_id: str | None = None,
    ) -> dict:
        """Accept the current offer and move to accepted state."""
        result = await self.db.execute(
            select(Negotiation).where(Negotiation.id == negotiation_id)
        )
        neg = result.scalar_one_or_none()
        if not neg:
            return {"error": "Negotiation not found"}

        current_status = neg.status.value if hasattr(neg.status, "value") else str(neg.status)

        try:
            new_state = transition(NegotiationState(current_status), "accept")
        except ValueError as e:
            return {"error": str(e)}

        neg.status = NegotiationStatus(new_state.value)
        neg.final_price = final_price
        neg.updated_at = datetime.utcnow()
        neg.state_entered_at = datetime.utcnow()
        neg.deadline_at = NegotiationTimer.get_deadline(new_state, datetime.utcnow())

        await self.event_store.append(
            event_type="negotiation.accepted",
            aggregate_type="negotiation",
            aggregate_id=negotiation_id,
            payload={"final_price": final_price, "from_role": from_role},
            actor_type="agent",
            correlation_id=correlation_id,
        )

        if self.event_bus:
            await self.event_bus.publish_negotiation_event(
                negotiation_id,
                "negotiation.accepted",
                {"final_price": final_price},
            )

        await self.db.commit()

        return {
            "negotiation_id": negotiation_id,
            "status": "accepted",
            "final_price": final_price,
        }

    async def _analyze_negotiation(self, negotiation_id: str) -> dict:
        """Analyze the negotiation state for ZOPA detection and broker mediation."""
        result = await self.db.execute(
            select(Negotiation).where(Negotiation.id == negotiation_id)
        )
        neg = result.scalar_one_or_none()
        if not neg:
            return {}

        # Get offer history
        offers = await self.db.execute(
            select(Offer)
            .where(Offer.property_id == neg.property_id)
            .order_by(Offer.created_at.desc())
        )
        offer_list = list(offers.scalars().all())

        if len(offer_list) < 2:
            return {"status": "insufficient_data"}

        prices = [o.offer_price for o in offer_list]
        spread = abs(max(prices) - min(prices)) / max(prices) * 100

        analysis = {
            "round": neg.round_count,
            "spread_percent": round(spread, 1),
            "offer_history": prices[:10],
        }

        # ZOPA detection (round 5+)
        if neg.round_count >= self.ZOPA_THRESHOLD_ROUNDS:
            if spread <= self.ZOPA_SPREAD_PERCENT:
                midpoint = (max(prices[-2:]) + min(prices[-2:])) / 2
                analysis["zopa_detected"] = True
                analysis["suggested_price"] = round(midpoint)
                analysis["recommendation"] = "suggest_split"
            else:
                analysis["zopa_detected"] = False

        # Auto-broker mediation
        if neg.round_count >= 5 and spread > self.BROKER_MEDIATION_SPREAD:
            analysis["broker_mediation_recommended"] = True
            analysis["recommendation"] = "escalate_to_broker"

        return analysis

    async def get_negotiation_state(self, negotiation_id: str) -> dict | None:
        """Get full negotiation state including event replay."""
        result = await self.db.execute(
            select(Negotiation).where(Negotiation.id == negotiation_id)
        )
        neg = result.scalar_one_or_none()
        if not neg:
            return None

        events = await self.event_store.replay_aggregate("negotiation", negotiation_id)

        return {
            "id": neg.id,
            "property_id": neg.property_id,
            "buyer_id": neg.buyer_id,
            "seller_id": neg.seller_id,
            "status": neg.status.value if hasattr(neg.status, "value") else str(neg.status),
            "round_count": neg.round_count,
            "final_price": neg.final_price,
            "deadline_at": neg.deadline_at.isoformat() if neg.deadline_at else None,
            "events": events,
        }
