"""End-to-end negotiation flow tests.

Covers: full negotiation lifecycle, event sourcing integrity,
guardrails enforcement, simulation config derivation from reports,
and the social-sim → report → negotiation pipeline.
"""

import pytest
from typing import Any, cast

from db.models import (
    DomainEvent,
    Negotiation,
    Offer,
    Property,
    UserProfile,
)
from services.event_store import EventStore
from agent.negotiation_engine import NegotiationEngine
from agent.guardrails import (
    GuardrailResult,
    check_escalation,
    check_max_rounds,
    check_price_per_sqft,
    validate_disclosures,
    validate_offer,
)
from agent.simulation_tools import SimulationState, create_simulation_tools
from services.negotiation_simulator import NegotiationSimulator


# ── Fixtures ──


@pytest.fixture
async def buyer(db):
    user = UserProfile(
        name="E2E Buyer",
        email="e2e_buyer@test.com",
        role="buyer",
        budget_max=500000,
        zip_code="60601",
    )
    db.add(user)
    await db.flush()
    return user


@pytest.fixture
async def seller(db):
    user = UserProfile(
        name="E2E Seller",
        email="e2e_seller@test.com",
        role="seller",
    )
    db.add(user)
    await db.flush()
    return user


@pytest.fixture
async def test_property(db, seller):
    prop = Property(
        seller_id=seller.id,
        address="200 E2E St, Chicago, IL 60601",
        asking_price=400000,
        bedrooms=3,
        bathrooms=2,
        sqft=1800,
        property_type="sfr",
        status="active",
    )
    db.add(prop)
    await db.flush()
    return prop


@pytest.fixture
async def negotiation(db, buyer, seller, test_property):
    neg = Negotiation(
        property_id=test_property.id,
        buyer_id=buyer.id,
        seller_id=seller.id,
        status="idle",
        round_count=0,
    )
    db.add(neg)
    await db.commit()
    return neg


@pytest.fixture
def event_store(db):
    return EventStore(db)


@pytest.fixture
def sample_social_report():
    """A MiroFish report generated from social simulation."""
    return {
        "market_outlook": {
            "trend": "cautiously_optimistic",
            "confidence": 0.6,
            "projected_appreciation_pct": 2.5,
            "market_health_score": 68,
            "source": "social_simulation",
        },
        "decision_anchors": {
            "max_recommended_price": 420000,
            "walk_away_price": 340000,
        },
        "strategy_comparison": [
            {
                "name": "Conservative",
                "recommended_offer_pct": 95,
                "success_probability": 0.75,
            },
            {
                "name": "Balanced",
                "recommended_offer_pct": 95,
                "success_probability": 0.65,
            },
            {
                "name": "Aggressive",
                "recommended_offer_pct": 98,
                "success_probability": 0.50,
            },
        ],
        "risk_assessment": [
            {
                "factor": "weak_tenant_protections",
                "severity": "high",
                "probability": 0.45,
            },
        ],
        "monte_carlo_results": {
            "probability_of_loss": 0.12,
            "mean_irr": 6.5,
            "hold_years": 10,
            "irr_distribution": {"p10": 2.0, "p50": 6.5, "p90": 11.0},
        },
        "comparable_sales_analysis": {
            "value_indicator": "at_market",
            "median_price_per_sqft": 222,
            "subject_price_per_sqft": 222,
        },
        "timing_recommendation": {
            "action": "proceed_cautiously",
            "reasoning": "Community sentiment is cautiously_optimistic.",
        },
        "neighborhood_scoring": {
            "overall_score": 68,
            "safety": 62,
            "community_support": 70,
            "policy_environment": 55,
        },
        "household_context": {
            "income_band": "moderate",
            "eviction_risk": 0.15,
            "voucher_eligible": False,
            "housing_cost_burden_pct": 28.0,
        },
        "community_intelligence": {
            "simulation_run_id": "test-social-run",
            "total_rounds": 5,
            "households_simulated": 4,
        },
    }


# ── Guardrails Tests ──


