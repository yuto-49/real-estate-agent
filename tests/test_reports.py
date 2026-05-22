"""Phase G: report artifact and replay tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from domain.decisions.runtime import DecisionRecommendation
from domain.market.models import MarketContextSnapshot
from domain.outcomes.projections import MarketOutcomeSnapshot
from domain.reactions.engine import NarrativeCluster
from domain.reactions.models import ReactionEvent, ReactionVector
from domain.reports import (
    NegotiationBriefing,
    PolicyRiskBrief,
    ReplayFrame,
    ReplayNarrative,
    UnderwritingReport,
    build_negotiation_briefing,
    build_policy_risk_brief,
    build_underwriting_report,
    replay_reactions,
)


# ---------- underwriting ----------

def test_underwriting_report_buy_when_positive_signals():
    outcome = MarketOutcomeSnapshot(
        listing_id="L1",
        price_change_pct=2.0,
        time_on_market_days=10,
        offer_volume=3,
        concession_rate=1.0,
        neighborhood_sentiment=0.85,
        permit_friction=0.1,
    )
    reaction = ReactionVector(
        investor_optimism=0.8,
        affordability_pressure=-0.3,
    )
    report = build_underwriting_report(
        listing_id="L1",
        asking_price=600_000,
        outcome=outcome,
        reaction=reaction,
    )
    assert isinstance(report, UnderwritingReport)
    assert report.recommendation == "buy"
    assert report.confidence >= 0.65
    assert any("sentiment" in driver for driver in report.drivers)


def test_underwriting_report_pass_when_negative_signals():
    outcome = MarketOutcomeSnapshot(
        listing_id="L2",
        neighborhood_sentiment=0.1,
        permit_friction=0.9,
    )
    reaction = ReactionVector(
        investor_optimism=-0.7,
        affordability_pressure=0.8,
    )
    report = build_underwriting_report(
        listing_id="L2",
        asking_price=900_000,
        outcome=outcome,
        reaction=reaction,
    )
    assert report.recommendation == "pass"
    assert report.confidence <= 0.35


def test_underwriting_report_hold_for_mixed_signals():
    outcome = MarketOutcomeSnapshot(neighborhood_sentiment=0.5)
    report = build_underwriting_report(
        listing_id="L3",
        asking_price=None,
        outcome=outcome,
    )
    assert report.recommendation == "hold"


# ---------- negotiation briefing ----------

def test_negotiation_briefing_uses_decision_recommendation():
    decision = DecisionRecommendation(
        kind="negotiation",
        action="suggest_split",
        score=0.88,
        rationale="round=6 spread=2.5%",
        payload={"zopa_detected": True, "spread_percent": 2.5},
    )
    briefing = build_negotiation_briefing(
        negotiation_id="N1",
        round_count=6,
        current_state="counter_pending",
        decision=decision,
    )
    assert isinstance(briefing, NegotiationBriefing)
    assert briefing.next_action == "suggest_split"
    assert briefing.zopa_detected is True
    assert briefing.spread_percent == pytest.approx(2.5)
    assert briefing.top_decision_score == pytest.approx(0.88)


def test_negotiation_briefing_falls_back_when_no_decision():
    briefing = build_negotiation_briefing(
        negotiation_id="N2",
        round_count=0,
        current_state="idle",
        decision=None,
    )
    assert briefing.next_action == "await_offer"
    assert briefing.top_decision_score == 0.0
    assert briefing.spread_percent is None


# ---------- policy risk brief ----------

def test_policy_risk_brief_expects_pushback_under_high_resistance():
    brief = build_policy_risk_brief(
        market=MarketContextSnapshot(
            property_id="P1",
            jurisdiction="san-francisco",
            zoning_code="R-1",
        ),
        reaction=ReactionVector(
            resistance_to_development=0.9,
            displacement_concern=0.8,
        ),
    )
    assert isinstance(brief, PolicyRiskBrief)
    assert brief.recommendation == "expect_pushback"
    assert brief.zoning_code == "R-1"
    assert brief.resistance_score > 0.9


def test_policy_risk_brief_proceeds_under_low_resistance():
    brief = build_policy_risk_brief(
        market=MarketContextSnapshot(jurisdiction="austin"),
        reaction=ReactionVector(
            resistance_to_development=-0.6,
            displacement_concern=-0.5,
        ),
    )
    assert brief.recommendation == "proceed"


def test_policy_risk_brief_attaches_top_narratives():
    narratives = [
        NarrativeCluster(
            variable="resistance_to_development",
            direction="positive",
            total_delta=0.8,
            event_count=4,
            sample_narratives=("traffic concerns",),
        ),
        NarrativeCluster(
            variable="displacement_concern",
            direction="positive",
            total_delta=0.5,
            event_count=2,
            sample_narratives=("rent fears", "eviction filings"),
        ),
        NarrativeCluster(
            variable="trust_in_trajectory",
            direction="positive",
            total_delta=1.0,
            event_count=3,
            sample_narratives=("ignore me",),
        ),
    ]
    brief = build_policy_risk_brief(
        market=MarketContextSnapshot(),
        reaction=ReactionVector(resistance_to_development=0.6),
        narratives=narratives,
    )
    assert "traffic concerns" in brief.key_narratives
    assert "ignore me" not in brief.key_narratives


def test_policy_risk_brief_includes_outcome_metrics():
    outcome = MarketOutcomeSnapshot(
        permit_friction=0.7,
        neighborhood_sentiment=0.4,
    )
    brief = build_policy_risk_brief(
        market=MarketContextSnapshot(jurisdiction="oakland"),
        reaction=ReactionVector(resistance_to_development=0.3),
        outcome=outcome,
    )
    assert brief.permit_friction == pytest.approx(0.7)
    assert brief.sentiment == pytest.approx(0.4)


# ---------- replay ----------

def test_replay_returns_one_frame_per_event_in_order():
    events = [
        ("a1", ReactionEvent(topic="rent", variable="affordability_pressure", delta=0.4)),
        ("a2", ReactionEvent(topic="zoning", variable="resistance_to_development", delta=0.5)),
        ("a1", ReactionEvent(topic="rent", variable="willingness_to_transact", delta=-0.3)),
    ]
    narrative = replay_reactions(events, summary="rent shock + zoning fight")
    assert isinstance(narrative, ReplayNarrative)
    assert len(narrative.frames) == 3
    assert [f.step for f in narrative.frames] == [0, 1, 2]
    assert narrative.summary == "rent shock + zoning fight"
    assert narrative.frames[0].actor_id == "a1"
    assert narrative.frames[1].event_topic == "zoning"


def test_replay_actor_vector_reflects_only_that_actor():
    events = [
        ("a1", ReactionEvent(topic="t", variable="trust_in_trajectory", delta=0.4)),
        ("a2", ReactionEvent(topic="t", variable="trust_in_trajectory", delta=-0.6)),
    ]
    narrative = replay_reactions(events)
    assert narrative.frames[0].actor_vector.trust_in_trajectory == pytest.approx(0.4)
    assert narrative.frames[1].actor_id == "a2"
    assert narrative.frames[1].actor_vector.trust_in_trajectory == pytest.approx(-0.6)


def test_replay_aggregate_sentiment_updates_per_step():
    events = [
        ("a1", ReactionEvent(topic="t", variable="trust_in_trajectory", delta=1.0)),
        ("a2", ReactionEvent(topic="t", variable="trust_in_trajectory", delta=1.0)),
    ]
    narrative = replay_reactions(events)
    sentiments = [f.aggregate_sentiment for f in narrative.frames]
    assert all(s is not None for s in sentiments)
    assert sentiments[1] >= sentiments[0]
    assert narrative.final_sentiment is not None


def test_replay_empty_input_yields_empty_narrative():
    narrative = replay_reactions([])
    assert narrative.frames == ()
    assert narrative.final_sentiment is None


def test_replay_frame_carries_event_metadata():
    occurred = datetime(2026, 5, 1, 10, 0, tzinfo=UTC)
    events = [
        (
            "a1",
            ReactionEvent(
                topic="news",
                variable="trust_in_trajectory",
                delta=0.2,
                narrative="transit announced",
                metadata={"source": "city_council"},
                occurred_at=occurred,
            ),
        )
    ]
    narrative = replay_reactions(events)
    frame = narrative.frames[0]
    assert isinstance(frame, ReplayFrame)
    assert frame.occurred_at == occurred
    assert frame.metadata == {"source": "city_council"}
    assert frame.event_delta == pytest.approx(0.2)
