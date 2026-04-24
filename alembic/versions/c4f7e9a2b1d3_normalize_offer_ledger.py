"""normalize offer ledger for negotiation-scoped history

Revision ID: c4f7e9a2b1d3
Revises: 7a3f91c2d5e8
Create Date: 2026-04-16 12:15:00.000000

Makes the `offers` table capable of acting as the authoritative negotiation
ledger by ensuring the negotiation/actor/parent/message fields and indexes
exist in migrated environments. Existing legacy rows are left intact so the
application can fall back safely while new writes use the normalized shape.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4f7e9a2b1d3"
down_revision: Union[str, None] = "7a3f91c2d5e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "offers"):
        return

    columns = _column_names(inspector, "offers")

    with op.batch_alter_table("offers") as batch:
        if "negotiation_id" not in columns:
            batch.add_column(
                sa.Column("negotiation_id", sa.String(), nullable=True)
            )
            batch.create_foreign_key(
                "fk_offers_negotiation_id_negotiations",
                "negotiations",
                ["negotiation_id"],
                ["id"],
            )
        if "actor_role" not in columns:
            batch.add_column(sa.Column("actor_role", sa.String(), nullable=True))
        if "actor_user_id" not in columns:
            batch.add_column(
                sa.Column("actor_user_id", sa.String(), nullable=True)
            )
            batch.create_foreign_key(
                "fk_offers_actor_user_id_user_profiles",
                "user_profiles",
                ["actor_user_id"],
                ["id"],
            )
        if "parent_offer_id" not in columns:
            batch.add_column(
                sa.Column("parent_offer_id", sa.String(), nullable=True)
            )
            batch.create_foreign_key(
                "fk_offers_parent_offer_id_offers",
                "offers",
                ["parent_offer_id"],
                ["id"],
            )
        if "message" not in columns:
            batch.add_column(sa.Column("message", sa.Text(), nullable=True))

    inspector = sa.inspect(bind)
    indexes = _index_names(inspector, "offers")
    if "ix_offers_negotiation_id" not in indexes:
        op.create_index("ix_offers_negotiation_id", "offers", ["negotiation_id"])
    if "ix_offers_actor_user_id" not in indexes:
        op.create_index("ix_offers_actor_user_id", "offers", ["actor_user_id"])
    if "ix_offers_parent_offer_id" not in indexes:
        op.create_index("ix_offers_parent_offer_id", "offers", ["parent_offer_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "offers"):
        return

    indexes = _index_names(inspector, "offers")
    for index_name in (
        "ix_offers_parent_offer_id",
        "ix_offers_actor_user_id",
        "ix_offers_negotiation_id",
    ):
        if index_name in indexes:
            op.drop_index(index_name, table_name="offers")

    columns = _column_names(sa.inspect(bind), "offers")
    with op.batch_alter_table("offers") as batch:
        if "message" in columns:
            batch.drop_column("message")
        if "parent_offer_id" in columns:
            batch.drop_column("parent_offer_id")
        if "actor_user_id" in columns:
            batch.drop_column("actor_user_id")
        if "actor_role" in columns:
            batch.drop_column("actor_role")
        if "negotiation_id" in columns:
            batch.drop_column("negotiation_id")
