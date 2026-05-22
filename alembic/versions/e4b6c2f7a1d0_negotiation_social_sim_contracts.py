"""merge negotiation ledger and social-sim lifecycle contracts

Revision ID: e4b6c2f7a1d0
Revises: 9b22e6b6c4b8, 7a3f91c2d5e8
Create Date: 2026-04-15 14:30:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "e4b6c2f7a1d0"
down_revision: Union[str, tuple[str, str], None] = ("9b22e6b6c4b8", "7a3f91c2d5e8")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_JSONB_EMPTY_ARRAY = sa.text("'[]'::jsonb")


def upgrade() -> None:
    with op.batch_alter_table("offers") as batch:
        batch.add_column(
            sa.Column(
                "negotiation_id",
                sa.String(),
                nullable=True,
            )
        )
        batch.add_column(sa.Column("actor_role", sa.String(), nullable=True))
        batch.add_column(
            sa.Column(
                "actor_user_id",
                sa.String(),
                nullable=True,
            )
        )
        batch.add_column(sa.Column("message", sa.Text(), nullable=True))
        batch.alter_column("buyer_id", existing_type=sa.String(), nullable=True)
        batch.create_foreign_key(
            "fk_offers_negotiation_id_negotiations",
            "negotiations",
            ["negotiation_id"],
            ["id"],
        )
        batch.create_foreign_key(
            "fk_offers_actor_user_id_user_profiles",
            "user_profiles",
            ["actor_user_id"],
            ["id"],
        )

    op.create_index("ix_offers_negotiation_id", "offers", ["negotiation_id"], unique=False)

    # Best-effort phase-1 backfill so existing buyer-authored offers still resolve through actor fields.
    op.execute(
        sa.text(
            """
            UPDATE offers
            SET actor_role = COALESCE(actor_role, 'buyer'),
                actor_user_id = COALESCE(actor_user_id, buyer_id)
            WHERE buyer_id IS NOT NULL
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE offers AS offer
            SET negotiation_id = negotiation.id
            FROM negotiations AS negotiation
            WHERE offer.negotiation_id IS NULL
              AND offer.property_id = negotiation.property_id
              AND (offer.buyer_id IS NULL OR offer.buyer_id = negotiation.buyer_id)
            """
        )
    )

    with op.batch_alter_table("social_simulation_runs") as batch:
        batch.add_column(
            sa.Column(
                "household_ids",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
                server_default=_JSONB_EMPTY_ARRAY,
            )
        )
        batch.add_column(
            sa.Column(
                "household_count",
                sa.Integer(),
                nullable=True,
                server_default="0",
            )
        )

    op.execute(
        sa.text(
            """
            UPDATE social_simulation_runs
            SET household_ids = COALESCE(household_ids, '[]'::jsonb),
                household_count = COALESCE(household_count, 0)
            """
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("social_simulation_runs") as batch:
        batch.drop_column("household_count")
        batch.drop_column("household_ids")

    op.drop_index("ix_offers_negotiation_id", table_name="offers")

    with op.batch_alter_table("offers") as batch:
        batch.drop_constraint("fk_offers_actor_user_id_user_profiles", type_="foreignkey")
        batch.drop_constraint("fk_offers_negotiation_id_negotiations", type_="foreignkey")
        batch.alter_column("buyer_id", existing_type=sa.String(), nullable=False)
        batch.drop_column("message")
        batch.drop_column("actor_user_id")
        batch.drop_column("actor_role")
        batch.drop_column("negotiation_id")
