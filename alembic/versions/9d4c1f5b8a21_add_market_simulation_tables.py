"""add market simulation persistence tables and persona profiles

Revision ID: 9d4c1f5b8a21
Revises: f3a8b1d472e0
Create Date: 2026-05-09 22:10:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "9d4c1f5b8a21"
down_revision: Union[str, None] = "f3a8b1d472e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_JSONB_DEFAULT_OBJECT = sa.text("'{}'::jsonb")
_JSONB_DEFAULT_ARRAY = sa.text("'[]'::jsonb")


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "market_simulation_runs"):
        op.create_table(
            "market_simulation_runs",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("run_label", sa.String(), nullable=True),
            sa.Column("status", sa.String(), nullable=True),
            sa.Column("property_scope", JSONB(), nullable=True, server_default=_JSONB_DEFAULT_OBJECT),
            sa.Column("cohort_preset", sa.String(), nullable=True),
            sa.Column("investor_count", sa.Integer(), nullable=True),
            sa.Column("property_count", sa.Integer(), nullable=True),
            sa.Column("total_ticks", sa.Integer(), nullable=True),
            sa.Column("current_tick", sa.Integer(), nullable=True),
            sa.Column("summary", JSONB(), nullable=True, server_default=_JSONB_DEFAULT_OBJECT),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
        )
    if "ix_market_sim_runs_status_created" not in _index_names(inspector, "market_simulation_runs"):
        op.create_index(
            "ix_market_sim_runs_status_created",
            "market_simulation_runs",
            ["status", "created_at"],
        )

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "market_simulation_investors"):
        op.create_table(
            "market_simulation_investors",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("run_id", sa.String(), sa.ForeignKey("market_simulation_runs.id"), nullable=False),
            sa.Column("investor_name", sa.String(), nullable=False),
            sa.Column("archetype", sa.String(), nullable=False),
            sa.Column("budget", sa.Float(), nullable=False),
            sa.Column("cash_remaining", sa.Float(), nullable=False),
            sa.Column("hold_horizon_ticks", sa.Integer(), nullable=True),
            sa.Column("risk_appetite", sa.Float(), nullable=True),
            sa.Column("diversification_cap", sa.Integer(), nullable=True),
            sa.Column("preferred_property_types", JSONB(), nullable=True, server_default=_JSONB_DEFAULT_ARRAY),
            sa.Column("signal_weights", JSONB(), nullable=True, server_default=_JSONB_DEFAULT_OBJECT),
            sa.Column("persona_profile", JSONB(), nullable=True, server_default=_JSONB_DEFAULT_OBJECT),
            sa.Column("holdings", JSONB(), nullable=True, server_default=_JSONB_DEFAULT_ARRAY),
            sa.Column("metadata_json", JSONB(), nullable=True, server_default=_JSONB_DEFAULT_OBJECT),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
    else:
        investor_columns = _column_names(inspector, "market_simulation_investors")
        if "persona_profile" not in investor_columns:
            op.add_column(
                "market_simulation_investors",
                sa.Column("persona_profile", JSONB(), nullable=True, server_default=_JSONB_DEFAULT_OBJECT),
            )
    if "ix_market_sim_investors_run" not in _index_names(inspector, "market_simulation_investors"):
        op.create_index(
            "ix_market_sim_investors_run",
            "market_simulation_investors",
            ["run_id"],
        )

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "market_simulation_property_states"):
        op.create_table(
            "market_simulation_property_states",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("run_id", sa.String(), sa.ForeignKey("market_simulation_runs.id"), nullable=False),
            sa.Column("property_id", sa.String(), sa.ForeignKey("properties.id"), nullable=False),
            sa.Column("tick_num", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(), nullable=True),
            sa.Column("attention_count", sa.Integer(), nullable=True),
            sa.Column("bid_count", sa.Integer(), nullable=True),
            sa.Column("top_bid", sa.Float(), nullable=True),
            sa.Column("bid_velocity", sa.Float(), nullable=True),
            sa.Column("local_competition", sa.Float(), nullable=True),
            sa.Column("recent_attention", sa.Float(), nullable=True),
            sa.Column("reservation_threshold", sa.Float(), nullable=False),
            sa.Column("winning_investor_id", sa.String(), sa.ForeignKey("market_simulation_investors.id"), nullable=True),
            sa.Column("signal_snapshot", JSONB(), nullable=True, server_default=_JSONB_DEFAULT_OBJECT),
            sa.Column("targeted_investor_ids", JSONB(), nullable=True, server_default=_JSONB_DEFAULT_ARRAY),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
    property_state_indexes = _index_names(inspector, "market_simulation_property_states")
    if "ix_market_sim_property_state_run_tick" not in property_state_indexes:
        op.create_index(
            "ix_market_sim_property_state_run_tick",
            "market_simulation_property_states",
            ["run_id", "tick_num"],
        )
    if "ix_market_sim_property_state_property" not in property_state_indexes:
        op.create_index(
            "ix_market_sim_property_state_property",
            "market_simulation_property_states",
            ["property_id", "tick_num"],
        )

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "market_simulation_decisions"):
        op.create_table(
            "market_simulation_decisions",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("run_id", sa.String(), sa.ForeignKey("market_simulation_runs.id"), nullable=False),
            sa.Column("tick_num", sa.Integer(), nullable=False),
            sa.Column("investor_id", sa.String(), sa.ForeignKey("market_simulation_investors.id"), nullable=False),
            sa.Column("property_id", sa.String(), sa.ForeignKey("properties.id"), nullable=True),
            sa.Column("chosen_action", sa.String(), nullable=False),
            sa.Column("bid_amount", sa.Float(), nullable=True),
            sa.Column("total_score", sa.Float(), nullable=True),
            sa.Column("score_breakdown", JSONB(), nullable=True, server_default=_JSONB_DEFAULT_OBJECT),
            sa.Column("explanation_payload", JSONB(), nullable=True, server_default=_JSONB_DEFAULT_OBJECT),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
    decision_indexes = _index_names(inspector, "market_simulation_decisions")
    if "ix_market_sim_decision_run_tick" not in decision_indexes:
        op.create_index(
            "ix_market_sim_decision_run_tick",
            "market_simulation_decisions",
            ["run_id", "tick_num"],
        )
    if "ix_market_sim_decision_investor_tick" not in decision_indexes:
        op.create_index(
            "ix_market_sim_decision_investor_tick",
            "market_simulation_decisions",
            ["investor_id", "tick_num"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "market_simulation_decisions"):
        decision_indexes = _index_names(inspector, "market_simulation_decisions")
        if "ix_market_sim_decision_investor_tick" in decision_indexes:
            op.drop_index("ix_market_sim_decision_investor_tick", table_name="market_simulation_decisions")
        if "ix_market_sim_decision_run_tick" in decision_indexes:
            op.drop_index("ix_market_sim_decision_run_tick", table_name="market_simulation_decisions")
        op.drop_table("market_simulation_decisions")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "market_simulation_property_states"):
        property_state_indexes = _index_names(inspector, "market_simulation_property_states")
        if "ix_market_sim_property_state_property" in property_state_indexes:
            op.drop_index("ix_market_sim_property_state_property", table_name="market_simulation_property_states")
        if "ix_market_sim_property_state_run_tick" in property_state_indexes:
            op.drop_index("ix_market_sim_property_state_run_tick", table_name="market_simulation_property_states")
        op.drop_table("market_simulation_property_states")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "market_simulation_investors"):
        investor_indexes = _index_names(inspector, "market_simulation_investors")
        if "ix_market_sim_investors_run" in investor_indexes:
            op.drop_index("ix_market_sim_investors_run", table_name="market_simulation_investors")
        op.drop_table("market_simulation_investors")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "market_simulation_runs"):
        run_indexes = _index_names(inspector, "market_simulation_runs")
        if "ix_market_sim_runs_status_created" in run_indexes:
            op.drop_index("ix_market_sim_runs_status_created", table_name="market_simulation_runs")
        op.drop_table("market_simulation_runs")
