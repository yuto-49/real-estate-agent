"""Phase F: outcome projection builder tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from domain.outcomes import (
    MarketOutcomeSnapshot,
    NegotiationOfferSnapshot,
    build_outcome_snapshot,
    project_concession_rate,
    project_neighborhood_sentiment,
    project_offer_behavior,
    project_permit_friction,
    project_price_movement,
    project_time_on_market,
)
from domain.reactions.models import ReactionVector


def _offer(price: float, *, status: str | None = None, oid: str = "o") -> NegotiationOfferSnapshot:
    return NegotiationOfferSnapshot(
        offer_id=oid,
        property_id="p1",
        buyer_id="b1",
        offer_price=price,
        status=status,
    )


# ---------- price movement ----------

def test_price_movement_none_for_short_history():
    assert project_price_movement([]) is None
    assert project_price_movement([_offer(500_000)]) is None


def test_price_movement_positive_when_offer_rises():
    pct = project_price_movement([_offer(500_000), _offer(525_000)])
    assert pct == pytest.approx(5.0)


def test_price_movement_negative_when_offer_falls():
    pct = project_price_movement([_offer(500_000), _offer(450_000)])
    assert pct == pytest.approx(-10.0)


def test_price_movement_handles_zero_first_price():
    assert project_price_movement([_offer(0), _offer(500_000)]) is None


# ---------- time on market ----------

def test_time_on_market_uses_now_when_active():
    listed = datetime.now(timezone.utc) - timedelta(days=10)
    days = project_time_on_market(listed)
    assert days == 10


def test_time_on_market_uses_close_date_when_provided():
    listed = datetime(2026, 1, 1, tzinfo=timezone.utc)
    closed = datetime(2026, 1, 15, tzinfo=timezone.utc)
    assert project_time_on_market(listed, closed_at=closed) == 14


def test_time_on_market_none_without_listed_at():
    assert project_time_on_market(None) is None


def test_time_on_market_handles_naive_datetimes():
    listed = datetime(2026, 1, 1)
    closed = datetime(2026, 1, 8)
    assert project_time_on_market(listed, closed_at=closed) == 7


# ---------- offer behavior ----------

def test_offer_behavior_empty_returns_zeros():
    behavior = project_offer_behavior([])
    assert behavior["offer_volume"] == 0
    assert behavior["acceptance_rate"] == 0.0


def test_offer_behavior_computes_status_rates():
    offers = [
        _offer(500_000, status="rejected", oid="o1"),
        _offer(510_000, status="rejected", oid="o2"),
        _offer(520_000, status="accepted", oid="o3"),
        _offer(515_000, status="withdrawn", oid="o4"),
    ]
    behavior = project_offer_behavior(offers)
    assert behavior["offer_volume"] == 4
    assert behavior["acceptance_rate"] == pytest.approx(0.25)
    assert behavior["rejection_rate"] == pytest.approx(0.5)
    assert behavior["withdrawal_rate"] == pytest.approx(0.25)


# ---------- concession rate ----------

def test_concession_rate_positive_when_offer_below_asking():
    rate = project_concession_rate(600_000, [_offer(540_000)])
    assert rate == pytest.approx(10.0)


def test_concession_rate_negative_when_offer_above_asking():
    rate = project_concession_rate(600_000, [_offer(660_000)])
    assert rate == pytest.approx(-10.0)


def test_concession_rate_none_without_inputs():
    assert project_concession_rate(None, [_offer(500_000)]) is None
    assert project_concession_rate(600_000, []) is None
    assert project_concession_rate(0, [_offer(500_000)]) is None


# ---------- permit friction ----------

def test_permit_friction_none_without_signal():
    assert project_permit_friction(ReactionVector()) is None


def test_permit_friction_high_under_strong_resistance():
    score = project_permit_friction(
        ReactionVector(resistance_to_development=0.9, displacement_concern=0.8)
    )
    assert score is not None
    assert score > 0.85


def test_permit_friction_blends_external_signal():
    score = project_permit_friction(
        ReactionVector(resistance_to_development=-0.5),
        permit_signal=0.9,
    )
    assert score is not None
    assert 0.5 < score < 0.9


def test_permit_friction_clamped_to_unit_interval():
    high = project_permit_friction(
        ReactionVector(resistance_to_development=1.0, displacement_concern=1.0),
        permit_signal=1.0,
    )
    low = project_permit_friction(
        ReactionVector(resistance_to_development=-1.0, displacement_concern=-1.0),
        permit_signal=0.0,
    )
    assert high == pytest.approx(1.0)
    assert low == pytest.approx(0.0)


# ---------- neighborhood sentiment ----------

def test_neighborhood_sentiment_none_for_empty_iterable():
    assert project_neighborhood_sentiment([]) is None


def test_neighborhood_sentiment_averages_components():
    score = project_neighborhood_sentiment(
        [
            ReactionVector(
                trust_in_trajectory=1.0,
                perceived_safety=1.0,
                displacement_concern=-1.0,
                willingness_to_transact=1.0,
            )
        ]
    )
    assert score == pytest.approx(1.0)


def test_neighborhood_sentiment_low_when_displacement_high():
    score = project_neighborhood_sentiment(
        [
            ReactionVector(
                trust_in_trajectory=-1.0,
                perceived_safety=-1.0,
                displacement_concern=1.0,
                willingness_to_transact=-1.0,
            )
        ]
    )
    assert score == pytest.approx(0.0)


def test_neighborhood_sentiment_averages_across_actors():
    high = ReactionVector(trust_in_trajectory=1.0, willingness_to_transact=1.0)
    low = ReactionVector(trust_in_trajectory=-1.0, willingness_to_transact=-1.0)
    score = project_neighborhood_sentiment([high, low])
    # Both around 0.5 mid-point — average should be near 0.5
    assert score is not None
    assert 0.4 < score < 0.6


# ---------- composition ----------

def test_build_outcome_snapshot_returns_complete_record():
    listed = datetime(2026, 1, 1, tzinfo=timezone.utc)
    closed = datetime(2026, 1, 30, tzinfo=timezone.utc)
    offers = [
        _offer(500_000, status="rejected", oid="o1"),
        _offer(540_000, status="accepted", oid="o2"),
    ]
    reactions = [
        ReactionVector(
            trust_in_trajectory=0.4,
            perceived_safety=0.3,
            willingness_to_transact=0.5,
            resistance_to_development=0.6,
        )
    ]

    snapshot = build_outcome_snapshot(
        listing_id="L1",
        asking_price=600_000,
        offers=offers,
        listed_at=listed,
        closed_at=closed,
        reactions=reactions,
        permit_signal=0.7,
        turnover_rate=0.05,
    )

    assert isinstance(snapshot, MarketOutcomeSnapshot)
    assert snapshot.listing_id == "L1"
    assert snapshot.price_change_pct == pytest.approx(8.0)
    assert snapshot.time_on_market_days == 29
    assert snapshot.offer_volume == 2
    assert snapshot.concession_rate == pytest.approx(10.0)
    assert snapshot.permit_friction is not None
    assert 0.0 <= snapshot.permit_friction <= 1.0
    assert snapshot.neighborhood_sentiment is not None
    assert snapshot.turnover_rate == pytest.approx(0.05)


def test_build_outcome_snapshot_handles_empty_inputs():
    snapshot = build_outcome_snapshot()
    assert snapshot.listing_id is None
    assert snapshot.price_change_pct is None
    assert snapshot.time_on_market_days is None
    assert snapshot.offer_volume == 0
    assert snapshot.concession_rate is None
    assert snapshot.permit_friction is None
    assert snapshot.neighborhood_sentiment is None
