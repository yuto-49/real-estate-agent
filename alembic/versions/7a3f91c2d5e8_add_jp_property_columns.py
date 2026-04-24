"""add JP property columns (additive, nullable, Phase 1 of Tokyo release)

Revision ID: 7a3f91c2d5e8
Revises: b0c55931823f
Create Date: 2026-04-15 10:00:00.000000

Adds JP-specific columns to `properties` without dropping any US-era columns
or constraints. The application code branches on settings.jurisdiction, so
the legacy US path keeps working until Phase 2 swaps the guardrails.

JPY-precision columns use Numeric(15, 0) — Float is rejected because it
silently loses integer precision past 2^24 yen.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "7a3f91c2d5e8"
down_revision: Union[str, None] = "b0c55931823f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_JSONB_DEFAULT_OBJECT = sa.text("'{}'::jsonb")
_JSONB_DEFAULT_ARRAY = sa.text("'[]'::jsonb")


def upgrade() -> None:
    with op.batch_alter_table("properties") as batch:
        batch.add_column(
            sa.Column(
                "address_jp",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
                comment="Normalized JP address: todoufuken/shikuchouson/chome/banchi/go/building + codes",
            )
        )
        batch.add_column(
            sa.Column(
                "nearest_stations",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
                server_default=_JSONB_DEFAULT_ARRAY,
                comment="List of {line, station, walk_minutes}",
            )
        )
        batch.add_column(sa.Column("built_year", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column(
                "structure",
                sa.String(length=32),
                nullable=True,
                comment="RC|SRC|鉄骨|木造 etc.",
            )
        )
        batch.add_column(
            sa.Column("youto_chiiki", sa.String(length=64), nullable=True)
        )
        batch.add_column(sa.Column("kenpei_ritsu", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("youseki_ritsu", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("menseki_m2", sa.Float(), nullable=True))
        batch.add_column(
            sa.Column(
                "baibai_kakaku_yen",
                sa.Numeric(precision=15, scale=0),
                nullable=True,
                comment="Price in integer yen; preferred over asking_price for JP listings",
            )
        )
        batch.add_column(
            sa.Column("kanrihi_yen", sa.Integer(), nullable=True, comment="管理費/月")
        )
        batch.add_column(
            sa.Column(
                "shuuzenzumitatekin_yen",
                sa.Integer(),
                nullable=True,
                comment="修繕積立金/月",
            )
        )
        batch.add_column(
            sa.Column(
                "takken_bukken_bangou",
                sa.String(length=64),
                nullable=True,
                comment="REINS 物件番号 (nullable until REINS membership acquired)",
            )
        )
        batch.add_column(
            sa.Column(
                "hazard_flags",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
                server_default=_JSONB_DEFAULT_OBJECT,
                comment="{flood, tsunami, landslide, liquefaction} bool overlays",
            )
        )
        batch.add_column(
            sa.Column("currency", sa.String(length=3), nullable=True, server_default="JPY")
        )
        batch.add_column(
            sa.Column(
                "jurisdiction",
                sa.String(length=16),
                nullable=True,
                server_default="us",
                comment="us|jp_tokyo — routes code to guardrails_jp when jp_*",
            )
        )

    # Indexes used by Phase 4 retriever filter pushdown.
    op.create_index(
        "ix_properties_takken_bukken_bangou",
        "properties",
        ["takken_bukken_bangou"],
        unique=True,
        postgresql_where=sa.text("takken_bukken_bangou IS NOT NULL"),
    )
    op.create_index(
        "ix_properties_address_jp_gin",
        "properties",
        ["address_jp"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_properties_jurisdiction",
        "properties",
        ["jurisdiction"],
    )


def downgrade() -> None:
    op.drop_index("ix_properties_jurisdiction", table_name="properties")
    op.drop_index("ix_properties_address_jp_gin", table_name="properties")
    op.drop_index("ix_properties_takken_bukken_bangou", table_name="properties")
    with op.batch_alter_table("properties") as batch:
        for col in (
            "jurisdiction",
            "currency",
            "hazard_flags",
            "takken_bukken_bangou",
            "shuuzenzumitatekin_yen",
            "kanrihi_yen",
            "baibai_kakaku_yen",
            "menseki_m2",
            "youseki_ritsu",
            "kenpei_ritsu",
            "youto_chiiki",
            "structure",
            "built_year",
            "nearest_stations",
            "address_jp",
        ):
            batch.drop_column(col)
