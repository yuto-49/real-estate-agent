"""drop negotiation, social-sim, market-sim, and mirofish tables

Pivot away from the buyer/seller chat product, NIMBY social simulator, and the
synthetic tick-based market simulator. The platform is being narrowed to JP
investor portfolio analytics (one-room mansion / aparuto / family mansion).

Tables removed:
- negotiation: ``negotiations``, ``offers``, ``agent_decisions``, ``agent_memory``,
  ``simulation_results``
- social sim: ``social_simulation_actions``, ``social_simulation_runs``,
  ``household_social_edges``, ``household_profiles``
- market sim: ``market_simulation_decisions``,
  ``market_simulation_property_states``, ``market_simulation_investors``,
  ``market_simulation_runs``
- mirofish: ``mirofish_reports``, ``mirofish_seeds``

``IF EXISTS`` is used because the prior ``Base.metadata.create_all`` startup
hook means some of these may exist outside Alembic's history. ``CASCADE``
covers indexes/FKs that the create-all path attached.

Revision ID: f9a1b2c3d4e5
Revises: d423ecdb672f
Create Date: 2026-05-28
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f9a1b2c3d4e5"
down_revision: Union[str, None] = "d423ecdb672f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Order matters: drop children before parents so a non-CASCADE Postgres
# config (or SQLite in tests) still succeeds.
_TABLES_TO_DROP = (
    # social sim
    "social_simulation_actions",
    "social_simulation_runs",
    "household_social_edges",
    "household_profiles",
    # negotiation chat product
    "agent_decisions",
    "agent_memory",
    "offers",
    "negotiations",
    "simulation_results",
    # mirofish stub
    "mirofish_reports",
    "mirofish_seeds",
    # market sim
    "market_simulation_decisions",
    "market_simulation_property_states",
    "market_simulation_investors",
    "market_simulation_runs",
)


def upgrade() -> None:
    for table in _TABLES_TO_DROP:
        op.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')


def downgrade() -> None:
    # Intentionally not reversible. These features are deleted, not paused.
    # Restoring them means re-running the original add_* migrations from
    # source control history, not running a downgrade here.
    raise NotImplementedError(
        "f9a1b2c3d4e5 is a one-way deletion. Restore from git history if needed."
    )
