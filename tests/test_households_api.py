"""Households API endpoint tests.

Covers: listing, filtering, stats, single household, neighbors.
"""

import pytest
from typing import cast

from db.models import (
    CommunicationStyle,
    HouseholdProfile,
    HouseholdSocialEdge,
)
from sqlalchemy import select, func


# ── Fixtures ──


@pytest.fixture
async def seeded_households(db):
    """Seed 10 households across 2 zip codes with social edges."""
    households = []
    for i in range(10):
        zip_code = "60601" if i < 6 else "60614"
        income_band = ["low", "moderate", "middle", "upper"][i % 4]
        housing = ["renter", "owner", "voucher"][i % 3]
        h = HouseholdProfile(
            name=f"Household {i}",
            zip_code=zip_code,
            income_band=income_band,
            household_size=2 + (i % 3),
            num_children=i % 2,
            primary_language="english" if i < 7 else "spanish",
            age_bracket="30-45",
            housing_type=housing,
            has_housing_voucher=1 if housing == "voucher" else 0,
            monthly_housing_cost=1000 + i * 100,
            monthly_income=3000 + i * 500,
            eviction_risk=round(0.05 + i * 0.03, 2),
            housing_market_sentiment=round(-0.5 + i * 0.1, 2),
            policy_support_score=round(-0.3 + i * 0.07, 2),
            neighborhood_satisfaction=round(0.3 + i * 0.06, 2),
            influence_weight=round(0.2 + i * 0.08, 2),
            communication_style=CommunicationStyle.VOCAL if i < 3 else CommunicationStyle.PASSIVE,
            social_connections=2 + i,
            opinion_stability=round(0.3 + i * 0.05, 2),
        )
        db.add(h)
        households.append(h)

    await db.flush()

    # Create edges: chain + some cross edges
    edges = []
    for i in range(9):
        edge = HouseholdSocialEdge(
            source_id=households[i].id,
            target_id=households[i + 1].id,
            edge_weight=0.5,
            edge_type="neighbor" if i < 5 else "income_peer",
        )
        db.add(edge)
        edges.append(edge)

    # Cross edges
    for src, tgt, etype in [(0, 5, "demographic"), (2, 7, "language_peer")]:
        edge = HouseholdSocialEdge(
            source_id=households[src].id,
            target_id=households[tgt].id,
            edge_weight=0.3,
            edge_type=etype,
        )
        db.add(edge)
        edges.append(edge)

    await db.commit()
    return {"households": households, "edges": edges}


# ── Model-Level Tests (DB layer) ──


class TestHouseholdModel:

    @pytest.mark.asyncio
    async def test_create_household(self, db):
        h = HouseholdProfile(
            name="Test Family",
            zip_code="60601",
            income_band="moderate",
            monthly_income=4500.0,
            monthly_housing_cost=1200.0,
        )
        db.add(h)
        await db.commit()
        await db.refresh(h)

        assert h.id is not None
        assert h.name == "Test Family"
        assert h.income_band == "moderate"

    @pytest.mark.asyncio
    async def test_social_edge_creation(self, db):
        h1 = HouseholdProfile(
            name="Source", zip_code="60601", income_band="low",
        )
        h2 = HouseholdProfile(
            name="Target", zip_code="60601", income_band="low",
        )
        db.add_all([h1, h2])
        await db.flush()

        edge = HouseholdSocialEdge(
            source_id=h1.id,
            target_id=h2.id,
            edge_weight=0.7,
            edge_type="neighbor",
        )
        db.add(edge)
        await db.commit()

        assert edge.id is not None
        assert edge.edge_type == "neighbor"
        assert edge.edge_weight == 0.7


# ── Query Tests (simulating API logic) ──


class TestHouseholdFiltering:

    @pytest.mark.asyncio
    async def test_filter_by_zip_code(self, db, seeded_households):
        result = await db.execute(
            select(HouseholdProfile)
            .where(HouseholdProfile.zip_code == "60601")
        )
        households = result.scalars().all()
        assert len(households) == 6

    @pytest.mark.asyncio
    async def test_filter_by_income_band(self, db, seeded_households):
        result = await db.execute(
            select(HouseholdProfile)
            .where(HouseholdProfile.income_band == "low")
        )
        households = result.scalars().all()
        # Indices 0, 4, 8 → low band
        assert len(households) == 3

    @pytest.mark.asyncio
    async def test_filter_by_housing_type(self, db, seeded_households):
        result = await db.execute(
            select(HouseholdProfile)
            .where(HouseholdProfile.housing_type == "voucher")
        )
        households = result.scalars().all()
        # Indices 2, 5, 8 → voucher
        assert len(households) == 3

    @pytest.mark.asyncio
    async def test_pagination(self, db, seeded_households):
        result = await db.execute(
            select(HouseholdProfile)
            .order_by(HouseholdProfile.created_at.desc())
            .offset(3)
            .limit(3)
        )
        households = result.scalars().all()
        assert len(households) == 3

    @pytest.mark.asyncio
    async def test_combined_filters(self, db, seeded_households):
        result = await db.execute(
            select(HouseholdProfile)
            .where(
                HouseholdProfile.zip_code == "60601",
                HouseholdProfile.income_band == "moderate",
            )
        )
        households = result.scalars().all()
        # 60601 indices: 0-5, moderate = index 1, 5 → 2 households
        assert len(households) == 2


