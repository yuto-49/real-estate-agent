"""add JP listing tier columns

Adds the discriminator columns that drive the recommender, depreciation
engine, and analyst council:

- ``asset_tier`` — ONE_ROOM / APARUTO / FAMILY_MANSION
- ``construction_type`` — wood / light_steel / steel / rc / src (drives 法定耐用年数)
- ``seismic_code`` — kyu_taishin / shin_taishin (1981-06 cutoff)
- ``re_buildable`` — 再建築可否 flag
- ``road_frontage_m`` — meters of frontage on a public road
- ``ward_code`` — Tokyo 23区 code
- ``walk_minutes_to_station`` — nearest-station 駅徒歩 minutes
- ``assumed_monthly_rent_yen`` / ``occupancy_rate`` — yield inputs

All nullable; backfill happens via the listing-import pipeline.

Revision ID: a1c4e6b8d2f0
Revises: f9a1b2c3d4e5
Create Date: 2026-05-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1c4e6b8d2f0"
down_revision: Union[str, None] = "f9a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("properties", sa.Column("asset_tier", sa.String(32), nullable=True))
    op.add_column("properties", sa.Column("construction_type", sa.String(32), nullable=True))
    op.add_column("properties", sa.Column("seismic_code", sa.String(32), nullable=True))
    op.add_column("properties", sa.Column("re_buildable", sa.Integer, nullable=True))
    op.add_column("properties", sa.Column("road_frontage_m", sa.Float, nullable=True))
    op.add_column("properties", sa.Column("ward_code", sa.String(8), nullable=True))
    op.add_column("properties", sa.Column("walk_minutes_to_station", sa.Integer, nullable=True))
    op.add_column("properties", sa.Column("assumed_monthly_rent_yen", sa.Integer, nullable=True))
    op.add_column("properties", sa.Column("occupancy_rate", sa.Float, nullable=True))
    op.create_index("ix_properties_asset_tier", "properties", ["asset_tier"])
    op.create_index("ix_properties_ward_code", "properties", ["ward_code"])


def downgrade() -> None:
    op.drop_index("ix_properties_ward_code", table_name="properties")
    op.drop_index("ix_properties_asset_tier", table_name="properties")
    for col in (
        "occupancy_rate",
        "assumed_monthly_rent_yen",
        "walk_minutes_to_station",
        "ward_code",
        "road_frontage_m",
        "re_buildable",
        "seismic_code",
        "construction_type",
        "asset_tier",
    ):
        op.drop_column("properties", col)
