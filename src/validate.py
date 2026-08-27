"""Data-quality validation for the ETL pipeline.

Each ``validate_*`` function splits its input into:
  - ``valid``    rows that passed every check and are safe to load
  - ``rejected`` rows that failed at least one check, each paired with the
                 reason(s) it failed, so the caller can quarantine them
                 (log + persist) instead of silently loading bad data or
                 silently dropping it.

This is a deliberate design choice: validation errors are *data*, not just
log lines. The caller decides what to do with ``rejected`` (see
scripts/run_pipeline.py and dags/etl_pipeline_dag.py), including aborting
the whole run if too large a share of records fail.
"""


def validate_tasks(tasks):
    """Validate CRM tasks.

    Returns:
        (valid_tasks, rejected) where rejected is a list of
        {"row": <original row>, "reasons": [str, ...]}.
    """
    valid = []
    rejected = []
    seen_ids = set()

    for row in tasks:
        reasons = []

        if not row["technician_name"]:
            reasons.append(f"Technician name is missing for task {row['task_id']}")

        if row["task_id"] in seen_ids:
            reasons.append(f"Duplicate task ID found: {row['task_id']}")
        seen_ids.add(row["task_id"])

        try:
            if int(row["duration_minutes"]) <= 0:
                reasons.append(
                    f"Invalid duration for task {row['task_id']}: {row['duration_minutes']}"
                )
        except (ValueError, TypeError):
            reasons.append(
                f"Invalid duration format for task {row['task_id']}: {row['duration_minutes']}"
            )

        if reasons:
            rejected.append({"row": row, "reasons": reasons})
        else:
            valid.append(row)

    return valid, rejected


def validate_materials(materials, valid_task_ids):
    """Validate ERP materials against the set of *validated* CRM task ids.

    Note: ``valid_task_ids`` should come from ``validate_tasks``' output, not
    the raw extract, so a material row referencing a task that itself failed
    validation is also rejected rather than loaded against a phantom task.
    """
    valid = []
    rejected = []

    for row in materials:
        if str(row["task_id"]).strip() not in valid_task_ids:
            rejected.append(
                {
                    "row": row,
                    "reasons": [f"Task ID {row['task_id']} not found in valid CRM tasks"],
                }
            )
        else:
            valid.append(row)

    return valid, rejected
