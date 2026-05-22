"""add supabase_user_id to user_profiles

Revision ID: 9b22e6b6c4b8
Revises: b0c55931823f
Create Date: 2026-04-08 18:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9b22e6b6c4b8"
down_revision: Union[str, None] = "b0c55931823f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotent: a parallel branch (f3a8b1d472e0) adds the same column, so on
    # a fresh DB whichever migration runs second would hit a duplicate column.
    # Guard with inspector checks so both branches can coexist.
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
        op.drop_index(
            "ix_user_profiles_supabase_user_id", table_name="user_profiles"
        )

    columns = {col["name"] for col in inspector.get_columns("user_profiles")}
    if "supabase_user_id" in columns:
        op.drop_column("user_profiles", "supabase_user_id")
