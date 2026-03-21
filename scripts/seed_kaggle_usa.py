"""Seed the database from the Kaggle USA Real Estate dataset.

Dataset: https://www.kaggle.com/datasets/ahmedshahriarsakib/usa-real-estate-dataset
Download with:
    pip install kagglehub
    python -c "import kagglehub; print(kagglehub.dataset_download('ahmedshahriarsakib/usa-real-estate-dataset'))"

Usage:
    python scripts/seed_kaggle_usa.py                          # default: 500 Chicago properties
    python scripts/seed_kaggle_usa.py --city "New York" --state "New York" --limit 300
    python scripts/seed_kaggle_usa.py --csv /path/to/realtor-data.zip.csv
"""

import argparse
import asyncio
import csv
import hashlib
import random
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.database import async_session, engine, Base
from db.models import Property, UserProfile

# ── Default CSV location (kagglehub cache) ──
DEFAULT_CSV = Path.home() / ".cache" / "kagglehub" / "datasets" / "ahmedshahriarsakib" / "usa-real-estate-dataset" / "versions" / "25" / "realtor-data.zip.csv"

# ── Chicago zip-code centroids (lat, lng) ──
ZIP_COORDS = {
    "60601": (41.8858, -87.6181), "60602": (41.8829, -87.6321),
    "60603": (41.8798, -87.6285), "60604": (41.8785, -87.6330),
    "60605": (41.8713, -87.6277), "60606": (41.8868, -87.6386),
    "60607": (41.8721, -87.6578), "60608": (41.8515, -87.6694),
    "60609": (41.8097, -87.6533), "60610": (41.9033, -87.6336),
    "60611": (41.8971, -87.6223), "60612": (41.8805, -87.6873),
    "60613": (41.9543, -87.6575), "60614": (41.9229, -87.6483),
    "60615": (41.8022, -87.6006), "60616": (41.8426, -87.6306),
    "60617": (41.7257, -87.5560), "60618": (41.9464, -87.7042),
    "60619": (41.7458, -87.6054), "60620": (41.7411, -87.6543),
    "60621": (41.7750, -87.6421), "60622": (41.9019, -87.6779),
    "60623": (41.8490, -87.7157), "60624": (41.8804, -87.7223),
    "60625": (41.9703, -87.7042), "60626": (42.0095, -87.6689),
    "60628": (41.6934, -87.6243), "60629": (41.7781, -87.7069),
    "60630": (41.9699, -87.7603), "60631": (41.9951, -87.8082),
    "60632": (41.8093, -87.7052), "60633": (41.6642, -87.5612),
    "60634": (41.9463, -87.8061), "60636": (41.7760, -87.6674),
    "60637": (41.7813, -87.6051), "60638": (41.7814, -87.7705),
    "60639": (41.9202, -87.7535), "60640": (41.9719, -87.6624),
    "60641": (41.9453, -87.7474), "60642": (41.9008, -87.6528),
    "60643": (41.6996, -87.6628), "60644": (41.8829, -87.7582),
    "60645": (42.0086, -87.6947), "60646": (41.9930, -87.7596),
    "60647": (41.9209, -87.7043), "60649": (41.7620, -87.5703),
    "60651": (41.9025, -87.7393), "60652": (41.7454, -87.7135),
    "60653": (41.8196, -87.6126), "60654": (41.8923, -87.6373),
    "60655": (41.6948, -87.7038), "60656": (41.9735, -87.8658),
    "60657": (41.9399, -87.6528), "60659": (41.9972, -87.7166),
    "60660": (41.9909, -87.6629), "60661": (41.8814, -87.6430),
    "60707": (41.9232, -87.8185), "60827": (41.6496, -87.6301),
}


def jitter(lat: float, lng: float) -> tuple[float, float]:
    """Add small random offset (~200m) so pins don't overlap exactly."""
    return (
        lat + random.uniform(-0.002, 0.002),
        lng + random.uniform(-0.002, 0.002),
    )


def infer_property_type(bed: int, house_size: float, acre_lot: float) -> str:
    if acre_lot > 1.0:
        return "land"
    if bed >= 5 or house_size >= 3000:
        return "sfr"
    if bed >= 3:
        return "sfr"
    if house_size < 900:
        return "condo"
    return "condo"


def parse_float(val: str) -> float | None:
    try:
        v = float(val)
        return v if v == v else None  # NaN check
    except (ValueError, TypeError):
        return None


def parse_int(val: str) -> int | None:
    f = parse_float(val)
    return int(f) if f is not None else None


