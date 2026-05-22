"""Runtime schema reconciliation tests."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import JSON, event, inspect, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from db.database import Base
from services.runtime_schema import ensure_market_simulation_schema

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def legacy_engine():
    engine = create_async_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, JSONB):
                column.type = JSON()

    async with engine.begin() as connection:
        await connection.execute(text("CREATE TABLE market_simulation_runs (id VARCHAR PRIMARY KEY)"))
        await connection.execute(text("""
            CREATE TABLE market_simulation_investors (
                id VARCHAR PRIMARY KEY,
                run_id VARCHAR NOT NULL,
                investor_name VARCHAR NOT NULL,
                archetype VARCHAR NOT NULL,
                budget FLOAT NOT NULL,
                cash_remaining FLOAT NOT NULL,
                hold_horizon_ticks INTEGER,
                risk_appetite FLOAT,
                diversification_cap INTEGER,
                created_at DATETIME
            )
        """))

    yield engine
    await engine.dispose()


@pytest.mark.asyncio
async def test_ensure_market_simulation_schema_adds_missing_persona_profile(legacy_engine):
    await ensure_market_simulation_schema(legacy_engine)

    async with legacy_engine.begin() as connection:
        def _get_columns(sync_connection):
            return {column["name"] for column in inspect(sync_connection).get_columns("market_simulation_investors")}

        columns = await connection.run_sync(_get_columns)

    assert "persona_profile" in columns
    assert "signal_weights" in columns
    assert "holdings" in columns
