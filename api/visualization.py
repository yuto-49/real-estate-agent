"""Visualization API — property map data and simulation replay endpoints."""

import re

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, and_

from api.schemas import (
    ConversationEvent,
    MapOverlay,
    PropertyResponse,
    PropertyVisualizationResponse,
    SimulationReplayListResponse,
    SimulationReplayResponse,
)
from db.models import Property, SimulationResult, HouseholdProfile
from services.negotiation_simulator import get_simulation, list_simulations

router = APIRouter()

_ZIP_PATTERN = re.compile(r"\b(\d{5})(?:-\d{4})?\b")


def _extract_zip_from_address(address: str) -> str | None:
    """Try to extract a 5-digit zip code from an address string."""
    match = _ZIP_PATTERN.search(address or "")
    return match.group(1) if match else None


def _classify_event_type(role: str, tool_calls: list[dict]) -> str:
    """Classify a transcript entry into a structured event type."""
    if role == "system":
        return "message"
    if role == "broker":
        return "broker_intervention"
    for tc in tool_calls:
        tool_name = tc.get("tool", "")
        if "accept" in tool_name:
            return "acceptance"
        if "counter" in tool_name:
            return "counter_offer"
        if "offer" in tool_name or "submit" in tool_name:
            return "offer"
        if "reject" in tool_name or "walk" in tool_name:
            return "rejection"
    return "message"


def _build_numerical_state(
    entry: dict,
    price_path: list[dict],
    round_num: int,
    asking_price: float,
    initial_offer: float,
) -> dict:
    """Build numerical state for a conversation event from price path and transcript data."""
    buyer_offer = initial_offer
    seller_ask = asking_price

    # Walk price_path up to this round to find latest buyer/seller positions
    for pp in price_path:
        if pp.get("round", 0) > round_num:
            break
        if pp.get("role") == "buyer":
            buyer_offer = pp.get("price", buyer_offer)
        elif pp.get("role") == "seller":
            seller_ask = pp.get("price", seller_ask)

    # Override with explicit price from transcript entry if available
    if "price" in entry:
        role = entry.get("role", "")
        if role == "buyer":
            buyer_offer = entry["price"]
        elif role == "seller":
            seller_ask = entry["price"]

    spread = round(abs(seller_ask - buyer_offer), 2)
    return {
        "buyer_offer": buyer_offer,
        "seller_ask": seller_ask,
        "spread": spread,
        "status": "negotiating",
    }


def _transcript_to_events(
    transcript: list[dict],
    price_path: list[dict],
    asking_price: float,
    initial_offer: float,
    outcome: str,
) -> list[ConversationEvent]:
    """Convert raw transcript entries into structured ConversationEvent objects."""
    events: list[ConversationEvent] = []
    for entry in transcript:
        role = entry.get("role", "system")
        tool_calls = entry.get("tool_calls", [])
        round_num = entry.get("round", 0)

        numerical_state = _build_numerical_state(
            entry, price_path, round_num, asking_price, initial_offer
        )

        # Mark final event status
        if entry is transcript[-1] and outcome:
            numerical_state["status"] = outcome

        events.append(ConversationEvent(
            round_number=round_num,
            timestamp=entry.get("timestamp", ""),
            role=role,
            event_type=_classify_event_type(role, tool_calls),
            content=entry.get("message", ""),
            numerical_state=numerical_state,
            tool_calls=tool_calls,
        ))
    return events


def _build_replay_from_db(row: SimulationResult, available_scenarios: list[str]) -> SimulationReplayResponse:
    """Build a SimulationReplayResponse from a DB-persisted SimulationResult."""
    summary = row.summary or {}
    transcript = summary.get("transcript", [])
    price_path = row.price_path or []

    events = _transcript_to_events(
        transcript, price_path, row.asking_price, row.initial_offer, row.outcome
    )

    return SimulationReplayResponse(
        simulation_id=str(row.id),
        batch_id=row.batch_id,
        scenario_name=row.scenario_name,
        property_id=row.property_id,
        asking_price=row.asking_price,
        initial_offer=row.initial_offer,
        max_rounds=row.max_rounds,
        events=events,
        final_outcome={
            "status": row.outcome,
            "final_price": row.final_price,
            "rounds_completed": row.rounds_completed,
            "spread": summary.get("final_spread", 0),
            "buyer_final": summary.get("buyer_final_position", row.initial_offer),
            "seller_final": summary.get("seller_final_position", row.asking_price),
        },
        available_scenarios=available_scenarios,
    )


