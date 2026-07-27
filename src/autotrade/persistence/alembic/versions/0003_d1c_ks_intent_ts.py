"""0003_d1c_ks_intent_ts

Revision ID: 0003_d1c_ks_intent_ts
Revises: 0002_d1b_certify
Create Date: 2026-07-27

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_d1c_ks_intent_ts"
down_revision: str | None = "0002_d1b_certify"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # KillSwitch.persist/.load filter by scope and call .one_or_none() —
    # duplicate scopes would raise MultipleResultsFound, and Pause (KS L1)
    # must never fail. Keep the newest row per scope (max id) before adding
    # the constraint so this migration doesn't fail against a DB that
    # already has dupes.
    op.execute(
        "DELETE FROM kill_switch_state "
        "WHERE id NOT IN (SELECT MAX(id) FROM kill_switch_state GROUP BY scope)"
    )
    with op.batch_alter_table("kill_switch_state") as batch_op:
        batch_op.create_unique_constraint("uq_kill_switch_scope", ["scope"])

    # SQLite rejects a non-constant (CURRENT_TIMESTAMP) default on a plain
    # ALTER TABLE ADD COLUMN, so this needs batch mode (table recreate) —
    # batch mode still backfills existing rows via the new table's DEFAULT.
    with op.batch_alter_table("order_intents") as batch_op:
        batch_op.add_column(
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("order_intents") as batch_op:
        batch_op.drop_column("created_at")
    with op.batch_alter_table("kill_switch_state") as batch_op:
        # Intentional: does not resurrect the duplicate rows removed by upgrade().
        batch_op.drop_constraint("uq_kill_switch_scope", type_="unique")
