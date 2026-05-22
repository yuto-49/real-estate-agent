"""add investor portfolio tables + UserProfile.preferred_mode

Revision ID: a72c98e5f441
Revises: f3a8b1d472e0
Create Date: 2026-05-14 01:30:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "a72c98e5f441"
down_revision: Union[str, None] = "f3a8b1d472e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_exists(inspector: sa.Inspector, table: str, column: str) -> bool:
    return column in {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # ── 1. preferred_mode column on user_profiles ────────────────────
    if _table_exists(inspector, "user_profiles") and not _column_exists(
        inspector, "user_profiles", "preferred_mode"
    ):
        op.add_column(
            "user_profiles",
            sa.Column(
                "preferred_mode",
                sa.String(),
                nullable=False,
                server_default="institutional",
            ),
        )

    # ── 2. investor_portfolios ────────────────────────────────────────
    if not _table_exists(inspector, "investor_portfolios"):
        op.create_table(
            "investor_portfolios",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column(
                "user_id",
                sa.String(),
                sa.ForeignKey("user_profiles.id"),
                nullable=False,
            ),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column(
                "investment_strategy",
                sa.String(),
                nullable=False,
                server_default="buy_hold",
            ),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index(
            "ix_investor_portfolios_user", "investor_portfolios", ["user_id"]
        )

    # ── 3. portfolio_holdings ─────────────────────────────────────────
    if not _table_exists(inspector, "portfolio_holdings"):
        op.create_table(
            "portfolio_holdings",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column(
                "portfolio_id",
                sa.String(),
                sa.ForeignKey("investor_portfolios.id"),
                nullable=False,
            ),
            sa.Column(
                "property_id",
                sa.String(),
                sa.ForeignKey("properties.id"),
                nullable=True,
            ),
            sa.Column("address", sa.String(), nullable=False),
            sa.Column("latitude", sa.Float(), nullable=True),
            sa.Column("longitude", sa.Float(), nullable=True),
            sa.Column("zip_code", sa.String(), nullable=True),
            sa.Column(
                "asset_class", sa.String(), nullable=False, server_default="sfr"
            ),
            sa.Column(
                "status", sa.String(), nullable=False, server_default="held"
            ),
            sa.Column("acquisition_date", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index(
            "ix_portfolio_holdings_portfolio",
            "portfolio_holdings",
            ["portfolio_id"],
        )
        op.create_index(
            "ix_portfolio_holdings_property",
            "portfolio_holdings",
            ["property_id"],
        )

    # ── 4. holding_financials ─────────────────────────────────────────
    if not _table_exists(inspector, "holding_financials"):
        op.create_table(
            "holding_financials",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column(
                "holding_id",
                sa.String(),
                sa.ForeignKey("portfolio_holdings.id"),
                nullable=False,
            ),
            sa.Column("cost_basis", sa.Float(), nullable=True),
            sa.Column("current_value_estimate", sa.Float(), nullable=True),
            sa.Column("value_estimate_source", sa.String(), nullable=True),
            sa.Column("loan_balance", sa.Float(), nullable=True),
            sa.Column("interest_rate", sa.Float(), nullable=True),
            sa.Column("loan_maturity", sa.DateTime(), nullable=True),
            sa.Column("monthly_piti", sa.Float(), nullable=True),
            sa.Column("monthly_rent", sa.Float(), nullable=True),
            sa.Column("vacancy_rate", sa.Float(), nullable=True),
            sa.Column("monthly_opex_estimate", sa.Float(), nullable=True),
            sa.Column("property_tax_annual", sa.Float(), nullable=True),
            sa.Column("insurance_annual", sa.Float(), nullable=True),
            sa.Column("last_updated", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index(
            "ix_holding_financials_holding",
            "holding_financials",
            ["holding_id"],
        )

    # ── 5. underwriting_scenarios ─────────────────────────────────────
    if not _table_exists(inspector, "underwriting_scenarios"):
        op.create_table(
            "underwriting_scenarios",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column(
                "holding_id",
                sa.String(),
                sa.ForeignKey("portfolio_holdings.id"),
                nullable=True,
            ),
            sa.Column("correlation_id", sa.String(), nullable=True),
            sa.Column("label", sa.String(), nullable=True),
            sa.Column("inputs", JSONB(), nullable=True),
            sa.Column("outputs", JSONB(), nullable=True),
            sa.Column("hazard_signals", JSONB(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index(
            "ix_underwriting_scenarios_holding",
            "underwriting_scenarios",
            ["holding_id"],
        )
        op.create_index(
            "ix_underwriting_scenarios_created",
            "underwriting_scenarios",
            ["created_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for tbl, idxs in [
        (
            "underwriting_scenarios",
            ["ix_underwriting_scenarios_created", "ix_underwriting_scenarios_holding"],
        ),
        ("holding_financials", ["ix_holding_financials_holding"]),
        (
            "portfolio_holdings",
            ["ix_portfolio_holdings_property", "ix_portfolio_holdings_portfolio"],
        ),
        ("investor_portfolios", ["ix_investor_portfolios_user"]),
    ]:
        if _table_exists(inspector, tbl):
            for idx in idxs:
                op.drop_index(idx, table_name=tbl)
            op.drop_table(tbl)

    if _table_exists(inspector, "user_profiles") and _column_exists(
        inspector, "user_profiles", "preferred_mode"
    ):
        op.drop_column("user_profiles", "preferred_mode")
