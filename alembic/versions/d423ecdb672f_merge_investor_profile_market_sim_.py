"""merge investor profile, market sim, negotiation heads

Revision ID: d423ecdb672f
Revises: 9d4c1f5b8a21, c1a9d75f0834, e4b6c2f7a1d0
Create Date: 2026-05-20 01:15:13.487665
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd423ecdb672f'
down_revision: Union[str, None] = ('9d4c1f5b8a21', 'c1a9d75f0834', 'e4b6c2f7a1d0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
