from datetime import datetime

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
        dt = datetime.strptime(d, "%Y-%m-%d")
        dims.append({
            "full_date": d,
            "year": dt.year,
            "month": dt.month,
            "day": dt.day,
            "weekday": dt.strftime("%A"),
        })
    return dims

def build_fact_rows(tasks, materials):
    """
    Build fact table for work orders
    """
    materials_by_task = {}
    for m in materials:
        materials_by_task.setdefault(str(m["task_id"]), []).append(m)
 
    rows = []
    for task in tasks:
        task_materials = materials_by_task.get(task["task_id"], [])
        total_cost = sum(float(m["quantity"]) * float(m["unit_cost"]) for m in task_materials)
        material_name = task_materials[0]["material_name"] if task_materials else None
        material_qty = sum(float(m["quantity"]) for m in task_materials)
 
        rows.append(
            {
                "technician_name": task["technician_name"],
                "material_name": material_name,
                "task_date": task["task_date"],
                "task_type": task["task_type"],
                "duration_minutes": int(task["duration_minutes"]),
                "material_quantity": material_qty,
                "total_cost": round(total_cost, 2),
                "status": task["status"],
            }
        )
    return rows