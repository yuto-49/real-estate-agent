"""Data models for GNN-powered buyer simulation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class BuyerProfile:
    agent_id: int
    budget_yen: int  # max willingness to pay
    risk_tolerance: float  # [0,1]
    life_stage: str  # "first_time" | "upgrade" | "investor" | "retiree"
    construction_pref: tuple[str, ...]  # preferred construction types
    commute_target_lat: float
    commute_target_lng: float
    max_commute_minutes: int
    hazard_sensitivity: float  # [0,1]
    yield_target: float | None = None  # for investors: minimum cap rate


@dataclass(frozen=True, slots=True)
class PropertyFeatures:
    property_id: str
    latitude: float
    longitude: float
    feature_vector: tuple[float, ...]  # normalized [0,1], ~20 dims
    asking_price_yen: int
    raw_features: dict[str, Any] = field(default_factory=dict)  # un-normalized for display


@dataclass(frozen=True, slots=True)
class Transaction:
    property_id: str
    buyer_id: int
    price_yen: int
    round_num: int


@dataclass(frozen=True, slots=True)
class BidRecord:
    round_num: int
    buyer_id: int
    property_id: str
    bid_yen: int
    score: float  # raw attractiveness score [0,1]
    factors: dict[str, float] = field(default_factory=dict)  # breakdown


@dataclass(frozen=True, slots=True)
class RoundResult:
    round_num: int
    bids: tuple[BidRecord, ...]
    transactions: tuple[Transaction, ...]  # winning bids
    active_buyers: int
    active_properties: int
    median_bid_yen: int
    price_std_yen: int


@dataclass(frozen=True, slots=True)
class SegmentSummary:
    life_stage: str
    count: int
    avg_bid_yen: int
    median_bid_yen: int
    win_rate: float


@dataclass(frozen=True, slots=True)
class BidBucket:
    low_yen: int
    high_yen: int
    count: int


@dataclass(frozen=True, slots=True)
class BuyerSimConfig:
    max_rounds: int = 15
    n_buyers: int = 50
    convergence_threshold: float = 0.02
    gnn_hidden_dim: int = 32
    gnn_layers: int = 2
    learning_rate: float = 0.01
    seed: int | None = None


@dataclass(frozen=True, slots=True)
class BuyerSimResult:
    rounds: tuple[RoundResult, ...]
    converged: bool
    converged_at_round: int | None
    property_valuations: dict[str, int]  # property_id -> GNN valuation yen
    buyer_segments: tuple[SegmentSummary, ...]
    bid_histogram: tuple[BidBucket, ...]
    config: BuyerSimConfig


@dataclass(frozen=True, slots=True)
class BuyerSimReport:
    property_id: str
    gnn_valuation_yen: int
    gnn_confidence_low_yen: int
    gnn_confidence_high_yen: int
    satei_price_yen: int | None
    price_probability_sweet_spot_yen: int | None
    buyer_segments: tuple[SegmentSummary, ...]
    bid_histogram: tuple[BidBucket, ...]
    median_bid_yen: int
    mean_bid_yen: int
    hazard_impact_pct: float
    rounds_to_converge: int
    narrative_jp: str
