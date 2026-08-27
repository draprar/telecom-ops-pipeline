import logging
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

# If more than this share of CRM tasks fail validation, treat it as a
# data-quality incident and abort the run instead of silently loading a
# partial (and possibly misleading) dataset. Tune per your tolerance.
MAX_REJECTED_TASK_RATIO = 0.2


def run(run_id="standalone"):
    logger.info("Running pipeline (run_id=%s)...", run_id)

    logger.info("Extracting source data...")
    tasks = load_crm_tasks()
    materials = load_erp_materials()
    tech_logs = load_technician_logs()

    logger.info("Validating source data...")
    valid_tasks, rejected_tasks = validate_tasks(tasks)
    valid_task_ids = {t["task_id"] for t in valid_tasks}
    valid_materials, rejected_materials = validate_materials(materials, valid_task_ids)

    if rejected_tasks or rejected_materials:
        logger.warning(
            "%d/%d task(s) and %d/%d material record(s) failed validation and will be quarantined.",
            len(rejected_tasks), len(tasks), len(rejected_materials), len(materials),
        )

    if tasks and len(rejected_tasks) / len(tasks) > MAX_REJECTED_TASK_RATIO:
        raise RuntimeError(
            f"{len(rejected_tasks)}/{len(tasks)} CRM tasks failed validation "
            f"(> {MAX_REJECTED_TASK_RATIO:.0%} threshold) - aborting run rather than "
            "loading a partial dataset. Inspect pipeline_quarantine after a run "
            "with a lower rejection rate, or fix the source data."
        )

    logger.info("Transforming data...")
    dim_technician_rows = build_dim_technician(tech_logs)
    dim_material_rows = build_dim_material(valid_materials)
    dim_date_rows = build_dim_date(valid_tasks)
    fact_rows = build_fact_rows(valid_tasks, valid_materials)

    logger.info("Loading data into database...")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            write_quarantine_batch(cur, run_id, "crm_task", rejected_tasks)
            write_quarantine_batch(cur, run_id, "erp_material", rejected_materials)

            load_dim_technician(cur, dim_technician_rows)
            load_dim_material(cur, dim_material_rows)
            load_dim_date(cur, dim_date_rows)
            tech_map, material_map, date_map = get_id_maps(cur)
            load_facts(cur, fact_rows, tech_map, material_map, date_map)
            conn.commit()
            logger.info(
                "Pipeline run complete: %d fact row(s) loaded, %d row(s) quarantined.",
                len(fact_rows), len(rejected_tasks) + len(rejected_materials),
            )
    except Exception:
        # Log the full traceback and roll back, then re-raise: a run that
        # fails must exit non-zero (so `docker wait` / CI / Airflow actually
        # notice), not print an error and exit cleanly.
        logger.exception("Pipeline run failed, rolling back.")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    run()
