import json
import logging
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook

from alerting import notify_on_failure
from extract import load_crm_tasks, load_erp_materials, load_technician_logs
from load import load_star_schema
from pipeline import (
    build_warehouse_rows,
    persist_quarantine,
    sanitize_run_id,
    split_extracted,
)

# Do NOT call setup_logging() here - Airflow configures root logging itself
# and captures per-task output into its own handlers/UI.
logger = logging.getLogger(__name__)

STAGING_ROOT = Path(__file__).resolve().parent.parent / "data" / "staging"
# Deliberately OUTSIDE the staging dir: cleanup_task deletes the staging dir
# after every run, but quarantine records need to survive for manual review.
QUARANTINE_ROOT = Path(__file__).resolve().parent.parent / "data" / "quarantine"

# The Connection with this ID is defined via the AIRFLOW_CONN_POSTGRES_DEFAULT
# env var in docker-compose.yml, not via os.getenv()/load.py like the
# standalone scripts/run_pipeline.py uses. See load_task() below and the
# README for why the DAG and the standalone script deliberately connect to
# Postgres two different ways.
POSTGRES_CONN_ID = "postgres_default"


def _run_slug(ti) -> str:
    return sanitize_run_id(ti.run_id)


def _staging_dir(run_id: str) -> Path:
    """Per-run staging folder so parallel DAG runs do not overwrite each other."""
    d = STAGING_ROOT / sanitize_run_id(run_id)
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
    """Validate extracted records and split them into clean vs quarantined.

    Only the clean subset is written back out for transform_task to
    consume - a bad row here no longer silently rides along to load_task.
    """
    tasks = _read_json(ti.xcom_pull(key="tasks_path", task_ids="extract"))
    materials = _read_json(ti.xcom_pull(key="materials_path", task_ids="extract"))
    tech_logs = _read_json(ti.xcom_pull(key="tech_logs_path", task_ids="extract"))

    clean_tasks, clean_materials, quarantined_tasks, quarantined_materials = split_extracted(
        tasks, materials, tech_logs
    )
    persist_quarantine(
        QUARANTINE_ROOT,
        _run_slug(ti),
        quarantined_tasks,
        quarantined_materials,
    )

    staging_dir = _staging_dir(ti.run_id)
    ti.xcom_push(
        key="clean_tasks_path",
        value=_write_json(staging_dir / "clean_tasks.json", clean_tasks),
    )
    ti.xcom_push(
        key="clean_materials_path",
        value=_write_json(staging_dir / "clean_materials.json", clean_materials),
    )


def transform_task(ti, **kwargs):
    clean_tasks = _read_json(ti.xcom_pull(key="clean_tasks_path", task_ids="validate"))
    clean_materials = _read_json(ti.xcom_pull(key="clean_materials_path", task_ids="validate"))
    tech_logs = _read_json(ti.xcom_pull(key="tech_logs_path", task_ids="extract"))

    staging_dir = _staging_dir(ti.run_id)
    dim_technician, dim_material, dim_date, fact_rows, material_lines = build_warehouse_rows(
        clean_tasks, clean_materials, tech_logs
    )

    ti.xcom_push(
        key="dim_technician_path",
        value=_write_json(staging_dir / "dim_technician.json", dim_technician),
    )
    ti.xcom_push(
        key="dim_material_path",
        value=_write_json(staging_dir / "dim_material.json", dim_material),
    )
    ti.xcom_push(
        key="dim_date_path",
        value=_write_json(staging_dir / "dim_date.json", dim_date),
    )
    ti.xcom_push(
        key="fact_rows_path",
        value=_write_json(staging_dir / "fact_rows.json", fact_rows),
    )
    ti.xcom_push(
        key="material_lines_path",
        value=_write_json(staging_dir / "material_lines.json", material_lines),
    )


def load_task(ti, **kwargs):
    dim_technician_rows = _read_json(ti.xcom_pull(key="dim_technician_path", task_ids="transform"))
    dim_material_rows = _read_json(ti.xcom_pull(key="dim_material_path", task_ids="transform"))
    dim_date_rows = _read_json(ti.xcom_pull(key="dim_date_path", task_ids="transform"))
    fact_rows = _read_json(ti.xcom_pull(key="fact_rows_path", task_ids="transform"))
    material_lines = _read_json(ti.xcom_pull(key="material_lines_path", task_ids="transform"))

    # Airflow-native connection lookup instead of os.getenv()/load_dotenv():
    # the credentials live in an Airflow Connection (here defined via the
    # AIRFLOW_CONN_POSTGRES_DEFAULT env var, see docker-compose.yml), which
    # is what Airflow itself considers the "correct" place for this instead
    # of an ad-hoc .env read inside task code.
    hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
    conn = hook.get_conn()
    try:
        load_star_schema(
            conn,
            dim_technician_rows,
            dim_material_rows,
            dim_date_rows,
            fact_rows,
            material_lines,
        )
        logger.info(
            "Loaded %d fact rows and %d material lines.",
            len(fact_rows),
            len(material_lines),
        )
    finally:
        conn.close()


def cleanup_task(ti, **kwargs):
    """Remove the staging folder after a successful run. Quarantine records
    live in QUARANTINE_ROOT, outside the staging dir, so they survive this."""
    staging_dir = STAGING_ROOT / _run_slug(ti)
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
        logger.info("Removed staging dir: %s", staging_dir)


with DAG(
    dag_id="telecom_ops_etl",
    description="Extract-validate-transform-load pipeline for telecom ops data",
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    schedule="@daily",
    catchup=False,
    tags=["etl", "telecom"],
    # Applies to every task below: if ANY of them fails (at 3am, unattended),
    # notify_on_failure() posts to the webhook configured via ALERT_WEBHOOK_URL
    # instead of the failure only being visible next time someone opens the UI.
    default_args={
        "on_failure_callback": notify_on_failure,
        "retries": 0,
        "retry_exponential_backoff": True,
    },
) as dag:

    extract = PythonOperator(
        task_id="extract",
        python_callable=extract_task,
        retries=2,
        retry_delay=timedelta(seconds=30),
    )
    validate = PythonOperator(task_id="validate", python_callable=validate_task)
    transform = PythonOperator(task_id="transform", python_callable=transform_task)
    load = PythonOperator(
        task_id="load",
        python_callable=load_task,
        retries=2,
        retry_delay=timedelta(seconds=30),
    )
    cleanup = PythonOperator(task_id="cleanup", python_callable=cleanup_task)

    extract >> validate >> transform >> load >> cleanup
