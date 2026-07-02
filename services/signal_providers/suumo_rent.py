"""SUUMO rent comp scraper — fetches rental listings from suumo.jp.

Rate-limited to 1 request per 3 seconds. Uses httpx for async HTTP.
Parses listing pages with BeautifulSoup to extract rent comp data.

IMPORTANT: This scraper is for personal research/educational use.
Respect SUUMO's robots.txt and terms of service.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

import httpx

from db.models import RentComp

log = logging.getLogger(__name__)

_BASE_URL = "https://suumo.jp/jj/chintai/ichiran/FR301FC001/"
_RATE_LIMIT_SECONDS = 3.0
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Ward code -> SUUMO area code mapping (Tokyo 23 wards)
_WARD_TO_SUUMO: dict[str, str] = {
    "131": "13101",  # 千代田区
    "132": "13123",  # 江戸川区
    "160": "13104",  # 新宿区
    "166": "13115",  # 杉並区
    "173": "13119",  # 板橋区
    "176": "13120",  # 練馬区
    "170": "13116",  # 豊島区
    "174": "13119",  # 板橋区 (alt zip prefix)
    "114": "13117",  # 北区
    "116": "13118",  # 荒川区
    "120": "13121",  # 足立区
    "124": "13122",  # 葛飾区
    "134": "13108",  # 中央区 (alt)
    "135": "13108",  # 中央区/江東区 border
    "136": "13108",  # 江東区
}


@dataclass(frozen=True)
class SuumoSearchParams:
    ward_code: str
    menseki_min: float = 15.0
    menseki_max: float = 35.0
    walk_max: int = 15


async def fetch_suumo_comps(
    params: SuumoSearchParams,
    *,
    property_id: str | None = None,
    client: httpx.AsyncClient | None = None,
    max_pages: int = 2,
) -> list[RentComp]:
    """Scrape SUUMO rental listings for a given ward.

    Returns parsed RentComp objects ready for DB insertion.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        log.error("beautifulsoup4 not installed — cannot scrape SUUMO")
        return []

    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(
            timeout=30.0,
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
        )

    comps: list[RentComp] = []
    now = datetime.utcnow()
    suumo_area = _WARD_TO_SUUMO.get(params.ward_code[:3], "")

    if not suumo_area:
        log.warning("No SUUMO area mapping for ward_code=%s", params.ward_code)
        if own_client:
            await client.aclose()
        return []

    try:
        for page in range(1, max_pages + 1):
            query_params = {
                "ar": "030",  # Tokyo
                "bs": "040",  # Rental
                "ta": "13",   # Tokyo prefecture
                "sc": suumo_area,
                "cb": "0.0",  # Min rent
                "ct": "9999999",  # Max rent
                "mb": str(int(params.menseki_min)),
                "mt": str(int(params.menseki_max)),
                "et": str(params.walk_max),
                "cn": "9999999",
                "shkr1": "03",  # Sort by newest
                "shkr2": "03",
                "shkr3": "03",
                "shkr4": "03",
                "sngz": "",
                "po1": "25",  # 25 per page
                "pc": "50",
                "page": str(page),
            }

            resp = await client.get(_BASE_URL, params=query_params)
            if resp.status_code != 200:
                log.warning("SUUMO returned %d for ward %s page %d", resp.status_code, params.ward_code, page)
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            listings = soup.select(".cassetteitem")

            if not listings:
                log.info("No listings found on page %d for ward %s", page, params.ward_code)
                break

            for item in listings:
                parsed = _parse_cassette_item(item, params.ward_code, property_id, now)
                if parsed:
                    comps.extend(parsed)

            # Rate limit between pages
            if page < max_pages:
                await asyncio.sleep(_RATE_LIMIT_SECONDS)

    except httpx.HTTPError as exc:
        log.warning("SUUMO HTTP error for ward %s: %s", params.ward_code, exc)
    finally:
        if own_client:
            await client.aclose()

    log.info("Fetched %d comps from SUUMO for ward %s", len(comps), params.ward_code)
    return comps


