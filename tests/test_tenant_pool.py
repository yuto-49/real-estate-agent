"""Tenant pool service + trajectory preset tests — Phase P5."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db.models import HouseholdProfile
from services.tenant_pool import (
    INCOME_BANDS,
    TenantPoolFilter,
    get_trajectory_preset,
    list_trajectory_presets,
    query_tenant_pool,
    summarize_pool,
)
from domain.reactions.social_dynamics import ALLOWED_REACTION_TOPICS


async def _seed_households(db_engine) -> None:
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    rows = [
        # zip, income_band, housing_type, voucher, income, housing_cost, eviction_risk
        ("60615", "low", "voucher", 1, 1800.0, 900.0, 0.6),
        ("60615", "low", "renter", 0, 2000.0, 1200.0, 0.4),
        ("60615", "moderate", "renter", 0, 4000.0, 1400.0, 0.15),
        ("60615", "middle", "owner", 0, 7000.0, 1800.0, 0.05),
        ("60640", "upper", "owner", 0, 12000.0, 2500.0, 0.0),
    ]
    async with factory() as s:
        for i, (zc, band, htype, voucher, income, cost, risk) in enumerate(rows):
            s.add(
                HouseholdProfile(
                    name=f"HH-{i}",
                    zip_code=zc,
                    income_band=band,
                    housing_type=htype,
                    has_housing_voucher=voucher,
                    monthly_income=income,
                    monthly_housing_cost=cost,
                    eviction_risk=risk,
                )
            )
        await s.commit()


@pytest.mark.asyncio
async def test_query_tenant_pool_filters_by_zip(db_engine):
    await _seed_households(db_engine)
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        pool = await query_tenant_pool(db, TenantPoolFilter(zip_code="60615"))
    assert len(pool) == 4
    assert all(h.zip_code == "60615" for h in pool)


@pytest.mark.asyncio
async def test_query_tenant_pool_filters_by_income_bands(db_engine):
    await _seed_households(db_engine)
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        pool = await query_tenant_pool(
            db, TenantPoolFilter(income_bands=("low", "moderate"))
        )
    assert {h.income_band for h in pool} == {"low", "moderate"}
    assert len(pool) == 3


@pytest.mark.asyncio
async def test_query_tenant_pool_voucher_and_risk_filters(db_engine):
    await _seed_households(db_engine)
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        voucher_pool = await query_tenant_pool(
            db, TenantPoolFilter(voucher_only=True)
        )
        low_risk = await query_tenant_pool(
            db, TenantPoolFilter(max_eviction_risk=0.2)
        )
    assert len(voucher_pool) == 1
    assert voucher_pool[0].has_housing_voucher == 1
    assert all(h.eviction_risk <= 0.2 for h in low_risk)
    assert len(low_risk) == 3


@pytest.mark.asyncio
async def test_query_tenant_pool_rejects_unknown_income_band(db_engine):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        with pytest.raises(ValueError):
            await query_tenant_pool(db, TenantPoolFilter(income_bands=("rich",)))


@pytest.mark.asyncio
async def test_summarize_pool_computes_breakdowns(db_engine):
    await _seed_households(db_engine)
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        pool = await query_tenant_pool(db, TenantPoolFilter(zip_code="60615"))
    summary = summarize_pool(pool)
    assert summary.total == 4
    assert summary.by_income_band == {"low": 2, "moderate": 1, "middle": 1}
    assert summary.voucher_holders == 1
    assert summary.avg_monthly_income == pytest.approx((1800 + 2000 + 4000 + 7000) / 4)
    # cost burden = housing_cost / income, averaged
    assert 0.0 < summary.avg_cost_burden < 1.0
    assert summary.avg_eviction_risk == pytest.approx((0.6 + 0.4 + 0.15 + 0.05) / 4)


def test_summarize_pool_handles_empty():
    summary = summarize_pool([])
    assert summary.total == 0
    assert summary.by_income_band == {}
    assert summary.avg_monthly_income == 0.0
    assert summary.avg_cost_burden == 0.0


def test_trajectory_preset_registry():
    presets = list_trajectory_presets()
    assert presets, "expected at least one trajectory preset"
    preset = get_trajectory_preset("neighborhood_trajectory")
    assert preset.name == "neighborhood_trajectory"
    assert preset.max_rounds > 0
    # Topics must be valid social-simulation topics.
    assert set(preset.topics).issubset(ALLOWED_REACTION_TOPICS)


def test_get_trajectory_preset_unknown_raises():
    with pytest.raises(KeyError):
        get_trajectory_preset("does_not_exist")


def test_income_bands_constant():
    assert INCOME_BANDS == ("low", "moderate", "middle", "upper")
