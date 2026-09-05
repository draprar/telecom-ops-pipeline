-- HISTORICAL REFERENCE ONLY.
--
-- This file is no longer applied automatically. It used to be mounted into
-- Postgres's docker-entrypoint-initdb.d/ and run on first container start,
-- but schema creation and changes are now owned by Alembic - see
-- migrations/versions/ and the `migrate` service in docker-compose.yml.
--
-- Kept here only as a single-file snapshot of the current ("head") schema
-- shape, for quick reference without having to read through every
-- migration file to reconstruct it.

CREATE TABLE dim_technician (
    technician_id SERIAL PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL UNIQUE,
    region VARCHAR(50),
    hire_date DATE
);

CREATE TABLE dim_material (
    material_id SERIAL PRIMARY KEY,
    material_name VARCHAR(100) NOT NULL UNIQUE,
    unit_cost NUMERIC(10,2)
);

CREATE TABLE dim_date (
    date_id SERIAL PRIMARY KEY,
    full_date DATE NOT NULL UNIQUE,
    year INT,
    month INT,
    day INT,
    weekday VARCHAR(10)
);

CREATE TABLE fact_work_orders (
    work_order_id SERIAL PRIMARY KEY,
    task_id INT UNIQUE,
    technician_id INT REFERENCES dim_technician(technician_id),
    date_id INT REFERENCES dim_date(date_id),
    task_type VARCHAR(50),
    duration_minutes INT,
    status VARCHAR(20)
);

CREATE TABLE fact_work_order_materials (
    work_order_material_id SERIAL PRIMARY KEY,
    task_id INT NOT NULL REFERENCES fact_work_orders(task_id),
    material_id INT NOT NULL REFERENCES dim_material(material_id),
    quantity NUMERIC(10,2) NOT NULL,
    line_cost NUMERIC(10,2) NOT NULL,
    UNIQUE (task_id, material_id)
);

CREATE TABLE quarantine_records (
    quarantine_id SERIAL PRIMARY KEY,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    pipeline_run_id VARCHAR(200) NOT NULL,
    source_system VARCHAR(32) NOT NULL,
    task_id VARCHAR(64),
    source_row JSONB NOT NULL,
    errors TEXT[] NOT NULL
);

CREATE INDEX ix_quarantine_records_pipeline_run_id
    ON quarantine_records (pipeline_run_id);

CREATE INDEX ix_quarantine_records_source_task
    ON quarantine_records (source_system, task_id);