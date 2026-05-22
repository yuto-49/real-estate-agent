"""Zillow listing URL parser — Phase P2."""

from __future__ import annotations

import pytest

from services.listing_import import (
    ListingParseError,
    parse_zillow_url,
    is_supported_listing_url,
)


def test_zillow_homedetails_url_zpid_extraction():
    url = "https://www.zillow.com/homedetails/123-Main-St-Chicago-IL-60601/12345678_zpid/"
    parsed = parse_zillow_url(url)
    assert parsed.zpid == "12345678"
    assert "Chicago" in parsed.address_hint
    assert parsed.state == "IL"
    assert parsed.zip_code == "60601"


def test_zillow_homedetails_alt_format():
    url = "https://www.zillow.com/homedetails/55-Oak-Ave-Chicago-IL-60614/9876543_zpid/"
    parsed = parse_zillow_url(url)
    assert parsed.zpid == "9876543"
    assert parsed.zip_code == "60614"
    assert parsed.state == "IL"


def test_zillow_url_short_zpid_form():
    url = "https://www.zillow.com/b/45-w-erie-st-chicago-il-60654/87654321_zpid/"
    parsed = parse_zillow_url(url)
    assert parsed.zpid == "87654321"
    assert parsed.zip_code == "60654"


def test_non_zillow_url_raises():
    with pytest.raises(ListingParseError):
        parse_zillow_url("https://www.redfin.com/IL/Chicago/123-Main-St")


def test_zillow_url_without_zpid_raises():
    with pytest.raises(ListingParseError):
        parse_zillow_url("https://www.zillow.com/homes/Chicago_IL/")


def test_is_supported_listing_url():
    assert is_supported_listing_url(
        "https://www.zillow.com/homedetails/x/123_zpid/"
    )
    assert is_supported_listing_url(
        "https://zillow.com/homedetails/x/123_zpid/"
    )
    assert not is_supported_listing_url("https://realtor.com/anything")
    assert not is_supported_listing_url("not a url at all")
