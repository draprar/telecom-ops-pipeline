import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from extract import load_crm_tasks, load_erp_materials, load_technician_logs
from load import get_connection, load_pipeline
from logging_config import setup_logging
from pipeline import build_warehouse_rows, log_quarantine_summary, split_extracted

logger = logging.getLogger(__name__)


def run():
    logger.info("Running pipeline...")

    logger.info("Loading CRM tasks...")
    tasks = load_crm_tasks()
    logger.info("Loading ERP materials...")
    materials = load_erp_materials()
    logger.info("Loading technician logs...")
    tech_logs = load_technician_logs()

    logger.info("Validating tasks...")
    clean_tasks, clean_materials, quarantined_tasks, quarantined_materials = split_extracted(
        tasks, materials, tech_logs
    )
    log_quarantine_summary(quarantined_tasks, quarantined_materials)
    pipeline_run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    logger.info("Transforming data...")
    dim_technician_rows, dim_material_rows, dim_date_rows, fact_rows, material_lines = (
        build_warehouse_rows(clean_tasks, clean_materials, tech_logs)
    )

    logger.info("Loading data into database...")
    conn = get_connection()
    try:
        load_pipeline(
            conn,
            pipeline_run_id,
            quarantined_tasks,
            quarantined_materials,
            dim_technician_rows,
            dim_material_rows,
            dim_date_rows,
            fact_rows,
            material_lines,
        )
        logger.info(
            "Data loaded successfully, %d fact rows and %d material lines inserted",
            len(fact_rows),
            len(material_lines),
        )
    except Exception:
        logger.exception("Pipeline run failed")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    setup_logging()
    run()
