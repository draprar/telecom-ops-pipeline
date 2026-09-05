from datetime import date


def build_dim_technician(tech_logs):
    """Build dimension table for technicians"""
    return [{
        "full_name": row["technician_name"],
        "region": row["region"],
        "hire_date": row["hire_date"],
    }
    for row in tech_logs
    ]


def build_dim_material(materials):
    unique = {}
    for row in materials:
        unique.setdefault(
            row["material_name"],
            {"material_name": row["material_name"], "unit_cost": row["unit_cost"]}
        )
    return list(unique.values())


def build_dim_date(tasks):
    """Build dimension table for dates"""
    unique_dates = sorted({row["task_date"] for row in tasks})
    dims = []
    for d in unique_dates:
        dt = date.fromisoformat(d)
        dims.append({
            "full_date": d,
            "year": dt.year,
            "month": dt.month,
            "day": dt.day,
            "weekday": dt.strftime("%A"),
        })
    return dims


def build_fact_rows(tasks):
    """One fact row per work order — materials live on the bridge table."""
    return [
        {
            "task_id": int(task["task_id"]),
            "technician_name": task["technician_name"],
            "task_date": task["task_date"],
            "task_type": task["task_type"],
            "duration_minutes": int(task["duration_minutes"]),
            "status": task["status"],
        }
        for task in tasks
    ]


def build_material_lines(materials):
    """One row per (task, material), summing duplicate source lines."""
    aggregated = {}
    for row in materials:
        task_id = int(str(row["task_id"]).strip())
        key = (task_id, row["material_name"])
        quantity = float(row["quantity"])
        line_cost = quantity * float(row["unit_cost"])
        if key not in aggregated:
            aggregated[key] = {
                "task_id": task_id,
                "material_name": row["material_name"],
                "quantity": 0.0,
                "line_cost": 0.0,
            }
        aggregated[key]["quantity"] += quantity
        aggregated[key]["line_cost"] += line_cost

    lines = []
    for row in aggregated.values():
        lines.append(
            {
                "task_id": row["task_id"],
                "material_name": row["material_name"],
                "quantity": round(row["quantity"], 2),
                "line_cost": round(row["line_cost"], 2),
            }
        )
    return lines
