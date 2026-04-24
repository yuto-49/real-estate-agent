"""Seed Tokyo fixture corpus into local Postgres for RAG / domain dev work.

Reads every file under tests/fixtures/tokyo/ and loads structurally-real records
into the existing Property / UserProfile tables. Idempotent: re-running does not
create duplicates (dedup by synthesized REINS 物件番号 stored in disclosures).

Phase 0 limitation: current Property model is USD-shaped (Float price, no
JP-specific columns). JP fields are stashed in neighborhood_data.jp and
disclosures until the Phase 1 migration adds first-class columns. JPY prices are
lost-precision when stored as Float and must be converted to Numeric(15,0) in
Phase 1 — this file is the canonical list of call sites that need updating.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select

from db.database import Base, async_session, engine
from db.models import Property, PropertyStatus, UserProfile

FIXTURES_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "tokyo"

logger = logging.getLogger("seed_tokyo")


# ---------------------------------------------------------------------------
# Fixture loaders — each returns an iterable of (natural_key, insert_payload).
# ---------------------------------------------------------------------------


def _load_reins_files(reins_dir: Path) -> list[dict[str, Any]]:
    listings: list[dict[str, Any]] = []
    for json_path in sorted(reins_dir.glob("listings_*.json")):
        with json_path.open(encoding="utf-8") as fh:
            doc = json.load(fh)
        for item in doc.get("listings", []):
            item["_source_file"] = json_path.name
            listings.append(item)
    return listings


def _flatten_address(shozaichi: dict[str, Any]) -> str:
    parts = [
        shozaichi.get("todoufuken", ""),
        shozaichi.get("shikuchouson", ""),
        shozaichi.get("chome", ""),
        shozaichi.get("banchi_go", ""),
    ]
    if shozaichi.get("building_name"):
        parts.append(shozaichi["building_name"])
    return " ".join(p for p in parts if p)


def _reins_to_property_kwargs(listing: dict[str, Any]) -> dict[str, Any]:
    """Map one REINS-shaped listing to Property kwargs.

    Known lossy conversions (fix in Phase 1):
      - baibai_kakaku_yen (int) -> asking_price (Float). Values > 2^24 lose
        integer precision silently. Acceptable for fixtures (<1e9).
      - menseki_m2 (m^2) -> sqft (Integer). We store m^2 as-is since `sqft` is
        untyped in the DB layer; the JP conversion is documented in
        neighborhood_data.jp.menseki_m2 and consumed by JP code paths.
    """
    shozaichi = listing.get("shozaichi", {})
    nearest = listing.get("rinshii_eki", []) or []
    nearest_first = nearest[0] if nearest else {}

    neighborhood_jp = {
        "jp": {
            "reins_bukken_bangou": listing["bukken_bangou"],
            "shozaichi": shozaichi,
            "nearest_stations": nearest,
            "chikunen_seireki": listing.get("chikunen_seireki"),
            "kouzou": listing.get("kouzou"),
            "madori": listing.get("madori"),
            "menseki_m2": listing.get("menseki_m2"),
            "tochi_menseki_m2": listing.get("tochi_menseki_m2"),
            "tatemono_menseki_m2": listing.get("tatemono_menseki_m2"),
            "youto_chiiki": listing.get("youto_chiiki"),
            "kenpei_ritsu": listing.get("kenpei_ritsu"),
            "youseki_ritsu": listing.get("youseki_ritsu"),
            "kanrihi_yen": listing.get("kanrihi_yen"),
            "shuuzenzumitatekin_yen": listing.get("shuuzenzumitatekin_yen"),
            "kyuutaishin_flag": listing.get("kyuutaishin_flag", False),
            "source_file": listing.get("_source_file"),
        }
    }

    disclosures = {
        "reins_bukken_bangou": listing["bukken_bangou"],
        "torihiki_tokki": listing.get("torihiki_tokki"),
        "taishin_shindan": listing.get("taishin_shindan"),
        "media_permissions": listing.get("media_permissions", {}),
    }

    # Existing US guardrail requires REQUIRED_DISCLOSURES keys. Map JP fields
    # to satisfy the legacy schema until Phase 2 ships guardrails_jp.
    disclosures.update({
        "known_defects": listing.get("torihiki_tokki") or "none",
        "flood_zone": "unknown",
        "hoa_fees": str(listing.get("kanrihi_yen", 0)),
        "lead_paint": "na",
        "environmental_hazards": "unknown",
    })

    menseki_m2 = (
        listing.get("menseki_m2")
        or listing.get("tatemono_menseki_m2")
        or listing.get("tochi_menseki_m2")
        or 0
    )

    return {
        "address": _flatten_address(shozaichi),
        "latitude": listing.get("latitude"),
        "longitude": listing.get("longitude"),
        "asking_price": float(listing["baibai_kakaku_yen"]),
        "bedrooms": _rooms_from_madori(listing.get("madori")),
        "bathrooms": 1,
        "sqft": int(round(menseki_m2)),
        "property_type": listing.get("bukken_shubetsu", "mansion"),
        "hoa_fees": float(listing.get("kanrihi_yen") or 0),
        "disclosures": disclosures,
        "neighborhood_data": neighborhood_jp,
        "status": PropertyStatus.ACTIVE,
    }


def _rooms_from_madori(madori: str | None) -> int:
    if not madori:
        return 1
    digits = "".join(ch for ch in madori if ch.isdigit())
    return int(digits) if digits else 1


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------


async def _ensure_demo_user(db) -> UserProfile:
    result = await db.execute(
        select(UserProfile).where(UserProfile.email == "dev-tokyo@test.local")
    )
    user = result.scalar_one_or_none()
    if user:
        return user
    user = UserProfile(
        name="Tokyo Dev User",
        email="dev-tokyo@test.local",
        role="buyer",
        budget_min=50_000_000,
        budget_max=200_000_000,
        life_stage="first_time",
        investment_goals={"primary": "residence", "currency": "JPY"},
        risk_tolerance="moderate",
        timeline_days=120,
        latitude=35.6762,
        longitude=139.6503,
        zip_code="1060032",
        preferred_types=["mansion", "issenkodate"],
    )
    db.add(user)
    await db.flush()
    return user


async def _existing_reins_refs(db) -> set[str]:
    rows = (await db.execute(select(Property.disclosures))).scalars().all()
    refs: set[str] = set()
    for disclosures in rows:
        if isinstance(disclosures, dict):
            ref = disclosures.get("reins_bukken_bangou")
            if ref:
                refs.add(ref)
    return refs


async def seed_tokyo(fixtures_root: Path = FIXTURES_ROOT, *, dry_run: bool = False) -> dict[str, int]:
    listings = _load_reins_files(fixtures_root / "reins_samples")
    logger.info("Loaded %d REINS-style listings from fixtures", len(listings))

    if dry_run:
        return {"loaded": len(listings), "inserted": 0, "skipped": 0}

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    inserted = 0
    skipped = 0
    async with async_session() as db:
        await _ensure_demo_user(db)
        known_refs = await _existing_reins_refs(db)

        for listing in listings:
            ref = listing["bukken_bangou"]
            if ref in known_refs:
                skipped += 1
                continue
            try:
                kwargs = _reins_to_property_kwargs(listing)
            except (KeyError, TypeError, ValueError) as exc:
                logger.error("Skipping malformed listing %s: %s", ref, exc)
                skipped += 1
                continue
            db.add(Property(**kwargs))
            inserted += 1

        await db.commit()

    logger.info("Tokyo seed complete: inserted=%d, skipped=%d", inserted, skipped)
    return {"loaded": len(listings), "inserted": inserted, "skipped": skipped}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixtures-root",
        type=Path,
        default=FIXTURES_ROOT,
        help="Override the fixtures directory (default: tests/fixtures/tokyo).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse fixtures but do not write to the database.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Python logging level (default: INFO).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    summary = asyncio.run(seed_tokyo(args.fixtures_root, dry_run=args.dry_run))
    logger.info("Summary: %s", summary)


if __name__ == "__main__":
    main()
