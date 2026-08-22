import csv
import json
import random
from pathlib import Path
from faker import Faker

fake = Faker("pl_PL")
random.seed(42)

OUT_DIR = Path("data/raw")
OUT_DIR.mkdir(parents=True, exist_ok=True)

TASK_TYPES = ["fiber_splice", "installation", "inspection", "repair", "upgrade"]
MATERIALS = ["fiber_cable_50m", "connector_sc", "splice_closure", "patch_panel", "media_converter"]
STATUSES = ["completed", "in_progress", "cancelled"]
REGIONS = ["Gdansk", "Gdynia", "Sopot", "Tczew", "Wejherowo"]

technicians = [fake.name() for _ in range(15)]

# CRM tickets
tasks = []
for i in range(1, 301):
    tasks.append({
        "task_id": i,
        "technician_name": random.choice(technicians),
        "task_type": random.choice(TASK_TYPES),
        "task_date": fake.date_between(start_date="-90d", end_date="today").isoformat(),
        "duration_minutes": random.randint(30, 240),
        "status": random.choices(STATUSES, weights=[0.8, 0.15, 0.05])[0],
    })

with open(OUT_DIR / "crm_tasks.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=tasks[0].keys())
    writer.writeheader()
    writer.writerows(tasks)

# Material usage from ERP (JSON, per ticket)
materials_usage = []
for task in tasks:
    if random.random() < 0.9:
        materials_usage.append({
            "task_id": task["task_id"],
            "material_name": random.choice(MATERIALS),
            "quantity": round(random.uniform(1, 10), 1),
            "unit_cost": round(random.uniform(5, 150), 2),
        })

with open(OUT_DIR / "erp_materials.json", "w", encoding="utf-8") as f:
    json.dump(materials_usage, f, indent=2, ensure_ascii=False)

# Technician logs
tech_logs = [
    {
        "technician_name": name,
        "region": random.choice(REGIONS),
        "hire_date": fake.date_between(start_date="-8y", end_date="-30d").isoformat(),
    }
    for name in technicians
]

with open(OUT_DIR / "technician_logs.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=tech_logs[0].keys())
    writer.writeheader()
    writer.writerows(tech_logs)

print(f"Generated {len(tasks)} tasks, {len(materials_usage)} material usage records, {len(tech_logs)} technicians.")