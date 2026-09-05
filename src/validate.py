from datetime import date

TASK_REQUIRED_FIELDS = (
    "task_id",
    "technician_name",
    "duration_minutes",
    "task_date",
    "task_type",
    "status",
)
MATERIAL_REQUIRED_FIELDS = ("task_id", "material_name", "quantity", "unit_cost")


def task_id_label(row):
    """Stable key for grouping validation errors and quarantine splits."""
    if "task_id" not in row or row["task_id"] is None or str(row["task_id"]).strip() == "":
        return "<missing task_id>"
    return row["task_id"]


def _missing_fields(row, required):
    return [field for field in required if field not in row or row[field] is None]


def validate_tasks(tasks, known_technician_names):
    """Validate CRM tasks against known technicians from HR logs.

    Returns a list of (task_id, message) tuples rather than plain strings,
    so callers (see quarantine.py) can group every error by the task it
    belongs to and decide what to quarantine.
    """
    errors = []
    seen_ids = set()

    for row in tasks:
        task_id = task_id_label(row)
        missing = _missing_fields(row, TASK_REQUIRED_FIELDS)
        for field in missing:
            errors.append((task_id, f"Missing field {field} for task {task_id}"))

        if "task_id" not in missing:
            try:
                int(str(row["task_id"]).strip())
            except (TypeError, ValueError):
                errors.append(
                    (task_id, f"Invalid task_id format for task {task_id}: {row['task_id']}")
                )
            if row["task_id"] in seen_ids:
                errors.append((task_id, f"Duplicate task ID found: {task_id}"))
            seen_ids.add(row["task_id"])

        if "technician_name" not in missing:
            name = row["technician_name"]
            if not name:
                errors.append((task_id, f"Technician name is missing for task {task_id}"))
            elif name not in known_technician_names:
                errors.append(
                    (
                        task_id,
                        f"Technician {name} for task {task_id} is not in technician logs",
                    )
                )

        if "duration_minutes" not in missing:
            try:
                if int(row["duration_minutes"]) <= 0:
                    errors.append(
                        (
                            task_id,
                            f"Invalid duration for task {task_id}: {row['duration_minutes']}",
                        )
                    )
            except (TypeError, ValueError):
                errors.append(
                    (
                        task_id,
                        f"Invalid duration format for task {task_id}: {row['duration_minutes']}",
                    )
                )

        if "task_date" not in missing:
            raw_date = row["task_date"]
            try:
                date.fromisoformat(str(raw_date))
            except ValueError:
                errors.append(
                    (task_id, f"Invalid task_date for task {task_id}: {raw_date}")
                )

    return errors


def validate_materials(materials, valid_task_ids):
    """Validate ERP materials.

    Returns a list of (row_index, message) tuples so a bad quantity on one
    material row does not quarantine sibling materials for the same task.
    """
    errors = []
    for index, row in enumerate(materials):
        missing = _missing_fields(row, MATERIAL_REQUIRED_FIELDS)
        task_id = task_id_label(row)
        for field in missing:
            errors.append((index, f"Missing field {field} for material on task {task_id}"))

        if "task_id" not in missing:
            normalized_id = str(row["task_id"]).strip()
            if normalized_id not in valid_task_ids:
                errors.append(
                    (index, f"Task ID {row['task_id']} not found in CRM tasks")
                )

        if "quantity" not in missing:
            try:
                quantity = float(row["quantity"])
            except (TypeError, ValueError):
                errors.append(
                    (
                        index,
                        f"Invalid quantity for material on task {task_id}: {row['quantity']}",
                    )
                )
            else:
                if quantity <= 0:
                    errors.append(
                        (
                            index,
                            f"Invalid quantity for material on task {task_id}: {row['quantity']}",
                        )
                    )

        if "unit_cost" not in missing:
            try:
                unit_cost = float(row["unit_cost"])
            except (TypeError, ValueError):
                errors.append(
                    (
                        index,
                        f"Invalid unit_cost for material on task {task_id}: {row['unit_cost']}",
                    )
                )
            else:
                if unit_cost < 0:
                    errors.append(
                        (
                            index,
                            f"Invalid unit_cost for material on task {task_id}: {row['unit_cost']}",
                        )
                    )

    return errors
