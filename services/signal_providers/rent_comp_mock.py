"""Mock rent comp provider — deterministic Tokyo ward fixtures for dev + tests."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any, Final
from uuid import uuid4

from db.models import RentComp

# Realistic Tokyo rent data by ward code (first 3 digits of zip)
# Format: (menseki_m2, madori, walk_min, rent_yen, mgmt_fee, built_year, construction)
_WARD_FIXTURES: Final[dict[str, list[tuple]]] = {
    "173": [  # 板橋区 Itabashi — APARUTO heartland
        (22.5, "1K", 7, 72000, 5000, 2005, "wood"),
        (25.0, "1K", 5, 78000, 5000, 2008, "wood"),
        (20.0, "1R", 10, 65000, 4000, 2000, "wood"),
        (28.0, "1K", 8, 82000, 6000, 2010, "light_steel"),
        (24.0, "1K", 6, 75000, 5000, 2003, "wood"),
        (30.0, "1DK", 4, 88000, 6000, 2012, "light_steel"),
        (21.0, "1R", 12, 62000, 4000, 1998, "wood"),
        (26.0, "1K", 9, 76000, 5000, 2006, "wood"),
        (23.0, "1K", 7, 73000, 5000, 2004, "wood"),
        (27.0, "1K", 5, 80000, 5500, 2009, "wood"),
    ],
    "176": [  # 練馬区 Nerima
        (23.0, "1K", 8, 70000, 5000, 2004, "wood"),
        (26.0, "1K", 6, 76000, 5000, 2007, "wood"),
        (20.0, "1R", 11, 63000, 4000, 1999, "wood"),
        (29.0, "1DK", 5, 84000, 6000, 2011, "light_steel"),
        (22.0, "1K", 9, 68000, 4500, 2002, "wood"),
        (25.0, "1K", 7, 74000, 5000, 2005, "wood"),
        (30.0, "1DK", 4, 86000, 6000, 2013, "light_steel"),
        (24.0, "1K", 8, 72000, 5000, 2003, "wood"),
        (21.0, "1R", 13, 60000, 4000, 1997, "wood"),
        (27.0, "1K", 6, 78000, 5500, 2008, "wood"),
    ],
    "132": [  # 江戸川区 Edogawa — east Tokyo value
        (24.0, "1K", 9, 66000, 4500, 2003, "wood"),
        (28.0, "1DK", 6, 75000, 5000, 2008, "wood"),
        (20.0, "1R", 12, 58000, 4000, 1998, "wood"),
        (25.0, "1K", 7, 70000, 5000, 2005, "wood"),
        (22.0, "1K", 10, 64000, 4500, 2001, "wood"),
        (30.0, "1LDK", 5, 82000, 6000, 2012, "light_steel"),
        (26.0, "1K", 8, 68000, 5000, 2004, "wood"),
        (23.0, "1K", 11, 62000, 4000, 2000, "wood"),
        (27.0, "1DK", 6, 73000, 5000, 2007, "wood"),
        (21.0, "1R", 14, 56000, 3500, 1996, "wood"),
    ],
    "166": [  # 杉並区 Suginami — mid-tier
        (22.0, "1K", 6, 80000, 6000, 2006, "wood"),
        (25.0, "1K", 4, 88000, 6000, 2010, "light_steel"),
        (20.0, "1R", 8, 74000, 5000, 2002, "wood"),
        (28.0, "1DK", 5, 92000, 7000, 2013, "rc"),
        (24.0, "1K", 7, 82000, 6000, 2005, "wood"),
        (30.0, "1DK", 3, 96000, 7000, 2015, "rc"),
        (21.0, "1R", 10, 72000, 5000, 2000, "wood"),
        (26.0, "1K", 6, 85000, 6000, 2008, "light_steel"),
        (23.0, "1K", 8, 78000, 5500, 2004, "wood"),
        (27.0, "1K", 5, 86000, 6000, 2009, "light_steel"),
    ],
    "160": [  # 新宿区 Shinjuku — premium ONE_ROOM
        (20.0, "1R", 5, 95000, 8000, 2008, "rc"),
        (22.0, "1K", 3, 105000, 8000, 2012, "rc"),
        (18.0, "1R", 7, 88000, 7000, 2005, "rc"),
        (25.0, "1K", 4, 110000, 9000, 2015, "src"),
        (20.0, "1R", 6, 92000, 7500, 2007, "rc"),
        (23.0, "1K", 5, 100000, 8000, 2010, "rc"),
        (19.0, "1R", 8, 85000, 7000, 2003, "rc"),
        (24.0, "1K", 4, 108000, 8500, 2014, "src"),
        (21.0, "1K", 6, 98000, 8000, 2009, "rc"),
        (22.0, "1K", 3, 112000, 9000, 2016, "src"),
    ],
}


def generate_mock_comps(
    zip_code: str,
    *,
    property_id: str | None = None,
    now: datetime | None = None,
) -> list[RentComp]:
    """Generate mock RentComp rows for a zip/ward code."""
    when = now or datetime.utcnow()
    expires = when + timedelta(days=30)

    # Try exact match first, then first 3 digits (ward prefix)
    fixtures = _WARD_FIXTURES.get(zip_code) or _WARD_FIXTURES.get(zip_code[:3], [])
    if not fixtures:
        return []

    comps: list[RentComp] = []
    for i, (menseki, madori, walk, rent, mgmt, built, constr) in enumerate(fixtures):
        comps.append(RentComp(
            id=str(uuid4()),
            property_id=property_id,
            zip_code=zip_code,
            ward_code=zip_code[:3] if len(zip_code) >= 3 else None,
            source="mock",
            source_listing_id=f"mock-{zip_code}-{i}",
            address_hint=f"Mock listing {i+1} in {zip_code}",
            menseki_m2=menseki,
            madori=madori,
            walk_minutes=walk,
            monthly_rent_yen=rent,
            management_fee_yen=mgmt,
            built_year=built,
            construction_type=constr,
            fetched_at=when,
            expires_at=expires,
        ))
    return comps
