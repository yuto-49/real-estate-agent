"""Deterministic market investor simulator tests."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from api.schemas import MarketSimulationScope, MarketSimulationStartRequest
from db.models import (
    MarketSignal,
    MarketSimulationDecision,
    MarketSimulationInvestor,
    MarketSimulationPropertyState,
    Property,
    UserProfile,
)
from services.market_investor_simulator import (
    initialize_market_simulation_run,
    run_market_simulation,
)
from services.market_state import SUBJECT_NEIGHBORHOOD, SUBJECT_PROPERTY


async def _seed_property(
    db,
    *,
    seller_id: str,
    address: str,
    asking_price: float,
    neighborhood_id: str,
    zip_code: str,
    property_type: str = "condo",
    latitude: float = 41.881,
    longitude: float = -87.623,
) -> Property:
    prop = Property(
        seller_id=seller_id,
        address=address,
        asking_price=asking_price,
        property_type=property_type,
        latitude=latitude,
        longitude=longitude,
        status="active",
        neighborhood_data={
            "neighborhood_id": neighborhood_id,
            "zip_code": zip_code,
            "market_heat": 0.45,
            "risk_score": 0.22,
        },
        disclosures={
            "known_defects": [],
            "flood_zone": "X",
        },
    )
    db.add(prop)
    await db.commit()
    await db.refresh(prop)
    return prop


async def _seed_signal(
    db,
    *,
    signal_type: str,
    subject_type: str,
    subject_id: str,
    value: float | None = None,
    payload: dict | None = None,
) -> None:
    db.add(
        MarketSignal(
            signal_type=signal_type,
            subject_type=subject_type,
            subject_id=subject_id,
            value=value,
            payload=payload or {},
        )
    )
    await db.commit()


@pytest.mark.asyncio
async def test_market_simulation_records_seeded_personas_and_rich_decision_payloads(db):
    seller = UserProfile(name="Seller", email="seller-market@test.com", role="seller")
    db.add(seller)
    await db.commit()
    await db.refresh(seller)

    priced = await _seed_property(
        db,
        seller_id=seller.id,
        address="100 Lake St, Chicago, IL 60601",
        asking_price=420_000,
        neighborhood_id="loop-core",
        zip_code="60601",
    )
    fallback = await _seed_property(
        db,
        seller_id=seller.id,
        address="200 Oak St, Chicago, IL 60602",
        asking_price=350_000,
        neighborhood_id="river-north",
        zip_code="60602",
        latitude=41.892,
        longitude=-87.635,
    )

    await _seed_signal(
        db,
        signal_type="median_sale_price",
        subject_type=SUBJECT_PROPERTY,
        subject_id=priced.id,
        value=465_000,
    )
    await _seed_signal(
        db,
        signal_type="median_rent",
        subject_type=SUBJECT_PROPERTY,
        subject_id=priced.id,
        value=3_600,
    )
    await _seed_signal(
        db,
        signal_type="transit_score",
        subject_type=SUBJECT_NEIGHBORHOOD,
        subject_id="loop-core",
        value=95,
    )
    await _seed_signal(
        db,
        signal_type="safety_score",
        subject_type=SUBJECT_NEIGHBORHOOD,
        subject_id="loop-core",
        value=74,
    )

    request = MarketSimulationStartRequest(
        investor_count=6,
        tick_count=4,
        cohort_preset="balanced",
        run_label="Loop competition",
        scope=MarketSimulationScope(property_ids=[priced.id, fallback.id]),
        seeded_personas=[
            {
                "display_name": "Jordan Pike",
                "archetype": "value",
                "budget": 460_000,
                "risk_posture": "measured",
                "hold_horizon": "6-8 ticks",
                "target_yield": "5-7% gross yield",
                "preferred_property_types": ["condo", "multifamily"],
                "preferred_price_band": "$350k-$475k",
                "neighborhood_preferences": ["walkable transit-rich corridors", "core Loop access"],
                "avoidance_triggers": ["flood exposure", "deferred maintenance"],
                "competition_style": "patient but willing to raise once conviction is high",
                "exit_style": "walk away when risk-adjusted upside compresses",
                "investment_thesis": "Acquire mispriced urban assets with resilient rent demand.",
            },
            {
                "display_name": "Mina Foster",
                "archetype": "yield",
                "budget": 490_000,
                "risk_posture": "income-focused",
                "hold_horizon": "8-10 ticks",
                "target_yield": "6-8% stabilized yield",
                "preferred_property_types": ["multifamily", "condo"],
                "preferred_price_band": "$320k-$510k",
                "neighborhood_preferences": ["dense rental demand", "strong safety scores"],
                "avoidance_triggers": ["weak rent comps", "high HOA drag"],
                "competition_style": "measured and selective",
                "exit_style": "hold unless yield deteriorates materially",
                "investment_thesis": "Favor income durability over short-term excitement.",
            },
            {
                "display_name": "Theo Mercer",
                "archetype": "momentum",
                "budget": 510_000,
                "risk_posture": "assertive",
                "hold_horizon": "4-6 ticks",
                "target_yield": "accept lower yield for faster appreciation",
                "preferred_property_types": ["condo", "sfr"],
                "preferred_price_band": "$400k-$540k",
                "neighborhood_preferences": ["high-velocity submarkets", "areas with rising attention"],
                "avoidance_triggers": ["stalled bid activity", "soft safety trends"],
                "competition_style": "aggressive when peers converge",
                "exit_style": "rotate out when momentum stalls",
                "investment_thesis": "Lean into competitive assets where peer demand confirms upside.",
            },
            {
                "display_name": "Avery Sloan",
                "archetype": "contrarian",
                "budget": 430_000,
                "risk_posture": "disciplined",
                "hold_horizon": "6-7 ticks",
                "target_yield": "seek upside from underappreciated pricing",
                "preferred_property_types": ["condo", "sfr"],
                "preferred_price_band": "$300k-$450k",
                "neighborhood_preferences": ["stable but overlooked pockets"],
                "avoidance_triggers": ["crowded bidding wars", "headline hazard risk"],
                "competition_style": "avoid crowds and wait for conviction",
                "exit_style": "leave when competition overwhelms thesis",
                "investment_thesis": "Find pricing inefficiencies before the rest of the market wakes up.",
            },
            {
                "display_name": "Priya Dalton",
                "archetype": "value",
                "budget": 455_000,
                "risk_posture": "measured",
                "hold_horizon": "6-8 ticks",
                "target_yield": "5-6% cash-on-cash",
                "preferred_property_types": ["condo", "multifamily"],
                "preferred_price_band": "$340k-$470k",
                "neighborhood_preferences": ["strong transit access", "steady rent demand"],
                "avoidance_triggers": ["excessive defect load", "price overextension"],
                "competition_style": "disciplined with one strong counter",
                "exit_style": "pause when underwriting edge disappears",
                "investment_thesis": "Stay valuation-led and preserve dry powder for the best setups.",
            },
            {
                "display_name": "Lucas Hale",
                "archetype": "yield",
                "budget": 470_000,
                "risk_posture": "income-focused",
                "hold_horizon": "8-10 ticks",
                "target_yield": "6-7% rent-supported return",
                "preferred_property_types": ["multifamily", "condo"],
                "preferred_price_band": "$330k-$490k",
                "neighborhood_preferences": ["consistent tenant demand", "high school and safety scores"],
                "avoidance_triggers": ["rent softness", "structural hazard flags"],
                "competition_style": "measured",
                "exit_style": "exit when yield support breaks",
                "investment_thesis": "Prioritize stable cash flow with enough upside to warrant patience.",
            },
        ],
    )

    run = await initialize_market_simulation_run(db, request)
    investors_result = await db.execute(
        select(MarketSimulationInvestor).where(MarketSimulationInvestor.run_id == run.id)
    )
    investors = list(investors_result.scalars().all())
    assert investors[0].investor_name == "Jordan Pike"
    assert dict(investors[0].persona_profile or {})["investment_thesis"].startswith("Acquire mispriced urban assets")

    summary = await run_market_simulation(db, run.id)

    decisions_result = await db.execute(
        select(MarketSimulationDecision).where(MarketSimulationDecision.run_id == run.id)
    )
    decisions = list(decisions_result.scalars().all())
    assert len(decisions) == 24

    property_state_result = await db.execute(
        select(MarketSimulationPropertyState).where(
            MarketSimulationPropertyState.run_id == run.id
        )
    )
    property_states = list(property_state_result.scalars().all())
    assert len(property_states) == 8

    first_decision = decisions[0]
    explanation = dict(first_decision.explanation_payload or {})
    assert "signal_scores" in explanation
    assert "peer_inputs" in explanation
    assert "chosen_action_reason" in explanation
    assert "entry_or_exit_reason" in explanation
    assert "persona_weights" in explanation
    assert "property_match_factors" in explanation
    assert "budget_position" in explanation
    assert "persona_summary" in explanation
    assert "rejected_alternatives" in explanation

    score_keys = set(explanation["signal_scores"].keys())
    assert score_keys == {
        "valuation_gap",
        "yield_proxy",
        "neighborhood_quality",
        "risk_penalty",
        "peer_momentum",
    }

    fallback_decision = next(
        decision for decision in decisions if decision.property_id == fallback.id
    )
    fallback_scores = dict(fallback_decision.explanation_payload["signal_scores"])
    assert all(value is not None for value in fallback_scores.values())
    assert isinstance(fallback_decision.explanation_payload["property_match_factors"], list)
    assert "cash_remaining" in fallback_decision.explanation_payload["budget_position"]

    assert summary["completed_ticks"] == 4
    assert summary["decision_count"] == 24
    assert summary["property_count"] == 2
    assert summary["investor_count"] == 6


@pytest.mark.asyncio
async def test_market_simulation_marks_acquisitions_when_reservation_threshold_is_met(db):
    seller = UserProfile(name="Seller 2", email="seller2-market@test.com", role="seller")
    db.add(seller)
    await db.commit()
    await db.refresh(seller)

    target = await _seed_property(
        db,
        seller_id=seller.id,
        address="300 Wacker Dr, Chicago, IL 60606",
        asking_price=310_000,
        neighborhood_id="west-loop",
        zip_code="60606",
        property_type="multifamily",
    )
    await _seed_signal(
        db,
        signal_type="median_sale_price",
        subject_type=SUBJECT_PROPERTY,
        subject_id=target.id,
        value=360_000,
    )
    await _seed_signal(
        db,
        signal_type="median_rent",
        subject_type=SUBJECT_PROPERTY,
        subject_id=target.id,
        value=4_200,
    )
    await _seed_signal(
        db,
        signal_type="inventory_pressure",
        subject_type=SUBJECT_PROPERTY,
        subject_id=target.id,
        value=0.15,
    )

    request = MarketSimulationStartRequest(
        investor_count=5,
        tick_count=5,
        cohort_preset="income",
        scope=MarketSimulationScope(property_ids=[target.id]),
    )
    run = await initialize_market_simulation_run(db, request)
    await run_market_simulation(db, run.id)

    result = await db.execute(
        select(MarketSimulationPropertyState)
        .where(MarketSimulationPropertyState.run_id == run.id)
        .where(MarketSimulationPropertyState.property_id == target.id)
        .order_by(MarketSimulationPropertyState.tick_num.desc())
    )
    latest_state = result.scalars().first()
    assert latest_state is not None
    assert latest_state.status == "acquired"
    assert latest_state.winning_investor_id is not None
    assert latest_state.top_bid is not None
    assert latest_state.top_bid >= latest_state.reservation_threshold
