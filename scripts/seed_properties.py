"""Seed the database with sample properties for development."""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select

from db.database import async_session, engine, Base
from db.models import Property, UserProfile


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        # Sample user — skip if already exists (idempotent re-run)
        existing = await db.execute(
            select(UserProfile).where(UserProfile.email == "dev@test.com")
        )
        if existing.scalar_one_or_none() is None:
            user = UserProfile(
                name="Dev User",
                email="dev@test.com",
                role="buyer",
                budget_min=30_000_000,
                budget_max=50_000_000,
                life_stage="relocating",
                investment_goals={"primary": "residence", "secondary": "appreciation"},
                risk_tolerance="moderate",
                timeline_days=90,
                latitude=35.6762,
                longitude=139.6503,
                zip_code="1060032",
                preferred_types=["mansion", "aparuto"],
            )
            db.add(user)
            print("Created dev user.")
        else:
            print("Dev user already exists — skipped.")

        # Sample properties (Tokyo area)
        properties = [
            Property(
                address="東京都板橋区板橋1-42-5",
                latitude=35.7520, longitude=139.7104,
                asking_price=28_000_000, bedrooms=1, bathrooms=1, sqft=25,
                property_type="aparuto", status="active",
                disclosures={"known_defects": "none", "flood_zone": "no",
                             "seismic": "shin_taishin", "structure": "rc"},
            ),
            Property(
                address="東京都杉並区阿佐谷南3-12-8",
                latitude=35.7045, longitude=139.6355,
                asking_price=45_000_000, bedrooms=2, bathrooms=1, sqft=55,
                property_type="mansion", status="active",
                disclosures={"known_defects": "none", "flood_zone": "no",
                             "seismic": "shin_taishin", "structure": "src"},
            ),
            Property(
                address="東京都練馬区豊玉北5-20-11",
                latitude=35.7380, longitude=139.6540,
                asking_price=35_000_000, bedrooms=2, bathrooms=1, sqft=45,
                property_type="aparuto", status="active",
                disclosures={"known_defects": "none", "flood_zone": "no",
                             "seismic": "shin_taishin", "structure": "light_steel"},
            ),
        ]
        for p in properties:
            db.add(p)

        await db.commit()
        print(f"Seeded {len(properties)} properties.")


if __name__ == "__main__":
    asyncio.run(seed())