def stable_hash(s: str) -> str:
    """Create a deterministic street-number-like string from raw data."""
    h = int(hashlib.md5(s.encode()).hexdigest()[:8], 16)
    return str(h % 99999)


async def seed(csv_path: Path, city: str, state: str, limit: int, clear: bool):
    if not csv_path.exists():
        print(f"CSV not found at {csv_path}")
        print("Download with: python -c \"import kagglehub; kagglehub.dataset_download('ahmedshahriarsakib/usa-real-estate-dataset')\"")
        sys.exit(1)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Collect matching rows from CSV
    rows: list[dict] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["city"] != city or row["state"] != state:
                continue
            if row["status"] != "for_sale":
                continue
            price = parse_float(row["price"])
            bed = parse_int(row["bed"])
            if not price or price <= 0 or not bed:
                continue
            if not row["zip_code"]:
                continue
            rows.append(row)

    if not rows:
        print(f"No matching rows for {city}, {state}")
        sys.exit(1)

    # Shuffle and cap
    random.shuffle(rows)
    rows = rows[:limit]

    print(f"Found {len(rows)} properties for {city}, {state} (capped at {limit})")

    async with async_session() as db:
        if clear:
            from sqlalchemy import text
            await db.execute(text("TRUNCATE TABLE properties CASCADE"))
            await db.flush()
            print("Cleared existing properties (CASCADE).")

        # Create a seller user for these properties
        seller_email = f"kaggle-seller-{city.lower().replace(' ', '-')}@platform.com"
        from sqlalchemy import select
        result = await db.execute(select(UserProfile).where(UserProfile.email == seller_email))
        seller = result.scalar_one_or_none()
        if not seller:
            seller = UserProfile(
                name=f"{city} Listings (Kaggle)",
                email=seller_email,
                role="seller",
                budget_min=0,
                budget_max=0,
                life_stage="investor",
                investment_goals={"primary": "liquidation", "source": "kaggle_usa_real_estate"},
                risk_tolerance="moderate",
                timeline_days=60,
                latitude=ZIP_COORDS.get(rows[0]["zip_code"], (41.8781, -87.6298))[0],
                longitude=ZIP_COORDS.get(rows[0]["zip_code"], (41.8781, -87.6298))[1],
                zip_code=rows[0]["zip_code"],
            )
            db.add(seller)
            await db.flush()
            print(f"Created seller: {seller.name} ({seller.id})")
        else:
            print(f"Using existing seller: {seller.name} ({seller.id})")

        count = 0
        skipped = 0
        for row in rows:
            price = parse_float(row["price"])
            bed = parse_int(row["bed"])
            bath = parse_float(row["bath"])
            house_size = parse_float(row["house_size"])
            acre_lot = parse_float(row["acre_lot"]) or 0.0
            zip_code = row["zip_code"]

            # Geocode from zip
            coords = ZIP_COORDS.get(zip_code)
            if not coords:
                skipped += 1
                continue

            lat, lng = jitter(coords[0], coords[1])

            # Build address
            street_num = stable_hash(f"{row['street']}_{row['zip_code']}_{row['price']}")
            address = f"{street_num} {city}, {state} {zip_code}"

            prop = Property(
                seller_id=seller.id,
                address=address,
                latitude=lat,
                longitude=lng,
                asking_price=price,
                bedrooms=bed,
                bathrooms=bath,
                sqft=int(house_size) if house_size else None,
                property_type=infer_property_type(bed or 2, house_size or 1000, acre_lot),
                status="active",
                disclosures={
                    "acre_lot": acre_lot,
                    "prev_sold_date": row.get("prev_sold_date", ""),
                    "known_defects": "none",
                    "flood_zone": "no",
                    "data_source": "kaggle_usa_real_estate",
                },
                neighborhood_data={
                    "zip_code": zip_code,
                    "city": city,
                    "state": state,
                },
            )
            db.add(prop)
            count += 1

        await db.commit()
        print(f"Seeded {count} properties. Skipped {skipped} (no coords for zip).")
        print(f"Seller ID: {seller.id}")


def main():
    parser = argparse.ArgumentParser(description="Seed database from Kaggle USA Real Estate dataset")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="Path to realtor-data.zip.csv")
    parser.add_argument("--city", default="Chicago", help="City to filter (default: Chicago)")
    parser.add_argument("--state", default="Illinois", help="State to filter (default: Illinois)")
    parser.add_argument("--limit", type=int, default=500, help="Max properties to seed (default: 500)")
    parser.add_argument("--clear", action="store_true", help="Clear existing properties before seeding")
    args = parser.parse_args()

    asyncio.run(seed(args.csv, args.city, args.state, args.limit, args.clear))


if __name__ == "__main__":
    main()
