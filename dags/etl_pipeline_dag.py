import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from airflow import DAG
from airflow.operators.python import PythonOperator

from extract import load_crm_tasks, load_erp_materials, load_technician_logs
from validate import validate_tasks, validate_materials
from transform import build_dim_technician, build_dim_material, build_dim_date, build_fact_rows
from load import (
    get_connection,
    load_dim_technician,
    load_dim_material,
    load_dim_date,
    get_id_maps,
    load_facts,
)

STAGING_ROOT = Path(__file__).resolve().parent.parent / "data" / "staging"


def _staging_dir(run_id: str) -> Path:
    """Per-run staging folder so parallel DAG runs do not overwrite each other."""
    d = STAGING_ROOT / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_json(path: Path, data) -> str:
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def _read_json(path_str: str):
    return json.loads(Path(path_str).read_text(encoding="utf-8"))


def extract_task(ti, **kwargs):
    staging_dir = _staging_dir(ti.run_id)

    tasks_path = _write_json(staging_dir / "tasks.json", load_crm_tasks())
    materials_path = _write_json(staging_dir / "materials.json", load_erp_materials())
    tech_logs_path = _write_json(staging_dir / "tech_logs.json", load_technician_logs())

    ti.xcom_push(key="tasks_path", value=tasks_path)
    ti.xcom_push(key="materials_path", value=materials_path)
    ti.xcom_push(key="tech_logs_path", value=tech_logs_path)


def validate_task(ti, **kwargs):
    tasks = _read_json(ti.xcom_pull(key="tasks_path", task_ids="extract"))
    materials = _read_json(ti.xcom_pull(key="materials_path", task_ids="extract"))

    valid_task_ids = {t["task_id"] for t in tasks}
    errors = validate_tasks(tasks) + validate_materials(materials, valid_task_ids)

    if errors:
        print(f"Found {len(errors)} validation issues, e.g.: {errors[:3]}")
    else:
        print("No validation issues found.")


def transform_task(ti, **kwargs):
    tasks = _read_json(ti.xcom_pull(key="tasks_path", task_ids="extract"))
    materials = _read_json(ti.xcom_pull(key="materials_path", task_ids="extract"))
    tech_logs = _read_json(ti.xcom_pull(key="tech_logs_path", task_ids="extract"))

    staging_dir = _staging_dir(ti.run_id)

    ti.xcom_push(
        key="dim_technician_path",
        value=_write_json(staging_dir / "dim_technician.json", build_dim_technician(tech_logs)),
    )
    ti.xcom_push(
        key="dim_material_path",
        value=_write_json(staging_dir / "dim_material.json", build_dim_material(materials)),
    )
    ti.xcom_push(
        key="dim_date_path",
        value=_write_json(staging_dir / "dim_date.json", build_dim_date(tasks)),
    )
    ti.xcom_push(
        key="fact_rows_path",
        value=_write_json(staging_dir / "fact_rows.json", build_fact_rows(tasks, materials)),
    )


def load_task(ti, **kwargs):
    dim_technician_rows = _read_json(ti.xcom_pull(key="dim_technician_path", task_ids="transform"))
    dim_material_rows = _read_json(ti.xcom_pull(key="dim_material_path", task_ids="transform"))
    dim_date_rows = _read_json(ti.xcom_pull(key="dim_date_path", task_ids="transform"))
    fact_rows = _read_json(ti.xcom_pull(key="fact_rows_path", task_ids="transform"))

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            load_dim_technician(cur, dim_technician_rows)
            load_dim_material(cur, dim_material_rows)
            load_dim_date(cur, dim_date_rows)
            conn.commit()

            tech_map, material_map, date_map = get_id_maps(cur)
            load_facts(cur, fact_rows, tech_map, material_map, date_map)
            conn.commit()
        print(f"Loaded {len(fact_rows)} fact rows.")
    finally:
        conn.close()


def cleanup_task(ti, **kwargs):
    """Remove the staging folder after a successful run. In production, files are
    often kept for a short retention window (e.g. 7 days) to help with debugging."""
    staging_dir = STAGING_ROOT / ti.run_id
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
        print(f"Removed staging dir: {staging_dir}")


with DAG(
    dag_id="telecom_ops_etl",
    description="Extract-validate-transform-load pipeline for telecom ops data",
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["etl", "telecom"],
) as dag:

    extract = PythonOperator(task_id="extract", python_callable=extract_task)
    validate = PythonOperator(task_id="validate", python_callable=validate_task)
    transform = PythonOperator(task_id="transform", python_callable=transform_task)
    load = PythonOperator(task_id="load", python_callable=load_task)
    cleanup = PythonOperator(task_id="cleanup", python_callable=cleanup_task)

    extract >> validate >> transform >> load >> cleanup