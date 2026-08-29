"""add unique constraint on fact_work_orders.task_id

Reproduces the fix that was originally applied by hand via psql: without
this, load_facts()'s ON CONFLICT (task_id) DO UPDATE upsert has nothing to
conflict on, so re-running the pipeline for the same task_id would insert
duplicate rows instead of updating the existing one.

Revision ID: d950881c7915
Revises: 481c46cc63b7
Create Date: 2026-08-28 21:55:12.240115

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd950881c7915'
down_revision: str | Sequence[str] | None = '481c46cc63b7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_unique_constraint(
        "uq_fact_work_orders_task_id", "fact_work_orders", ["task_id"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "uq_fact_work_orders_task_id", "fact_work_orders", type_="unique"
    )
