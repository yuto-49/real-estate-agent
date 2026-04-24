"""Offer API tests for the normalized negotiation ledger shape."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db.database import get_db
from db.models import Negotiation, NegotiationStatus, Property, UserProfile
from main import app


@pytest_asyncio.fixture
async def client(db_engine):
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
async def seeded_offer_context(db):
    buyer = UserProfile(
        name="Offer Buyer",
        email="offer_buyer@test.com",
        role="buyer",
        budget_max=500000,
    )
    second_buyer = UserProfile(
        name="Offer Buyer Two",
        email="offer_buyer_two@test.com",
        role="buyer",
        budget_max=500000,
    )
    seller = UserProfile(
        name="Offer Seller",
        email="offer_seller@test.com",
        role="seller",
    )
    db.add_all([buyer, second_buyer, seller])
    await db.flush()

    prop = Property(
        seller_id=seller.id,
        address="222 Offer Ledger Way, Chicago, IL 60601",
        asking_price=420000,
        property_type="condo",
    )
    db.add(prop)
    await db.flush()

    negotiation = Negotiation(
        property_id=prop.id,
        buyer_id=buyer.id,
        seller_id=seller.id,
        status=NegotiationStatus.IDLE,
    )
    other_negotiation = Negotiation(
        property_id=prop.id,
        buyer_id=second_buyer.id,
        seller_id=seller.id,
        status=NegotiationStatus.IDLE,
    )
    db.add_all([negotiation, other_negotiation])
    await db.commit()

    return {
        "buyer": buyer,
        "second_buyer": second_buyer,
        "seller": seller,
        "property": prop,
        "negotiation": negotiation,
        "other_negotiation": other_negotiation,
    }


class TestOfferLedgerAPI:
    @pytest.mark.asyncio
    async def test_create_offer_accepts_ledger_fields(
        self, client, seeded_offer_context,
    ):
        buyer = seeded_offer_context["buyer"]
        negotiation = seeded_offer_context["negotiation"]
        prop = seeded_offer_context["property"]

        resp = await client.post(
            "/api/offers/",
            json={
                "property_id": prop.id,
                "buyer_id": buyer.id,
                "negotiation_id": negotiation.id,
                "actor_role": "buyer",
                "actor_user_id": buyer.id,
                "offer_price": 400000,
                "message": "Ledger-backed API offer",
            },
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["negotiation_id"] == negotiation.id
        assert data["actor_role"] == "buyer"
        assert data["actor_user_id"] == buyer.id
        assert data["message"] == "Ledger-backed API offer"

    @pytest.mark.asyncio
    async def test_list_offers_filters_by_negotiation_id(
        self, client, seeded_offer_context,
    ):
        prop = seeded_offer_context["property"]
        buyer = seeded_offer_context["buyer"]
        second_buyer = seeded_offer_context["second_buyer"]
        negotiation = seeded_offer_context["negotiation"]
        other_negotiation = seeded_offer_context["other_negotiation"]

        first_resp = await client.post(
            "/api/offers/",
            json={
                "property_id": prop.id,
                "buyer_id": buyer.id,
                "negotiation_id": negotiation.id,
                "actor_role": "buyer",
                "actor_user_id": buyer.id,
                "offer_price": 401000,
            },
        )
        assert first_resp.status_code == 201

        second_resp = await client.post(
            "/api/offers/",
            json={
                "property_id": prop.id,
                "buyer_id": second_buyer.id,
                "negotiation_id": other_negotiation.id,
                "actor_role": "buyer",
                "actor_user_id": second_buyer.id,
                "offer_price": 415000,
            },
        )
        assert second_resp.status_code == 201

        resp = await client.get(
            "/api/offers/",
            params={"negotiation_id": negotiation.id},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["negotiation_id"] == negotiation.id
        assert data[0]["actor_user_id"] == buyer.id
