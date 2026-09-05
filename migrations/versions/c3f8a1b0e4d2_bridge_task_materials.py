"""bridge task materials and drop collapsed material columns on facts

Work orders can use several materials. fact_work_orders keeps one row per
task; fact_work_order_materials holds quantity and line_cost per
(task_id, material_id). Existing fact rows cannot be reconstructed into
lines — reload from source after upgrade.

Revision ID: c3f8a1b0e4d2
Revises: d950881c7915
Create Date: 2026-09-05 15:10:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3f8a1b0e4d2"
down_revision: str | Sequence[str] | None = "d950881c7915"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fact_work_order_materials",
        sa.Column("work_order_material_id", sa.Integer(), primary_key=True),
        sa.Column(
            "task_id",
            sa.Integer(),
            sa.ForeignKey("fact_work_orders.task_id"),
            nullable=False,
        ),
        sa.Column(
            "material_id",
            sa.Integer(),
            sa.ForeignKey("dim_material.material_id"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Numeric(10, 2), nullable=False),
        sa.Column("line_cost", sa.Numeric(10, 2), nullable=False),
        sa.UniqueConstraint(
            "task_id",
            "material_id",
            name="uq_fact_work_order_materials_task_material",
        ),
    )
    op.drop_column("fact_work_orders", "total_cost")
    op.drop_column("fact_work_orders", "material_quantity")
    op.drop_column("fact_work_orders", "material_id")


def downgrade() -> None:
    op.add_column(
        "fact_work_orders",
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("dim_material.material_id")),
    )
    op.add_column(
        "fact_work_orders",
        sa.Column("material_quantity", sa.Numeric(10, 2)),
    )
    op.add_column(
        "fact_work_orders",
        sa.Column("total_cost", sa.Numeric(10, 2)),
    )
    op.drop_table("fact_work_order_materials")
