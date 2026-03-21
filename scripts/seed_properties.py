"""Seed the database with sample properties for development."""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.database import async_session, engine, Base
from db.models import Property, UserProfile


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        # Sample user
        user = UserProfile(
            name="Dev User",
            email="dev@test.com",
            role="buyer",
            budget_min=300000,
            budget_max=500000,
            life_stage="relocating",
            investment_goals={"primary": "residence", "secondary": "appreciation"},
            risk_tolerance="moderate",
            timeline_days=90,
            latitude=41.8781,
            longitude=-87.6298,
            zip_code="60614",
            preferred_types=["sfr", "condo"],
        )
        db.add(user)

        # Sample properties (Chicago area)
        properties = [
            Property(
                address="1842 W Armitage Ave, Chicago, IL 60622",
                latitude=41.9178, longitude=-87.6735,
                asking_price=485000, bedrooms=3, bathrooms=2, sqft=1800,
                property_type="sfr", status="active",
                disclosures={"known_defects": "none", "flood_zone": "no",
                             "hoa_fees": "0", "lead_paint": "no",
                             "environmental_hazards": "none"},
            ),
            Property(
                address="2105 N Damen Ave, Chicago, IL 60647",
                latitude=41.9207, longitude=-87.6776,
                asking_price=340000, bedrooms=2, bathrooms=1, sqft=1200,
                property_type="condo", status="active",
                disclosures={"known_defects": "minor foundation crack", "flood_zone": "no",
                             "hoa_fees": "350", "lead_paint": "no",
                             "environmental_hazards": "none"},
            ),
            Property(
                address="4521 N Sheridan Rd, Chicago, IL 60640",
                latitude=41.9667, longitude=-87.6553,
                asking_price=275000, bedrooms=2, bathrooms=1.5, sqft=1100,
                property_type="condo", status="active",
                disclosures={"known_defects": "none", "flood_zone": "no",
                             "hoa_fees": "425", "lead_paint": "no",
                             "environmental_hazards": "none"},
            ),
        ]
        for p in properties:
            db.add(p)

        await db.commit()
        print(f"Seeded 1 user and {len(properties)} properties.")


if __name__ == "__main__":
    asyncio.run(seed())
