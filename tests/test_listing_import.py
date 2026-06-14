"""Listing URL parser — Suumo / REINFOLIB — Phase P2."""

from __future__ import annotations

import pytest

from services.listing_import import (
    ListingParseError,
    parse_listing_url,
    is_supported_listing_url,
)


def test_suumo_url_nc_path_extraction():
    url = "https://suumo.jp/ms/chuko/tokyo/sc_minatoku/nc_12345678/"
    parsed = parse_listing_url(url)
    assert parsed.source == "suumo"
    assert parsed.property_id == "12345678"
    assert parsed.prefecture == "東京都"


def test_suumo_url_nc_query_extraction():
    url = "https://suumo.jp/jj/bukken/shosai/JJ012FJ010/?ar=030&bs=011&nc=87654321"
    parsed = parse_listing_url(url)
    assert parsed.source == "suumo"
    assert parsed.property_id == "87654321"


def test_suumo_url_address_hint():
    url = "https://suumo.jp/ms/chuko/tokyo/sc_shibuya/nc_11111111/"
    parsed = parse_listing_url(url)
    assert "tokyo" in parsed.address_hint.lower() or "shibuya" in parsed.address_hint.lower()


def test_reinfolib_url_with_id_param():
    url = "https://www.reinfolib.mlit.go.jp/realEstate/detailAction?id=TX-20260315-001"
    parsed = parse_listing_url(url)
    assert parsed.source == "reinfolib"
    assert parsed.property_id == "TX-20260315-001"
    assert parsed.prefecture == "東京都"


def test_reinfolib_url_with_code_param():
    url = "https://www.reinfolib.mlit.go.jp/realEstate/detailAction?code=13103&area=minato"
    parsed = parse_listing_url(url)
    assert parsed.source == "reinfolib"
    assert parsed.property_id == "13103"


def test_non_supported_url_raises():
    with pytest.raises(ListingParseError):
        parse_listing_url("https://www.zillow.com/homedetails/123-Main/12345_zpid/")


def test_redfin_url_raises():
    with pytest.raises(ListingParseError):
        parse_listing_url("https://www.redfin.com/IL/Chicago/123-Main-St")


def test_suumo_url_without_nc_raises():
    with pytest.raises(ListingParseError):
        parse_listing_url("https://suumo.jp/ms/chuko/tokyo/sc_minatoku/")


def test_is_supported_listing_url():
    assert is_supported_listing_url(
        "https://suumo.jp/ms/chuko/tokyo/sc_minatoku/nc_12345678/"
    )
    assert is_supported_listing_url(
        "https://www.reinfolib.mlit.go.jp/realEstate/detailAction?id=TX-001"
    )
    assert not is_supported_listing_url("https://www.zillow.com/homedetails/x/123_zpid/")
    assert not is_supported_listing_url("https://realtor.com/anything")
    assert not is_supported_listing_url("not a url at all")
