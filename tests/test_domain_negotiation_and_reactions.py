"""Focused domain tests for the next negotiation/reaction refactor phase."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from domain.decisions import (
    NegotiationAction,
    build_negotiation_analysis,
    resolve_offer_action,
)
from domain.outcomes import NegotiationOfferSnapshot, project_negotiation_session
from domain.reactions import SocialReactionRuntime


def _make_household(
    household_id: str,
    *,
    income_band: str,
    housing_type: str,
    influence_weight: float,
    communication_style: str,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=household_id,
        income_band=income_band,
        housing_type=housing_type,
        influence_weight=influence_weight,
        communication_style=communication_style,
        opinion_stability=0.5,
    )


def test_decision_domain_builds_negotiation_analysis_and_projection():
    assert resolve_offer_action("idle") == NegotiationAction.PLACE_OFFER
    assert resolve_offer_action("offer_pending") == NegotiationAction.COUNTER

    analysis = build_negotiation_analysis(
        round_count=5,
        offer_prices=[380000, 382000, 381000, 381500, 381250],
    )
    assert analysis["zopa_detected"] is True
    assert analysis["recommendation"] == "suggest_split"

    negotiation = SimpleNamespace(
        id="neg-1",
        property_id="prop-1",
        buyer_id="buyer-1",
        seller_id="seller-1",
        status="offer_pending",
        round_count=5,
        final_price=None,
        deadline_at=datetime(2026, 4, 15, 12, 0, 0),
    )
    offers = [
        NegotiationOfferSnapshot(
            offer_id="offer-1",
            property_id="prop-1",
            buyer_id="buyer-1",
            offer_price=380000,
            actor_role="buyer",
            actor_user_id="buyer-1",
            created_at=datetime(2026, 4, 15, 9, 0, 0),
        ),
        NegotiationOfferSnapshot(
            offer_id="offer-2",
            property_id="prop-1",
            buyer_id="buyer-1",
            offer_price=381250,
            actor_role="seller",
            actor_user_id="seller-1",
            message="Final seller counter",
            parent_offer_id="offer-1",
            created_at=datetime(2026, 4, 15, 10, 0, 0),
        ),
    ]
    events = [
        {
            "event_type": "negotiation.started",
            "payload": {"property_id": "prop-1"},
            "sequence": 1,
            "created_at": "2026-04-15T09:00:00",
        }
    ]

    session = project_negotiation_session(
        negotiation=negotiation,
        offers=offers,
        events=events,
        analysis=analysis,
    )

    assert session["status"] == "offer_pending"
    assert session["current_analysis"]["spread_percent"] < 1.0
    assert session["offer_history"][1]["actor_role"] == "seller"
    assert session["offer_history"][1]["message"] == "Final seller counter"
    assert session["events"][0]["event_type"] == "negotiation.started"


def test_reaction_domain_runtime_tracks_neighbors_and_narratives():
    households = [
        _make_household(
            "h1",
            income_band="upper",
            housing_type="owner",
            influence_weight=0.8,
            communication_style="vocal",
        ),
        _make_household(
            "h2",
            income_band="low",
            housing_type="renter",
            influence_weight=0.3,
            communication_style="passive",
        ),
        _make_household(
            "h3",
            income_band="middle",
            housing_type="renter",
            influence_weight=0.5,
            communication_style="analytical",
        ),
    ]
    edges = [
        SimpleNamespace(source_id="h1", target_id="h2", edge_weight=0.8, edge_type="neighbor"),
        SimpleNamespace(source_id="h2", target_id="h3", edge_weight=0.5, edge_type="income_peer"),
    ]
    opinions = {
        "h1": {"market_prices": 0.7},
        "h2": {"market_prices": -0.4},
        "h3": {"market_prices": 0.1},
    }

    runtime = SocialReactionRuntime(
        households=households,
        edges=edges,
        opinions=opinions,
    )

    neighbors = runtime.gather_neighbor_opinions("h2", "market_prices")
    assert len(neighbors) == 2
    assert {neighbor["id"] for neighbor in neighbors} == {"h1", "h3"}

    previous = {"h2": {"market_prices": -0.4}}
    runtime.opinions["h2"]["market_prices"] = -0.25
    assert abs(runtime.compute_round_delta(previous) - 0.15) < 1e-9

    delta = runtime.compute_sentiment_delta(
        initial_opinions={
            "h1": {"market_prices": 0.6},
            "h2": {"market_prices": -0.5},
            "h3": {"market_prices": 0.0},
        },
        topics=["market_prices"],
    )
    assert delta["market_prices"]["shift"] > 0

    narratives = runtime.detect_narratives(["market_prices"])
    assert narratives["market_prices"]["supportive_count"] == 1
    assert narratives["market_prices"]["opposed_count"] == 1
    assert narratives["market_prices"]["neutral_count"] == 1
