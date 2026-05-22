"""add investor_profiles table (onboarding wizard P4)

Revision ID: c1a9d75f0834
Revises: a72c98e5f441
Create Date: 2026-05-17 02:30:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "c1a9d75f0834"
down_revision: Union[str, None] = "a72c98e5f441"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "investor_profiles"):
        return

    op.create_table(
        "investor_profiles",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(),
            sa.ForeignKey("user_profiles.id"),
            nullable=False,
        ),
        sa.Column("budget", sa.Float(), nullable=True),
        sa.Column("strategy", sa.String(), nullable=True),
        sa.Column("target_cap_rate", sa.Float(), nullable=True),
        sa.Column("target_coc", sa.Float(), nullable=True),
        sa.Column(
            "geography",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_investor_profiles_user",
        "investor_profiles",
        ["user_id"],
        unique=True,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "investor_profiles"):
        return
    op.drop_index("ix_investor_profiles_user", table_name="investor_profiles")
    op.drop_table("investor_profiles")
