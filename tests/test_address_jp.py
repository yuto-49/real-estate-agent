"""Unit tests for services.address_jp.OfflineTokyoNormalizer.

Fixture-driven: pairs in tests/fixtures/tokyo/addresses/tokyo23_normalized.json
are the contract the normalizer must satisfy so downstream RAG metadata
filters collapse variant forms to the same key.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.address_jp import (
    TOKYO23_WARD_CODES,
    NormalizedAddress,
    OfflineTokyoNormalizer,
    normalize,
)

FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "tokyo"
    / "addresses"
    / "tokyo23_normalized.json"
)


def _pairs() -> list[dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["pairs"]


@pytest.mark.unit
def test_ward_code_table_covers_23_wards():
    assert len(TOKYO23_WARD_CODES) == 23
    for code in TOKYO23_WARD_CODES.values():
        assert code.startswith("13")
        assert len(code) == 5


@pytest.mark.unit
@pytest.mark.parametrize("pair", _pairs())
def test_fixture_pairs_normalize_to_expected_form(pair):
    result = normalize(pair["raw"])
    expected = pair["normalized"]
    assert result.todoufuken == expected["todoufuken"]
    assert result.shikuchouson == expected["shikuchouson"]
    assert result.chome == expected["chome"]
    assert result.banchi == expected["banchi"]
    assert result.go == expected["go"]
    assert result.building == expected["building"]
    assert result.todoufuken_code == expected["todoufuken_code"]
    assert result.shichouson_code == expected["shichouson_code"]


@pytest.mark.unit
def test_variants_of_same_address_collapse_to_one_canonical():
    variants = [
        "東京都港区六本木6-10-1",
        "港区六本木六丁目10番1号",
        "港区六本木6丁目10-1",
    ]
    canonicals = {normalize(v).canonical() for v in variants}
    assert len(canonicals) == 1, canonicals


@pytest.mark.unit
def test_non_tokyo_input_degrades_without_raising():
    result = normalize("大阪府大阪市北区梅田1-1-1")
    assert result.shikuchouson is None
    assert result.shichouson_code is None


@pytest.mark.unit
def test_fullwidth_digits_normalize_to_halfwidth():
    result = normalize("東京都港区六本木６丁目１０番１号")
    assert result.chome == "六本木六丁目"
    assert result.banchi == "10"
    assert result.go == "1"


@pytest.mark.unit
def test_building_preserved_when_present():
    result = normalize("新宿区神楽坂4-2-11 神楽坂レジデンス301")
    assert result.building == "神楽坂レジデンス301"


@pytest.mark.unit
def test_normalizer_is_pure_function():
    n = OfflineTokyoNormalizer()
    raw = "東京都港区六本木6-10-1"
    first = n.normalize(raw)
    second = n.normalize(raw)
    assert first == second
    assert isinstance(first, NormalizedAddress)
