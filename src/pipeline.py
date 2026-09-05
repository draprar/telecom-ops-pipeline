"""Shared in-memory steps used by the DAG and the standalone runner.

DAG tasks still own staging files and Airflow connections; this module
owns validate → split → transform so those rules cannot drift.
"""

import logging
import re

from quarantine import split_materials, split_tasks
from transform import (
    build_dim_date,
    build_dim_material,
    build_dim_technician,
    build_fact_rows,
    build_material_lines,
)
from validate import validate_materials, validate_tasks

logger = logging.getLogger(__name__)

# NTFS rejects : * ? " < > | and Airflow run_ids contain : and +.
_UNSAFE_FS_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_run_id(run_id: str) -> str:
    """Turn an Airflow run_id into a single path component safe on NTFS."""
    slug = _UNSAFE_FS_CHARS.sub("_", run_id).strip("._")
    return slug or "run"


def split_extracted(tasks, materials, tech_logs):
    """Validate sources and split them into clean vs quarantined rows."""
    known_technicians = {row["technician_name"] for row in tech_logs}
    valid_task_ids = {str(t["task_id"]).strip() for t in tasks if "task_id" in t}
    task_errors = validate_tasks(tasks, known_technicians)
    material_errors = validate_materials(materials, valid_task_ids)

    clean_tasks, quarantined_tasks = split_tasks(tasks, task_errors)
    clean_task_ids = {str(t["task_id"]).strip() for t in clean_tasks}
    clean_materials, quarantined_materials = split_materials(
        materials, material_errors, clean_task_ids
    )
    return clean_tasks, clean_materials, quarantined_tasks, quarantined_materials


def log_quarantine_summary(quarantined_tasks, quarantined_materials):
    """Log how many rows were set aside. Persistence is Postgres, at load time."""
    if not quarantined_tasks and not quarantined_materials:
        logger.info("No validation issues found.")
        return

    logger.warning(
        "Quarantined %d task(s) and %d material row(s); committing to Postgres before star load",
        len(quarantined_tasks),
        len(quarantined_materials),
    )


def build_warehouse_rows(clean_tasks, clean_materials, tech_logs):
    """Build dimension, fact, and material-line payloads from the clean subset."""
    return (
        build_dim_technician(tech_logs),
        build_dim_material(clean_materials),
        build_dim_date(clean_tasks),
        build_fact_rows(clean_tasks),
        build_material_lines(clean_materials),
    )
