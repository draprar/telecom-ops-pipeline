import os

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import Json

from quarantine import SOURCE_CRM_TASKS, SOURCE_ERP_MATERIALS

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
            ON CONFLICT (full_name) DO UPDATE SET
                region = EXCLUDED.region,
                hire_date = EXCLUDED.hire_date
            """,
            (row["full_name"], row["region"], row["hire_date"]),
        )

def load_dim_material(cur, rows):
    for row in rows:
        cur.execute(
            """
            INSERT INTO dim_material (material_name, unit_cost)
            VALUES (%s, %s)
            ON CONFLICT (material_name) DO UPDATE SET
                unit_cost = EXCLUDED.unit_cost
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

def load_facts(cur, fact_rows, tech_map, date_map):
    for row in fact_rows:
        cur.execute(
            """
            INSERT INTO fact_work_orders
                (task_id, technician_id, date_id, task_type, duration_minutes, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (task_id) DO UPDATE SET
                technician_id = EXCLUDED.technician_id,
                date_id = EXCLUDED.date_id,
                task_type = EXCLUDED.task_type,
                duration_minutes = EXCLUDED.duration_minutes,
                status = EXCLUDED.status
            """,
            (
                row["task_id"],
                tech_map.get(row["technician_name"]),
                date_map.get(row["task_date"]),
                row["task_type"],
                row["duration_minutes"],
                row["status"],
            ),
        )


def replace_material_lines(cur, material_lines, material_map, batch_task_ids):
    """Replace all material lines for tasks in this batch.

    A full-file reload can drop a material from a task; DELETE-then-INSERT
    is the snapshot-safe way to drop stale (task_id, material_id) pairs.
    """
    if batch_task_ids:
        cur.execute(
            "DELETE FROM fact_work_order_materials WHERE task_id = ANY(%s)",
            (list(batch_task_ids),),
        )
    for row in material_lines:
        cur.execute(
            """
            INSERT INTO fact_work_order_materials
                (task_id, material_id, quantity, line_cost)
            VALUES (%s, %s, %s, %s)
            """,
            (
                row["task_id"],
                material_map.get(row["material_name"]),
                row["quantity"],
                row["line_cost"],
            ),
        )


def _task_id_text(record):
    if not isinstance(record, dict) or record.get("task_id") is None:
        return None
    text = str(record["task_id"]).strip()
    return text or None


def load_quarantine_records(cur, pipeline_run_id, quarantined_tasks, quarantined_materials):
    """Insert DQ rows for this run. Does not commit."""
    rows = [
        (SOURCE_CRM_TASKS, entry) for entry in quarantined_tasks
    ] + [
        (SOURCE_ERP_MATERIALS, entry) for entry in quarantined_materials
    ]
    for source_system, entry in rows:
        record = entry.get("record") or {}
        errors = list(entry.get("errors") or [])
        cur.execute(
            """
            INSERT INTO quarantine_records
                (pipeline_run_id, source_system, task_id, source_row, errors)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                pipeline_run_id,
                source_system,
                _task_id_text(record),
                Json(record),
                errors,
            ),
        )


def commit_quarantine_records(
    conn, pipeline_run_id, quarantined_tasks, quarantined_materials
):
    """Commit the DQ table in its own transaction, before star load."""
    if not quarantined_tasks and not quarantined_materials:
        return
    try:
        with conn.cursor() as cur:
            load_quarantine_records(
                cur, pipeline_run_id, quarantined_tasks, quarantined_materials
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def load_pipeline(
    conn,
    pipeline_run_id,
    quarantined_tasks,
    quarantined_materials,
    dim_technician_rows,
    dim_material_rows,
    dim_date_rows,
    fact_rows,
    material_lines,
):
    """Commit quarantine first, then load dimensions and facts."""
    commit_quarantine_records(
        conn, pipeline_run_id, quarantined_tasks, quarantined_materials
    )
    load_star_schema(
        conn,
        dim_technician_rows,
        dim_material_rows,
        dim_date_rows,
        fact_rows,
        material_lines,
    )


def load_star_schema(
    conn,
    dim_technician_rows,
    dim_material_rows,
    dim_date_rows,
    fact_rows,
    material_lines,
):
    """Load dimensions, facts, then material lines in one transaction."""
    try:
        with conn.cursor() as cur:
            load_dim_technician(cur, dim_technician_rows)
            load_dim_material(cur, dim_material_rows)
            load_dim_date(cur, dim_date_rows)
            tech_map, material_map, date_map = get_id_maps(cur)
            load_facts(cur, fact_rows, tech_map, date_map)
            replace_material_lines(
                cur,
                material_lines,
                material_map,
                {row["task_id"] for row in fact_rows},
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise