"""Phase E: decision runtime tests."""

from __future__ import annotations

import logging

import pytest

from domain.actors.profiles import ActorSignalState
from domain.decisions import (
    ChurnPolicy,
    DecisionContext,
    DecisionRecommendation,
    DecisionRuntime,
    DevResistancePolicy,
    LeasePolicy,
    ListHoldPolicy,
    NegotiationPolicy,
    default_policies,
)
from domain.market.models import MarketContextSnapshot
from domain.reactions.models import ReactionVector


def _ctx(**overrides) -> DecisionContext:
    market = overrides.pop("market", MarketContextSnapshot(property_id="p1"))
    reaction = overrides.pop("reaction", ReactionVector())
    actor = overrides.pop("actor", None)
    metadata = overrides.pop("metadata", {})
    return DecisionContext(
        market=market,
        reaction=reaction,
        actor=actor,
        metadata=metadata,
    )


# ---------- runtime ----------

def test_runtime_register_and_evaluate_returns_sorted_recommendations():
    class HighScore:
        kind = "high"

        def evaluate(self, context):
            return DecisionRecommendation(kind=self.kind, action="x", score=0.9)

    class LowScore:
        kind = "low"

        def evaluate(self, context):
            return DecisionRecommendation(kind=self.kind, action="y", score=0.1)

    runtime = DecisionRuntime([LowScore(), HighScore()])
    recs = runtime.evaluate(_ctx())
    assert [r.kind for r in recs] == ["high", "low"]


def test_runtime_skips_none_results():
    class Quiet:
        kind = "quiet"

        def evaluate(self, context):
            return None

    runtime = DecisionRuntime([Quiet()])
    assert runtime.evaluate(_ctx()) == []


def test_runtime_top_returns_best_or_none():
    class Single:
        kind = "single"

        def evaluate(self, context):
            return DecisionRecommendation(kind=self.kind, action="go", score=0.5)

    runtime = DecisionRuntime([Single()])
    top = runtime.top(_ctx())
    assert top is not None
    assert top.action == "go"

    empty = DecisionRuntime([])
    assert empty.top(_ctx()) is None


def test_runtime_register_rejects_invalid_policy():
    runtime = DecisionRuntime()
    with pytest.raises(TypeError):
        runtime.register(object())


def test_runtime_logs_warning_on_duplicate_kind(caplog):
    class Dup:
        kind = "dup"

        def evaluate(self, context):
            return None

    with caplog.at_level(logging.WARNING, logger="domain.decisions.runtime"):
        runtime = DecisionRuntime([Dup(), Dup()])
    assert any("Duplicate decision policy kind" in r.message for r in caplog.records)
    assert len(runtime.policies) == 2


def test_runtime_isolates_policy_exceptions(caplog):
    class Boom:
        kind = "boom"

        def evaluate(self, context):
            raise RuntimeError("kaboom")

    class Ok:
        kind = "ok"

        def evaluate(self, context):
            return DecisionRecommendation(kind=self.kind, action="ok", score=0.5)

    runtime = DecisionRuntime([Boom(), Ok()])
    with caplog.at_level(logging.WARNING, logger="domain.decisions.runtime"):
        recs = runtime.evaluate(_ctx())
    assert [r.kind for r in recs] == ["ok"]
    assert any("kaboom" in r.message for r in caplog.records)


# ---------- built-in policies ----------

def test_negotiation_policy_returns_none_without_offer_history():
    policy = NegotiationPolicy()
    assert policy.evaluate(_ctx()) is None


def test_negotiation_policy_recommends_counter_with_history():
    policy = NegotiationPolicy()
    rec = policy.evaluate(
        _ctx(
            metadata={
                "offer_prices": [500_000, 510_000],
                "negotiation_state": "offer_pending",
                "round_count": 2,
            }
        )
    )
    assert rec is not None
    assert rec.kind == "negotiation"
    assert rec.action in {"counter", "place_offer", "suggest_split", "escalate_to_broker"}
    assert "round=2" in rec.rationale


