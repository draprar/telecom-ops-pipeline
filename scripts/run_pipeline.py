import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from extract import load_crm_tasks, load_erp_materials, load_technician_logs
from load import get_connection, load_star_schema
from logging_config import setup_logging
from quarantine import split_materials, split_tasks, write_quarantine_file
from transform import (
    build_dim_date,
    build_dim_material,
    build_dim_technician,
    build_fact_rows,
)
from validate import validate_materials, validate_tasks

logger = logging.getLogger(__name__)

QUARANTINE_ROOT = Path(__file__).resolve().parent.parent / "data" / "quarantine"


def run():
    logger.info("Running pipeline...")

    logger.info("Loading CRM tasks...")
    tasks = load_crm_tasks()
    logger.info("Loading ERP materials...")
    materials = load_erp_materials()
    logger.info("Loading technician logs...")
    tech_logs = load_technician_logs()

    logger.info("Validating tasks...")
    known_technicians = {row["technician_name"] for row in tech_logs}
    valid_task_ids = {str(t["task_id"]).strip() for t in tasks if "task_id" in t}
    task_errors = validate_tasks(tasks, known_technicians)
    material_errors = validate_materials(materials, valid_task_ids)

    clean_tasks, quarantined_tasks = split_tasks(tasks, task_errors)
    clean_task_ids = {str(t["task_id"]).strip() for t in clean_tasks}
    clean_materials, quarantined_materials = split_materials(
        materials, material_errors, clean_task_ids
    )

    if quarantined_tasks or quarantined_materials:
        run_timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        quarantine_path = QUARANTINE_ROOT / f"{run_timestamp}.json"
        write_quarantine_file(quarantine_path, quarantined_tasks, quarantined_materials)
        logger.warning(
            "Quarantined %d task(s) and %d material row(s); details written to %s",
            len(quarantined_tasks),
            len(quarantined_materials),
            quarantine_path,
        )
    else:
        logger.info("No validation issues found.")

    logger.info("Transforming data...")
    dim_technician_rows = build_dim_technician(tech_logs)
    dim_material_rows = build_dim_material(clean_materials)
    dim_date_rows = build_dim_date(clean_tasks)
    fact_rows = build_fact_rows(clean_tasks, clean_materials)

    logger.info("Loading data into database...")
    conn = get_connection()
    try:
        load_star_schema(
            conn,
            dim_technician_rows,
            dim_material_rows,
            dim_date_rows,
            fact_rows,
        )
        logger.info("Data loaded successfully, %d fact rows inserted", len(fact_rows))
    except Exception:
        logger.exception("Pipeline run failed, rolling back")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    setup_logging()
    run()