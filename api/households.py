"""Household API — CRUD and statistics for synthetic household population."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import select, func

from api.schemas import HouseholdResponse, HouseholdListResponse
from db.database import async_session
from db.models import HouseholdProfile, HouseholdSocialEdge

router = APIRouter()


@router.get("/")
async def list_households(
    zip_code: str | None = None,
    income_band: str | None = None,
    housing_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> HouseholdListResponse:
    """List households with optional filters."""
    async with async_session() as db:
        query = select(HouseholdProfile).order_by(HouseholdProfile.created_at.desc())
        if zip_code:
            query = query.where(HouseholdProfile.zip_code == zip_code)
        if income_band:
            query = query.where(HouseholdProfile.income_band == income_band)
        if housing_type:
            query = query.where(HouseholdProfile.housing_type == housing_type)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0

        # Paginate
        query = query.offset(offset).limit(limit)
        result = await db.execute(query)
        households = result.scalars().all()

    items = [HouseholdResponse.model_validate(h) for h in households]
    return HouseholdListResponse(households=items, count=total)


@router.get("/stats")
async def household_stats():
    """Get aggregate statistics about the household population."""
    async with async_session() as db:
        # Total count
        total_result = await db.execute(select(func.count(HouseholdProfile.id)))
        total = total_result.scalar() or 0

        if total == 0:
            return {"total": 0, "message": "No households seeded. Run: python scripts/seed_households.py"}

        # Income distribution
        income_result = await db.execute(
            select(
                HouseholdProfile.income_band,
                func.count().label("count"),
                func.avg(HouseholdProfile.monthly_income).label("avg_income"),
            )
            .group_by(HouseholdProfile.income_band)
        )
        income_dist = {
            row.income_band: {"count": row.count, "avg_monthly_income": round(row.avg_income or 0, 2)}
            for row in income_result.all()
        }

        # Housing type distribution
        housing_result = await db.execute(
            select(
                HouseholdProfile.housing_type,
                func.count().label("count"),
            )
            .group_by(HouseholdProfile.housing_type)
        )
        housing_dist = {row.housing_type: row.count for row in housing_result.all()}

        # Zip code distribution
        zip_result = await db.execute(
            select(
                HouseholdProfile.zip_code,
                func.count().label("count"),
            )
            .group_by(HouseholdProfile.zip_code)
        )
        zip_dist = {row.zip_code: row.count for row in zip_result.all()}

        # Sentiment averages
        sentiment_result = await db.execute(
            select(
                func.avg(HouseholdProfile.housing_market_sentiment).label("avg_market_sentiment"),
                func.avg(HouseholdProfile.policy_support_score).label("avg_policy_support"),
                func.avg(HouseholdProfile.neighborhood_satisfaction).label("avg_satisfaction"),
                func.avg(HouseholdProfile.eviction_risk).label("avg_eviction_risk"),
            )
        )
        sentiment = sentiment_result.one()

        # Edge counts
        edge_result = await db.execute(select(func.count(HouseholdSocialEdge.id)))
        edge_count = edge_result.scalar() or 0

        edge_type_result = await db.execute(
            select(
                HouseholdSocialEdge.edge_type,
                func.count().label("count"),
            )
            .group_by(HouseholdSocialEdge.edge_type)
        )
        edge_types = {row.edge_type: row.count for row in edge_type_result.all()}

    return {
        "total_households": total,
        "total_social_edges": edge_count,
        "avg_edges_per_household": round(edge_count * 2 / total, 1) if total > 0 else 0,
        "income_distribution": income_dist,
        "housing_type_distribution": housing_dist,
        "zip_code_distribution": zip_dist,
        "sentiment_averages": {
            "market_sentiment": round(sentiment.avg_market_sentiment or 0, 4),
            "policy_support": round(sentiment.avg_policy_support or 0, 4),
            "neighborhood_satisfaction": round(sentiment.avg_satisfaction or 0, 4),
            "eviction_risk": round(sentiment.avg_eviction_risk or 0, 4),
        },
        "edge_type_distribution": edge_types,
    }


@router.get("/{household_id}")
async def get_household(household_id: str) -> HouseholdResponse:
    """Get a single household by ID."""
    async with async_session() as db:
        result = await db.execute(
            select(HouseholdProfile).where(HouseholdProfile.id == household_id)
        )
        household = result.scalar_one_or_none()

    if not household:
        raise HTTPException(status_code=404, detail="Household not found")

    return HouseholdResponse.model_validate(household)


@router.get("/{household_id}/neighbors")
async def get_household_neighbors(household_id: str) -> list[dict]:
    """Get social graph neighbors for a household."""
    async with async_session() as db:
        # Edges where this household is source or target
        edges_result = await db.execute(
            select(HouseholdSocialEdge).where(
                (HouseholdSocialEdge.source_id == household_id)
                | (HouseholdSocialEdge.target_id == household_id)
            )
        )
        edges = edges_result.scalars().all()

        # Collect neighbor IDs
        neighbor_ids = set()
        edge_map: dict[str, list[dict]] = {}
        for edge in edges:
            nid = edge.target_id if edge.source_id == household_id else edge.source_id
            neighbor_ids.add(nid)
            edge_map.setdefault(nid, []).append({
                "edge_type": edge.edge_type,
                "weight": edge.edge_weight,
            })

        if not neighbor_ids:
            return []

        # Load neighbor profiles
        neighbors_result = await db.execute(
            select(HouseholdProfile).where(HouseholdProfile.id.in_(neighbor_ids))
        )
        neighbors = {n.id: n for n in neighbors_result.scalars().all()}

    result = []
    for nid, edges_info in edge_map.items():
        n = neighbors.get(nid)
        if not n:
            continue
        result.append({
            "id": n.id,
            "name": n.name,
            "income_band": n.income_band,
            "housing_type": n.housing_type,
            "zip_code": n.zip_code,
            "market_sentiment": n.housing_market_sentiment,
            "policy_support": n.policy_support_score,
            "edges": edges_info,
        })

    return result