def test_negotiation_policy_escalates_on_wide_spread():
    policy = NegotiationPolicy()
    rec = policy.evaluate(
        _ctx(
            metadata={
                "offer_prices": [500_000, 600_000],
                "negotiation_state": "counter_pending",
                "round_count": 6,
            }
        )
    )
    assert rec is not None
    assert rec.action == "escalate_to_broker"
    assert rec.score >= 0.9


def test_list_hold_policy_picks_list_when_low_inventory_high_optimism():
    policy = ListHoldPolicy()
    rec = policy.evaluate(
        _ctx(
            market=MarketContextSnapshot(property_id="p1", inventory_pressure=0.1),
            reaction=ReactionVector(investor_optimism=0.8),
        )
    )
    assert rec is not None
    assert rec.action == "list"


def test_list_hold_policy_picks_hold_when_high_inventory_high_displacement():
    policy = ListHoldPolicy()
    rec = policy.evaluate(
        _ctx(
            market=MarketContextSnapshot(property_id="p1", inventory_pressure=0.9),
            reaction=ReactionVector(displacement_concern=0.8),
        )
    )
    assert rec is not None
    assert rec.action == "hold"


def test_list_hold_policy_returns_none_without_inventory_signal():
    policy = ListHoldPolicy()
    assert policy.evaluate(_ctx()) is None


def test_lease_policy_freezes_rent_when_affordability_pressure_high():
    policy = LeasePolicy()
    rec = policy.evaluate(
        _ctx(
            market=MarketContextSnapshot(property_id="p1", median_rent=2400.0),
            reaction=ReactionVector(affordability_pressure=0.8),
        )
    )
    assert rec is not None
    assert rec.action == "freeze_rent"
    assert rec.score > 0.7


def test_lease_policy_raises_when_willingness_high_affordability_low():
    policy = LeasePolicy()
    rec = policy.evaluate(
        _ctx(
            market=MarketContextSnapshot(property_id="p1", median_rent=2400.0),
            reaction=ReactionVector(
                willingness_to_transact=0.7,
                affordability_pressure=-0.5,
            ),
        )
    )
    assert rec is not None
    assert rec.action == "raise_rent"


def test_lease_policy_returns_none_without_market_rent():
    policy = LeasePolicy()
    assert policy.evaluate(_ctx()) is None


def test_churn_policy_returns_none_for_neutral_signal():
    policy = ChurnPolicy()
    assert policy.evaluate(_ctx()) is None


def test_churn_policy_flags_intervene_under_high_displacement():
    policy = ChurnPolicy()
    rec = policy.evaluate(
        _ctx(reaction=ReactionVector(displacement_concern=0.8, perceived_safety=-0.5))
    )
    assert rec is not None
    assert rec.action == "intervene"
    assert rec.score > 0.6


def test_dev_resistance_policy_expects_pushback_under_high_resistance():
    policy = DevResistancePolicy()
    rec = policy.evaluate(
        _ctx(
            market=MarketContextSnapshot(property_id="p1", zoning_code="R-1"),
            reaction=ReactionVector(
                resistance_to_development=0.8,
                displacement_concern=0.6,
            ),
        )
    )
    assert rec is not None
    assert rec.action == "expect_pushback"
    assert "zoning=R-1" in rec.rationale


# ---------- default bundle ----------

def test_default_policies_bundle_runs_clean():
    runtime = DecisionRuntime(default_policies())
    context = DecisionContext(
        market=MarketContextSnapshot(
            property_id="p1",
            inventory_pressure=0.3,
            median_rent=2400.0,
            zoning_code="R-2",
        ),
        reaction=ReactionVector(
            investor_optimism=0.5,
            affordability_pressure=0.4,
            displacement_concern=0.3,
            resistance_to_development=0.6,
            willingness_to_transact=0.2,
        ),
        actor=ActorSignalState(),
        metadata={
            "offer_prices": [500_000, 520_000],
            "negotiation_state": "offer_pending",
            "round_count": 3,
        },
    )
    recs = runtime.evaluate(context)
    kinds = {r.kind for r in recs}
    assert {"negotiation", "list_hold", "lease", "dev_resistance"}.issubset(kinds)
    # All scores must be in [0, 1]
    assert all(0.0 <= r.score <= 1.0 for r in recs)
    # Output must be sorted descending by score
    assert recs == sorted(recs, key=lambda r: r.score, reverse=True)
