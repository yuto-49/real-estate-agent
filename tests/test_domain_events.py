"""Phase A: canonical event taxonomy tests (lenient registry mode)."""

from __future__ import annotations

import logging

import pytest

from domain.events import (
    ACTOR_EVENTS,
    DECISION_EVENTS,
    EventNamespace,
    MARKET_EVENTS,
    OUTCOME_EVENTS,
    REACTION_EVENTS,
    canonical_event,
    is_known_event,
    namespace_of,
)


def test_namespaces_are_disjoint():
    all_buckets = [MARKET_EVENTS, ACTOR_EVENTS, REACTION_EVENTS, DECISION_EVENTS, OUTCOME_EVENTS]
    for i, a in enumerate(all_buckets):
        for b in all_buckets[i + 1 :]:
            assert a.isdisjoint(b), f"event names duplicated across namespaces: {a & b}"


def test_canonical_event_returns_registered_name():
    assert canonical_event(EventNamespace.MARKET, "property.listed") == "property.listed"


def test_canonical_event_accepts_string_namespace():
    assert canonical_event("decision", "offer.created") == "offer.created"


def test_canonical_event_unknown_name_warns_but_passes_through(caplog):
    with caplog.at_level(logging.WARNING, logger="domain.events"):
        result = canonical_event(EventNamespace.MARKET, "property.teleported")
    assert result == "property.teleported"
    assert any("Unregistered market event" in record.message for record in caplog.records)


def test_canonical_event_rejects_unknown_namespace():
    with pytest.raises(ValueError):
        canonical_event("noosphere", "property.listed")


def test_is_known_event():
    assert is_known_event("property.listed")
    assert is_known_event("offer.accepted")
    assert is_known_event("round.started")
    assert not is_known_event("totally.fake")


def test_namespace_of_routes_correctly():
    assert namespace_of("property.listed") is EventNamespace.MARKET
    assert namespace_of("household.created") is EventNamespace.ACTOR
    assert namespace_of("round.started") is EventNamespace.REACTION
    assert namespace_of("offer.created") is EventNamespace.DECISION
    assert namespace_of("deal.closed") is EventNamespace.OUTCOME
    assert namespace_of("nonsense.event") is None


def test_existing_inline_event_strings_are_registered():
    """Events already emitted from agent/orchestrator and tools should be in the registry."""
    inline_events = {
        "property.listed",
        "property.price_updated",
        "offer.created",
        "offer.accepted",
        "negotiation.started",
        "negotiation.mediated",
        "contract.generated",
        "inspection.scheduled",
    }
    for ev in inline_events:
        assert is_known_event(ev), f"existing emit-site uses unregistered event {ev!r}"
