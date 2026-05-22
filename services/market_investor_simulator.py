"""Deterministic market-wide investor simulation engine."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from statistics import median
from typing import Any
import re

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import (
    MarketInvestorPersona,
    MarketSimulationPersonaRequest,
    MarketSimulationScope,
    MarketSimulationStartRequest,
)
from db.database import async_session
from db.models import (
    HouseholdProfile,
    MarketSimulationDecision,
    MarketSimulationInvestor,
    MarketSimulationPropertyState,
    MarketSimulationRun,
    Property,
    PropertyStatus,
)
from services.logging import get_logger
from services.market_state import build_snapshot
from services.persona_generator import InvestorPersona, fallback_market_personas, generate_market_investor_personas

logger = get_logger(__name__)

ACTIONS = ("watch", "enter", "raise_bid", "hold", "exit", "acquire", "skip")

_ARCHETYPE_WEIGHTS: dict[str, dict[str, float]] = {
    "value": {
        "valuation_gap": 0.42,
        "yield_proxy": 0.18,
        "neighborhood_quality": 0.18,
        "risk_penalty": 0.15,
        "peer_momentum": 0.07,
    },
    "yield": {
        "valuation_gap": 0.18,
        "yield_proxy": 0.42,
        "neighborhood_quality": 0.14,
        "risk_penalty": 0.18,
        "peer_momentum": 0.08,
    },
    "momentum": {
        "valuation_gap": 0.18,
        "yield_proxy": 0.12,
        "neighborhood_quality": 0.20,
        "risk_penalty": 0.10,
        "peer_momentum": 0.40,
    },
    "contrarian": {
        "valuation_gap": 0.38,
        "yield_proxy": 0.14,
        "neighborhood_quality": 0.15,
        "risk_penalty": 0.20,
        "peer_momentum": -0.12,
    },
}

_PRESET_ARCHETYPES: dict[str, tuple[str, ...]] = {
    "balanced": ("value", "yield", "momentum", "contrarian"),
    "income": ("yield", "yield", "value", "contrarian"),
    "momentum": ("momentum", "momentum", "value", "yield"),
}

_ARC_PROFILE: dict[str, dict[str, Any]] = {
    "value": {
        "horizon": 8,
        "risk": 0.38,
        "diversification": 2,
        "types": ["condo", "sfr", "multifamily"],
    },
    "yield": {
        "horizon": 10,
        "risk": 0.44,
        "diversification": 3,
        "types": ["multifamily", "duplex", "triplex", "condo"],
    },
    "momentum": {
        "horizon": 5,
        "risk": 0.72,
        "diversification": 2,
        "types": ["condo", "sfr", "multifamily"],
    },
    "contrarian": {
        "horizon": 7,
        "risk": 0.48,
        "diversification": 2,
        "types": ["sfr", "condo", "multifamily"],
    },
}


@dataclass(slots=True)
class CandidateScore:
    property_row: Property
    total_score: float
    signal_scores: dict[str, float]
    peer_inputs: dict[str, float]
    risk_penalty: float
    reservation_threshold: float


@dataclass(slots=True)
class RuntimePropertyState:
    property_id: str
    reservation_threshold: float
    current_top_bid: float | None = None
    winning_investor_id: str | None = None
    status: str = "active"
    previous_attention_count: int = 0
    recent_attention: float = 0.0
    previous_top_bid: float | None = None
    last_bid_velocity: float = 0.0
    local_competition: float = 0.0
    winning_tick: int | None = None
    signal_snapshot: dict[str, float] | None = None


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


async def _scoped_properties(
    db: AsyncSession,
    scope: MarketSimulationScope,
) -> list[Property]:
    query = select(Property)
    if scope.include_pending:
        query = query.where(Property.status.in_([PropertyStatus.ACTIVE, PropertyStatus.PENDING]))
    else:
        query = query.where(Property.status == PropertyStatus.ACTIVE)
    if scope.property_ids:
        query = query.where(Property.id.in_(scope.property_ids))
    if scope.min_price is not None:
        query = query.where(Property.asking_price >= scope.min_price)
    if scope.max_price is not None:
        query = query.where(Property.asking_price <= scope.max_price)
    if scope.property_types:
        query = query.where(Property.property_type.in_(scope.property_types))

    result = await db.execute(query.order_by(Property.listed_at.desc()))
    properties = list(result.scalars().all())
    if scope.zip_codes:
        zip_set = set(scope.zip_codes)
        properties = [
            prop
            for prop in properties
            if str((prop.neighborhood_data or {}).get("zip_code", "")) in zip_set
        ]
    return properties


async def _household_sentiment_by_zip(db: AsyncSession) -> dict[str, float]:
    result = await db.execute(
        select(HouseholdProfile.zip_code, func.avg(HouseholdProfile.housing_market_sentiment))
        .group_by(HouseholdProfile.zip_code)
    )
    return {
        str(zip_code): float(avg_sentiment)
        for zip_code, avg_sentiment in result.all()
        if zip_code is not None and avg_sentiment is not None
    }


def _seed_budget(price_points: list[float], index: int, count: int, archetype: str) -> float:
    anchors = price_points or [400_000.0]
    anchor_index = min(len(anchors) - 1, int((index / max(count - 1, 1)) * (len(anchors) - 1)))
    anchor = anchors[anchor_index]
    multiplier_cycle = {
        "value": (0.92, 1.0, 1.06),
        "yield": (0.98, 1.08, 1.16),
        "momentum": (1.02, 1.15, 1.28),
        "contrarian": (0.94, 1.02, 1.10),
    }
    multiplier = multiplier_cycle[archetype][index % len(multiplier_cycle[archetype])]
    return round(anchor * multiplier, 2)


def _archetype_cycle(count: int, preset: str) -> list[str]:
    cycle = _PRESET_ARCHETYPES.get(preset, _PRESET_ARCHETYPES["balanced"])
    return [cycle[index % len(cycle)] for index in range(count)]


def _inventory_summary(properties: list[Property]) -> dict[str, Any]:
    prices = sorted(float(prop.asking_price or 0.0) for prop in properties if prop.asking_price)
    zip_codes = sorted({str((prop.neighborhood_data or {}).get("zip_code") or "") for prop in properties if (prop.neighborhood_data or {}).get("zip_code")})
    property_types = sorted({str(prop.property_type) for prop in properties if prop.property_type})
    return {
        "property_count": len(properties),
        "zip_codes": zip_codes[:6],
        "property_types": property_types,
        "price_range": {
            "min": prices[0] if prices else None,
            "median": median(prices) if prices else None,
            "max": prices[-1] if prices else None,
        },
        "sample_properties": [
            {
                "address": prop.address,
                "asking_price": float(prop.asking_price or 0.0),
                "property_type": prop.property_type,
                "zip_code": (prop.neighborhood_data or {}).get("zip_code"),
            }
            for prop in properties[:6]
        ],
    }


async def preview_market_personas(
    db: AsyncSession,
    request: MarketSimulationPersonaRequest,
) -> dict[str, Any]:
    properties = await _scoped_properties(db, request.scope)
    if not properties:
        raise ValueError("No properties matched the requested simulation scope")

    inventory_summary = _inventory_summary(properties)
    archetypes = _archetype_cycle(request.investor_count, request.cohort_preset)
    price_points = sorted(float(prop.asking_price or 0.0) for prop in properties if prop.asking_price)
    budgets = [
        _seed_budget(price_points, index, request.investor_count, archetype)
        for index, archetype in enumerate(archetypes)
    ]
    personas = await generate_market_investor_personas(archetypes, budgets, inventory_summary)
    return {
        "property_count": len(properties),
        "personas": [persona.to_dict() for persona in personas],
        "inventory_summary": inventory_summary,
    }


def _parse_horizon_ticks(value: str, default: int) -> int:
    matches = [int(match) for match in re.findall(r"\d+", value or "")]
    if not matches:
        return default
    if len(matches) == 1:
        return matches[0]
    return round(sum(matches[:2]) / 2)


def _persona_from_seed(seed: MarketInvestorPersona | dict[str, Any]) -> InvestorPersona:
    payload = seed.model_dump() if hasattr(seed, "model_dump") else dict(seed)
    return InvestorPersona(**payload)


def _adjust_signal_weights(base_weights: dict[str, float], persona: InvestorPersona) -> dict[str, float]:
    weights = dict(base_weights)
    risk_posture = persona.risk_posture.lower()
    competition_style = persona.competition_style.lower()
    exit_style = persona.exit_style.lower()
    target_yield = persona.target_yield.lower()

    if any(keyword in risk_posture for keyword in ("assertive", "high", "aggressive")):
        weights["peer_momentum"] = weights.get("peer_momentum", 0.0) + 0.05
        weights["risk_penalty"] = max(0.04, weights.get("risk_penalty", 0.0) - 0.03)
    elif any(keyword in risk_posture for keyword in ("disciplined", "measured", "low")):
        weights["risk_penalty"] = weights.get("risk_penalty", 0.0) + 0.04
        weights["peer_momentum"] = weights.get("peer_momentum", 0.0) - 0.02

    if "yield" in target_yield or "income" in risk_posture:
        weights["yield_proxy"] = weights.get("yield_proxy", 0.0) + 0.04
    if any(keyword in target_yield for keyword in ("appreciation", "momentum")):
        weights["peer_momentum"] = weights.get("peer_momentum", 0.0) + 0.03
        weights["valuation_gap"] = weights.get("valuation_gap", 0.0) - 0.02

    if "aggressive" in competition_style:
        weights["peer_momentum"] = weights.get("peer_momentum", 0.0) + 0.05
    elif any(keyword in competition_style for keyword in ("avoid", "patient", "selective")):
        weights["peer_momentum"] = weights.get("peer_momentum", 0.0) - 0.04
        weights["valuation_gap"] = weights.get("valuation_gap", 0.0) + 0.02

    if any(keyword in exit_style for keyword in ("yield", "income")):
        weights["yield_proxy"] = weights.get("yield_proxy", 0.0) + 0.02

    total_abs = sum(abs(value) for value in weights.values()) or 1.0
    return {key: round(value / total_abs, 4) for key, value in weights.items()}


def _persona_budget(seed_budget: float, persona: InvestorPersona) -> float:
    budget = float(persona.budget or 0.0)
    return round(budget if budget > 0 else seed_budget, 2)


async def initialize_market_simulation_run(
    db: AsyncSession,
    request: MarketSimulationStartRequest,
) -> MarketSimulationRun:
    properties = await _scoped_properties(db, request.scope)
    if not properties:
        raise ValueError("No properties matched the requested simulation scope")

    run = MarketSimulationRun(
        run_label=request.run_label,
        status="pending",
        property_scope=request.scope.model_dump(),
        cohort_preset=request.cohort_preset,
        investor_count=request.investor_count,
        property_count=len(properties),
        total_ticks=request.tick_count,
        current_tick=0,
    )
    db.add(run)
    await db.flush()

    price_points = sorted(float(prop.asking_price or 0) for prop in properties if prop.asking_price)
    inventory_summary = _inventory_summary(properties)
    archetypes = _archetype_cycle(request.investor_count, request.cohort_preset)
    fallback_personas = fallback_market_personas(
        archetypes,
        [
            _seed_budget(price_points, index, request.investor_count, archetype)
            for index, archetype in enumerate(archetypes)
        ],
        inventory_summary,
    )
    seeded_personas = [_persona_from_seed(persona) for persona in request.seeded_personas]

    rows: list[MarketSimulationInvestor] = []
    for idx in range(request.investor_count):
        default_archetype = archetypes[idx]
        default_profile = _ARC_PROFILE[default_archetype]
        default_budget = _seed_budget(price_points, idx, request.investor_count, default_archetype)
        persona = seeded_personas[idx] if idx < len(seeded_personas) else fallback_personas[idx]
        archetype = persona.archetype or default_archetype
        profile = _ARC_PROFILE.get(archetype, default_profile)
        budget = _persona_budget(default_budget, persona)
        signal_weights = _adjust_signal_weights(dict(_ARCHETYPE_WEIGHTS.get(archetype, _ARCHETYPE_WEIGHTS[default_archetype])), persona)

        rows.append(
            MarketSimulationInvestor(
                run_id=run.id,
                investor_name=persona.display_name,
                archetype=archetype,
                budget=budget,
                cash_remaining=budget,
                hold_horizon_ticks=_parse_horizon_ticks(persona.hold_horizon, int(profile["horizon"])),
                risk_appetite=float(profile["risk"]),
                diversification_cap=int(profile["diversification"]),
                preferred_property_types=list(persona.preferred_property_types or profile["types"]),
                signal_weights=signal_weights,
                persona_profile=persona.to_dict(),
                holdings=[],
                metadata_json={"focus_property_id": None, "last_action": "skip"},
            )
        )

    db.add_all(rows)
    await db.commit()
    await db.refresh(run)
    return run


def _valuation_gap(property_row: Property, median_sale_price: float | None) -> float:
    asking = float(property_row.asking_price or 0)
    if asking <= 0:
        return 0.5
    if median_sale_price:
        ratio = (median_sale_price - asking) / asking
        return round(_clamp(0.5 + (ratio * 2.5)), 4)
    market_heat = float((property_row.neighborhood_data or {}).get("market_heat", 0.0) or 0.0)
    return round(_clamp(0.5 + (market_heat * 0.2)), 4)


def _yield_proxy(property_row: Property, median_rent: float | None) -> float:
    asking = float(property_row.asking_price or 0)
    if asking <= 0:
        return 0.45
    if median_rent:
        gross_yield = (median_rent * 12) / asking
        return round(_clamp(gross_yield / 0.12), 4)
    base = 0.58 if property_row.property_type in {"multifamily", "duplex", "triplex"} else 0.44
    hoa_penalty = _clamp(float(property_row.hoa_fees or 0) / 1000.0, 0.0, 0.2)
    return round(_clamp(base - hoa_penalty), 4)


def _neighborhood_quality(
    property_row: Property,
    *,
    transit_score: float | None,
    school_score: float | None,
    safety_score: float | None,
    household_sentiment: float | None,
) -> float:
    normalized_parts: list[float] = []
    for metric in (transit_score, school_score, safety_score):
        if metric is not None:
            normalized_parts.append(_clamp(metric / 100.0))
    if household_sentiment is not None:
        normalized_parts.append(_clamp((household_sentiment + 1.0) / 2.0))
    market_heat = float((property_row.neighborhood_data or {}).get("market_heat", 0.0) or 0.0)
    normalized_parts.append(_clamp(0.5 + market_heat * 0.25))
    return round(sum(normalized_parts) / len(normalized_parts), 4)


def _risk_penalty(
    property_row: Property,
    *,
    safety_score: float | None,
    inventory_pressure: float | None,
    hazard_flags: dict[str, Any],
) -> float:
    nd = dict(property_row.neighborhood_data or {})
    disclosures = dict(property_row.disclosures or {})
    risk_score = float(nd.get("risk_score", 0.22) or 0.22)
    known_defects = disclosures.get("known_defects") or []
    defect_penalty = min(len(known_defects) * 0.08, 0.24)
    flood_zone = str(disclosures.get("flood_zone") or hazard_flags.get("flood_zone") or "").upper()
    flood_penalty = 0.18 if flood_zone and flood_zone != "X" else 0.04
    hazard_penalty = 0.12 if hazard_flags else 0.0
    safety_penalty = 0.0 if safety_score is None else _clamp((65 - safety_score) / 65.0, 0.0, 0.25)
    inventory_penalty = 0.0 if inventory_pressure is None else _clamp(inventory_pressure * 0.22, 0.0, 0.2)
    return round(_clamp(risk_score + defect_penalty + flood_penalty + hazard_penalty + safety_penalty + inventory_penalty), 4)


def _peer_momentum(previous_state: RuntimePropertyState, asking_price: float) -> tuple[float, dict[str, float]]:
    price_scale = max(asking_price * 0.03, 1.0)
    peer_inputs = {
        "investor_count": float(previous_state.previous_attention_count),
        "bid_velocity": float(previous_state.last_bid_velocity),
        "local_competition": float(previous_state.local_competition),
        "recent_attention": float(previous_state.recent_attention),
    }
    normalized = round(
        _clamp(
            (peer_inputs["investor_count"] / 5.0) * 0.35
            + (abs(peer_inputs["bid_velocity"]) / price_scale) * 0.30
            + (peer_inputs["local_competition"] / 4.0) * 0.20
            + (peer_inputs["recent_attention"] / 6.0) * 0.15
        ),
        4,
    )
    return normalized, peer_inputs


def _reservation_threshold(property_row: Property, candidate_risk: float, inventory_pressure: float | None) -> float:
    market_heat = float((property_row.neighborhood_data or {}).get("market_heat", 0.0) or 0.0)
    urgency = float((property_row.disclosures or {}).get("seller_urgency", 0.2) or 0.2)
    inventory_delta = 0.0 if inventory_pressure is None else _clamp((0.5 - inventory_pressure) * 0.08, -0.03, 0.04)
    risk_discount = candidate_risk * 0.07
    heat_lift = market_heat * 0.03
    urgency_discount = urgency * 0.04
    multiplier = _clamp(0.95 + heat_lift + inventory_delta - risk_discount - urgency_discount, 0.84, 1.02)
    return round(float(property_row.asking_price or 0) * multiplier, 2)


def _score_property(
    investor: MarketSimulationInvestor,
    property_row: Property,
    previous_state: RuntimePropertyState,
    signal_snapshot: dict[str, Any],
    household_sentiment: float | None,
) -> CandidateScore:
    valuation = _valuation_gap(property_row, signal_snapshot.get("median_sale_price"))
    yield_score = _yield_proxy(property_row, signal_snapshot.get("median_rent"))
    neighborhood = _neighborhood_quality(
        property_row,
        transit_score=signal_snapshot.get("transit_score"),
        school_score=signal_snapshot.get("school_score"),
        safety_score=signal_snapshot.get("safety_score"),
        household_sentiment=household_sentiment,
    )
    risk = _risk_penalty(
        property_row,
        safety_score=signal_snapshot.get("safety_score"),
        inventory_pressure=signal_snapshot.get("inventory_pressure"),
        hazard_flags=dict(signal_snapshot.get("hazard_flags") or {}),
    )
    peer_momentum, peer_inputs = _peer_momentum(previous_state, float(property_row.asking_price or 0))
    reservation = _reservation_threshold(
        property_row,
        risk,
        signal_snapshot.get("inventory_pressure"),
    )

    weights = dict(investor.signal_weights or _ARCHETYPE_WEIGHTS[investor.archetype])
    total = (
        valuation * weights.get("valuation_gap", 0.0)
        + yield_score * weights.get("yield_proxy", 0.0)
        + neighborhood * weights.get("neighborhood_quality", 0.0)
        + peer_momentum * weights.get("peer_momentum", 0.0)
        - risk * weights.get("risk_penalty", 0.0)
    )

    preferred_types = list(investor.preferred_property_types or [])
    if preferred_types and property_row.property_type and property_row.property_type in preferred_types:
        total += 0.05

    total += 0.02 if (property_row.asking_price or 0) <= (investor.cash_remaining or 0) * 0.95 else -0.08

    signal_scores = {
        "valuation_gap": round(valuation, 4),
        "yield_proxy": round(yield_score, 4),
        "neighborhood_quality": round(neighborhood, 4),
        "risk_penalty": round(risk, 4),
        "peer_momentum": round(peer_momentum, 4),
    }

    return CandidateScore(
        property_row=property_row,
        total_score=round(total, 4),
        signal_scores=signal_scores,
        peer_inputs=peer_inputs,
        risk_penalty=risk,
        reservation_threshold=reservation,
    )


def _proposed_bid(
    investor: MarketSimulationInvestor,
    candidate: CandidateScore,
    previous_state: RuntimePropertyState,
) -> float:
    asking = float(candidate.property_row.asking_price or 0)
    budget = float(investor.cash_remaining or 0)
    base = previous_state.current_top_bid or asking * 0.92
    uplift = asking * (0.012 + (candidate.total_score * 0.012))
    if investor.archetype == "momentum":
        uplift += asking * 0.015
    if investor.archetype == "contrarian":
        uplift -= asking * 0.004
    bid = min(base + uplift, budget)
    return round(max(0.0, bid), 2)


def _choose_action(
    investor: MarketSimulationInvestor,
    shortlist: list[CandidateScore],
    previous_states: dict[str, RuntimePropertyState],
    focus_property_id: str | None,
) -> tuple[str, CandidateScore | None, float | None, str, list[dict[str, Any]]]:
    holdings = list(investor.holdings or [])
    if len(holdings) >= int(investor.diversification_cap or 0):
        reason = "Diversification cap reached, so the investor holds existing positions."
        return "hold", None, None, reason, []

    if not shortlist:
        return "skip", None, None, "No active properties met the affordability or scope filters.", []

    best = shortlist[0]
    rejected = [
        {
            "property_id": item.property_row.id,
            "address": item.property_row.address,
            "score": item.total_score,
            "action_bias": "watch" if item.total_score >= 0.28 else "skip",
            "reason": "The chosen property held the stronger blended conviction score after fit and risk adjustments.",
        }
        for item in shortlist[1:3]
    ]

    if float(investor.cash_remaining or 0) < float(best.property_row.asking_price or 0) * 0.82:
        return (
            "watch",
            best,
            None,
            "The property is interesting, but the investor is still capital constrained this tick.",
            rejected,
        )

    if best.total_score < 0.18:
        return (
            "skip",
            best,
            None,
            "The blended signal score stayed below the investor's entry threshold.",
            rejected,
        )

    previous_state = previous_states[best.property_row.id]
    if focus_property_id and focus_property_id == best.property_row.id:
        if best.total_score < 0.2:
            return (
                "exit",
                best,
                None,
                "Signals cooled relative to the prior tick, so the investor exits the watchlist.",
                rejected,
            )
        proposed_bid = _proposed_bid(investor, best, previous_state)
        action = "raise_bid" if previous_state.current_top_bid else "enter"
        reason = "The investor stays on the same asset and improves position as conviction remains intact."
        return action, best, proposed_bid, reason, rejected

    if best.total_score >= 0.54:
        proposed_bid = _proposed_bid(investor, best, previous_state)
        return (
            "enter",
            best,
            proposed_bid,
            "The combined valuation, yield, and local momentum cleared the investor's entry bar.",
            rejected,
        )

    return (
        "watch",
        best,
        None,
        "The investor prefers to watch one more tick before committing capital.",
        rejected,
    )


async def _property_snapshots(
    db: AsyncSession,
    properties: list[Property],
    zip_sentiment: dict[str, float],
) -> tuple[dict[str, dict[str, Any]], dict[str, float | None]]:
    snapshots: dict[str, dict[str, Any]] = {}
    sentiments: dict[str, float | None] = {}
    for property_row in properties:
        snapshot = await build_snapshot(db, property_id=property_row.id)
        neighborhood_data = dict(property_row.neighborhood_data or {})
        disclosures = dict(property_row.disclosures or {})
        hazard_flags = dict(getattr(snapshot, "hazard_flags", {}) or {}) if snapshot else {}
        zip_code = str(neighborhood_data.get("zip_code") or (snapshot.zip_code if snapshot else "") or "")
        snapshots[property_row.id] = {
            "median_sale_price": snapshot.median_sale_price if snapshot else None,
            "median_rent": snapshot.median_rent if snapshot else None,
            "transit_score": snapshot.transit_score if snapshot else None,
            "school_score": snapshot.school_score if snapshot else None,
            "safety_score": snapshot.safety_score if snapshot else None,
            "inventory_pressure": snapshot.inventory_pressure if snapshot else None,
            "hazard_flags": hazard_flags,
            "market_heat": neighborhood_data.get("market_heat"),
            "risk_score": neighborhood_data.get("risk_score"),
            "known_defects": disclosures.get("known_defects") or [],
        }
        sentiments[property_row.id] = zip_sentiment.get(zip_code)
    return snapshots, sentiments


def _persona_summary(investor: MarketSimulationInvestor) -> dict[str, Any]:
    persona = dict(investor.persona_profile or {})
    return {
        "display_name": persona.get("display_name") or investor.investor_name,
        "investment_thesis": persona.get("investment_thesis") or "",
        "competition_style": persona.get("competition_style") or "",
        "exit_style": persona.get("exit_style") or "",
        "risk_posture": persona.get("risk_posture") or "",
    }


def _budget_position(
    investor: MarketSimulationInvestor,
    property_row: Property,
    bid_amount: float | None,
) -> dict[str, Any]:
    cash_remaining = float(investor.cash_remaining or 0.0)
    asking_price = float(property_row.asking_price or 0.0)
    proposed_bid = float(bid_amount or 0.0)
    headroom = round(cash_remaining - asking_price, 2)
    return {
        "cash_remaining": round(cash_remaining, 2),
        "asking_price": round(asking_price, 2),
        "proposed_bid": round(proposed_bid, 2) if bid_amount is not None else None,
        "headroom": headroom,
        "headroom_ratio": round(headroom / max(asking_price, 1.0), 4),
        "is_affordable": cash_remaining >= asking_price * 0.95,
    }


def _property_match_factors(
    investor: MarketSimulationInvestor,
    candidate: CandidateScore | None,
) -> list[str]:
    if candidate is None:
        return []

    property_row = candidate.property_row
    factors: list[str] = []
    persona = dict(investor.persona_profile or {})
    preferred_types = list(investor.preferred_property_types or [])
    if property_row.property_type and property_row.property_type in preferred_types:
        factors.append(f"Matches preferred property type: {property_row.property_type}.")

    preferred_band = str(persona.get("preferred_price_band") or "")
    if preferred_band:
        factors.append(f"Fits the persona's preferred price band ({preferred_band}).")

    if candidate.signal_scores["valuation_gap"] >= 0.6:
        factors.append("Local sale-price signals suggest the listing is attractively priced.")
    if candidate.signal_scores["yield_proxy"] >= 0.6:
        factors.append("The yield proxy supports the investor's return target.")
    if candidate.signal_scores["neighborhood_quality"] >= 0.58:
        factors.append("Neighborhood quality signals stayed supportive this tick.")
    if candidate.signal_scores["peer_momentum"] >= 0.45:
        factors.append("Peer attention increased enough to reinforce conviction.")
    if candidate.signal_scores["risk_penalty"] >= 0.35:
        factors.append("Risk signals are elevated, which tempers position sizing.")

    return factors[:4]


def _entry_or_exit_reason(action: str, candidate: CandidateScore | None) -> str:
    if action in {"enter", "raise_bid", "acquire"}:
        return "Entry conviction stayed above threshold after fit, risk, and budget checks."
    if action == "exit":
        return "The investor no longer saw enough risk-adjusted upside to keep capital committed."
    if action == "watch":
        return "The investor is still looking for one more tick of confirmation before deploying capital."
    if action == "hold":
        return "The investor protected the broader portfolio instead of expanding exposure this tick."
    return "The investor held back because the opportunity failed to clear conviction or affordability thresholds."


async def run_market_simulation(db: AsyncSession, run_id: str) -> dict[str, Any]:
    run_result = await db.execute(select(MarketSimulationRun).where(MarketSimulationRun.id == run_id))
    run = run_result.scalar_one_or_none()
    if run is None:
        raise ValueError("Market simulation run not found")

    properties = await _scoped_properties(
        db,
        MarketSimulationScope(**dict(run.property_scope or {})),
    )
    investors_result = await db.execute(
        select(MarketSimulationInvestor)
        .where(MarketSimulationInvestor.run_id == run.id)
        .order_by(MarketSimulationInvestor.investor_name.asc())
    )
    investors = list(investors_result.scalars().all())

    zip_sentiment = await _household_sentiment_by_zip(db)
    snapshots, sentiments = await _property_snapshots(db, properties, zip_sentiment)

    property_states: dict[str, RuntimePropertyState] = {}
    for property_row in properties:
        risk = _risk_penalty(
            property_row,
            safety_score=snapshots[property_row.id].get("safety_score"),
            inventory_pressure=snapshots[property_row.id].get("inventory_pressure"),
            hazard_flags=dict(snapshots[property_row.id].get("hazard_flags") or {}),
        )
        reservation = _reservation_threshold(
            property_row,
            risk,
            snapshots[property_row.id].get("inventory_pressure"),
        )
        property_states[property_row.id] = RuntimePropertyState(
            property_id=property_row.id,
            reservation_threshold=reservation,
            signal_snapshot={
                "valuation_gap": _valuation_gap(property_row, snapshots[property_row.id].get("median_sale_price")),
                "yield_proxy": _yield_proxy(property_row, snapshots[property_row.id].get("median_rent")),
                "neighborhood_quality": _neighborhood_quality(
                    property_row,
                    transit_score=snapshots[property_row.id].get("transit_score"),
                    school_score=snapshots[property_row.id].get("school_score"),
                    safety_score=snapshots[property_row.id].get("safety_score"),
                    household_sentiment=sentiments[property_row.id],
                ),
                "risk_penalty": risk,
                "peer_momentum": 0.0,
            },
        )

    run.status = "running"
    await db.commit()

    try:
        for tick_num in range(1, int(run.total_ticks) + 1):
            decision_rows: list[MarketSimulationDecision] = []
            property_targets: dict[str, list[str]] = defaultdict(list)
            bid_candidates: dict[str, list[dict[str, Any]]] = defaultdict(list)
            active_property_ids = [
                property_row.id
                for property_row in properties
                if property_states[property_row.id].status != "acquired"
            ]

            for investor in investors:
                focus_property_id = dict(investor.metadata_json or {}).get("focus_property_id")
                shortlist: list[CandidateScore] = []
                for property_row in properties:
                    if property_row.id not in active_property_ids:
                        continue
                    candidate = _score_property(
                        investor,
                        property_row,
                        property_states[property_row.id],
                        snapshots[property_row.id],
                        sentiments[property_row.id],
                    )
                    shortlist.append(candidate)
                shortlist.sort(key=lambda item: (-item.total_score, item.property_row.asking_price))

                action, chosen, bid_amount, reason, rejected = _choose_action(
                    investor,
                    shortlist,
                    property_states,
                    focus_property_id,
                )

                property_id = chosen.property_row.id if chosen else focus_property_id
                if property_id:
                    property_targets[property_id].append(investor.id)

                explanation_payload = {
                    "signal_scores": dict(chosen.signal_scores) if chosen else {
                        "valuation_gap": 0.5,
                        "yield_proxy": 0.45,
                        "neighborhood_quality": 0.5,
                        "risk_penalty": 0.25,
                        "peer_momentum": 0.0,
                    },
                    "persona_weights": dict(investor.signal_weights or {}),
                    "peer_inputs": dict(chosen.peer_inputs) if chosen else {
                        "investor_count": 0.0,
                        "bid_velocity": 0.0,
                        "local_competition": 0.0,
                        "recent_attention": 0.0,
                    },
                    "property_match_factors": _property_match_factors(investor, chosen),
                    "budget_position": _budget_position(investor, chosen.property_row if chosen else shortlist[0].property_row, bid_amount) if (chosen or shortlist) else {},
                    "persona_summary": _persona_summary(investor),
                    "chosen_action_reason": reason,
                    "entry_or_exit_reason": _entry_or_exit_reason(action, chosen),
                    "rejected_alternatives": rejected,
                    "reservation_threshold": chosen.reservation_threshold if chosen else None,
                }
                decision = MarketSimulationDecision(
                    run_id=run.id,
                    tick_num=tick_num,
                    investor_id=investor.id,
                    property_id=property_id,
                    chosen_action=action,
                    bid_amount=bid_amount,
                    total_score=chosen.total_score if chosen else 0.0,
                    score_breakdown=explanation_payload["signal_scores"],
                    explanation_payload=explanation_payload,
                )
                decision_rows.append(decision)
                if action in {"enter", "raise_bid"} and chosen and bid_amount:
                    bid_candidates[chosen.property_row.id].append(
                        {
                            "investor": investor,
                            "decision": decision,
                            "candidate": chosen,
                            "bid_amount": bid_amount,
                        }
                    )
                new_focus = property_id if action in {"watch", "enter", "raise_bid", "hold"} else None
                investor.metadata_json = {
                    **dict(investor.metadata_json or {}),
                    "focus_property_id": new_focus,
                    "last_action": action,
                }

            for property_row in properties:
                runtime_state = property_states[property_row.id]
                contenders = bid_candidates.get(property_row.id, [])
                contenders.sort(
                    key=lambda item: (-item["bid_amount"], -item["candidate"].total_score, item["investor"].investor_name)
                )
                previous_top = runtime_state.current_top_bid or 0.0
                winning_investor_id = runtime_state.winning_investor_id
                if contenders:
                    best = contenders[0]
                    runtime_state.current_top_bid = best["bid_amount"]
                    runtime_state.winning_investor_id = best["investor"].id
                    runtime_state.last_bid_velocity = round((runtime_state.current_top_bid or 0.0) - previous_top, 2)
                    winning_investor_id = best["investor"].id
                    if best["bid_amount"] >= runtime_state.reservation_threshold:
                        runtime_state.status = "acquired"
                        runtime_state.winning_tick = tick_num
                        holdings = list(best["investor"].holdings or [])
                        if property_row.id not in holdings:
                            holdings.append(property_row.id)
                        best["investor"].holdings = holdings
                        best["investor"].cash_remaining = round(
                            max(0.0, float(best["investor"].cash_remaining or 0.0) - best["bid_amount"]),
                            2,
                        )
                        best["decision"].chosen_action = "acquire"
                        best["decision"].explanation_payload = {
                            **dict(best["decision"].explanation_payload or {}),
                            "chosen_action_reason": (
                                dict(best["decision"].explanation_payload or {}).get("chosen_action_reason", "")
                                + " Reservation threshold was met, so the property converted to an acquisition."
                            ).strip(),
                            "entry_or_exit_reason": "The investor converted conviction into an executed acquisition once the seller threshold cleared.",
                        }
                else:
                    runtime_state.last_bid_velocity = 0.0

                target_ids = property_targets.get(property_row.id, [])
                runtime_state.previous_attention_count = len(target_ids)
                runtime_state.recent_attention = round((runtime_state.recent_attention * 0.45) + len(target_ids), 4)
                runtime_state.local_competition = round(len(contenders), 4)

                state_row = MarketSimulationPropertyState(
                    run_id=run.id,
                    property_id=property_row.id,
                    tick_num=tick_num,
                    status=runtime_state.status,
                    attention_count=len(target_ids),
                    bid_count=len(contenders),
                    top_bid=runtime_state.current_top_bid,
                    bid_velocity=runtime_state.last_bid_velocity,
                    local_competition=runtime_state.local_competition,
                    recent_attention=runtime_state.recent_attention,
                    reservation_threshold=runtime_state.reservation_threshold,
                    winning_investor_id=winning_investor_id,
                    signal_snapshot={
                        **dict(runtime_state.signal_snapshot or {}),
                        "peer_momentum": _peer_momentum(runtime_state, float(property_row.asking_price or 0))[0],
                    },
                    targeted_investor_ids=target_ids,
                )
                db.add(state_row)

            for decision in decision_rows:
                db.add(decision)

            run.current_tick = tick_num
            await db.commit()

        acquisitions_summary: list[dict[str, Any]] = []
        investor_lookup = {investor.id: investor for investor in investors}
        for property_row in properties:
            runtime_state = property_states[property_row.id]
            if runtime_state.status != "acquired" or not runtime_state.winning_investor_id:
                continue
            winner = investor_lookup[runtime_state.winning_investor_id]
            acquisitions_summary.append(
                {
                    "property_id": property_row.id,
                    "property_address": property_row.address,
                    "winning_investor_id": winner.id,
                    "winning_investor_name": winner.investor_name,
                    "acquired_tick": runtime_state.winning_tick or run.total_ticks,
                    "winning_bid": runtime_state.current_top_bid or 0.0,
                }
            )

        summary = {
            "completed_ticks": int(run.total_ticks),
            "decision_count": int(run.total_ticks) * len(investors),
            "property_count": len(properties),
            "investor_count": len(investors),
            "acquired_count": len(acquisitions_summary),
            "acquired_property_ids": [item["property_id"] for item in acquisitions_summary],
            "market_temperature": round(
                sum(state.recent_attention for state in property_states.values()) / max(len(property_states), 1),
                4,
            ),
        }
        run.status = "completed"
        run.current_tick = int(run.total_ticks)
        run.summary = summary
        run.completed_at = datetime.utcnow()
        await db.commit()
        return summary
    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)
        await db.commit()
        logger.error(
            "market_simulation.failed",
            run_id=run_id,
            error=str(exc),
            exc_info=True,
        )
        raise


async def execute_market_simulation(run_id: str) -> dict[str, Any]:
    async with async_session() as db:
        return await run_market_simulation(db, run_id)


async def get_market_simulation_status(db: AsyncSession, run_id: str) -> MarketSimulationRun | None:
    result = await db.execute(select(MarketSimulationRun).where(MarketSimulationRun.id == run_id))
    return result.scalar_one_or_none()


async def _investor_outcome_summaries(db: AsyncSession, run_id: str) -> dict[str, dict[str, Any]]:
    result = await db.execute(
        select(MarketSimulationDecision, Property)
        .outerjoin(Property, Property.id == MarketSimulationDecision.property_id)
        .where(MarketSimulationDecision.run_id == run_id)
        .order_by(MarketSimulationDecision.tick_num.asc(), MarketSimulationDecision.created_at.asc())
    )
    summaries: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "decisions_made": 0,
            "watch_actions": 0,
            "bid_actions": 0,
            "acquisitions": 0,
            "last_action": None,
            "last_property_id": None,
            "last_property_address": None,
        }
    )
    for decision, property_row in result.all():
        summary = summaries[decision.investor_id]
        summary["decisions_made"] += 1
        if decision.chosen_action == "watch":
            summary["watch_actions"] += 1
        if decision.chosen_action in {"enter", "raise_bid", "acquire"}:
            summary["bid_actions"] += 1
        if decision.chosen_action == "acquire":
            summary["acquisitions"] += 1
        summary["last_action"] = decision.chosen_action
        summary["last_property_id"] = decision.property_id
        summary["last_property_address"] = property_row.address if property_row else None
    return summaries


def _investor_payload(investor: MarketSimulationInvestor, outcome_summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": investor.id,
        "investor_name": investor.investor_name,
        "archetype": investor.archetype,
        "budget": float(investor.budget or 0.0),
        "cash_remaining": float(investor.cash_remaining or 0.0),
        "hold_horizon_ticks": int(investor.hold_horizon_ticks or 0),
        "risk_appetite": float(investor.risk_appetite or 0.0),
        "diversification_cap": int(investor.diversification_cap or 0),
        "preferred_property_types": list(investor.preferred_property_types or []),
        "signal_weights": dict(investor.signal_weights or {}),
        "holdings": list(investor.holdings or []),
        "persona": dict(investor.persona_profile or {}) or None,
        "outcome_summary": dict(outcome_summary or {}),
    }


async def build_market_simulation_result(db: AsyncSession, run_id: str) -> dict[str, Any] | None:
    run = await get_market_simulation_status(db, run_id)
    if run is None:
        return None

    investors_result = await db.execute(
        select(MarketSimulationInvestor)
        .where(MarketSimulationInvestor.run_id == run.id)
        .order_by(MarketSimulationInvestor.investor_name.asc())
    )
    investors = list(investors_result.scalars().all())
    outcome_summaries = await _investor_outcome_summaries(db, run.id)

    states_result = await db.execute(
        select(MarketSimulationPropertyState, Property, MarketSimulationInvestor)
        .join(Property, Property.id == MarketSimulationPropertyState.property_id)
        .outerjoin(
            MarketSimulationInvestor,
            MarketSimulationInvestor.id == MarketSimulationPropertyState.winning_investor_id,
        )
        .where(MarketSimulationPropertyState.run_id == run.id)
        .order_by(MarketSimulationPropertyState.property_id.asc(), MarketSimulationPropertyState.tick_num.desc())
    )
    acquisitions: list[dict[str, Any]] = []
    seen_properties: set[str] = set()
    for state_row, property_row, investor_row in states_result.all():
        if property_row.id in seen_properties:
            continue
        seen_properties.add(property_row.id)
        if state_row.status != "acquired" or investor_row is None:
            continue
        acquisitions.append(
            {
                "property_id": property_row.id,
                "property_address": property_row.address,
                "winning_investor_id": investor_row.id,
                "winning_investor_name": investor_row.investor_name,
                "acquired_tick": state_row.tick_num,
                "winning_bid": float(state_row.top_bid or 0.0),
            }
        )

    return {
        "run_id": run.id,
        "status": run.status,
        "total_ticks": int(run.total_ticks),
        "completed_ticks": int(run.current_tick),
        "summary": dict(run.summary or {}),
        "acquisitions": acquisitions,
        "investors": [
            _investor_payload(investor, outcome_summaries.get(investor.id, {}))
            for investor in investors
        ],
    }


async def build_market_simulation_replay(db: AsyncSession, run_id: str) -> dict[str, Any] | None:
    run = await get_market_simulation_status(db, run_id)
    if run is None:
        return None

    investors_result = await db.execute(
        select(MarketSimulationInvestor)
        .where(MarketSimulationInvestor.run_id == run.id)
        .order_by(MarketSimulationInvestor.investor_name.asc())
    )
    investors = list(investors_result.scalars().all())
    investor_lookup = {investor.id: investor for investor in investors}
    outcome_summaries = await _investor_outcome_summaries(db, run.id)

    state_rows_result = await db.execute(
        select(MarketSimulationPropertyState, Property)
        .join(Property, Property.id == MarketSimulationPropertyState.property_id)
        .where(MarketSimulationPropertyState.run_id == run.id)
        .order_by(MarketSimulationPropertyState.tick_num.asc(), Property.address.asc())
    )

    decision_rows_result = await db.execute(
        select(MarketSimulationDecision, MarketSimulationInvestor, Property)
        .join(MarketSimulationInvestor, MarketSimulationInvestor.id == MarketSimulationDecision.investor_id)
        .outerjoin(Property, Property.id == MarketSimulationDecision.property_id)
        .where(MarketSimulationDecision.run_id == run.id)
        .order_by(MarketSimulationDecision.tick_num.asc(), MarketSimulationInvestor.investor_name.asc())
    )

    ticks: dict[int, dict[str, Any]] = defaultdict(lambda: {"property_states": [], "decisions": []})
    for state_row, property_row in state_rows_result.all():
        ticks[int(state_row.tick_num)]["property_states"].append(
            {
                "property_id": property_row.id,
                "address": property_row.address,
                "latitude": property_row.latitude,
                "longitude": property_row.longitude,
                "asking_price": float(property_row.asking_price or 0.0),
                "property_type": property_row.property_type,
                "tick_num": int(state_row.tick_num),
                "status": state_row.status,
                "attention_count": int(state_row.attention_count or 0),
                "bid_count": int(state_row.bid_count or 0),
                "top_bid": state_row.top_bid,
                "bid_velocity": float(state_row.bid_velocity or 0.0),
                "local_competition": float(state_row.local_competition or 0.0),
                "recent_attention": float(state_row.recent_attention or 0.0),
                "reservation_threshold": float(state_row.reservation_threshold or 0.0),
                "winning_investor_id": state_row.winning_investor_id,
                "signal_snapshot": dict(state_row.signal_snapshot or {}),
                "targeted_investor_ids": list(state_row.targeted_investor_ids or []),
            }
        )

    for decision_row, investor_row, property_row in decision_rows_result.all():
        explanation = dict(decision_row.explanation_payload or {})
        ticks[int(decision_row.tick_num)]["decisions"].append(
            {
                "investor_id": investor_row.id,
                "investor_name": investor_row.investor_name,
                "archetype": investor_row.archetype,
                "tick_num": int(decision_row.tick_num),
                "property_id": decision_row.property_id,
                "property_address": property_row.address if property_row else None,
                "chosen_action": decision_row.chosen_action,
                "bid_amount": decision_row.bid_amount,
                "total_score": float(decision_row.total_score or 0.0),
                "signal_scores": dict(explanation.get("signal_scores") or {}),
                "persona_weights": dict(explanation.get("persona_weights") or {}),
                "peer_inputs": dict(explanation.get("peer_inputs") or {}),
                "property_match_factors": list(explanation.get("property_match_factors") or []),
                "budget_position": dict(explanation.get("budget_position") or {}),
                "persona_summary": dict(explanation.get("persona_summary") or {}),
                "chosen_action_reason": str(explanation.get("chosen_action_reason") or ""),
                "entry_or_exit_reason": str(explanation.get("entry_or_exit_reason") or ""),
                "rejected_alternatives": list(explanation.get("rejected_alternatives") or []),
            }
        )

    ordered_ticks = [
        {
            "tick_number": tick_number,
            "property_states": ticks[tick_number]["property_states"],
            "decisions": ticks[tick_number]["decisions"],
        }
        for tick_number in sorted(ticks.keys())
    ]

    return {
        "run_id": run.id,
        "status": run.status,
        "run_label": run.run_label,
        "total_ticks": int(run.total_ticks),
        "completed_ticks": int(run.current_tick),
        "investors": [
            _investor_payload(investor, outcome_summaries.get(investor.id, {}))
            for investor in investors
        ],
        "ticks": ordered_ticks,
        "summary": dict(run.summary or {}),
    }
