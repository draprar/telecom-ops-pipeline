from transform import (
    build_dim_date,
    build_dim_material,
    build_dim_technician,
    build_fact_rows,
    build_material_lines,
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


def test_build_fact_rows_does_not_embed_materials():
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
    result = build_fact_rows(tasks)
    assert result == [
        {
            "task_id": 1,
            "technician_name": "Jan Kowalski",
            "task_date": "2026-08-17",
            "task_type": "repair",
            "duration_minutes": 60,
            "status": "completed",
        }
    ]


def test_build_material_lines_keeps_one_row_per_material():
    materials = [
        {"task_id": "1", "material_name": "cable", "quantity": 2, "unit_cost": 10},
        {"task_id": "1", "material_name": "connector", "quantity": 1, "unit_cost": 5},
    ]
    result = build_material_lines(materials)
    by_name = {row["material_name"]: row for row in result}
    assert by_name["cable"] == {
        "task_id": 1,
        "material_name": "cable",
        "quantity": 2.0,
        "line_cost": 20.0,
    }
    assert by_name["connector"]["line_cost"] == 5.0


def test_build_material_lines_sums_duplicate_source_rows():
    materials = [
        {"task_id": "1", "material_name": "cable", "quantity": 2, "unit_cost": 10},
        {"task_id": "1", "material_name": "cable", "quantity": 3, "unit_cost": 10},
    ]
    result = build_material_lines(materials)
    assert result == [
        {"task_id": 1, "material_name": "cable", "quantity": 5.0, "line_cost": 50.0}
    ]


def test_build_material_lines_empty():
    assert build_material_lines([]) == []
