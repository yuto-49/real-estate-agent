"""Seed the database with sample SaleComp records for satei engine development.

Inserts realistic Tokyo comparable-sale transactions across several wards and
zip codes so that ``services.satei_engine.compute_satei`` returns meaningful
results in local dev.  Idempotent — skips if records already exist.
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import func, select

from db.database import async_session, engine, Base
from db.models import SaleComp

# Tokyo ward/city codes used by the seed properties in seed_properties.py
_COMPS: list[dict] = [
    # ── 板橋区 (Itabashi) — city_code 13119, zip 1730004 ──────────
    {"city_code": "13119", "zip_code": "1730004", "ward_code": "itabashi",
     "address_hint": "板橋区板橋2丁目", "trade_price_yen": 26_500_000,
     "menseki_m2": 22.0, "built_year": 2005, "construction_type": "RC",
     "walk_minutes": 6, "transaction_year": 2025, "transaction_quarter": 4},
    {"city_code": "13119", "zip_code": "1730004", "ward_code": "itabashi",
     "address_hint": "板橋区板橋3丁目", "trade_price_yen": 29_800_000,
     "menseki_m2": 27.0, "built_year": 2010, "construction_type": "RC",
     "walk_minutes": 4, "transaction_year": 2025, "transaction_quarter": 3},
    {"city_code": "13119", "zip_code": "1730004", "ward_code": "itabashi",
     "address_hint": "板橋区仲宿", "trade_price_yen": 24_000_000,
     "menseki_m2": 20.5, "built_year": 2000, "construction_type": "鉄骨",
     "walk_minutes": 8, "transaction_year": 2025, "transaction_quarter": 2},
    {"city_code": "13119", "zip_code": "1730004", "ward_code": "itabashi",
     "address_hint": "板橋区大山金井町", "trade_price_yen": 31_000_000,
     "menseki_m2": 28.0, "built_year": 2015, "construction_type": "RC",
     "walk_minutes": 3, "transaction_year": 2026, "transaction_quarter": 1},

    # ── 杉並区 (Suginami) — city_code 13115, zip 1660004 ──────────
    {"city_code": "13115", "zip_code": "1660004", "ward_code": "suginami",
     "address_hint": "杉並区阿佐谷南2丁目", "trade_price_yen": 42_000_000,
     "menseki_m2": 50.0, "built_year": 2012, "construction_type": "SRC",
     "walk_minutes": 5, "transaction_year": 2025, "transaction_quarter": 4},
    {"city_code": "13115", "zip_code": "1660004", "ward_code": "suginami",
     "address_hint": "杉並区阿佐谷北3丁目", "trade_price_yen": 48_000_000,
     "menseki_m2": 58.0, "built_year": 2018, "construction_type": "SRC",
     "walk_minutes": 3, "transaction_year": 2025, "transaction_quarter": 3},
    {"city_code": "13115", "zip_code": "1660004", "ward_code": "suginami",
     "address_hint": "杉並区高円寺南", "trade_price_yen": 39_500_000,
     "menseki_m2": 45.0, "built_year": 2008, "construction_type": "RC",
     "walk_minutes": 7, "transaction_year": 2025, "transaction_quarter": 2},
    {"city_code": "13115", "zip_code": "1660004", "ward_code": "suginami",
     "address_hint": "杉並区荻窪5丁目", "trade_price_yen": 52_000_000,
     "menseki_m2": 60.0, "built_year": 2020, "construction_type": "SRC",
     "walk_minutes": 2, "transaction_year": 2026, "transaction_quarter": 1},

    # ── 練馬区 (Nerima) — city_code 13120, zip 1760012 ─────────
    {"city_code": "13120", "zip_code": "1760012", "ward_code": "nerima",
     "address_hint": "練馬区豊玉北4丁目", "trade_price_yen": 33_000_000,
     "menseki_m2": 40.0, "built_year": 2010, "construction_type": "軽量鉄骨",
     "walk_minutes": 5, "transaction_year": 2025, "transaction_quarter": 4},
    {"city_code": "13120", "zip_code": "1760012", "ward_code": "nerima",
     "address_hint": "練馬区中村北2丁目", "trade_price_yen": 36_000_000,
     "menseki_m2": 48.0, "built_year": 2014, "construction_type": "RC",
     "walk_minutes": 4, "transaction_year": 2025, "transaction_quarter": 3},
    {"city_code": "13120", "zip_code": "1760012", "ward_code": "nerima",
     "address_hint": "練馬区豊玉中3丁目", "trade_price_yen": 30_500_000,
     "menseki_m2": 38.0, "built_year": 2006, "construction_type": "鉄骨",
     "walk_minutes": 7, "transaction_year": 2025, "transaction_quarter": 2},
    {"city_code": "13120", "zip_code": "1760012", "ward_code": "nerima",
     "address_hint": "練馬区練馬1丁目", "trade_price_yen": 38_500_000,
     "menseki_m2": 50.0, "built_year": 2017, "construction_type": "RC",
     "walk_minutes": 3, "transaction_year": 2026, "transaction_quarter": 1},
]


async def seed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        count = (await db.execute(select(func.count()).select_from(SaleComp))).scalar() or 0
        if count > 0:
            print(f"SaleComp table already has {count} rows — skipped.")
            return

        now = datetime.utcnow()
        for row in _COMPS:
            db.add(SaleComp(fetched_at=now, **row))

        await db.commit()
        print(f"Seeded {len(_COMPS)} SaleComp records across 3 Tokyo wards.")


if __name__ == "__main__":
    asyncio.run(seed())
