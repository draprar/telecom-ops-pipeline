import logging
import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


POSTGRES_CONN_ID = os.getenv("POSTGRES_CONN_ID", "telecom_ops_postgres")


def _connect_from_env():
    """Fallback used by the standalone `app` container and local dev, where
    there is no Airflow metadata database to hold a Connection."""
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


def get_connection():
    """Get a psycopg2 connection.

    Prefers an Airflow Connection (encrypted at rest, editable from the UI
    without touching code or redeploying) when running inside Airflow. Falls
    back to plain env vars for the standalone `app` container / local runs,
    where Airflow's metadata store doesn't exist.
    """
    try:
        from airflow.exceptions import AirflowNotFoundException
        from airflow.hooks.base import BaseHook
    except ImportError:
        # Not running inside Airflow at all.
        return _connect_from_env()

    try:
        conn = BaseHook.get_connection(POSTGRES_CONN_ID)
    except AirflowNotFoundException:
        logger.warning(
            "Airflow Connection '%s' not configured, falling back to env vars. "
            "Set it up via the UI or AIRFLOW_CONN_%s for production use.",
            POSTGRES_CONN_ID,
            POSTGRES_CONN_ID.upper(),
        )
        return _connect_from_env()

    return psycopg2.connect(
        host=conn.host,
        port=conn.port,
        dbname=conn.schema,
        user=conn.login,
        password=conn.password,
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
    logger.info("Loaded %d technician row(s) (deduplicated on full_name).", len(rows))


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
    logger.info("Loaded %d material row(s) (deduplicated on material_name).", len(rows))


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
    logger.info("Loaded %d date row(s).", len(rows))


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
                (task_id, technician_id, material_id, date_id, task_type,
                duration_minutes, material_quantity, total_cost, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (task_id) DO UPDATE SET
                technician_id = EXCLUDED.technician_id,
                material_id = EXCLUDED.material_id,
                date_id = EXCLUDED.date_id,
                task_type = EXCLUDED.task_type,
                duration_minutes = EXCLUDED.duration_minutes,
                material_quantity = EXCLUDED.material_quantity,
                total_cost = EXCLUDED.total_cost,
                status = EXCLUDED.status
            """,
            (
                row["task_id"],
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
    logger.info("Upserted %d fact row(s) into fact_work_orders.", len(fact_rows))
