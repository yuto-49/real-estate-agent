"""Phase D: reaction engine tests."""

from __future__ import annotations

import logging

import pytest

from domain.reactions import (
    ConvergenceReport,
    NarrativeCluster,
    ReactionEngine,
    ReactionEvent,
    ReactionVector,
    extract_narratives,
    vector_distance,
)


def _event(variable: str, delta: float, *, topic: str = "rent_shock", narrative: str = "") -> ReactionEvent:
    return ReactionEvent(topic=topic, variable=variable, delta=delta, narrative=narrative)


def test_apply_updates_actor_vector():
    engine = ReactionEngine()
    updated = engine.apply("a1", _event("trust_in_trajectory", 0.3))
    assert isinstance(updated, ReactionVector)
    assert updated.trust_in_trajectory == pytest.approx(0.3)


def test_apply_clamps_to_unit_interval():
    engine = ReactionEngine()
    engine.apply("a1", _event("trust_in_trajectory", 0.9))
    engine.apply("a1", _event("trust_in_trajectory", 0.5))  # would push past 1.0
    assert engine.vector_for("a1").trust_in_trajectory == pytest.approx(1.0)

    engine.apply("a1", _event("trust_in_trajectory", -3.0))  # would push past -1.0
    assert engine.vector_for("a1").trust_in_trajectory == pytest.approx(-1.0)


def test_apply_unknown_variable_warns_and_drops(caplog):
    engine = ReactionEngine()
    with caplog.at_level(logging.WARNING, logger="domain.reactions.engine"):
        result = engine.apply("a1", _event("teleportation_score", 0.5))
    assert result == ReactionVector()
    assert any("Unknown reaction variable" in r.message for r in caplog.records)


def test_apply_batch_returns_final_vectors():
    engine = ReactionEngine()
    pairs = [
        ("a1", _event("affordability_pressure", 0.4)),
        ("a2", _event("affordability_pressure", 0.6)),
        ("a1", _event("perceived_safety", -0.2)),
    ]
    vectors = engine.apply_batch(pairs)
    assert vectors["a1"].affordability_pressure == pytest.approx(0.4)
    assert vectors["a1"].perceived_safety == pytest.approx(-0.2)
    assert vectors["a2"].affordability_pressure == pytest.approx(0.6)


def test_convergence_report_empty_engine_is_converged():
    engine = ReactionEngine()
    report = engine.convergence()
    assert isinstance(report, ConvergenceReport)
    assert report.aggregate_variance == 0.0
    assert report.is_converged is True


def test_convergence_detects_high_variance():
    engine = ReactionEngine()
    engine.apply("a1", _event("trust_in_trajectory", 1.0))
    engine.apply("a2", _event("trust_in_trajectory", -1.0))
    report = engine.convergence()
    assert report.is_converged is False
    assert report.per_variable_variance["trust_in_trajectory"] > 0.5


def test_convergence_detects_low_variance():
    engine = ReactionEngine(convergence_threshold=0.05)
    engine.apply("a1", _event("trust_in_trajectory", 0.5))
    engine.apply("a2", _event("trust_in_trajectory", 0.51))
    engine.apply("a3", _event("trust_in_trajectory", 0.49))
    report = engine.convergence()
    assert report.is_converged is True


def test_extract_narratives_groups_by_variable_and_direction():
    events = [
        _event("affordability_pressure", 0.4, narrative="rent up 20% in soma"),
        _event("affordability_pressure", 0.3, narrative="evictions rising"),
        _event("affordability_pressure", -0.1, narrative="new voucher pilot"),
        _event("trust_in_trajectory", 0.2, narrative="transit announced"),
    ]
    clusters = extract_narratives(events)
    assert len(clusters) == 3
    top = clusters[0]
    assert top.variable == "affordability_pressure"
    assert top.direction == "positive"
    assert top.event_count == 2
    assert top.total_delta == pytest.approx(0.7)
    assert "rent up 20% in soma" in top.sample_narratives


def test_extract_narratives_skips_zero_delta_and_unknown_variables(caplog):
    events = [
        _event("affordability_pressure", 0.0, narrative="no movement"),
        _event("teleportation_score", 0.5, narrative="???"),
        _event("perceived_safety", -0.3, narrative="crime spike"),
    ]
    with caplog.at_level(logging.WARNING, logger="domain.reactions.engine"):
        clusters = extract_narratives(events)
    assert len(clusters) == 1
    assert clusters[0].variable == "perceived_safety"
    assert clusters[0].direction == "negative"


def test_extract_narratives_returns_empty_for_no_events():
    assert extract_narratives([]) == []


def test_vector_distance_zero_for_identical():
    a = ReactionVector(trust_in_trajectory=0.5, perceived_safety=0.3)
    b = ReactionVector(trust_in_trajectory=0.5, perceived_safety=0.3)
    assert vector_distance(a, b) == pytest.approx(0.0)


def test_vector_distance_increases_with_difference():
    a = ReactionVector(trust_in_trajectory=0.0)
    b = ReactionVector(trust_in_trajectory=1.0)
    c = ReactionVector(trust_in_trajectory=0.5)
    assert vector_distance(a, b) > vector_distance(a, c)


def test_engine_vectors_property_returns_copy():
    engine = ReactionEngine()
    engine.apply("a1", _event("affordability_pressure", 0.5))
    snapshot = engine.vectors
    snapshot["a1"] = ReactionVector()  # mutate the copy
    # original engine state untouched
    assert engine.vector_for("a1").affordability_pressure == pytest.approx(0.5)
