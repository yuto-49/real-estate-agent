"""Seed the database from the Kaggle Chicago 2024 Real Estate dataset.

Dataset: https://www.kaggle.com/datasets/kanchana1990/real-estate-data-chicago-2024
Download with:
    pip install kagglehub
    python -c "import kagglehub; print(kagglehub.dataset_download('kanchana1990/real-estate-data-chicago-2024'))"

Usage:
    python scripts/seed_kaggle_chicago_2024.py                        # default: full dataset
    python scripts/seed_kaggle_chicago_2024.py --limit 200
    python scripts/seed_kaggle_chicago_2024.py --csv tests/fixtures/chicago_2024_sample.csv --limit 50
    python scripts/seed_kaggle_chicago_2024.py --clear                # wipe existing properties first
"""

import argparse
import asyncio
import csv
import hashlib
import random
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.database import Base, async_session, engine
from db.models import Property, UserProfile

# ── Default CSV locations ──
KAGGLEHUB_CSV = (
    Path.home()
    / ".cache"
    / "kagglehub"
    / "datasets"
    / "kanchana1990"
    / "real-estate-data-chicago-2024"
    / "versions"
    / "1"
    / "real_estate_data_chicago.csv"
)
FIXTURE_CSV = PROJECT_ROOT / "tests" / "fixtures" / "chicago_2024_sample.csv"