def _build_replay_from_memory(sim: dict, available_scenarios: list[str]) -> SimulationReplayResponse:
    """Build a SimulationReplayResponse from an in-memory simulation dict."""
    config = sim.get("config", {})
    transcript = sim.get("transcript", [])
    price_path = sim.get("price_path", [])
    summary = sim.get("summary", {})
    asking_price = config.get("asking_price", 0)
    initial_offer = config.get("initial_offer", 0)
    outcome = sim.get("outcome", "unknown")

    events = _transcript_to_events(
        transcript, price_path, asking_price, initial_offer, outcome
    )

    return SimulationReplayResponse(
        simulation_id=sim["id"],
        batch_id=None,
        scenario_name=None,
        property_id=config.get("property_id", ""),
        asking_price=asking_price,
        initial_offer=initial_offer,
        max_rounds=sim.get("max_rounds", 10),
        events=events,
        final_outcome={
            "status": outcome,
            "final_price": sim.get("final_price"),
            "rounds_completed": sim.get("current_round", 0),
            "spread": summary.get("final_spread", 0),
            "buyer_final": summary.get("buyer_final_position", initial_offer),
            "seller_final": summary.get("seller_final_position", asking_price),
        },
        available_scenarios=available_scenarios,
    )


# ── Endpoints ──


@router.get("/property/{property_id}")
async def get_property_visualization(property_id: str) -> PropertyVisualizationResponse:
    """Return property data with map overlays and available simulation IDs."""
    from db.database import async_session

    async with async_session() as db:
        # Fetch the target property
        result = await db.execute(
            select(Property).where(Property.id == property_id)
        )
        prop = result.scalar_one_or_none()
        if not prop:
            raise HTTPException(status_code=404, detail="Property not found")

        lat = prop.latitude if prop.latitude is not None else 0.0
        lng = prop.longitude if prop.longitude is not None else 0.0

        # Fetch comparable properties (same type, ±20% price, limit 10)
        comps: list[PropertyResponse] = []
        if prop.asking_price and prop.asking_price > 0:
            price_low = prop.asking_price * 0.8
            price_high = prop.asking_price * 1.2
            comp_query = (
                select(Property)
                .where(
                    and_(
                        Property.id != property_id,
                        Property.asking_price >= price_low,
                        Property.asking_price <= price_high,
                    )
                )
                .limit(10)
            )
            if prop.property_type:
                comp_query = comp_query.where(Property.property_type == prop.property_type)

            comp_result = await db.execute(comp_query)
            comps = [
                PropertyResponse.model_validate(c)
                for c in comp_result.scalars().all()
            ]

        # Fetch simulation result IDs for this property
        sim_result = await db.execute(
            select(SimulationResult.id)
            .where(SimulationResult.property_id == property_id)
            .order_by(SimulationResult.created_at.desc())
            .limit(20)
        )
        sim_ids = [str(r) for r in sim_result.scalars().all()]

        # Also check in-memory simulations
        for sim in list_simulations():
            if sim.get("config", {}).get("property_id") == property_id:
                if sim["id"] not in sim_ids:
                    sim_ids.insert(0, sim["id"])

        # Build overlays — each section guarded so one failure doesn't crash the endpoint
        overlays: list[MapOverlay] = []
        nd = prop.neighborhood_data or {}

        if "sentiment" in nd or "market_heat" in nd:
            sentiment_val = nd.get("sentiment", nd.get("market_heat", 0))
            sentiment_score = sentiment_val if isinstance(sentiment_val, (int, float)) else 0.5
            color = "#22c55e" if sentiment_score > 0.5 else "#ef4444" if sentiment_score < -0.5 else "#eab308"
            overlays.append(MapOverlay(
                overlay_type="sentiment_zone",
                center_lat=lat,
                center_lng=lng,
                radius_meters=800,
                value=sentiment_score,
                label=f"Neighborhood sentiment: {sentiment_score:.1f}",
                color=color,
            ))

        if "risk_score" in nd:
            risk = nd["risk_score"]
            if isinstance(risk, (int, float)):
                overlays.append(MapOverlay(
                    overlay_type="risk_zone",
                    center_lat=lat,
                    center_lng=lng,
                    radius_meters=600,
                    value=risk,
                    label=f"Risk score: {risk:.2f}",
                    color="#ef4444" if risk > 0.6 else "#eab308" if risk > 0.3 else "#22c55e",
                ))

        # Household cluster overlays — extract zip from neighborhood_data or address
        prop_zip = nd.get("zip_code") or _extract_zip_from_address(prop.address)
        if prop_zip:
            hh_result = await db.execute(
                select(HouseholdProfile.zip_code, HouseholdProfile.housing_market_sentiment)
                .where(HouseholdProfile.zip_code == prop_zip)
                .limit(50)
            )
            households = hh_result.all()
            if households:
                avg_sentiment = sum(h[1] or 0 for h in households) / len(households)
                overlays.append(MapOverlay(
                    overlay_type="household_cluster",
                    center_lat=lat,
                    center_lng=lng,
                    radius_meters=1000,
                    value=avg_sentiment,
                    label=f"{len(households)} households, avg sentiment: {avg_sentiment:.2f}",
                    color="#3b82f6",
                    metadata={"household_count": len(households)},
                ))

        # Comparable property overlays
        for comp in comps:
            if comp.latitude and comp.longitude:
                overlays.append(MapOverlay(
                    overlay_type="comparable",
                    center_lat=comp.latitude,
                    center_lng=comp.longitude,
                    radius_meters=0,
                    value=comp.asking_price,
                    label=f"${comp.asking_price:,.0f} — {comp.address}",
                    color="#8b5cf6",
                ))

    return PropertyVisualizationResponse(
        property_id=str(prop.id),
        address=prop.address,
        latitude=lat,
        longitude=lng,
        asking_price=prop.asking_price,
        property_type=prop.property_type,
        overlays=overlays,
        comparable_properties=comps,
        simulation_ids=sim_ids,
    )


