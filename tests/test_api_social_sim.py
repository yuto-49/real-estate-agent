"""API-level tests for social simulation and household endpoints.

Uses httpx.AsyncClient against the FastAPI app with dependency overrides.
"""

import pytest
import pytest_asyncio
from typing import cast
from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db.models import (
    CommunicationStyle,
    HouseholdProfile,
    HouseholdSocialEdge,
    MiroFishReport,
    Property,
    SocialSimulationAction,
    SocialSimulationRun,
    UserProfile,
)
from main import app


# ── Fixtures ──


@pytest_asyncio.fixture
async def client(db, db_engine):
    """httpx AsyncClient with DB override."""
    # Override async_session used by API routers
    test_session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False,
    )

    # Patch all places that import async_session
    async def _override_session():
        async with test_session_factory() as session:
            yield session

    with (
        patch("api.households.async_session", test_session_factory),
        patch("api.social_simulation.async_session", test_session_factory),
        patch(
            "services.social_simulator.async_session",
            test_session_factory,
        ),
        patch(
            "services.social_report_bridge.async_session",
            test_session_factory,
        ),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test",
        ) as ac:
            yield ac


@pytest_asyncio.fixture
async def seeded_data(db):
    """Seed test data: user, property, households, edges."""
    user = UserProfile(
        name="API User",
        email="api_user@test.com",
        role="buyer",
        budget_max=500000,
        zip_code="60601",
    )
    db.add(user)
    await db.flush()

    prop = Property(
        seller_id=user.id,
        address="300 API St, Chicago, IL 60601",
        asking_price=350000,
        bedrooms=3,
        bathrooms=2,
        sqft=1500,
        property_type="condo",
        status="active",
    )
    db.add(prop)
    await db.flush()

    # Create 5 households
    households = []
    for i in range(5):
        h = HouseholdProfile(
            name=f"API Household {i}",
            zip_code="60601",
            income_band=["low", "moderate", "middle", "upper", "low"][i],
            household_size=2 + i,
            monthly_income=3000 + i * 1000,
            monthly_housing_cost=900 + i * 200,
            eviction_risk=round(0.1 + i * 0.05, 2),
            housing_market_sentiment=round(-0.3 + i * 0.15, 2),
            policy_support_score=round(-0.2 + i * 0.1, 2),
            neighborhood_satisfaction=round(0.3 + i * 0.1, 2),
            influence_weight=round(0.3 + i * 0.1, 2),
            communication_style=CommunicationStyle.VOCAL if i == 0 else CommunicationStyle.PASSIVE,
            opinion_stability=0.5,
            housing_type="renter" if i < 3 else "owner",
        )
        db.add(h)
        households.append(h)

    await db.flush()

    # Edges: simple chain
    for i in range(4):
        edge = HouseholdSocialEdge(
            source_id=households[i].id,
            target_id=households[i + 1].id,
            edge_weight=0.5,
            edge_type="neighbor",
        )
        db.add(edge)

    await db.commit()

    return {
        "user": user,
        "property": prop,
        "households": households,
    }


# ── Household API Tests ──


