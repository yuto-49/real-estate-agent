"""add supabase_user_id to user_profiles

Revision ID: f3a8b1d472e0
Revises: e1f8a9c4d572
Create Date: 2026-05-09 16:20:00.000000

Backfills the column that was added to ``UserProfile`` without an
accompanying migration. Idempotent — uses inspector checks so re-applying
on a DB that already has the column (added manually via ALTER) is a no-op.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3a8b1d472e0"
down_revision: Union[str, None] = "e1f8a9c4d572"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = {col["name"] for col in inspector.get_columns("user_profiles")}
    if "supabase_user_id" not in columns:
        op.add_column(
            "user_profiles",
            sa.Column("supabase_user_id", sa.String(), nullable=True),
        )

    indexes = {idx["name"] for idx in inspector.get_indexes("user_profiles")}
    if "ix_user_profiles_supabase_user_id" not in indexes:
        op.create_index(
            "ix_user_profiles_supabase_user_id",
            "user_profiles",
            ["supabase_user_id"],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    indexes = {idx["name"] for idx in inspector.get_indexes("user_profiles")}
    if "ix_user_profiles_supabase_user_id" in indexes:
        op.drop_index("ix_user_profiles_supabase_user_id", table_name="user_profiles")

    columns = {col["name"] for col in inspector.get_columns("user_profiles")}
    if "supabase_user_id" in columns:
        op.drop_column("user_profiles", "supabase_user_id")
