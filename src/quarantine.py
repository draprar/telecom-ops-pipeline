"""Splits extracted records into records that are safe to load and records
that get set aside for manual follow-up ("quarantined"), based on the
(task_id, message) error lists produced by validate.py.

Design decision: quarantine, not fail-fast. A bad row (e.g. one task with a
zero duration) should not block loading the rest of a day's work orders -
so validation failures here only remove the offending rows from the load,
they never raise. This is documented in README under "Design decisions &
known simplifications".
"""

SOURCE_CRM_TASKS = "crm_tasks"
SOURCE_ERP_MATERIALS = "erp_materials"


def split_tasks(tasks, task_errors):
    """Split CRM tasks into (clean_tasks, quarantined_tasks).

    `quarantined_tasks` is a list of {"record": ..., "errors": [...]}
    dicts — one entry per flagged source row, including every duplicate
    `task_id`, so the review table matches what was excluded from load.
    """
    errors_by_task = {}
    for task_id, message in task_errors:
        errors_by_task.setdefault(task_id, []).append(message)

    clean, quarantined = [], []
    for row in tasks:
        task_id = row["task_id"]
        if task_id in errors_by_task:
            quarantined.append({"record": row, "errors": errors_by_task[task_id]})
        else:
            clean.append(row)
    return clean, quarantined


def split_materials(materials, material_errors, clean_task_ids):
    """Split ERP materials into (clean_materials, quarantined_materials).

    A material row is quarantined if validate_materials() flagged that
    row (by index), OR if its task_id isn't in `clean_task_ids` — which
    also cascades the quarantine: a material for a task that existed but
    was itself quarantined gets quarantined too, since it has nothing
    valid left to attach to.
    """
    errors_by_index = {}
    for index, message in material_errors:
        errors_by_index.setdefault(index, []).append(message)

    clean, quarantined = [], []
    for index, row in enumerate(materials):
        task_id = str(row.get("task_id", "")).strip()
        reasons = list(errors_by_index.get(index, []))
        if task_id not in clean_task_ids and not reasons:
            reasons.append(
                f"Task ID {row.get('task_id')} was quarantined, so its materials are too"
            )
        if reasons:
            quarantined.append({"record": row, "errors": reasons})
        else:
            clean.append(row)
    return clean, quarantined
