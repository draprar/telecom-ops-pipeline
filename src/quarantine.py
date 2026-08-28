"""Splits extracted records into records that are safe to load and records
that get set aside for manual follow-up ("quarantined"), based on the
(task_id, message) error lists produced by validate.py.

Design decision: quarantine, not fail-fast. A bad row (e.g. one task with a
zero duration) should not block loading the rest of a day's work orders -
so validation failures here only remove the offending rows from the load,
they never raise. This is documented in README under "Design decisions &
known simplifications".
"""

import json
from pathlib import Path


def split_tasks(tasks, task_errors):
    """Split CRM tasks into (clean_tasks, quarantined_tasks).

    `quarantined_tasks` is a list of {"record": ..., "errors": [...]}
    dicts - one entry per distinct bad task_id, even if that task_id
    triggered several different validation errors.
    """
    errors_by_task = {}
    for task_id, message in task_errors:
        errors_by_task.setdefault(task_id, []).append(message)

    clean, quarantined = [], []
    already_quarantined = set()
    for row in tasks:
        task_id = row["task_id"]
        if task_id in errors_by_task:
            if task_id not in already_quarantined:
                quarantined.append({"record": row, "errors": errors_by_task[task_id]})
                already_quarantined.add(task_id)
        else:
            clean.append(row)
    return clean, quarantined


def split_materials(materials, material_errors, clean_task_ids):
    """Split ERP materials into (clean_materials, quarantined_materials).

    A material row is quarantined if validate_materials() flagged it
    directly (unknown task_id), OR if its task_id isn't in
    `clean_task_ids` - which also cascades the quarantine: a material
    for a task that existed but was itself quarantined gets quarantined
    too, since it has nothing valid left to attach to.
    """
    errors_by_task = {}
    for task_id, message in material_errors:
        errors_by_task.setdefault(task_id, []).append(message)

    clean, quarantined = [], []
    for row in materials:
        task_id = str(row["task_id"]).strip()
        reasons = list(errors_by_task.get(task_id, []))
        if task_id not in clean_task_ids and not reasons:
            reasons.append(f"Task ID {row['task_id']} was quarantined, so its materials are too")
        if reasons:
            quarantined.append({"record": row, "errors": reasons})
        else:
            clean.append(row)
    return clean, quarantined


def write_quarantine_file(path: Path, quarantined_tasks, quarantined_materials) -> None:
    """Persist quarantined records to disk for manual review.

    Callers are expected to write this OUTSIDE the per-run staging
    directory (which gets deleted after a successful run) so quarantine
    records actually survive to be looked at.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "quarantined_tasks": quarantined_tasks,
                "quarantined_materials": quarantined_materials,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )