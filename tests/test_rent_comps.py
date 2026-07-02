"""Tests for rent comp feature — model, validator, mock provider, API."""

from datetime import datetime, timedelta

import pytest
import pytest_asyncio

from db.models import Property, RentComp, gen_uuid
from services.rent_validator import RentValidation, validate_rent
from services.signal_providers.rent_comp_mock import generate_mock_comps


# ── Mock provider tests ──────────────────────────────────────────────


def test_mock_comps_itabashi():
    """Mock provider generates 10 comps for Itabashi ward (173)."""
    comps = generate_mock_comps("173")
    assert len(comps) == 10
    for comp in comps:
        assert comp.source == "mock"
        assert comp.zip_code == "173"
        assert comp.monthly_rent_yen > 0
        assert comp.menseki_m2 is not None


def test_mock_comps_shinjuku():
    """Mock provider generates 10 comps for Shinjuku (160)."""
    comps = generate_mock_comps("160")
    assert len(comps) == 10
    shinjuku_avg = sum(c.monthly_rent_yen for c in comps) / len(comps)
    itabashi_comps = generate_mock_comps("173")
    itabashi_avg = sum(c.monthly_rent_yen for c in itabashi_comps) / len(itabashi_comps)
    assert shinjuku_avg > itabashi_avg


def test_mock_comps_unknown_zip():
    """Mock provider returns empty for unknown zip."""
    comps = generate_mock_comps("999")
    assert len(comps) == 0


def test_mock_comps_with_property_id():
    """Mock provider sets property_id when provided."""
    pid = gen_uuid()
    comps = generate_mock_comps("173", property_id=pid)
    assert all(c.property_id == pid for c in comps)


def test_mock_comps_expiration():
    """Mock comps have 30-day TTL."""
    now = datetime(2026, 1, 1)
    comps = generate_mock_comps("173", now=now)
    for comp in comps:
        assert comp.fetched_at == now
        assert comp.expires_at == now + timedelta(days=30)


# ── Rent validator tests ─────────────────────────────────────────────


@pytest_asyncio.fixture
async def property_with_comps(db):
    """Create a property and insert mock comps for validation tests."""
    prop = Property(
        id=gen_uuid(),
        address="Itabashi test property",
        asking_price=25000000,
        ward_code="173",
        menseki_m2=25.0,
        walk_minutes_to_station=7,
        assumed_monthly_rent_yen=75000,
        status="active",
    )
    db.add(prop)

    comps = generate_mock_comps("173", property_id=prop.id)
    for comp in comps:
        db.add(comp)
    await db.commit()
    return prop


@pytest.mark.asyncio
async def test_validate_rent_aligned(db, property_with_comps):
    """Property with 75000 yen assumed rent is aligned with Itabashi comps."""
    prop = property_with_comps
    result = await validate_rent(db, prop.id)

    assert isinstance(result, RentValidation)
    assert result.property_id == prop.id
    assert result.assumed_rent_yen == 75000
    assert result.comp_count > 0
    assert result.comp_median_yen > 0
    assert result.verdict in ("aligned", "above_market", "below_market")


@pytest.mark.asyncio
async def test_validate_rent_above_market(db):
    """Property with inflated rent flags above_market."""
    prop = Property(
        id=gen_uuid(),
        address="Overpriced property",
        asking_price=30000000,
        ward_code="173",
        menseki_m2=25.0,
        walk_minutes_to_station=7,
        assumed_monthly_rent_yen=120000,
        status="active",
    )
    db.add(prop)
    comps = generate_mock_comps("173", property_id=prop.id)
    for comp in comps:
        db.add(comp)
    await db.commit()

    result = await validate_rent(db, prop.id)
    assert result.verdict == "above_market"
    assert result.flag is True
    assert result.deviation_pct > 15.0


