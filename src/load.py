import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD")
    )

def load_dim_technician(cur, rows):
    for row in rows:
        cur.execute(
            """
            INSERT INTO dim_technician (full_name, region, hire_date)
            VALUES (%s, %s, %s)
            ON CONFLICT (full_name) DO NOTHING
            """,
            (row["full_name"], row["region"], row["hire_date"]),
        )

def load_dim_material(cur, rows):
    for row in rows:
        cur.execute(
            """
            INSERT INTO dim_material (material_name, unit_cost)
            VALUES (%s, %s)
            ON CONFLICT (material_name) DO NOTHING
            """,
            (row["material_name"], row["unit_cost"]),
        )
 
 
def load_dim_date(cur, rows):
    for row in rows:
        cur.execute(
            """
            INSERT INTO dim_date (full_date, year, month, day, weekday)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (full_date) DO NOTHING
            """,
            (row["full_date"], row["year"], row["month"], row["day"], row["weekday"]),
        )

def get_id_maps(cur):
    cur.execute("SELECT technician_id, full_name FROM dim_technician")
    tech_map = {name: tid for tid, name in cur.fetchall()}
 
    cur.execute("SELECT material_id, material_name FROM dim_material")
    material_map = {name: mid for mid, name in cur.fetchall()}
 
    cur.execute("SELECT date_id, full_date FROM dim_date")
    date_map = {str(d): did for did, d in cur.fetchall()}
 
    return tech_map, material_map, date_map

def load_facts(cur, fact_rows, tech_map, material_map, date_map):
    for row in fact_rows:
        cur.execute(
            """
            INSERT INTO fact_work_orders
                (technician_id, material_id, date_id, task_type,
                 duration_minutes, material_quantity, total_cost, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                tech_map.get(row["technician_name"]),
                material_map.get(row["material_name"]),
                date_map.get(row["task_date"]),
                row["task_type"],
                row["duration_minutes"],
                row["material_quantity"],
                row["total_cost"],
                row["status"],
            ),
        )