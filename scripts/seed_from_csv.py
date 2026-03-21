"""Seed the database from the Real Estate Valuation CSV dataset."""

import asyncio
import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.database import async_session, engine, Base
from db.models import Property, UserProfile

CSV_PATH = Path.home() / "Downloads" / "Real estate valuation data set.csv"

# Conversion constants
NTD_TO_USD = 0.032          # approximate NTD → USD
PING_TO_SQFT = 35.58        # 1 ping ≈ 35.58 sqft
DEFAULT_SQFT = 900           # fallback unit size in sqft
PRICE_MULTIPLIER = 10_000    # Y column is in units of 10k NTD


def estimate_usd_price(price_per_unit_area: float, sqft: int = DEFAULT_SQFT) -> float:
    """Convert NTD-per-ping to a total USD price."""
    pings = sqft / PING_TO_SQFT
    total_ntd = price_per_unit_area * PRICE_MULTIPLIER * pings
    return round(total_ntd * NTD_TO_USD, -3)


def infer_property_type(house_age: float) -> str:
    if house_age < 10:
        return "condo"
    elif house_age < 25:
        return "condo"
    else:
        return "sfr"


def infer_bedrooms(price_per_unit: float) -> int:
    if price_per_unit > 50:
        return 3
    elif price_per_unit > 30:
        return 2
    return 1


async def seed():
    if not CSV_PATH.exists():
        print(f"CSV not found at {CSV_PATH}")
        print("Place 'Real estate valuation data set.csv' in ~/Downloads/")
        sys.exit(1)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        # --- Users ---
        buyer = UserProfile(
            name="Test Buyer",
            email="buyer@test.com",
            role="buyer",
            budget_min=150_000,
            budget_max=500_000,
            life_stage="relocating",
            investment_goals={"primary": "residence", "secondary": "appreciation"},
            risk_tolerance="moderate",
            timeline_days=90,
            latitude=24.975,
            longitude=121.540,
            zip_code="10608",
            preferred_types=["sfr", "condo"],
        )
        seller = UserProfile(
            name="Test Seller",
            email="seller@test.com",
            role="seller",
            budget_min=0,
            budget_max=0,
            life_stage="investor",
            investment_goals={"primary": "liquidation"},
            risk_tolerance="moderate",
            timeline_days=60,
            latitude=24.975,
            longitude=121.540,
            zip_code="10608",
        )
        db.add(buyer)
        db.add(seller)
        await db.flush()

        # --- Properties from CSV ---
        count = 0
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                price_per_unit = float(row["Y house price of unit area"])
                house_age = float(row["X2 house age"])
                lat = float(row["X5 latitude"])
                lng = float(row["X6 longitude"])
                mrt_distance = float(row["X3 distance to the nearest MRT station"])
                stores = int(row["X4 number of convenience stores"])

                sqft = DEFAULT_SQFT
                usd_price = estimate_usd_price(price_per_unit, sqft)

                prop = Property(
                    seller_id=seller.id,
                    address=f"Taipei #{row['No'].strip()}, {mrt_distance:.0f}m from MRT",
                    latitude=lat,
                    longitude=lng,
                    asking_price=usd_price,
                    bedrooms=infer_bedrooms(price_per_unit),
                    bathrooms=1,
                    sqft=sqft,
                    property_type=infer_property_type(house_age),
                    status="active",
                    disclosures={
                        "house_age_years": house_age,
                        "mrt_distance_meters": mrt_distance,
                        "nearby_convenience_stores": stores,
                        "known_defects": "none",
                        "flood_zone": "no",
                    },
                    neighborhood_data={
                        "convenience_stores": stores,
                        "mrt_distance_m": mrt_distance,
                        "price_per_unit_area_ntd": price_per_unit,
                    },
                )
                db.add(prop)
                count += 1

        await db.commit()
        print(f"Seeded 2 users (buyer + seller) and {count} properties from CSV.")


if __name__ == "__main__":
    asyncio.run(seed())
