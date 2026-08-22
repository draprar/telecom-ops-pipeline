from transform import (
    build_dim_technician,
    build_dim_material,
    build_dim_date,
    build_fact_rows,
)


def test_build_dim_technician_maps_fields():
    tech_logs = [{"technician_name": "Jan Kowalski", "region": "Gdansk", "hire_date": "2020-01-01"}]
    result = build_dim_technician(tech_logs)
    assert result == [{"full_name": "Jan Kowalski", "region": "Gdansk", "hire_date": "2020-01-01"}]


def test_build_dim_material_deduplicates():
    materials = [
        {"task_id": 1, "material_name": "cable", "quantity": 2, "unit_cost": 10},
        {"task_id": 2, "material_name": "cable", "quantity": 5, "unit_cost": 10},
    ]
    result = build_dim_material(materials)
    assert len(result) == 1
    assert result[0]["material_name"] == "cable"


def test_build_dim_date_parses_weekday():
    tasks = [{"task_date": "2026-08-17"}]  # Monday
    result = build_dim_date(tasks)
    assert result[0]["year"] == 2026
    assert result[0]["month"] == 8
    assert result[0]["weekday"] == "Monday"


def test_build_fact_rows_sums_material_cost():
    tasks = [
        {
            "task_id": "1",
            "technician_name": "Jan Kowalski",
            "task_type": "repair",
            "task_date": "2026-08-17",
            "duration_minutes": "60",
            "status": "completed",
        }
    ]
    materials = [
        {"task_id": "1", "material_name": "cable", "quantity": 2, "unit_cost": 10},
        {"task_id": "1", "material_name": "connector", "quantity": 1, "unit_cost": 5},
    ]
    result = build_fact_rows(tasks, materials)
    assert len(result) == 1
    assert result[0]["total_cost"] == 25.0
    assert result[0]["material_quantity"] == 3.0


def test_build_fact_rows_handles_task_without_material():
    tasks = [
        {
            "task_id": "2",
            "technician_name": "Anna Nowak",
            "task_type": "inspection",
            "task_date": "2026-08-18",
            "duration_minutes": "30",
            "status": "completed",
        }
    ]
    result = build_fact_rows(tasks, materials=[])
    assert result[0]["material_name"] is None
    assert result[0]["total_cost"] == 0