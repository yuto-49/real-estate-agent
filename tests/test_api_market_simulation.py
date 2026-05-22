"""API tests for market-wide investor simulation."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db.models import MarketSignal, Property, UserProfile
from main import app
from services.market_state import SUBJECT_NEIGHBORHOOD, SUBJECT_PROPERTY
from services.persona_generator import InvestorPersona


@pytest_asyncio.fixture
async def client(db_engine):
    test_session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False,
    )

    with (
        patch("api.market_simulation.async_session", test_session_factory),
        patch("services.market_investor_simulator.async_session", test_session_factory),
        patch("api.market_simulation._run_simulation", new=AsyncMock()),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test",
        ) as ac:
            yield ac


async def _seed_market_fixture(db):
    seller = UserProfile(name="API Seller", email="api-seller@test.com", role="seller")
    db.add(seller)
    await db.commit()
    await db.refresh(seller)

    property_rows = [
        Property(
            seller_id=seller.id,
            address="401 Market St, Chicago, IL 60601",
            asking_price=390_000,
            latitude=41.886,
            longitude=-87.624,
            property_type="condo",
            status="active",
            neighborhood_data={"neighborhood_id": "loop-east", "zip_code": "60601", "market_heat": 0.58},
            disclosures={"known_defects": [], "flood_zone": "X"},
        ),
        Property(
            seller_id=seller.id,
            address="120 Fulton St, Chicago, IL 60607",
            asking_price=520_000,
            latitude=41.8865,
            longitude=-87.648,
            property_type="multifamily",
            status="active",
            neighborhood_data={"neighborhood_id": "west-loop", "zip_code": "60607", "market_heat": 0.62},
            disclosures={"known_defects": ["roof aging"], "flood_zone": "AE"},
        ),
    ]
    db.add_all(property_rows)
    await db.commit()
    for prop in property_rows:
        await db.refresh(prop)

    db.add_all([
        MarketSignal(
            signal_type="median_sale_price",
            subject_type=SUBJECT_PROPERTY,
            subject_id=property_rows[0].id,
            value=430_000,
        ),
        MarketSignal(
            signal_type="median_rent",
            subject_type=SUBJECT_PROPERTY,
            subject_id=property_rows[0].id,
            value=3_200,
        ),
        MarketSignal(
            signal_type="inventory_pressure",
            subject_type=SUBJECT_PROPERTY,
            subject_id=property_rows[0].id,
            value=0.25,
        ),
        MarketSignal(
            signal_type="transit_score",
            subject_type=SUBJECT_NEIGHBORHOOD,
            subject_id="west-loop",
            value=91,
        ),
        MarketSignal(
            signal_type="safety_score",
            subject_type=SUBJECT_NEIGHBORHOOD,
            subject_id="west-loop",
            value=69,
        ),
    ])
    await db.commit()

    return {
        "seller": seller,
        "properties": property_rows,
    }


@pytest.mark.asyncio
async def test_market_persona_preview_and_seeded_run_replay(client, db):
    seeded = await _seed_market_fixture(db)
    property_ids = [prop.id for prop in seeded["properties"]]

    preview_personas = [
        InvestorPersona(
            display_name="Jordan Pike",
            archetype="value",
            budget=410_000,
            risk_posture="measured",
            hold_horizon="6-8 ticks",
            target_yield="5-7% gross yield",
            preferred_property_types=["condo", "multifamily"],
            preferred_price_band="$320k-$430k",
            neighborhood_preferences=["walkable transit-rich corridors", "core Loop access"],
            avoidance_triggers=["flood exposure", "deferred maintenance"],
            competition_style="patient but willing to raise once conviction is high",
            exit_style="walk away when risk-adjusted upside compresses",
            investment_thesis="Acquire mispriced urban assets with resilient rent demand.",
        ),
        InvestorPersona(
            display_name="Mina Foster",
            archetype="yield",
            budget=470_000,
            risk_posture="income-focused",
            hold_horizon="8-10 ticks",
            target_yield="6-8% stabilized yield",
            preferred_property_types=["multifamily", "condo"],
            preferred_price_band="$360k-$490k",
            neighborhood_preferences=["dense rental demand", "strong safety scores"],
            avoidance_triggers=["weak rent comps", "high HOA drag"],
            competition_style="measured and selective",
            exit_style="hold unless yield deteriorates materially",
            investment_thesis="Favor income durability over short-term excitement.",
        ),
        InvestorPersona(
            display_name="Theo Mercer",
            archetype="momentum",
            budget=560_000,
            risk_posture="assertive",
            hold_horizon="4-6 ticks",
            target_yield="accept lower yield for faster appreciation",
            preferred_property_types=["condo", "multifamily"],
            preferred_price_band="$430k-$575k",
            neighborhood_preferences=["high-velocity submarkets", "areas with rising attention"],
            avoidance_triggers=["stalled bid activity", "soft safety trends"],
            competition_style="aggressive when peers converge",
            exit_style="rotate out when momentum stalls",
            investment_thesis="Lean into competitive assets where peer demand confirms upside.",
        ),
        InvestorPersona(
            display_name="Avery Sloan",
            archetype="contrarian",
            budget=445_000,
            risk_posture="disciplined",
            hold_horizon="6-7 ticks",
            target_yield="seek upside from underappreciated pricing",
            preferred_property_types=["condo", "sfr"],
            preferred_price_band="$320k-$455k",
            neighborhood_preferences=["stable but overlooked pockets"],
            avoidance_triggers=["crowded bidding wars", "headline hazard risk"],
            competition_style="avoid crowds and wait for conviction",
            exit_style="leave when competition overwhelms thesis",
            investment_thesis="Find pricing inefficiencies before the rest of the market wakes up.",
        ),
    ]

    with patch(
        "services.market_investor_simulator.generate_market_investor_personas",
        new=AsyncMock(return_value=preview_personas),
    ):
        preview_resp = await client.post(
            "/api/simulation/market/personas",
            json={
                "investor_count": 4,
                "cohort_preset": "balanced",
                "scope": {"property_ids": property_ids},
            },
        )
    assert preview_resp.status_code == 200
    preview_data = preview_resp.json()
    assert preview_data["property_count"] == 2
    assert len(preview_data["personas"]) == 4
    assert preview_data["personas"][0]["display_name"] == "Jordan Pike"
    assert preview_data["inventory_summary"]["property_count"] == 2

    start_resp = await client.post(
        "/api/simulation/market/start",
        json={
            "investor_count": 4,
            "tick_count": 4,
            "cohort_preset": "balanced",
            "run_label": "Persona market sim",
            "scope": {"property_ids": property_ids},
            "seeded_personas": preview_data["personas"],
        },
    )
    assert start_resp.status_code == 202
    run_id = start_resp.json()["run_id"]

    status_data = None
    for _ in range(20):
        status_resp = await client.get(f"/api/simulation/market/status/{run_id}")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        if status_data["status"] == "completed":
            break
        await asyncio.sleep(0.05)

    assert status_data is not None
    assert status_data["status"] == "completed"
    assert status_data["investor_count"] == 4
    assert status_data["property_count"] == 2
    assert status_data["progress"] == 100

    result_resp = await client.get(f"/api/simulation/market/result/{run_id}")
    assert result_resp.status_code == 200
    result_data = result_resp.json()
    assert result_data["run_id"] == run_id
    assert result_data["summary"]["completed_ticks"] == 4
    assert result_data["summary"]["decision_count"] == 16
    assert len(result_data["investors"]) == 4
    assert result_data["investors"][0]["persona"]["display_name"] == "Avery Sloan" or result_data["investors"][0]["persona"]["display_name"] == "Jordan Pike"
    assert "outcome_summary" in result_data["investors"][0]

    replay_resp = await client.get(f"/api/simulation/market/replay/{run_id}")
    assert replay_resp.status_code == 200
    replay_data = replay_resp.json()
    assert replay_data["run_id"] == run_id
    assert replay_data["total_ticks"] == 4
    assert len(replay_data["investors"]) == 4
    assert len(replay_data["ticks"]) == 4

    first_investor = replay_data["investors"][0]
    assert first_investor["persona"]
    assert "investment_thesis" in first_investor["persona"]
    assert first_investor["outcome_summary"]["decisions_made"] == 4

    first_tick = replay_data["ticks"][0]
    assert len(first_tick["property_states"]) == 2
    assert len(first_tick["decisions"]) == 4

    first_decision = first_tick["decisions"][0]
    assert set(first_decision["signal_scores"].keys()) == {
        "valuation_gap",
        "yield_proxy",
        "neighborhood_quality",
        "risk_penalty",
        "peer_momentum",
    }
    assert "investor_count" in first_decision["peer_inputs"]
    assert "persona_weights" in first_decision
    assert "property_match_factors" in first_decision
    assert "budget_position" in first_decision
    assert "persona_summary" in first_decision
    assert first_decision["entry_or_exit_reason"]
    assert first_decision["chosen_action"] in {
        "watch", "enter", "raise_bid", "hold", "exit", "acquire", "skip",
    }
    assert first_decision["chosen_action_reason"]
    assert isinstance(first_decision["rejected_alternatives"], list)


@pytest.mark.asyncio
async def test_market_simulation_handoff_to_negotiation(client, db):
    seeded = await _seed_market_fixture(db)
    property_ids = [prop.id for prop in seeded["properties"]]

    start_resp = await client.post(
        "/api/simulation/market/start",
        json={
            "investor_count": 4,
            "tick_count": 3,
            "cohort_preset": "momentum",
            "scope": {"property_ids": property_ids},
        },
    )
    run_id = start_resp.json()["run_id"]

    for _ in range(20):
        status_resp = await client.get(f"/api/simulation/market/status/{run_id}")
        if status_resp.json()["status"] == "completed":
            break
        await asyncio.sleep(0.05)

    replay_resp = await client.get(f"/api/simulation/market/replay/{run_id}")
    replay_data = replay_resp.json()
    first_decision = next(
        decision
        for tick in replay_data["ticks"]
        for decision in tick["decisions"]
        if decision["property_id"]
    )

    handoff_resp = await client.post(
        "/api/simulation/market/handoff-to-negotiation",
        json={
            "run_id": run_id,
            "investor_id": first_decision["investor_id"],
            "property_id": first_decision["property_id"],
            "max_rounds": 6,
        },
    )
    assert handoff_resp.status_code == 202
    handoff_data = handoff_resp.json()
    assert handoff_data["property_id"] == first_decision["property_id"]
    assert handoff_data["investor_id"] == first_decision["investor_id"]
    assert handoff_data["simulation_id"]
    assert handoff_data["seeded_config"]["max_rounds"] == 6
