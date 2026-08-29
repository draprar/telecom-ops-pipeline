"""initial schema

Represents the schema as it existed BEFORE the (task_id, UNIQUE) fix that
was originally applied by hand via psql - see the next migration for that
change. Reproduced here as a separate step (rather than folded into one
"final" schema) specifically to demonstrate migrating a database that
already has this table and data, not just creating a fresh one.

Revision ID: 481c46cc63b7
Revises:
Create Date: 2026-08-28 21:55:01.889807

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '481c46cc63b7'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "dim_technician",
        sa.Column("technician_id", sa.Integer(), primary_key=True),
        sa.Column("full_name", sa.String(length=100), nullable=False, unique=True),
        sa.Column("region", sa.String(length=50)),
        sa.Column("hire_date", sa.Date()),
    )

    op.create_table(
        "dim_material",
        sa.Column("material_id", sa.Integer(), primary_key=True),
        sa.Column("material_name", sa.String(length=100), nullable=False, unique=True),
        sa.Column("unit_cost", sa.Numeric(10, 2)),
    )

    op.create_table(
        "dim_date",
        sa.Column("date_id", sa.Integer(), primary_key=True),
        sa.Column("full_date", sa.Date(), nullable=False, unique=True),
        sa.Column("year", sa.Integer()),
        sa.Column("month", sa.Integer()),
        sa.Column("day", sa.Integer()),
        sa.Column("weekday", sa.String(length=10)),
    )

    op.create_table(
        "fact_work_orders",
        sa.Column("work_order_id", sa.Integer(), primary_key=True),
        # Deliberately NOT unique here - that constraint is added in the
        # next migration, matching what actually happened to this database.
        sa.Column("task_id", sa.Integer()),
        sa.Column(
            "technician_id", sa.Integer(), sa.ForeignKey("dim_technician.technician_id")
        ),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("dim_material.material_id")),
        sa.Column("date_id", sa.Integer(), sa.ForeignKey("dim_date.date_id")),
        sa.Column("task_type", sa.String(length=50)),
        sa.Column("duration_minutes", sa.Integer()),
        sa.Column("material_quantity", sa.Numeric(10, 2)),
        sa.Column("total_cost", sa.Numeric(10, 2)),
        sa.Column("status", sa.String(length=20)),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("fact_work_orders")
    op.drop_table("dim_date")
    op.drop_table("dim_material")
    op.drop_table("dim_technician")