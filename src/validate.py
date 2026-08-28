def validate_tasks(tasks):
    """Validate CRM tasks.

    Returns a list of (task_id, message) tuples rather than plain strings,
    so callers (see quarantine.py) can group every error by the task it
    belongs to and decide what to quarantine.
    """
    errors = []
    seen_ids = set()

    for row in tasks:
        task_id = row["task_id"]

        if not row["technician_name"]:
            errors.append((task_id, f"Technician name is missing for task {task_id}"))
        if task_id in seen_ids:
            errors.append((task_id, f"Duplicate task ID found: {task_id}"))
        seen_ids.add(task_id)

        try:
            if int(row["duration_minutes"]) <= 0:
                errors.append((task_id, f"Invalid duration for task {task_id}: {row['duration_minutes']}"))
        except ValueError:
            errors.append((task_id, f"Invalid duration format for task {task_id}: {row['duration_minutes']}"))

    return errors


def validate_materials(materials, valid_task_ids):
    """Validate ERP materials.

    Returns a list of (task_id, message) tuples. `task_id` here is the
    material row's own (stripped) task_id - that's exactly what's being
    checked against `valid_task_ids`.
    """
    errors = []
    for row in materials:
        task_id = str(row["task_id"]).strip()
        if task_id not in valid_task_ids:
            errors.append((task_id, f"Task ID {row['task_id']} not found in CRM tasks"))
    return errors