class TestGuardrails:

    def test_valid_offer_passes(self):
        result = validate_offer(
            offer_price=350000,
            asking_price=400000,
            buyer_budget=500000,
        )
        assert result.passed
        assert result.reason == "OK"

    def test_offer_below_minimum_rejected(self):
        # 50% of 400k = 200k minimum
        result = validate_offer(
            offer_price=190000,
            asking_price=400000,
            buyer_budget=500000,
        )
        assert not result.passed
        assert "below" in result.reason.lower()

    def test_offer_exceeds_budget_rejected(self):
        result = validate_offer(
            offer_price=550000,
            asking_price=400000,
            buyer_budget=500000,
        )
        assert not result.passed
        assert "budget" in result.reason.lower()

    def test_escalation_threshold(self):
        assert check_escalation(3_000_000) is True
        assert check_escalation(1_000_000) is False

    def test_max_rounds_check(self):
        from config import settings
        assert check_max_rounds(settings.max_counter_rounds) is True
        assert check_max_rounds(1) is False

    def test_disclosures_validation(self):
        # Missing disclosures
        result = validate_disclosures({"known_defects": True})
        assert not result.passed
        assert "Missing" in result.reason

        # Complete disclosures
        complete = {
            "known_defects": True,
            "flood_zone": False,
            "hoa_fees": 0,
            "lead_paint": False,
            "environmental_hazards": False,
        }
        result = validate_disclosures(complete)
        assert result.passed

    def test_price_per_sqft_check(self):
        # Reasonable price
        result = check_price_per_sqft(400000, 1800)
        assert result.passed

        # Extreme price
        result = check_price_per_sqft(10_000_000, 500)
        assert not result.passed
        assert "threshold" in result.reason.lower()

        # Invalid sqft
        result = check_price_per_sqft(400000, 0)
        assert not result.passed


# ── Event Sourcing Tests ──


class TestEventSourcingIntegrity:

    @pytest.mark.asyncio
    async def test_full_negotiation_event_chain(
        self, db, negotiation, event_store,
    ):
        """Verify a complete negotiation produces ordered events."""
        neg_id = cast(str, negotiation.id)
        corr_id = "corr-e2e-test-1"

        # Simulate a 3-round negotiation with events
        events_to_record = [
            ("negotiation.started", {"status": "idle"}),
            ("offer.created", {"price": 360000, "from": "buyer"}),
            ("offer.countered", {"price": 390000, "from": "seller"}),
            ("offer.countered", {"price": 375000, "from": "buyer"}),
            ("offer.countered", {"price": 382000, "from": "seller"}),
            ("offer.accepted", {"price": 382000, "by": "buyer"}),
        ]

        for etype, payload in events_to_record:
            await event_store.append(
                event_type=etype,
                aggregate_type="negotiation",
                aggregate_id=neg_id,
                payload=payload,
                correlation_id=corr_id,
            )
        await db.commit()

        # Replay and verify
        events = await event_store.get_events("negotiation", neg_id)
        assert len(events) == 6

        # Verify sequence is strictly monotonic
        for i, e in enumerate(events):
            assert e.sequence == i + 1

        # Verify event types in correct order
        assert events[0].event_type == "negotiation.started"
        assert events[-1].event_type == "offer.accepted"

        # Verify price path makes sense
        prices = [
            e.payload.get("price")
            for e in events
            if e.payload.get("price")
        ]
        assert prices == [360000, 390000, 375000, 382000, 382000]

    @pytest.mark.asyncio
    async def test_correlation_id_links_all_events(
        self, db, negotiation, event_store,
    ):
        """Events across aggregates share correlation ID."""
        corr_id = "corr-cross-aggregate"
        neg_id = cast(str, negotiation.id)

        await event_store.append(
            event_type="offer.created",
            aggregate_type="negotiation",
            aggregate_id=neg_id,
            payload={"price": 350000},
            correlation_id=corr_id,
        )
        await event_store.append(
            event_type="agent.decision",
            aggregate_type="agent",
            aggregate_id="buyer-agent-1",
            payload={"action": "counter"},
            correlation_id=corr_id,
        )
        await event_store.append(
            event_type="agent.decision",
            aggregate_type="agent",
            aggregate_id="seller-agent-1",
            payload={"action": "accept"},
            correlation_id=corr_id,
        )
        await db.commit()

        events = await event_store.get_by_correlation(corr_id)
        assert len(events) == 3

        aggregate_types = {cast(str, e.aggregate_type) for e in events}
        assert aggregate_types == {"negotiation", "agent"}

    @pytest.mark.asyncio
    async def test_replay_produces_consistent_state(
        self, db, event_store,
    ):
        """Replaying events should reconstruct negotiation state."""
        neg_id = "neg-replay-test"

        await event_store.append(
            event_type="negotiation.started",
            aggregate_type="negotiation",
            aggregate_id=neg_id,
            payload={"asking_price": 400000},
        )
        await event_store.append(
            event_type="offer.created",
            aggregate_type="negotiation",
            aggregate_id=neg_id,
            payload={"price": 360000},
        )
        await event_store.append(
            event_type="offer.accepted",
            aggregate_type="negotiation",
            aggregate_id=neg_id,
            payload={"price": 380000},
        )
        await db.commit()

        replay = await event_store.replay_aggregate(
            "negotiation", neg_id,
        )
        assert len(replay) == 3
        assert replay[0]["event_type"] == "negotiation.started"
        assert replay[-1]["event_type"] == "offer.accepted"
        assert replay[-1]["payload"]["price"] == 380000


