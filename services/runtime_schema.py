"""Additive runtime schema reconciliation for local/dev environments."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine

from db.database import engine as default_engine
from db.models import (
    MarketSimulationDecision,
    MarketSimulationInvestor,
    MarketSimulationPropertyState,
    MarketSimulationRun,
)

_MARKET_SIM_TABLES = [
    MarketSimulationRun.__table__,
    MarketSimulationInvestor.__table__,
    MarketSimulationPropertyState.__table__,
    MarketSimulationDecision.__table__,
]

_JSON_OBJECT_COLUMNS: dict[str, tuple[str, ...]] = {
    "market_simulation_runs": ("property_scope", "summary"),
    "market_simulation_investors": ("signal_weights", "persona_profile", "metadata_json"),
    "market_simulation_property_states": ("signal_snapshot",),
    "market_simulation_decisions": ("score_breakdown", "explanation_payload"),
}

_JSON_ARRAY_COLUMNS: dict[str, tuple[str, ...]] = {
    "market_simulation_investors": ("preferred_property_types", "holdings"),
    "market_simulation_property_states": ("targeted_investor_ids",),
}


def _json_column_sql(dialect_name: str) -> str:
    return "JSONB" if dialect_name == "postgresql" else "JSON"


def _default_literal(dialect_name: str, kind: str) -> str:
    if dialect_name == "postgresql":
        return "'{}'::jsonb" if kind == "object" else "'[]'::jsonb"
    return "'{}'" if kind == "object" else "'[]'"


def _sync_ensure_market_simulation_schema(connection: sa.Connection) -> None:
    dialect_name = connection.dialect.name
    for table in _MARKET_SIM_TABLES:
        table.create(connection, checkfirst=True)

    inspector = sa.inspect(connection)
    table_names = set(inspector.get_table_names())
    json_type = _json_column_sql(dialect_name)

    for table_name, columns in _JSON_OBJECT_COLUMNS.items():
        if table_name not in table_names:
            continue
        existing = {column["name"] for column in inspector.get_columns(table_name)}
        for column_name in columns:
            if column_name in existing:
                continue
            default_sql = _default_literal(dialect_name, "object")
            connection.execute(
                sa.text(
                    f"ALTER TABLE {table_name} ADD COLUMN {column_name} {json_type} DEFAULT {default_sql}"
                )
            )

    inspector = sa.inspect(connection)
    table_names = set(inspector.get_table_names())
    for table_name, columns in _JSON_ARRAY_COLUMNS.items():
        if table_name not in table_names:
            continue
        existing = {column["name"] for column in inspector.get_columns(table_name)}
        for column_name in columns:
            if column_name in existing:
                continue
            default_sql = _default_literal(dialect_name, "array")
            connection.execute(
                sa.text(
                    f"ALTER TABLE {table_name} ADD COLUMN {column_name} {json_type} DEFAULT {default_sql}"
                )
            )


async def ensure_market_simulation_schema(engine: AsyncEngine | None = None) -> None:
    active_engine = engine or default_engine
    async with active_engine.begin() as connection:
        await connection.run_sync(_sync_ensure_market_simulation_schema)
