import json
import logging
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from airflow import DAG
from airflow.exceptions import AirflowFailException
from airflow.operators.python import PythonOperator
from alerts import notify_failure

from extract import load_crm_tasks, load_erp_materials, load_technician_logs
from load import (
    get_connection,
    get_id_maps,
    load_dim_date,
    load_dim_material,
    load_dim_technician,
    load_facts,
)
from quarantine import write_quarantine_batch
from transform import (
    build_dim_date,
    build_dim_material,
    build_dim_technician,
    build_fact_rows,
)
from validate import validate_materials, validate_tasks

logger = logging.getLogger(__name__)

STAGING_ROOT = Path(__file__).resolve().parent.parent / "data" / "staging"

# See scripts/run_pipeline.py for the rationale - kept identical between the
# standalone runner and the DAG so both paths apply the same quality bar.
MAX_REJECTED_TASK_RATIO = 0.2


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
    staging_dir = _staging_dir(ti.run_id)
    tasks = _read_json(ti.xcom_pull(key="tasks_path", task_ids="extract"))
    materials = _read_json(ti.xcom_pull(key="materials_path", task_ids="extract"))

    valid_tasks, rejected_tasks = validate_tasks(tasks)
    valid_task_ids = {t["task_id"] for t in valid_tasks}
    valid_materials, rejected_materials = validate_materials(materials, valid_task_ids)

    if rejected_tasks or rejected_materials:
        logger.warning(
            "%d/%d task(s) and %d/%d material record(s) failed validation and will be quarantined.",
            len(rejected_tasks), len(tasks), len(rejected_materials), len(materials),
        )
    else:
        logger.info("No validation issues found.")

    if tasks and len(rejected_tasks) / len(tasks) > MAX_REJECTED_TASK_RATIO:
        # AirflowFailException marks the task (and the run) failed immediately,
        # without burning through retries - this is a data-quality gate, not a
        # transient error, so retrying with the same input would just fail again.
        raise AirflowFailException(
            f"{len(rejected_tasks)}/{len(tasks)} CRM tasks failed validation "
            f"(> {MAX_REJECTED_TASK_RATIO:.0%} threshold) - aborting run."
        )

    ti.xcom_push(key="valid_tasks_path", value=_write_json(staging_dir / "valid_tasks.json", valid_tasks))
    ti.xcom_push(
        key="valid_materials_path",
        value=_write_json(staging_dir / "valid_materials.json", valid_materials),
    )
    ti.xcom_push(
        key="rejected_tasks_path",
        value=_write_json(staging_dir / "rejected_tasks.json", rejected_tasks),
    )
    ti.xcom_push(
        key="rejected_materials_path",
        value=_write_json(staging_dir / "rejected_materials.json", rejected_materials),
    )


def transform_task(ti, **kwargs):
    # Deliberately reads the *validated* tasks/materials from the validate
    # task, not the raw extract - rejected rows never reach the transform
    # step, and dims/facts are built only from data that passed the gate.
    tasks = _read_json(ti.xcom_pull(key="valid_tasks_path", task_ids="validate"))
    materials = _read_json(ti.xcom_pull(key="valid_materials_path", task_ids="validate"))
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
    rejected_tasks = _read_json(ti.xcom_pull(key="rejected_tasks_path", task_ids="validate"))
    rejected_materials = _read_json(ti.xcom_pull(key="rejected_materials_path", task_ids="validate"))

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            write_quarantine_batch(cur, ti.run_id, "crm_task", rejected_tasks)
            write_quarantine_batch(cur, ti.run_id, "erp_material", rejected_materials)

            load_dim_technician(cur, dim_technician_rows)
            load_dim_material(cur, dim_material_rows)
            load_dim_date(cur, dim_date_rows)
            conn.commit()

            tech_map, material_map, date_map = get_id_maps(cur)
            load_facts(cur, fact_rows, tech_map, material_map, date_map)
            conn.commit()
        logger.info(
            "Loaded %d fact row(s), quarantined %d row(s).",
            len(fact_rows), len(rejected_tasks) + len(rejected_materials),
        )
    except Exception:
        logger.exception("Load task failed, rolling back.")
        conn.rollback()
        raise
    finally:
        conn.close()


def cleanup_task(ti, **kwargs):
    """Remove the staging folder after a successful run. In production, files are
    often kept for a short retention window (e.g. 7 days) to help with debugging."""
    staging_dir = STAGING_ROOT / ti.run_id
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
        logger.info("Removed staging dir: %s", staging_dir)


default_args = {
    # Notified on any task failure in this DAG, including the validation
    # gate raising AirflowFailException - see dags/alerts.py.
    "on_failure_callback": notify_failure,
}

with DAG(
    dag_id="telecom_ops_etl",
    description="Extract-validate-transform-load pipeline for telecom ops data",
    default_args=default_args,
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
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
