"""Initial star schema (dim_technician, dim_material, dim_date, fact_work_orders).

This mirrors sql/schema.sql as it exists today, including the task_id UNIQUE
constraint on fact_work_orders (previously applied by hand via psql, and
subsequently added to schema.sql for fresh installs). From this point on,
schema changes go through a new Alembic revision instead of hand edits.

Revision ID: 0001
Revises:
Create Date: 2026-08-26
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS dim_technician (
            technician_id SERIAL PRIMARY KEY,
            full_name VARCHAR(100) NOT NULL UNIQUE,
            region VARCHAR(50),
            hire_date DATE
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS dim_material (
            material_id SERIAL PRIMARY KEY,
            material_name VARCHAR(100) NOT NULL UNIQUE,
            unit_cost NUMERIC(10,2)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS dim_date (
            date_id SERIAL PRIMARY KEY,
            full_date DATE NOT NULL UNIQUE,
            year INT,
            month INT,
            day INT,
            weekday VARCHAR(10)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS fact_work_orders (
            work_order_id SERIAL PRIMARY KEY,
            task_id INT UNIQUE,
            technician_id INT REFERENCES dim_technician(technician_id),
            material_id INT REFERENCES dim_material(material_id),
            date_id INT REFERENCES dim_date(date_id),
            task_type VARCHAR(50),
            duration_minutes INT,
            material_quantity NUMERIC(10,2),
            total_cost NUMERIC(10,2),
            status VARCHAR(20)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS fact_work_orders")
    op.execute("DROP TABLE IF EXISTS dim_date")
    op.execute("DROP TABLE IF EXISTS dim_material")
    op.execute("DROP TABLE IF EXISTS dim_technician")
