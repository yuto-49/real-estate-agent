"""Smoke tests for Tokyo fixture corpus + scripts/seed_tokyo.py.

These tests pin the *shape* of the fixture tree so that later phases
(RAG ingest, JP guardrails, agent tools) can rely on stable contracts.
No database required — pure parsing + mapping.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.address_jp import TOKYO23_WARD_CODES
from scripts.seed_tokyo import (
    FIXTURES_ROOT,
    _flatten_address,
    _load_reins_files,
    _reins_to_property_kwargs,
    _rooms_from_madori,
)

EXPECTED_WARDS = {"港区", "世田谷区", "新宿区"}
REINS_DIR = FIXTURES_ROOT / "reins_samples"


# ---------------------------------------------------------------------------
# Fixture tree layout
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_fixture_tree_has_expected_subdirs():
    for sub in (
        "reins_samples",
        "mlit_transactions",
        "estat_demographics",
        "hazard_maps",
        "zoning",
        "addresses",
        "juuyou_docs",
    ):
        assert (FIXTURES_ROOT / sub).is_dir(), f"missing fixtures subdir: {sub}"


@pytest.mark.unit
def test_readme_documents_synthetic_origin():
    readme = (FIXTURES_ROOT / "README.md").read_text(encoding="utf-8")
    assert "synthetic" in readme.lower()
    assert "REINS" in readme
    assert "redistribution" in readme.lower()


@pytest.mark.unit
def test_pdf_directory_is_gitignored():
    gitignore = (FIXTURES_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "juuyou_docs/*.pdf" in gitignore


# ---------------------------------------------------------------------------
# REINS listings
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_reins_listings_load_from_all_three_wards():
    listings = _load_reins_files(REINS_DIR)
    assert len(listings) == 9
    wards = {l["shozaichi"]["shikuchouson"] for l in listings}
    assert wards == EXPECTED_WARDS


@pytest.mark.unit
def test_every_reins_listing_marked_synthetic():
    """Guard against accidentally committing a real REINS record."""
    for json_path in REINS_DIR.glob("listings_*.json"):
        doc = json.loads(json_path.read_text(encoding="utf-8"))
        assert doc.get("fixture_source") == "synthetic", json_path.name
        for listing in doc["listings"]:
            assert listing["bukken_bangou"].startswith("SYN-"), listing


@pytest.mark.unit
def test_bukken_bangou_globally_unique():
    listings = _load_reins_files(REINS_DIR)
    refs = [l["bukken_bangou"] for l in listings]
    assert len(refs) == len(set(refs)), "duplicate bukken_bangou"


@pytest.mark.unit
def test_reins_schema_required_fields_present():
    required = {
        "bukken_bangou",
        "torihiki_taiyou",
        "bukken_shubetsu",
        "shozaichi",
        "baibai_kakaku_yen",
        "touroku_date",
    }
    for listing in _load_reins_files(REINS_DIR):
        missing = required - listing.keys()
        assert not missing, f"{listing['bukken_bangou']} missing {missing}"


@pytest.mark.unit
def test_shozaichi_has_prefecture_and_ward():
    for listing in _load_reins_files(REINS_DIR):
        sz = listing["shozaichi"]
        assert sz["todoufuken"] == "東京都"
        assert sz["shikuchouson"] in EXPECTED_WARDS
        assert sz["chome"]
        assert sz["banchi_go"]


@pytest.mark.unit
def test_kyuutaishin_flag_matches_built_year():
    """1981/6 is the 新耐震 cutoff; pre-cutoff records must be flagged."""
    for listing in _load_reins_files(REINS_DIR):
        seireki = listing.get("chikunen_seireki")
        if seireki and seireki < 1981:
            assert listing.get("kyuutaishin_flag") is True, listing["bukken_bangou"]


# ---------------------------------------------------------------------------
# REINS -> Property kwargs mapping
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_every_reins_listing_maps_to_property_kwargs():
    for listing in _load_reins_files(REINS_DIR):
        kwargs = _reins_to_property_kwargs(listing)
        assert kwargs["address"], listing["bukken_bangou"]
        assert kwargs["asking_price"] > 0
        assert kwargs["sqft"] > 0
        assert kwargs["latitude"] is not None
        assert kwargs["longitude"] is not None
        assert kwargs["neighborhood_data"]["jp"]["reins_bukken_bangou"] == listing["bukken_bangou"]


@pytest.mark.unit
def test_every_listing_gets_the_reinfolib_ward_code():
    """``ward_code`` is the join key REINFOLIB signals are addressed by.

    Without it, MLIT municipality-keyed signals can never resolve to a property
    and the Analysis / Simulation / Portfolio surface stays empty.
    """
    for listing in _load_reins_files(REINS_DIR):
        kwargs = _reins_to_property_kwargs(listing)
        ward = listing["shozaichi"]["shikuchouson"]
        assert kwargs["ward_code"] == TOKYO23_WARD_CODES[ward], listing["bukken_bangou"]
        assert kwargs["ward_code"].startswith("13")
        assert len(kwargs["ward_code"]) == 5


@pytest.mark.unit
def test_tokyo_listings_are_seeded_as_jp_jurisdiction():
    """Tokyo stock must not inherit the legacy ``jurisdiction="us"`` column default."""
    for listing in _load_reins_files(REINS_DIR):
        kwargs = _reins_to_property_kwargs(listing)
        assert kwargs["jurisdiction"] == "jp"
        assert kwargs["currency"] == "JPY"


@pytest.mark.skip(reason="US guardrails removed in pivot (migration f9a1b2c3d4e5)")
@pytest.mark.unit
def test_us_required_disclosures_synthesized_for_legacy_guardrail():
    pass


@pytest.mark.unit
def test_disclosures_preserve_reins_ref_for_idempotent_seed():
    for listing in _load_reins_files(REINS_DIR):
        kwargs = _reins_to_property_kwargs(listing)
        assert kwargs["disclosures"]["reins_bukken_bangou"] == listing["bukken_bangou"]


@pytest.mark.unit
def test_address_flattening_includes_building_when_present():
    listing = {
        "shozaichi": {
            "todoufuken": "東京都",
            "shikuchouson": "港区",
            "chome": "六本木六丁目",
            "banchi_go": "10-1",
            "building_name": "六本木ヒルズレジデンスB棟",
        }
    }
    addr = _flatten_address(listing["shozaichi"])
    assert "六本木ヒルズ" in addr
    assert "港区" in addr


@pytest.mark.unit
@pytest.mark.parametrize(
    "madori,expected",
    [
        ("1LDK", 1),
        ("2LDK", 2),
        ("4LDK+S", 4),
        (None, 1),
        ("", 1),
        ("ワンルーム", 1),
    ],
)
def test_rooms_from_madori(madori, expected):
    assert _rooms_from_madori(madori) == expected


# ---------------------------------------------------------------------------
# Sibling fixtures (MLIT / e-Stat / GeoJSON / addresses)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_mlit_csv_parses_as_utf8_with_expected_columns():
    import csv

    csv_path = FIXTURES_ROOT / "mlit_transactions" / "2024_tokyo_13_sample.csv"
    with csv_path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
    assert rows, "MLIT sample is empty"
    required_cols = {"種類", "都道府県名", "市区町村名", "取引価格(総額)", "取引時点"}
    assert required_cols.issubset(reader.fieldnames or [])
    for row in rows:
        assert row["都道府県名"] == "東京都"


@pytest.mark.unit
def test_estat_demographics_references_matching_wards():
    path = FIXTURES_ROOT / "estat_demographics" / "chome_population.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    wards = {r["shikuchouson"] for r in doc["records"]}
    assert wards.issubset(EXPECTED_WARDS)
    for r in doc["records"]:
        assert r["kcode"].startswith("13")  # 東京都 prefecture code
        assert r["souchouju_jinkou"] > 0


@pytest.mark.unit
def test_hazard_geojson_is_valid_featurecollection():
    path = FIXTURES_ROOT / "hazard_maps" / "minato_flood.geojson"
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["type"] == "FeatureCollection"
    assert doc["features"], "empty FeatureCollection"
    for feature in doc["features"]:
        assert feature["geometry"]["type"] == "Polygon"
        assert feature["properties"]["hazard_type"] in {"flood", "tsunami", "landslide"}


@pytest.mark.unit
def test_zoning_geojson_has_youto_chiiki_properties():
    path = FIXTURES_ROOT / "zoning" / "tokyo23_zoning_sample.geojson"
    doc = json.loads(path.read_text(encoding="utf-8"))
    for feature in doc["features"]:
        props = feature["properties"]
        assert "youto_chiiki" in props
        assert 0 < props["kenpei_ritsu"] <= 100
        assert 0 < props["youseki_ritsu"] <= 1500


@pytest.mark.unit
def test_address_pairs_are_consistent_for_round_trip():
    path = FIXTURES_ROOT / "addresses" / "tokyo23_normalized.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    for pair in doc["pairs"]:
        n = pair["normalized"]
        assert n["todoufuken_code"] == "13"
        assert n["shichouson_code"].startswith("13")
        assert n["chome"].endswith("丁目"), n
        assert n["banchi"].isdigit()
        assert n["go"].isdigit()