# ── Chicago zip-code centroids (lat, lng) — reused from seed_kaggle_usa.py ──
ZIP_COORDS: dict[str, tuple[float, float]] = {
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

# ── Neighborhood → zip code mapping (extracted from listing text patterns) ──
NEIGHBORHOOD_ZIPS: dict[str, str] = {
    "loop": "60601", "south loop": "60605", "west loop": "60607",
    "river north": "60654", "gold coast": "60610", "old town": "60610",
    "lincoln park": "60614", "lakeview": "60657", "wrigleyville": "60613",
    "bucktown": "60622", "wicker park": "60622", "logan square": "60647",
    "humboldt park": "60647", "ukrainian village": "60622",
    "pilsen": "60608", "bridgeport": "60609", "chinatown": "60616",
    "hyde park": "60615", "kenwood": "60615", "bronzeville": "60653",
    "uptown": "60640", "edgewater": "60660", "rogers park": "60626",
    "andersonville": "60640", "ravenswood": "60625", "albany park": "60625",
    "irving park": "60618", "avondale": "60618", "portage park": "60634",
    "jefferson park": "60630", "edgebrook": "60646", "norwood park": "60631",
    "mount greenwood": "60655", "beverly": "60643", "morgan park": "60643",
    "chatham": "60619", "south shore": "60649", "woodlawn": "60637",
    "austin": "60644", "garfield park": "60624", "englewood": "60621",
    "back of the yards": "60609", "little village": "60623",
    "south chicago": "60617", "hegewisch": "60633",
    "clearing": "60638", "archer heights": "60632",
    "gage park": "60629", "marquette park": "60629",
    "north center": "60618", "roscoe village": "60618",
    "noble square": "60622", "east village": "60622",
    "streeterville": "60611", "near north": "60610",
    "west town": "60622", "hermosa": "60639",
}

ALL_ZIPS = list(ZIP_COORDS.keys())


def extract_zip_from_text(text: str) -> str:
    """Try to extract a Chicago zip code from the listing description text."""
    # Look for neighborhood names in the text
    text_lower = text.lower()
    for neighborhood, zip_code in NEIGHBORHOOD_ZIPS.items():
        if neighborhood in text_lower:
            return zip_code

    # Fallback: assign deterministically from text hash
    h = int(hashlib.sha256(text[:80].encode()).hexdigest()[:8], 16)
    return ALL_ZIPS[h % len(ALL_ZIPS)]


def jitter(lat: float, lng: float) -> tuple[float, float]:
    """Add small random offset (~200m) so pins don't overlap exactly."""
    return (
        lat + random.uniform(-0.002, 0.002),
        lng + random.uniform(-0.002, 0.002),
    )


def map_property_type(kaggle_type: str) -> str:
    """Map Kaggle type field to our Property.property_type values."""
    mapping = {
        "single_family": "sfr",
        "condos": "condo",
        "townhomes": "condo",
        "multi_family": "multifamily",
        "apartment": "condo",
        "mobile": "sfr",
        "land": "land",
    }
    return mapping.get(kaggle_type, "sfr")


def stable_address(text: str, zip_code: str, idx: int) -> str:
    """Generate a deterministic street address from listing text."""
    h = int(hashlib.md5(text[:60].encode()).hexdigest()[:8], 16)
    street_num = (h % 9000) + 100
    # Extract a street name hint from text, fallback to generic
    street_match = re.search(
        r"(\d+\s+[NSEW]\.?\s+[\w]+(?:\s+(?:Ave|St|Blvd|Dr|Rd|Ct|Pl|Way)))",
        text,
    )
    if street_match:
        return f"{street_match.group(1)}, Chicago, IL {zip_code}"
    streets = [
        "Michigan Ave", "State St", "Clark St", "Damen Ave",
        "Western Ave", "Ashland Ave", "Halsted St", "Broadway",
        "Division St", "Fullerton Ave", "Belmont Ave", "Irving Park Rd",
    ]
    street = streets[idx % len(streets)]
    return f"{street_num} {street}, Chicago, IL {zip_code}"


def parse_float(val: str) -> float | None:
    try:
        v = float(val)
        return v if v == v else None  # NaN check
    except (ValueError, TypeError):
        return None


def parse_int(val: str) -> int | None:
    f = parse_float(val)
    return int(f) if f is not None else None


async def seed(csv_path: Path, limit: int, clear: bool) -> None:
    if not csv_path.exists():
        print(f"CSV not found at {csv_path}")
        print("Download with: python -c \"import kagglehub; "
              "kagglehub.dataset_download('kanchana1990/real-estate-data-chicago-2024')\"")
        print(f"Or use fixture: --csv tests/fixtures/chicago_2024_sample.csv")
        sys.exit(1)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Read and filter CSV
    rows: list[dict[str, str]] = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["status"] != "for_sale":
                continue
            price = parse_float(row.get("listPrice", ""))
            if not price or price < 50000:
                continue
            rows.append(row)

    if not rows:
        print("No valid rows found in CSV.")
        sys.exit(1)

    # Deterministic shuffle via seed, then cap
    random.seed(42)
    random.shuffle(rows)
    rows = rows[:limit]
    print(f"Processing {len(rows)} listings from {csv_path.name}")

    async with async_session() as db:
        if clear:
            from sqlalchemy import text
            await db.execute(text("TRUNCATE TABLE properties CASCADE"))
            await db.flush()
            print("Cleared existing properties.")

        # Create or find the test buyer profile
        from sqlalchemy import select
        buyer_email = "chicago-buyer@test.platform.com"
        result = await db.execute(
            select(UserProfile).where(UserProfile.email == buyer_email)
        )
        buyer = result.scalar_one_or_none()
        if not buyer:
            buyer = UserProfile(
                name="Alex Chen",
                email=buyer_email,
                role="buyer",
                budget_min=200000,
                budget_max=600000,
                life_stage="first_time",
                investment_goals={
                    "primary": "primary_residence",
                    "neighborhood_priority": "walkability",
                    "source": "kaggle_chicago_2024",
                },
                risk_tolerance="moderate",
                timeline_days=90,
                latitude=41.8858,
                longitude=-87.6181,
                zip_code="60601",
                search_radius=15,
                preferred_types=["sfr", "condo"],
            )
            db.add(buyer)
            await db.flush()
            print(f"Created buyer profile: {buyer.name} ({buyer.id})")
        else:
            print(f"Using existing buyer: {buyer.name} ({buyer.id})")

        # Create seller profile for these listings
        seller_email = "chicago-seller@test.platform.com"
        result = await db.execute(
            select(UserProfile).where(UserProfile.email == seller_email)
        )
        seller = result.scalar_one_or_none()
        if not seller:
            seller = UserProfile(
                name="Chicago Listings (Kaggle 2024)",
                email=seller_email,
                role="seller",
                budget_min=0,
                budget_max=0,
                life_stage="investor",
                investment_goals={
                    "primary": "liquidation",
                    "source": "kaggle_chicago_2024",
                },
                risk_tolerance="moderate",
                timeline_days=60,
                latitude=41.8781,
                longitude=-87.6298,
                zip_code="60601",
            )
            db.add(seller)
            await db.flush()
            print(f"Created seller: {seller.name} ({seller.id})")
        else:
            print(f"Using existing seller: {seller.name} ({seller.id})")

        # Seed properties
        count = 0
        for idx, row in enumerate(rows):
            price = parse_float(row["listPrice"])
            if not price:
                continue

            text = row.get("text", "")
            zip_code = extract_zip_from_text(text)
            coords = ZIP_COORDS.get(zip_code, (41.8781, -87.6298))
            lat, lng = jitter(coords[0], coords[1])

            beds = parse_int(row.get("beds", ""))
            baths = parse_float(row.get("baths", ""))
            sqft = parse_int(row.get("sqft", ""))
            year_built = parse_int(row.get("year_built", ""))
            lot_sqft = parse_float(row.get("lot_sqft", ""))
            stories = parse_int(row.get("stories", ""))
            last_sold = parse_float(row.get("lastSoldPrice", ""))
            sold_on = row.get("soldOn", "")

            prop = Property(
                seller_id=seller.id,
                address=stable_address(text, zip_code, idx),
                latitude=lat,
                longitude=lng,
                asking_price=price,
                bedrooms=beds,
                bathrooms=baths,
                sqft=sqft,
                property_type=map_property_type(row.get("type", "single_family")),
                status="active",
                disclosures={
                    "year_built": year_built,
                    "lot_sqft": lot_sqft,
                    "stories": stories,
                    "garage": parse_int(row.get("garage", "")),
                    "last_sold_price": last_sold,
                    "sold_on": sold_on,
                    "known_defects": "none",
                    "flood_zone": "no",
                    "data_source": "kaggle_chicago_2024",
                },
                neighborhood_data={
                    "zip_code": zip_code,
                    "city": "Chicago",
                    "state": "Illinois",
                    "description": text[:300] if text else "",
                },
            )
            db.add(prop)
            count += 1

        await db.commit()

        # Print summary
        prices = [
            float(r["listPrice"]) for r in rows
            if parse_float(r["listPrice"])
        ]
        print(f"\nSeeded {count} properties from Kaggle Chicago 2024 dataset.")
        print(f"Buyer profile: {buyer.name} (id={buyer.id})")
        print(f"Seller profile: {seller.name} (id={seller.id})")
        if prices:
            prices.sort()
            print(f"Price range: ${min(prices):,.0f} – ${max(prices):,.0f}")
            print(f"Median: ${prices[len(prices)//2]:,.0f}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed database from Kaggle Chicago 2024 Real Estate dataset"
    )
    default_csv = KAGGLEHUB_CSV if KAGGLEHUB_CSV.exists() else FIXTURE_CSV
    parser.add_argument(
        "--csv", type=Path, default=default_csv,
        help=f"Path to CSV (default: kagglehub cache or tests/fixtures/)",
    )
    parser.add_argument(
        "--limit", type=int, default=500,
        help="Max properties to seed (default: 500)",
    )
    parser.add_argument(
        "--clear", action="store_true",
        help="Clear existing properties before seeding",
    )
    args = parser.parse_args()
    asyncio.run(seed(args.csv, args.limit, args.clear))


if __name__ == "__main__":
    main()
