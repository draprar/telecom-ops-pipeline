import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from extract import load_crm_tasks, load_erp_materials, load_technician_logs
from load import (
    get_connection,
    get_id_maps,
    load_dim_date,
    load_dim_material,
    load_dim_technician,
    load_facts,
)
from transform import (
    build_dim_date,
    build_dim_material,
    build_dim_technician,
    build_fact_rows,
)
from validate import validate_materials, validate_tasks


def run():
    print("Running pipeline...")
    print("Loading CRM tasks...")
    tasks = load_crm_tasks()
    print("Loading ERP materials...")
    materials = load_erp_materials()
    print("Loading technician logs...")
    tech_logs = load_technician_logs()
    print("Validating tasks...")
    valid_task_ids = {t["task_id"] for t in tasks}
    errors = validate_tasks(tasks) + validate_materials(materials, valid_task_ids)
    if errors:  
        print("Errors found, e.g.: {errors[:3]}")
    else:
        print("No errors found")

    print("Transforming data...")
    dim_technician_rows = build_dim_technician(tech_logs)
    dim_material_rows = build_dim_material(materials)
    dim_date_rows = build_dim_date(tasks)
    fact_rows = build_fact_rows(tasks, materials)
    print("Loading data into database...")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            print("Loading technicians...")
            load_dim_technician(cur, dim_technician_rows)
            print("Loading materials...")
            load_dim_material(cur, dim_material_rows)
            print("Loading dates...")
            load_dim_date(cur, dim_date_rows)
            tech_map, material_map, date_map = get_id_maps(cur)
            print("Loading facts...")
            load_facts(cur, fact_rows, tech_map, material_map, date_map)
            conn.commit()
            print(f"Data loaded successfully, {len(fact_rows)} fact rows inserted")
    except Exception as e: # noqa: BLE001 - guard at the highest level of the script, intentionally wide
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    run()