class TestHouseholdsAPI:

    @pytest.mark.asyncio
    async def test_list_households(self, client, seeded_data):
        resp = await client.get("/api/households/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 5
        assert len(data["households"]) == 5

    @pytest.mark.asyncio
    async def test_list_households_filter_zip(self, client, seeded_data):
        resp = await client.get(
            "/api/households/", params={"zip_code": "60601"},
        )
        assert resp.status_code == 200
        assert resp.json()["count"] == 5

    @pytest.mark.asyncio
    async def test_list_households_filter_income(
        self, client, seeded_data,
    ):
        resp = await client.get(
            "/api/households/", params={"income_band": "low"},
        )
        assert resp.status_code == 200
        # indices 0, 4 are "low"
        assert resp.json()["count"] == 2

    @pytest.mark.asyncio
    async def test_list_households_filter_housing_type(
        self, client, seeded_data,
    ):
        resp = await client.get(
            "/api/households/", params={"housing_type": "owner"},
        )
        assert resp.status_code == 200
        assert resp.json()["count"] == 2

    @pytest.mark.asyncio
    async def test_list_households_pagination(self, client, seeded_data):
        resp = await client.get(
            "/api/households/", params={"limit": 2, "offset": 0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["households"]) == 2
        assert data["count"] == 5  # total count unchanged

    @pytest.mark.asyncio
    async def test_get_single_household(self, client, seeded_data):
        h_id = cast(str, seeded_data["households"][0].id)
        resp = await client.get(f"/api/households/{h_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "API Household 0"
        assert data["zip_code"] == "60601"

    @pytest.mark.asyncio
    async def test_get_household_not_found(self, client, seeded_data):
        resp = await client.get("/api/households/nonexistent-id")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_household_stats(self, client, seeded_data):
        resp = await client.get("/api/households/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_households"] == 5
        assert data["total_social_edges"] == 4
        assert "income_distribution" in data
        assert "housing_type_distribution" in data
        assert "sentiment_averages" in data
        assert "edge_type_distribution" in data

    @pytest.mark.asyncio
    async def test_household_stats_empty(self, client, db):
        """Stats with no households returns guidance message."""
        resp = await client.get("/api/households/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert "seed" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_household_neighbors(self, client, seeded_data):
        h_id = cast(str, seeded_data["households"][0].id)
        resp = await client.get(f"/api/households/{h_id}/neighbors")
        assert resp.status_code == 200
        neighbors = resp.json()
        assert len(neighbors) >= 1
        for n in neighbors:
            assert "id" in n
            assert "name" in n
            assert "edges" in n

    @pytest.mark.asyncio
    async def test_household_neighbors_empty(self, client, db):
        """Household with no edges returns empty list."""
        h = HouseholdProfile(
            name="Lonely",
            zip_code="99999",
            income_band="low",
        )
        db.add(h)
        await db.commit()

        resp = await client.get(
            f"/api/households/{cast(str, h.id)}/neighbors",
        )
        assert resp.status_code == 200
        assert resp.json() == []


# ── Social Simulation API Tests ──


class TestSocialSimAPI:

    @pytest.mark.asyncio
    async def test_start_social_sim(self, client, seeded_data):
        """POST /api/social-sim/start returns run_id."""
        user_id = cast(str, seeded_data["user"].id)

        with patch(
            "api.social_simulation.start_social_simulation",
            new_callable=AsyncMock,
            return_value="test-run-123",
        ):
            resp = await client.post(
                "/api/social-sim/start",
                json={
                    "user_id": user_id,
                    "zip_code": "60601",
                    "max_rounds": 5,
                },
            )

        assert resp.status_code == 202
        data = resp.json()
        assert data["run_id"] == "test-run-123"
        assert data["status"] == "preparing"

    @pytest.mark.asyncio
    async def test_sim_status_from_db(self, client, db, seeded_data):
        """GET /api/social-sim/{run_id}/status reads from DB."""
        user_id = cast(str, seeded_data["user"].id)

        run = SocialSimulationRun(
            trigger_user_id=user_id,
            total_rounds=10,
            current_round=3,
            status="running",
            topics=["market_prices"],
        )
        db.add(run)
        await db.commit()
        run_id = cast(str, run.id)

        # Patch get_social_sim to return None (not in memory)
        with patch(
            "api.social_simulation.get_social_sim",
            return_value=None,
        ):
            resp = await client.get(
                f"/api/social-sim/{run_id}/status",
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == run_id
        assert data["status"] == "running"
        assert data["current_round"] == 3

    @pytest.mark.asyncio
    async def test_sim_status_from_memory(self, client, seeded_data):
        """GET status returns from in-memory cache when available."""
        with patch(
            "api.social_simulation.get_social_sim",
            return_value={
                "id": "mem-run-1",
                "status": "running",
                "current_round": 7,
                "total_rounds": 10,
                "action_count": 42,
            },
        ):
            resp = await client.get(
                "/api/social-sim/mem-run-1/status",
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["current_round"] == 7
        assert data["action_count"] == 42

    @pytest.mark.asyncio
    async def test_sim_status_not_found(self, client, seeded_data):
        with patch(
            "api.social_simulation.get_social_sim",
            return_value=None,
        ):
            resp = await client.get(
                "/api/social-sim/nonexistent/status",
            )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_sim_result_completed(self, client, db, seeded_data):
        """GET result for completed simulation."""
        user_id = cast(str, seeded_data["user"].id)

        run = SocialSimulationRun(
            trigger_user_id=user_id,
            total_rounds=5,
            current_round=5,
            status="completed",
            topics=["market_prices"],
            narrative_output={"market_prices": {"avg_opinion": 0.2}},
            sentiment_delta={"market_prices": {"shift": 0.1}},
        )
        db.add(run)
        await db.commit()
        run_id = cast(str, run.id)

        resp = await client.get(f"/api/social-sim/{run_id}/result")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_sim_result_still_running(
        self, client, db, seeded_data,
    ):
        """GET result for running simulation returns 409."""
        user_id = cast(str, seeded_data["user"].id)

        run = SocialSimulationRun(
            trigger_user_id=user_id,
            total_rounds=10,
            current_round=3,
            status="running",
            topics=["market_prices"],
        )
        db.add(run)
        await db.commit()
        run_id = cast(str, run.id)

        resp = await client.get(f"/api/social-sim/{run_id}/result")
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_sim_result_not_found(self, client, seeded_data):
        resp = await client.get(
            "/api/social-sim/nonexistent/result",
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_sim_actions(self, client, db, seeded_data):
        """GET actions returns paginated action log."""
        user_id = cast(str, seeded_data["user"].id)
        h_id = cast(str, seeded_data["households"][0].id)

        run = SocialSimulationRun(
            trigger_user_id=user_id,
            total_rounds=3,
            current_round=3,
            status="completed",
            topics=["market_prices"],
        )
        db.add(run)
        await db.flush()
        run_id = cast(str, run.id)

        # Add some actions
        for round_num in range(1, 4):
            action = SocialSimulationAction(
                run_id=run_id,
                round_num=round_num,
                household_id=h_id,
                action_type="post_opinion",
                topic="market_prices",
                content=f"Round {round_num} opinion.",
                sentiment_value=0.1 * round_num,
            )
            db.add(action)
        await db.commit()

        resp = await client.get(f"/api/social-sim/{run_id}/actions")
        assert resp.status_code == 200
        actions = resp.json()
        assert len(actions) == 3

    @pytest.mark.asyncio
    async def test_sim_actions_filter_round(
        self, client, db, seeded_data,
    ):
        """Filter actions by round_num."""
        user_id = cast(str, seeded_data["user"].id)
        h_id = cast(str, seeded_data["households"][0].id)

        run = SocialSimulationRun(
            trigger_user_id=user_id,
            total_rounds=3,
            status="completed",
            topics=["market_prices"],
        )
        db.add(run)
        await db.flush()
        run_id = cast(str, run.id)

        for rn in [1, 1, 2]:
            db.add(SocialSimulationAction(
                run_id=run_id,
                round_num=rn,
                household_id=h_id,
                action_type="post_opinion",
                topic="market_prices",
                content="opinion",
                sentiment_value=0.1,
            ))
        await db.commit()

        resp = await client.get(
            f"/api/social-sim/{run_id}/actions",
            params={"round_num": 1},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    @pytest.mark.asyncio
    async def test_sim_timeline(self, client, db, seeded_data):
        """GET timeline returns round-by-round aggregation."""
        user_id = cast(str, seeded_data["user"].id)
        h_id = cast(str, seeded_data["households"][0].id)

        run = SocialSimulationRun(
            trigger_user_id=user_id,
            total_rounds=3,
            status="completed",
            topics=["market_prices"],
        )
        db.add(run)
        await db.flush()
        run_id = cast(str, run.id)

        # Actions across rounds
        for rn, sentiment in [(1, 0.1), (1, 0.3), (2, 0.2), (2, 0.4)]:
            db.add(SocialSimulationAction(
                run_id=run_id,
                round_num=rn,
                household_id=h_id,
                action_type="update_stance",
                topic="market_prices",
                content="opinion",
                sentiment_value=sentiment,
            ))
        await db.commit()

        resp = await client.get(f"/api/social-sim/{run_id}/timeline")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == run_id
        assert len(data["timeline"]) == 2  # 2 rounds

        # Round 1: avg of 0.1, 0.3 = 0.2 → neutral
        r1 = data["timeline"][0]
        assert r1["round_num"] == 1
        assert abs(r1["avg_sentiment"] - 0.2) < 0.01
        assert r1["action_count"] == 2

        # Round 2: avg of 0.2, 0.4 = 0.3 → supportive
        r2 = data["timeline"][1]
        assert r2["round_num"] == 2
        assert r2["dominant_stance"] == "supportive"

    @pytest.mark.asyncio
    async def test_sim_timeline_not_found(self, client, seeded_data):
        user_id = cast(str, seeded_data["user"].id)

        run = SocialSimulationRun(
            trigger_user_id=user_id,
            total_rounds=3,
            status="completed",
            topics=["market_prices"],
        )

        resp = await client.get(
            "/api/social-sim/nonexistent/timeline",
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_generate_report(self, client, db, seeded_data):
        """POST generate-report creates a MiroFish report."""
        user_id = cast(str, seeded_data["user"].id)
        prop_id = cast(str, seeded_data["property"].id)
        h_id = cast(str, seeded_data["households"][0].id)

        with patch(
            "api.social_simulation.generate_report_from_social_sim",
            new_callable=AsyncMock,
            return_value="report-abc-123",
        ):
            resp = await client.post(
                "/api/social-sim/test-run/generate-report",
                json={
                    "property_id": prop_id,
                    "household_id": h_id,
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["report_id"] == "report-abc-123"

    @pytest.mark.asyncio
    async def test_generate_report_not_ready(
        self, client, db, seeded_data,
    ):
        """POST generate-report returns 409 when sim not done."""
        prop_id = cast(str, seeded_data["property"].id)
        h_id = cast(str, seeded_data["households"][0].id)

        with patch(
            "api.social_simulation.generate_report_from_social_sim",
            new_callable=AsyncMock,
            return_value=None,
        ):
            resp = await client.post(
                "/api/social-sim/running-run/generate-report",
                json={
                    "property_id": prop_id,
                    "household_id": h_id,
                },
            )

        assert resp.status_code == 409


# ── Health Check ──


class TestHealthEndpoint:

    @pytest.mark.asyncio
    async def test_health(self, client, seeded_data):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
