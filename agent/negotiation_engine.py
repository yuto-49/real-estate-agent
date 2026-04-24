"""Multi-turn negotiation orchestration engine.

Handles the full negotiation loop: buyer offers, seller counters,
broker mediates. Implements ZOPA detection (round 5+) and
auto-broker-mediation when spread is too wide.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.decisions.negotiation import (
    NegotiationState,
    NegotiationTimer,
    build_negotiation_analysis,
    negotiation_event,
    normalize_action,
    normalize_state,
    resolve_offer_action,
    transition,
)
from domain.outcomes import NegotiationOfferSnapshot, project_negotiation_session
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

    async def _get_negotiation(self, negotiation_id: str) -> Negotiation | None:
        result = await self.db.execute(
            select(Negotiation).where(Negotiation.id == negotiation_id)
        )
        return result.scalar_one_or_none()

    async def _load_negotiation_offers(self, negotiation: Negotiation) -> list[Offer]:
        """Load authoritative offer ledger rows for a negotiation with legacy fallback."""
        result = await self.db.execute(
            select(Offer)
            .where(Offer.negotiation_id == negotiation.id)
            .order_by(Offer.created_at.asc())
        )
        offers = list(result.scalars().all())
        if offers:
            return offers

        legacy_result = await self.db.execute(
            select(Offer)
            .where(
                Offer.negotiation_id.is_(None),
                Offer.property_id == negotiation.property_id,
                Offer.buyer_id == negotiation.buyer_id,
            )
            .order_by(Offer.created_at.asc())
        )
        return list(legacy_result.scalars().all())

    async def _get_latest_offer(self, negotiation: Negotiation) -> Offer | None:
        offers = await self._load_negotiation_offers(negotiation)
        return offers[-1] if offers else None

    async def process_offer(
        self,
        negotiation_id: str,
        offer_price: float,
        from_role: str,  # "buyer" or "seller"
        message: str = "",
        correlation_id: str | None = None,
    ) -> dict:
        """Process an offer/counter-offer in a negotiation."""
        neg = await self._get_negotiation(negotiation_id)
        if not neg:
            return {"error": "Negotiation not found"}

        now = datetime.utcnow()

        # Check deadline
        if neg.deadline_at and now > neg.deadline_at:
            return {"error": "Negotiation has expired", "expired": True}

        current_status = normalize_state(neg.status)
        action = resolve_offer_action(current_status)

        # Attempt state transition
        try:
            new_state = transition(
                current_status,
                action,
                neg.round_count,
            )
        except ValueError as e:
            return {"error": str(e)}

        from_id = neg.buyer_id if from_role == "buyer" else neg.seller_id
        latest_offer = await self._get_latest_offer(neg)
        if latest_offer and latest_offer.status == "pending":
            latest_offer.status = "countered"

        offer = Offer(
            negotiation_id=negotiation_id,
            property_id=neg.property_id,
            buyer_id=neg.buyer_id,
            actor_role=from_role,
            actor_user_id=from_id,
            offer_price=offer_price,
            status="pending",
            parent_offer_id=latest_offer.id if latest_offer else None,
            message=message[:500] if message else None,
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
            event_type=negotiation_event(action),
            aggregate_type="negotiation",
            aggregate_id=negotiation_id,
            payload={
                "from_role": from_role,
                "offer_price": offer_price,
                "round": neg.round_count,
                "old_status": old_status.value,
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
            action=action.value,
            reasoning=message,
            correlation_id=correlation_id,
        )
        self.db.add(decision)

        # Publish event
        if self.event_bus:
            await self.event_bus.publish_negotiation_event(
                negotiation_id,
                negotiation_event(action),
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
            "action": action.value,
            "old_status": old_status.value,
            "new_status": new_state.value,
            "round": neg.round_count,
            "round_count": neg.round_count,
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
        neg = await self._get_negotiation(negotiation_id)
        if not neg:
            return {"error": "Negotiation not found"}

        now = datetime.utcnow()
        if neg.deadline_at and now > neg.deadline_at:
            return {"error": "Negotiation has expired", "expired": True}

        current_status = normalize_state(neg.status)

        try:
            new_state = transition(current_status, "accept")
        except ValueError as e:
            return {"error": str(e)}

        neg.status = NegotiationStatus(new_state.value)
        neg.final_price = final_price
        neg.updated_at = now
        neg.state_entered_at = now
        neg.deadline_at = NegotiationTimer.get_deadline(new_state, now)

        from_id = neg.buyer_id if from_role == "buyer" else neg.seller_id
        latest_offer = await self._get_latest_offer(neg)
        if latest_offer:
            latest_offer.status = "accepted"

        await self.event_store.append(
            event_type=negotiation_event("accept"),
            aggregate_type="negotiation",
            aggregate_id=negotiation_id,
            payload={
                "final_price": final_price,
                "from_role": from_role,
                "old_status": current_status.value,
                "new_status": new_state.value,
            },
            actor_type="agent",
            actor_id=from_id,
            correlation_id=correlation_id,
        )

        decision = AgentDecision(
            agent_type=from_role,
            negotiation_id=negotiation_id,
            user_id=from_id,
            action="accept",
            correlation_id=correlation_id,
        )
        self.db.add(decision)

        if self.event_bus:
            await self.event_bus.publish_negotiation_event(
                negotiation_id,
                negotiation_event("accept"),
                {"final_price": final_price, "new_status": new_state.value},
            )

        await self.db.commit()

        return {
            "negotiation_id": negotiation_id,
            "action": "accept",
            "old_status": current_status.value,
            "new_status": new_state.value,
            "status": "accepted",
            "final_price": final_price,
            "round_count": neg.round_count,
            "deadline_at": neg.deadline_at.isoformat() if neg.deadline_at else None,
        }

    async def transition_negotiation(
        self,
        negotiation_id: str,
        action: str,
        from_role: str = "broker",
        message: str = "",
        correlation_id: str | None = None,
    ) -> dict:
        """Advance a non-pricing negotiation lifecycle transition."""
        neg = await self._get_negotiation(negotiation_id)
        if not neg:
            return {"error": "Negotiation not found"}

        now = datetime.utcnow()
        if neg.deadline_at and now > neg.deadline_at:
            return {"error": "Negotiation has expired", "expired": True}

        current_status = normalize_state(neg.status)
        domain_action = normalize_action(action)

        try:
            new_state = transition(current_status, domain_action, neg.round_count)
        except ValueError as e:
            return {"error": str(e)}

        neg.status = NegotiationStatus(new_state.value)
        neg.updated_at = now
        neg.state_entered_at = now
        neg.deadline_at = NegotiationTimer.get_deadline(new_state, now)
        latest_offer = await self._get_latest_offer(neg)
        if latest_offer and domain_action.value in {"reject", "withdraw"}:
            latest_offer.status = "rejected" if domain_action.value == "reject" else "withdrawn"

        if from_role == "buyer":
            actor_id = neg.buyer_id
        elif from_role == "seller":
            actor_id = neg.seller_id
        else:
            actor_id = None

        await self.event_store.append(
            event_type=negotiation_event(domain_action),
            aggregate_type="negotiation",
            aggregate_id=negotiation_id,
            payload={
                "from_role": from_role,
                "message": message[:500] if message else "",
                "old_status": current_status.value,
                "new_status": new_state.value,
                "round": neg.round_count,
            },
            actor_type="agent" if from_role else "system",
            actor_id=actor_id,
            correlation_id=correlation_id,
        )

        self.db.add(
            AgentDecision(
                agent_type=from_role,
                negotiation_id=negotiation_id,
                user_id=actor_id,
                action=domain_action.value,
                reasoning=message,
                correlation_id=correlation_id,
            )
        )

        if self.event_bus:
            await self.event_bus.publish_negotiation_event(
                negotiation_id,
                negotiation_event(domain_action),
                {
                    "from_role": from_role,
                    "new_status": new_state.value,
                    "round": neg.round_count,
                },
            )

        await self.db.commit()

        return {
            "negotiation_id": negotiation_id,
            "action": domain_action.value,
            "old_status": current_status.value,
            "new_status": new_state.value,
            "round_count": neg.round_count,
            "deadline_at": neg.deadline_at.isoformat() if neg.deadline_at else None,
        }

    async def _analyze_negotiation(self, negotiation_id: str) -> dict:
        """Analyze the negotiation state for ZOPA detection and broker mediation."""
        neg = await self._get_negotiation(negotiation_id)
        if not neg:
            return {}

        offer_list = list(reversed(await self._load_negotiation_offers(neg)))
        return build_negotiation_analysis(
            round_count=neg.round_count,
            offer_prices=[offer.offer_price for offer in offer_list],
            zopa_threshold_rounds=self.ZOPA_THRESHOLD_ROUNDS,
            zopa_spread_percent=self.ZOPA_SPREAD_PERCENT,
            broker_mediation_spread=self.BROKER_MEDIATION_SPREAD,
        )

    async def get_negotiation_state(self, negotiation_id: str) -> dict | None:
        """Get full negotiation state including event replay."""
        neg = await self._get_negotiation(negotiation_id)
        if not neg:
            return None

        events = await self.event_store.replay_aggregate("negotiation", negotiation_id)
        offer_history = await self._load_negotiation_offers(neg)
        analysis = await self._analyze_negotiation(negotiation_id)

        return project_negotiation_session(
            negotiation=neg,
            offers=self._build_offer_snapshots(
                negotiation=neg,
                offers=offer_history,
                events=events,
            ),
            events=events,
            analysis=analysis,
        )

    def _build_offer_snapshots(
        self,
        *,
        negotiation: Negotiation,
        offers: list[Offer],
        events: list[dict],
    ) -> list[NegotiationOfferSnapshot]:
        """Project persisted offers into a richer session history."""
        pricing_events = [
            event
            for event in events
            if event["event_type"] in {
                negotiation_event("place_offer"),
                negotiation_event("counter"),
            }
        ]
        snapshots: list[NegotiationOfferSnapshot] = []
        for index, offer in enumerate(offers):
            event_payload = pricing_events[index]["payload"] if index < len(pricing_events) else {}
            actor_role = offer.actor_role or event_payload.get("from_role")
            if offer.actor_user_id:
                actor_user_id = offer.actor_user_id
            elif actor_role == "buyer":
                actor_user_id = negotiation.buyer_id
            elif actor_role == "seller":
                actor_user_id = negotiation.seller_id
            else:
                actor_user_id = offer.buyer_id
            snapshots.append(
                NegotiationOfferSnapshot(
                    offer_id=offer.id,
                    property_id=offer.property_id,
                    buyer_id=offer.buyer_id,
                    offer_price=offer.offer_price,
                    actor_role=actor_role,
                    actor_user_id=actor_user_id,
                    status=offer.status,
                    parent_offer_id=offer.parent_offer_id,
                    correlation_id=offer.correlation_id,
                    message=offer.message or event_payload.get("message"),
                    created_at=offer.created_at,
                )
            )
        return snapshots