def _parse_cassette_item(
    item: Any,
    ward_code: str,
    property_id: str | None,
    now: datetime,
) -> list[RentComp]:
    """Parse a single SUUMO cassetteitem into RentComp(s)."""
    comps: list[RentComp] = []

    try:
        # Building-level info
        title_el = item.select_one(".cassetteitem_content-title")
        address_el = item.select_one(".cassetteitem_detail-col1")
        built_el = item.select_one(".cassetteitem_detail-col3")

        address_hint = address_el.get_text(strip=True) if address_el else None
        built_year = _extract_built_year(built_el.get_text(strip=True) if built_el else "")
        construction = _extract_construction(built_el.get_text(strip=True) if built_el else "")

        # Walk time from station
        station_els = item.select(".cassetteitem_detail-col2 .cassetteitem_detail-text")
        walk_minutes = None
        for sel in station_els:
            text = sel.get_text(strip=True)
            walk_match = re.search(r"歩(\d+)分", text)
            if walk_match:
                walk_minutes = int(walk_match.group(1))
                break

        # Each room/unit in the building
        rows = item.select(".js-cassette_link")
        for row in rows:
            rent_el = row.select_one(".cassetteitem_price--rent")
            admin_el = row.select_one(".cassetteitem_price--administration")
            madori_el = row.select_one(".cassetteitem_madori")
            menseki_el = row.select_one(".cassetteitem_menseki")

            rent_yen = _parse_rent(rent_el.get_text(strip=True) if rent_el else "")
            if rent_yen is None or rent_yen <= 0:
                continue

            mgmt_fee = _parse_rent(admin_el.get_text(strip=True) if admin_el else "")
            madori = madori_el.get_text(strip=True) if madori_el else None
            menseki = _parse_menseki(menseki_el.get_text(strip=True) if menseki_el else "")

            comps.append(RentComp(
                id=str(uuid4()),
                property_id=property_id,
                zip_code=ward_code,
                ward_code=ward_code[:3] if len(ward_code) >= 3 else None,
                source="suumo",
                source_listing_id=f"suumo-{uuid4().hex[:8]}",
                address_hint=address_hint,
                menseki_m2=menseki,
                madori=madori,
                walk_minutes=walk_minutes,
                monthly_rent_yen=rent_yen,
                management_fee_yen=mgmt_fee or 0,
                built_year=built_year,
                construction_type=construction,
                fetched_at=now,
                expires_at=now + timedelta(days=30),
            ))

    except Exception as exc:
        log.debug("Failed to parse cassette item: %s", exc)

    return comps


def _parse_rent(text: str) -> int | None:
    """Parse '7.2万円' or '72000円' into yen integer."""
    if not text or text == "-" or text == "\u2014":
        return None
    # Match 万円 pattern: e.g., "7.2万円"
    m = re.search(r"([\d.]+)\s*万", text)
    if m:
        return int(float(m.group(1)) * 10000)
    # Match plain digits
    m = re.search(r"([\d,]+)\s*円", text)
    if m:
        return int(m.group(1).replace(",", ""))
    # Try plain number
    m = re.search(r"[\d,]+", text)
    if m:
        return int(m.group(0).replace(",", ""))
    return None


def _parse_menseki(text: str) -> float | None:
    """Parse '25.5m2' or '25.5㎡' into float."""
    m = re.search(r"([\d.]+)", text)
    return float(m.group(1)) if m else None


def _extract_built_year(text: str) -> int | None:
    """Extract built year from text like '2005年築'."""
    # Match 4-digit year
    m = re.search(r"(\d{4})年", text)
    if m:
        return int(m.group(1))
    # Match 令和/平成 era
    m = re.search(r"令和(\d+)年", text)
    if m:
        return 2018 + int(m.group(1))
    m = re.search(r"平成(\d+)年", text)
    if m:
        return 1988 + int(m.group(1))
    return None


def _extract_construction(text: str) -> str | None:
    """Extract construction type from building detail text."""
    if "木造" in text:
        return "wood"
    if "軽量鉄骨" in text:
        return "light_steel"
    if "鉄骨鉄筋" in text or "SRC" in text:
        return "src"
    if "鉄筋" in text or "RC" in text:
        return "rc"
    if "鉄骨" in text:
        return "steel"
    return None