# ── Simulation Tools Tests ──


class TestSimulationTools:

    @pytest.mark.asyncio
    async def test_place_offer_tracks_state(self):
        state = SimulationState(
            property_id="prop-1",
            asking_price=400000,
            buyer_maximum=450000,
            seller_minimum=380000,
        )
        tools = create_simulation_tools(state)

        result = await tools["place_offer"](
            property_id="prop-1",
            offer_price=370000,
        )

        assert result["status"] == "submitted"
        assert state.buyer_latest_price == 370000
        assert len(state.offers) == 1
        assert len(state.price_path) == 1

    @pytest.mark.asyncio
    async def test_counter_offer_updates_seller_price(self):
        state = SimulationState(
            property_id="prop-1",
            asking_price=400000,
            buyer_maximum=450000,
            seller_minimum=380000,
            buyer_latest_price=370000,
        )
        tools = create_simulation_tools(state)

        result = await tools["counter_offer"](
            negotiation_id="sim-neg",
            counter_price=395000,
            _from_role="seller",
        )

        assert state.seller_latest_price == 395000
        assert len(state.offers) == 1

    @pytest.mark.asyncio
    async def test_accept_offer_finalizes(self):
        state = SimulationState(
            property_id="prop-1",
            asking_price=400000,
            buyer_maximum=450000,
            seller_minimum=380000,
            buyer_latest_price=385000,
            seller_latest_price=385000,
        )
        tools = create_simulation_tools(state)

        result = await tools["accept_offer"](
            negotiation_id="sim-neg",
            _from_role="seller",
        )

        assert state.status == "accepted"

    @pytest.mark.asyncio
    async def test_price_path_tracks_rounds(self):
        state = SimulationState(
            property_id="prop-1",
            asking_price=400000,
            buyer_maximum=450000,
            seller_minimum=380000,
        )
        tools = create_simulation_tools(state)

        # Round 1: buyer offers
        state.current_round = 1
        await tools["place_offer"](offer_price=360000)

        # Round 1: seller counters
        await tools["counter_offer"](
            counter_price=395000, _from_role="seller",
        )

        # Round 2: buyer counters
        state.current_round = 2
        await tools["counter_offer"](
            counter_price=375000, _from_role="buyer",
        )

        assert len(state.price_path) == 3
        assert state.price_path[0]["price"] == 360000
        assert state.price_path[1]["price"] == 395000
        assert state.price_path[2]["price"] == 375000


# ── Derive Config from Social Report Tests ──


