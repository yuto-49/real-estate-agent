"""Negotiation API contract tests."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import cast

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db.database import get_db
from db.models import Negotiation, NegotiationStatus, Property, UserProfile
from main import app


@pytest_asyncio.fixture
async def client(db_engine):
    """httpx AsyncClient with DB dependency override for negotiation routes."""
    test_session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False,
    )

    async def _override_db():
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seeded_negotiation(db):
    """Seed a buyer, seller, property, and idle negotiation."""
    buyer = UserProfile(
        name="API Buyer",
        email="api_buyer@test.com",
        role="buyer",
        budget_max=500000,
    )
    seller = UserProfile(
        name="API Seller",
        email="api_seller@test.com",
        role="seller",
    )
    db.add_all([buyer, seller])
    await db.flush()

    prop = Property(
        seller_id=buyer.id,
        address="101 Contract Ave, Chicago, IL 60601",
        asking_price=400000,
        property_type="condo",
        status="active",
    )
    db.add(prop)
    await db.flush()

    negotiation = Negotiation(
        property_id=prop.id,
        buyer_id=buyer.id,
        seller_id=seller.id,
        status=NegotiationStatus.IDLE,
    )
    db.add(negotiation)
    await db.commit()

    return {
        "buyer": buyer,
        "seller": seller,
        "property": prop,
        "negotiation": negotiation,
    }


class TestNegotiationAPI:
    @pytest.mark.asyncio
    async def test_offer_endpoint_accepts_typed_json_body(
        self, client, seeded_negotiation,
    ):
        negotiation_id = cast(str, seeded_negotiation["negotiation"].id)

        resp = await client.post(
            f"/api/negotiations/{negotiation_id}/offer",
            json={
                "offer_price": 370000,
                "from_role": "buyer",
                "message": "Opening offer from the buyer.",
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "place_offer"
        assert data["old_status"] == "idle"
        assert data["new_status"] == "offer_pending"
        assert data["round_count"] == 1
        assert data["offer_price"] == 370000
        assert data["analysis"]["status"] == "insufficient_data"

    @pytest.mark.asyncio
    async def test_get_negotiation_returns_canonical_session_model(
        self, client, seeded_negotiation,
    ):
        negotiation_id = cast(str, seeded_negotiation["negotiation"].id)

        await client.post(
            f"/api/negotiations/{negotiation_id}/offer",
            json={
                "offer_price": 370000,
                "from_role": "buyer",
                "message": "Opening offer from the buyer.",
            },
        )

        resp = await client.get(f"/api/negotiations/{negotiation_id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == negotiation_id
        assert data["status"] == "offer_pending"
        assert data["round_count"] == 1
        assert len(data["offer_history"]) == 1
        assert data["offer_history"][0]["actor_role"] == "buyer"
        assert data["offer_history"][0]["message"] == "Opening offer from the buyer."
        assert "current_analysis" in data
        assert len(data["events"]) >= 1

    @pytest.mark.asyncio
    async def test_accept_and_transition_endpoints_use_typed_contracts(
        self, client, seeded_negotiation,
    ):
        negotiation_id = cast(str, seeded_negotiation["negotiation"].id)

        await client.post(
            f"/api/negotiations/{negotiation_id}/offer",
            json={
                "offer_price": 382000,
                "from_role": "buyer",
                "message": "Best and final.",
            },
        )

        accept_resp = await client.post(
            f"/api/negotiations/{negotiation_id}/accept",
            json={
                "from_role": "seller",
                "final_price": 382000,
            },
        )
        assert accept_resp.status_code == 200
        accept_data = accept_resp.json()
        assert accept_data["action"] == "accept"
        assert accept_data["old_status"] == "offer_pending"
        assert accept_data["new_status"] == "accepted"

        transition_resp = await client.post(
            f"/api/negotiations/{negotiation_id}/transition",
            json={
                "action": "generate_contract",
                "from_role": "broker",
                "message": "Move to contract drafting.",
            },
        )
        assert transition_resp.status_code == 200
        transition_data = transition_resp.json()
        assert transition_data["action"] == "generate_contract"
        assert transition_data["old_status"] == "accepted"
        assert transition_data["new_status"] == "contract_phase"

    @pytest.mark.asyncio
    async def test_offer_not_found_maps_to_404(self, client):
        resp = await client.post(
            "/api/negotiations/missing-negotiation/offer",
            json={
                "offer_price": 350000,
                "from_role": "buyer",
            },
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_expired_negotiation_maps_to_409(
        self, client, db, seeded_negotiation,
    ):
        negotiation = seeded_negotiation["negotiation"]
        negotiation.status = NegotiationStatus.OFFER_PENDING
        negotiation.deadline_at = datetime.utcnow() - timedelta(hours=1)
        db.add(negotiation)
        await db.commit()

        resp = await client.post(
            f"/api/negotiations/{cast(str, negotiation.id)}/offer",
            json={
                "offer_price": 390000,
                "from_role": "seller",
            },
        )

        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_invalid_role_rejected_by_schema(
        self, client, seeded_negotiation,
    ):
        negotiation_id = cast(str, seeded_negotiation["negotiation"].id)

        resp = await client.post(
            f"/api/negotiations/{negotiation_id}/offer",
            json={
                "offer_price": 370000,
                "from_role": "assistant",
            },
        )

        assert resp.status_code == 422
