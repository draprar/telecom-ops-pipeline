CREATE TABLE dim_technician (
    technician_id SERIAL PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    region VARCHAR(50),
    hire_date DATE
);

CREATE TABLE dim_material (
    material_id SERIAL PRIMARY KEY,
    material_name VARCHAR(100) NOT NULL,
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
    technician_id INT REFERENCES dim_technician(technician_id),
    material_id INT REFERENCES dim_material(material_id),
    date_id INT REFERENCES dim_date(date_id),
    task_type VARCHAR(50),
    duration_minutes INT,
    material_quantity NUMERIC(10,2),
    total_cost NUMERIC(10,2),
    status VARCHAR(20)
);