@router.get("/replay/{simulation_id}")
async def get_simulation_replay(simulation_id: str) -> SimulationReplayResponse:
    """Return a structured replay of a simulation for the conversation viewer."""
    from db.database import async_session

    # First check DB for persisted results
    async with async_session() as db:
        result = await db.execute(
            select(SimulationResult).where(SimulationResult.id == simulation_id)
        )
        row = result.scalar_one_or_none()
        if row:
            # Find sibling scenarios for scenario switching
            available_scenarios: list[str] = []
            if row.batch_id:
                siblings = await db.execute(
                    select(SimulationResult.scenario_name)
                    .where(SimulationResult.batch_id == row.batch_id)
                    .where(SimulationResult.scenario_name.isnot(None))
                )
                available_scenarios = [s for s in siblings.scalars().all() if s]
            return _build_replay_from_db(row, available_scenarios)

    # Fall back to in-memory simulations
    sim = get_simulation(simulation_id)
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")

    if sim["status"] not in ("completed", "failed"):
        raise HTTPException(status_code=409, detail="Simulation still running — poll /status/{id}")

    return _build_replay_from_memory(sim, [])


@router.get("/replay/batch/{batch_id}")
async def get_batch_replays(batch_id: str) -> SimulationReplayListResponse:
    """Return replays for all scenarios in a batch."""
    from db.database import async_session

    async with async_session() as db:
        result = await db.execute(
            select(SimulationResult)
            .where(SimulationResult.batch_id == batch_id)
            .order_by(SimulationResult.scenario_name)
        )
        rows = result.scalars().all()

    if not rows:
        raise HTTPException(status_code=404, detail="No simulation results found for this batch")

    scenario_names = [r.scenario_name for r in rows if r.scenario_name]

    replays = [_build_replay_from_db(row, scenario_names) for row in rows]
    return SimulationReplayListResponse(replays=replays, count=len(replays))


@router.get("/replay/by-property/{property_id}")
async def get_property_replays(
    property_id: str,
    limit: int = Query(default=5, le=20),
) -> SimulationReplayListResponse:
    """Return recent simulation replays for a specific property."""
    from db.database import async_session

    async with async_session() as db:
        result = await db.execute(
            select(SimulationResult)
            .where(SimulationResult.property_id == property_id)
            .order_by(SimulationResult.created_at.desc())
            .limit(limit)
        )
        rows = result.scalars().all()

    replays = [_build_replay_from_db(row, []) for row in rows]
    return SimulationReplayListResponse(replays=replays, count=len(replays))