@pytest.mark.asyncio
async def test_validate_rent_below_market(db):
    """Property with low rent flags below_market."""
    prop = Property(
        id=gen_uuid(),
        address="Underpriced property",
        asking_price=20000000,
        ward_code="173",
        menseki_m2=25.0,
        walk_minutes_to_station=7,
        assumed_monthly_rent_yen=45000,
        status="active",
    )
    db.add(prop)
    comps = generate_mock_comps("173", property_id=prop.id)
    for comp in comps:
        db.add(comp)
    await db.commit()

    result = await validate_rent(db, prop.id)
    assert result.verdict == "below_market"
    assert result.flag is True
    assert result.deviation_pct < -15.0


@pytest.mark.asyncio
async def test_validate_rent_no_assumed_rent(db):
    """Property without assumed rent returns insufficient_data."""
    prop = Property(
        id=gen_uuid(),
        address="No rent property",
        asking_price=25000000,
        ward_code="173",
        status="active",
    )
    db.add(prop)
    await db.commit()

    result = await validate_rent(db, prop.id)
    assert result.verdict == "insufficient_data"
    assert result.flag is False


@pytest.mark.asyncio
async def test_validate_rent_insufficient_comps(db):
    """Property with no comps in DB returns insufficient_data."""
    prop = Property(
        id=gen_uuid(),
        address="No comps property",
        asking_price=25000000,
        ward_code="999",
        menseki_m2=25.0,
        walk_minutes_to_station=7,
        assumed_monthly_rent_yen=75000,
        status="active",
    )
    db.add(prop)
    await db.commit()

    result = await validate_rent(db, prop.id)
    assert result.verdict == "insufficient_data"
    assert result.comp_count < 3


@pytest.mark.asyncio
async def test_validate_rent_nonexistent_property(db):
    """validate_rent raises ValueError for non-existent property."""
    with pytest.raises(ValueError, match="not found"):
        await validate_rent(db, "nonexistent-id")


# ── SUUMO parser unit tests ─────────────────────────────────────────


def test_suumo_parse_rent():
    from services.signal_providers.suumo_rent import _parse_rent
    assert _parse_rent("7.2万円") == 72000
    assert _parse_rent("12.5万円") == 125000
    assert _parse_rent("72,000円") == 72000
    assert _parse_rent("-") is None
    assert _parse_rent("") is None


def test_suumo_parse_menseki():
    from services.signal_providers.suumo_rent import _parse_menseki
    assert _parse_menseki("25.5m2") == 25.5
    assert _parse_menseki("30.0m2") == 30.0
    assert _parse_menseki("") is None


def test_suumo_extract_built_year():
    from services.signal_providers.suumo_rent import _extract_built_year
    assert _extract_built_year("2005年築") == 2005
    assert _extract_built_year("令和3年築") == 2021
    assert _extract_built_year("平成20年築") == 2008
    assert _extract_built_year("不明") is None


def test_suumo_extract_construction():
    from services.signal_providers.suumo_rent import _extract_construction
    assert _extract_construction("木造2階建") == "wood"
    assert _extract_construction("鉄筋コンクリート造") == "rc"
    assert _extract_construction("鉄骨鉄筋コンクリート造") == "src"
    assert _extract_construction("軽量鉄骨造") == "light_steel"
    assert _extract_construction("鉄骨造") == "steel"
    assert _extract_construction("不明") is None


# ── RentComp model tests ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rent_comp_model_roundtrip(db):
    """RentComp can be persisted and retrieved."""
    comp = RentComp(
        id=gen_uuid(),
        zip_code="173",
        ward_code="173",
        source="manual",
        monthly_rent_yen=75000,
        menseki_m2=25.0,
        madori="1K",
        walk_minutes=7,
    )
    db.add(comp)
    await db.commit()

    loaded = await db.get(RentComp, comp.id)
    assert loaded is not None
    assert loaded.monthly_rent_yen == 75000
    assert loaded.source == "manual"
    assert loaded.zip_code == "173"
