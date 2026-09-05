"""store quarantined source rows in postgres

Row-level DQ findings are committed to quarantine_records before the
star schema load, so a later fact failure does not lose the review
queue. JSON files are not the source of truth.

Revision ID: e91b4c7a2d08
Revises: c3f8a1b0e4d2
Create Date: 2026-09-05 15:20:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "e91b4c7a2d08"
down_revision: str | Sequence[str] | None = "c3f8a1b0e4d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "quarantine_records",
        sa.Column("quarantine_id", sa.Integer(), primary_key=True),
        sa.Column(
            "loaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("pipeline_run_id", sa.String(length=200), nullable=False),
        sa.Column("source_system", sa.String(length=32), nullable=False),
        sa.Column("task_id", sa.String(length=64)),
        sa.Column("source_row", JSONB(), nullable=False),
        sa.Column("errors", sa.ARRAY(sa.Text()), nullable=False),
    )
    op.create_index(
        "ix_quarantine_records_pipeline_run_id",
        "quarantine_records",
        ["pipeline_run_id"],
    )
    op.create_index(
        "ix_quarantine_records_source_task",
        "quarantine_records",
        ["source_system", "task_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_quarantine_records_source_task", table_name="quarantine_records")
    op.drop_index(
        "ix_quarantine_records_pipeline_run_id", table_name="quarantine_records"
    )
    op.drop_table("quarantine_records")
