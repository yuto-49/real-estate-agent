"""Listing URL → ParsedListing for Japanese real-estate portals.

Supported URL shapes
--------------------
- Suumo: ``https://suumo.jp/ms/chuko/tokyo/sc_minatoku/nc_12345678/``
         ``https://suumo.jp/jj/bukken/shosai/JJ012FJ010/?ar=030&bs=011&nc=12345678``
- REINFOLIB: ``https://www.reinfolib.mlit.go.jp/realEstate/detailAction?...``

Anything else raises :class:`ListingParseError`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final
from urllib.parse import parse_qs, urlparse

SUUMO_NC_PATH_PATTERN: Final[re.Pattern[str]] = re.compile(r"nc_(\d+)", re.IGNORECASE)
SUUMO_NC_QUERY_PATTERN: Final[re.Pattern[str]] = re.compile(r"nc=(\d+)", re.IGNORECASE)
SUUMO_AREA_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"/(?:ms|jj|chukoikkodate)/(?:chuko/)?([^/]+)/(?:sc_([^/]+))?", re.IGNORECASE
)

REINFOLIB_HOSTS: Final[frozenset[str]] = frozenset(
    {"www.reinfolib.mlit.go.jp", "reinfolib.mlit.go.jp"}
)


class ListingParseError(ValueError):
    """Raised when a URL is not a parseable listing URL."""


@dataclass(frozen=True, slots=True)
class ParsedListing:
    source: str
    property_id: str
    url: str
    address_hint: str
    prefecture: str | None
    postal_code: str | None


def _normalize_host(netloc: str) -> str:
    host = netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def _parse_suumo(url: str, parsed: object) -> ParsedListing:
    path = parsed.path  # type: ignore[attr-defined]
    query = parsed.query  # type: ignore[attr-defined]

    nc_match = SUUMO_NC_PATH_PATTERN.search(path) or SUUMO_NC_QUERY_PATTERN.search(
        query
    )
    if not nc_match:
        raise ListingParseError("no_property_id_in_suumo_url")
    property_id = nc_match.group(1)

    area_match = SUUMO_AREA_PATTERN.search(path)
    address_hint = ""
    if area_match:
        parts = [p for p in area_match.groups() if p]
        address_hint = " ".join(p.replace("_", " ") for p in parts)

    return ParsedListing(
        source="suumo",
        property_id=property_id,
        url=url,
        address_hint=address_hint,
        prefecture="東京都",
        postal_code=None,
    )


def _parse_reinfolib(url: str, parsed: object) -> ParsedListing:
    query = parsed.query  # type: ignore[attr-defined]
    path = parsed.path  # type: ignore[attr-defined]
    qs = parse_qs(query)

    property_id = ""
    if "id" in qs:
        property_id = qs["id"][0]
    elif "code" in qs:
        property_id = qs["code"][0]
    else:
        slug = path.rstrip("/").rsplit("/", 1)[-1]
        if slug and slug != path.strip("/"):
            property_id = slug

    if not property_id:
        raise ListingParseError("no_property_id_in_reinfolib_url")

    area_code = qs.get("area", [None])[0]
    address_hint = area_code or ""

    return ParsedListing(
        source="reinfolib",
        property_id=property_id,
        url=url,
        address_hint=address_hint,
        prefecture="東京都",
        postal_code=None,
    )


def is_supported_listing_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except (ValueError, AttributeError):
        return False
    if not parsed.scheme or not parsed.netloc:
        return False
    host = _normalize_host(parsed.netloc)
    return host == "suumo.jp" or host in REINFOLIB_HOSTS


def parse_listing_url(url: str) -> ParsedListing:
    """Parse a Suumo or REINFOLIB listing URL.

    Raises ``ListingParseError`` for unsupported hosts or missing IDs.
    """
    try:
        parsed = urlparse(url)
    except (ValueError, AttributeError) as exc:
        raise ListingParseError("invalid url") from exc

    if not parsed.scheme or not parsed.netloc:
        raise ListingParseError("invalid url")

    host = _normalize_host(parsed.netloc)

    if host == "suumo.jp":
        return _parse_suumo(url, parsed)

    if host in REINFOLIB_HOSTS:
        return _parse_reinfolib(url, parsed)

    raise ListingParseError(f"unsupported_host: {parsed.netloc}")


__all__ = [
    "ListingParseError",
    "ParsedListing",
    "is_supported_listing_url",
    "parse_listing_url",
]
