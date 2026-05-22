"""add market_signals table for Phase B spatial market-state foundation

Revision ID: e1f8a9c4d572
Revises: c4f7e9a2b1d3
Create Date: 2026-05-05 20:10:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "e1f8a9c4d572"
down_revision: Union[str, None] = "c4f7e9a2b1d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "market_signals"):
        return

    op.create_table(
        "market_signals",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("signal_type", sa.String(), nullable=False),
        sa.Column("subject_type", sa.String(), nullable=False),
        sa.Column("subject_id", sa.String(), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("payload", JSONB(), nullable=True),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_market_signals_subject",
        "market_signals",
        ["subject_type", "subject_id"],
    )
    op.create_index(
        "ix_market_signals_type_observed",
        "market_signals",
        ["signal_type", "observed_at"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "market_signals"):
        return

    op.drop_index("ix_market_signals_type_observed", table_name="market_signals")
    op.drop_index("ix_market_signals_subject", table_name="market_signals")
    op.drop_table("market_signals")
