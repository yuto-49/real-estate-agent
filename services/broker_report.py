"""Broker report models — disclosure checklist and audit trail."""

from __future__ import annotations

from dataclasses import dataclass

from domain.simulation.models import SimResult


@dataclass(frozen=True, slots=True)
class BrokerDisclosureItem:
    """One item on the 宅建業法 disclosure checklist."""

    category: str  # "重要事項説明", "告知事項", "特約条件"
    item: str
    status: str  # "confirmed", "pending", "flagged"
    source: str
    note: str = ""


@dataclass(frozen=True, slots=True)
class BrokerReport:
    """Complete broker report for a listing-investor match."""

    listing_id: str
    investor_match_score: float
    sim_result: SimResult
    analyst_score: float | None
    disclosure_checklist: tuple[BrokerDisclosureItem, ...]
    ranked_recommendations: tuple[str, ...]
    audit_event_ids: tuple[str, ...]
    warnings: tuple[str, ...] = ()
