def validate_tasks(tasks):
    """Validate CRM tasks"""
    errors = []
    seen_ids = set()

    for row in tasks:
        if not row['technician_name']:
            errors.append(f"Technician name is missing for task {row['task_id']}")
        if row['task_id'] in seen_ids:
            errors.append(f"Duplicate task ID found: {row['task_id']}")
        seen_ids.add(row['task_id'])

        try:
            if int(row["duration_minutes"]) <= 0:
                errors.append(f"Invalid duration for task {row['task_id']}: {row['duration_minutes']}")
        except ValueError:
            errors.append(f"Invalid duration format for task {row['task_id']}: {row['duration_minutes']}")
    
    return errors

def validate_materials(materials, valid_task_ids):
    """Validate ERP materials"""
    errors = []
    for row in materials:
        if str(row["task_id"]).strip() not in valid_task_ids:
            errors.append(f"Task ID {row['task_id']} not found in CRM tasks")
    return errors