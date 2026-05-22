"""Zillow listing URL → ParsedListing.

MVP scope: parse the canonical Zillow ``homedetails`` URL format which embeds
the address slug + zpid. We do NOT scrape the Zillow page itself — that would
require an authenticated key or a paid API. Instead we extract everything the
URL itself encodes and let the user fill in the rest.

Supported URL shapes
--------------------
- ``https://www.zillow.com/homedetails/<address-slug>/<zpid>_zpid/``
- ``https://zillow.com/homedetails/<address-slug>/<zpid>_zpid/``
- ``https://www.zillow.com/b/<address-slug>/<zpid>_zpid/``

Anything else raises :class:`ListingParseError`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final
from urllib.parse import urlparse

ZPID_PATTERN: Final[re.Pattern[str]] = re.compile(r"(\d+)_zpid", re.IGNORECASE)
SLUG_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"/(?:homedetails|b)/([^/]+)/", re.IGNORECASE
)
US_STATE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"-([A-Z]{2})-(\d{5})$", re.IGNORECASE
)


class ListingParseError(ValueError):
    """Raised when a URL is not a parseable Zillow listing URL."""


@dataclass(frozen=True, slots=True)
class ParsedListing:
    source: str
    zpid: str
    url: str
    address_hint: str
    state: str | None
    zip_code: str | None


def is_supported_listing_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except (ValueError, AttributeError):
        return False
    if not parsed.scheme or not parsed.netloc:
        return False
    host = parsed.netloc.lower().lstrip("www.")
    if host != "zillow.com":
        return False
    return bool(ZPID_PATTERN.search(parsed.path))


def parse_zillow_url(url: str) -> ParsedListing:
    """Parse a Zillow homedetails URL.

    Raises ``ListingParseError`` for unsupported hosts or missing zpid.
    """
    try:
        parsed = urlparse(url)
    except (ValueError, AttributeError) as exc:
        raise ListingParseError("invalid url") from exc

    if not parsed.scheme or not parsed.netloc:
        raise ListingParseError("invalid url")

    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if host != "zillow.com":
        raise ListingParseError(f"unsupported_host: {parsed.netloc}")

    zpid_match = ZPID_PATTERN.search(parsed.path)
    if not zpid_match:
        raise ListingParseError("no_zpid_in_url")
    zpid = zpid_match.group(1)

    slug_match = SLUG_PATTERN.search(parsed.path)
    slug = slug_match.group(1) if slug_match else ""
    # Slug looks like: "123-Main-St-Chicago-IL-60601"
    address_hint = slug.replace("-", " ")

    state = None
    zip_code = None
    state_zip = US_STATE_PATTERN.search(slug)
    if state_zip:
        state = state_zip.group(1).upper()
        zip_code = state_zip.group(2)

    return ParsedListing(
        source="zillow",
        zpid=zpid,
        url=url,
        address_hint=address_hint,
        state=state,
        zip_code=zip_code,
    )


__all__ = [
    "ListingParseError",
    "ParsedListing",
    "is_supported_listing_url",
    "parse_zillow_url",
]