class TestDeriveConfigFromSocialReport:

    def test_extracts_buyer_maximum_from_anchors(
        self, sample_social_report,
    ):
        config = NegotiationSimulator.derive_config_from_report(
            sample_social_report, asking_price=400000,
        )
        assert config["buyer_maximum"] == 420000

    def test_extracts_walk_away_price(self, sample_social_report):
        config = NegotiationSimulator.derive_config_from_report(
            sample_social_report, asking_price=400000,
        )
        assert config["buyer_walk_away"] == 340000

    def test_selects_strategy_based_on_market(
        self, sample_social_report,
    ):
        config = NegotiationSimulator.derive_config_from_report(
            sample_social_report, asking_price=400000,
        )
        # cautiously_optimistic + prob_loss=0.12 → aggressive
        assert config["strategy"] == "aggressive"

    def test_initial_offer_from_strategy(self, sample_social_report):
        config = NegotiationSimulator.derive_config_from_report(
            sample_social_report, asking_price=400000,
        )
        # Aggressive strategy: recommended_offer_pct=98
        assert config["initial_offer"] == 392000  # 400k * 0.98

    def test_high_risk_reduces_max_rounds(self):
        report = {
            "decision_anchors": {"max_recommended_price": 420000},
            "strategy_comparison": [],
            "risk_assessment": [
                {
                    "factor": "major_risk",
                    "severity": "high",
                    "probability": 0.5,
                },
            ],
            "monte_carlo_results": {},
            "market_outlook": {},
        }
        config = NegotiationSimulator.derive_config_from_report(
            report, asking_price=400000,
        )
        assert config.get("max_rounds", 10) <= 8

    def test_buy_now_timing_sets_high_urgency(
        self, sample_social_report,
    ):
        report = dict(sample_social_report)
        report["timing_recommendation"] = {
            "action": "buy_now",
            "reasoning": "Market is bearish",
        }
        config = NegotiationSimulator.derive_config_from_report(
            report, asking_price=400000,
        )
        constraints = config.get("scenario_constraints", {})
        assert constraints.get("buyer_urgency") == "high"

    def test_bearish_market_selects_conservative(self):
        report = {
            "market_outlook": {
                "trend": "bearish",
                "market_health_score": 40,
            },
            "decision_anchors": {},
            "strategy_comparison": [
                {"name": "Conservative", "recommended_offer_pct": 88},
                {"name": "Balanced", "recommended_offer_pct": 92},
                {"name": "Aggressive", "recommended_offer_pct": 96},
            ],
            "risk_assessment": [],
            "monte_carlo_results": {
                "probability_of_loss": 0.35,
            },
        }
        config = NegotiationSimulator.derive_config_from_report(
            report, asking_price=400000,
        )
        assert config["strategy"] == "conservative"
        assert config["initial_offer"] == 352000  # 400k * 0.88

    def test_above_market_property_lowers_offer(self):
        report = {
            "market_outlook": {},
            "decision_anchors": {},
            "strategy_comparison": [],
            "risk_assessment": [],
            "monte_carlo_results": {"probability_of_loss": 0.2},
            "comparable_sales_analysis": {
                "value_indicator": "above_market",
                "median_price_per_sqft": 185,
            },
        }
        config = NegotiationSimulator.derive_config_from_report(
            report, asking_price=400000,
        )
        # Above market → initial offer at 90%
        assert config.get("initial_offer") == 360000


# ── Negotiation State Machine Tests ──


class TestNegotiationStateMachine:

    @pytest.mark.asyncio
    async def test_negotiation_creation(
        self, db, buyer, seller, test_property,
    ):
        neg = Negotiation(
            property_id=test_property.id,
            buyer_id=buyer.id,
            seller_id=seller.id,
            status="idle",
            round_count=0,
        )
        db.add(neg)
        await db.commit()
        await db.refresh(neg)

        assert neg.id is not None
        assert neg.status.value == "idle"
        assert neg.round_count == 0

    @pytest.mark.asyncio
    async def test_offer_creates_with_fk_chain(
        self, db, buyer, test_property, negotiation,
    ):
        offer = Offer(
            property_id=test_property.id,
            buyer_id=buyer.id,
            offer_price=380000,
            status="pending",
            correlation_id="corr-offer-test",
        )
        db.add(offer)
        await db.commit()
        await db.refresh(offer)

        assert offer.id is not None
        assert offer.offer_price == 380000
        assert offer.correlation_id == "corr-offer-test"