# ── Stats Tests ──


class TestHouseholdStats:

    @pytest.mark.asyncio
    async def test_total_count(self, db, seeded_households):
        result = await db.execute(
            select(func.count(HouseholdProfile.id))
        )
        total = result.scalar()
        assert total == 10

    @pytest.mark.asyncio
    async def test_income_distribution(self, db, seeded_households):
        result = await db.execute(
            select(
                HouseholdProfile.income_band,
                func.count().label("count"),
                func.avg(HouseholdProfile.monthly_income).label("avg_income"),
            )
            .group_by(HouseholdProfile.income_band)
        )
        rows = result.all()
        dist = {row.income_band: row.count for row in rows}

        assert dist["low"] == 3
        assert dist["moderate"] == 3
        assert dist["middle"] == 2
        assert dist["upper"] == 2

    @pytest.mark.asyncio
    async def test_edge_count(self, db, seeded_households):
        result = await db.execute(
            select(func.count(HouseholdSocialEdge.id))
        )
        count = result.scalar()
        # 9 chain edges + 2 cross edges = 11
        assert count == 11

    @pytest.mark.asyncio
    async def test_edge_type_distribution(self, db, seeded_households):
        result = await db.execute(
            select(
                HouseholdSocialEdge.edge_type,
                func.count().label("count"),
            )
            .group_by(HouseholdSocialEdge.edge_type)
        )
        dist = {row.edge_type: row.count for row in result.all()}

        assert "neighbor" in dist
        assert "income_peer" in dist
        assert "demographic" in dist
        assert "language_peer" in dist

    @pytest.mark.asyncio
    async def test_sentiment_averages(self, db, seeded_households):
        result = await db.execute(
            select(
                func.avg(HouseholdProfile.housing_market_sentiment),
                func.avg(HouseholdProfile.policy_support_score),
                func.avg(HouseholdProfile.neighborhood_satisfaction),
            )
        )
        row = result.one()
        # All averages should be in valid range
        assert -1.0 <= row[0] <= 1.0
        assert -1.0 <= row[1] <= 1.0
        assert 0.0 <= row[2] <= 1.0


# ── Neighbor Query Tests ──


class TestNeighborQuery:

    @pytest.mark.asyncio
    async def test_get_neighbors_for_household(
        self, db, seeded_households,
    ):
        h0 = seeded_households["households"][0]
        h0_id = cast(str, h0.id)

        # Query edges where h0 is source or target
        result = await db.execute(
            select(HouseholdSocialEdge).where(
                (HouseholdSocialEdge.source_id == h0_id)
                | (HouseholdSocialEdge.target_id == h0_id)
            )
        )
        edges = result.scalars().all()

        # h0 has edges to h1 (chain) and h5 (demographic)
        assert len(edges) == 2

        edge_types = {cast(str, e.edge_type) for e in edges}
        assert "neighbor" in edge_types
        assert "demographic" in edge_types

    @pytest.mark.asyncio
    async def test_isolated_household_has_no_neighbors(self, db):
        h = HouseholdProfile(
            name="Isolated",
            zip_code="99999",
            income_band="low",
        )
        db.add(h)
        await db.flush()

        result = await db.execute(
            select(HouseholdSocialEdge).where(
                (HouseholdSocialEdge.source_id == h.id)
                | (HouseholdSocialEdge.target_id == h.id)
            )
        )
        edges = result.scalars().all()
        assert len(edges) == 0

    @pytest.mark.asyncio
    async def test_bidirectional_edge_discovery(
        self, db, seeded_households,
    ):
        """Edges should be found whether household is source or target."""
        h1 = seeded_households["households"][1]
        h1_id = cast(str, h1.id)

        result = await db.execute(
            select(HouseholdSocialEdge).where(
                (HouseholdSocialEdge.source_id == h1_id)
                | (HouseholdSocialEdge.target_id == h1_id)
            )
        )
        edges = result.scalars().all()

        # h1 is target of h0→h1, source of h1→h2
        assert len(edges) == 2
