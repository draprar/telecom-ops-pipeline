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
TASK_COUNT = 1000

technicians = [fake.name() for _ in range(15)]
material_unit_cost = {name: round(random.uniform(5, 150), 2) for name in MATERIALS}

tasks = []
for i in range(1, TASK_COUNT + 1):
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

materials_usage = []
for task in tasks:
    if random.random() < 0.1:
        continue
    for material_name in random.sample(MATERIALS, k=random.randint(1, 3)):
        materials_usage.append({
            "task_id": task["task_id"],
            "material_name": material_name,
            "quantity": round(random.uniform(1, 10), 1),
            "unit_cost": material_unit_cost[material_name],
        })

with open(OUT_DIR / "erp_materials.json", "w", encoding="utf-8") as f:
    json.dump(materials_usage, f, indent=2, ensure_ascii=False)

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

print(
    f"Generated {len(tasks)} tasks, {len(materials_usage)} material usage records, "
    f"{len(tech_logs)} technicians."
)
