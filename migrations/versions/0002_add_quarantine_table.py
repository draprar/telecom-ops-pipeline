"""Add pipeline_quarantine table for records rejected by validation.

Backs the src/quarantine.py helper so validation failures are queryable
history instead of only console log lines.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-26
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS pipeline_quarantine (
            id SERIAL PRIMARY KEY,
            run_id VARCHAR(255) NOT NULL,
            record_type VARCHAR(50) NOT NULL,
            payload JSONB NOT NULL,
            reason TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_pipeline_quarantine_run_id ON pipeline_quarantine (run_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS pipeline_quarantine")
