import logging

from pipeline import (
    build_warehouse_rows,
    persist_quarantine,
    sanitize_run_id,
    split_extracted,
)


def test_sanitize_run_id_replaces_characters_illegal_on_ntfs():
    assert (
        sanitize_run_id("manual__2026-09-05T12:00:00+00:00")
        == "manual__2026-09-05T12_00_00_00_00"
    )


def test_sanitize_run_id_falls_back_when_empty():
    assert sanitize_run_id(":::") == "run"


def test_split_extracted_keeps_valid_rows(monkeypatch):
    tasks = [
        {
            "task_id": "1",
            "technician_name": "Jan Kowalski",
            "duration_minutes": "60",
            "task_date": "2026-08-17",
            "task_type": "repair",
            "status": "completed",
        }
    ]
    materials = [
        {"task_id": "1", "material_name": "cable", "quantity": 2, "unit_cost": 10}
    ]
    tech_logs = [
        {"technician_name": "Jan Kowalski", "region": "Gdansk", "hire_date": "2020-01-01"}
    ]

    clean_tasks, clean_materials, q_tasks, q_materials = split_extracted(
        tasks, materials, tech_logs
    )

    assert clean_tasks == tasks
    assert clean_materials == materials
    assert q_tasks == []
    assert q_materials == []


def test_split_extracted_quarantines_unknown_technician():
    tasks = [
        {
            "task_id": "1",
            "technician_name": "Anna Nowak",
            "duration_minutes": "60",
            "task_date": "2026-08-17",
            "task_type": "repair",
            "status": "completed",
        }
    ]
    materials = [
        {"task_id": "1", "material_name": "cable", "quantity": 2, "unit_cost": 10}
    ]
    tech_logs = [
        {"technician_name": "Jan Kowalski", "region": "Gdansk", "hire_date": "2020-01-01"}
    ]

    clean_tasks, clean_materials, q_tasks, q_materials = split_extracted(
        tasks, materials, tech_logs
    )

    assert clean_tasks == []
    assert clean_materials == []
    assert len(q_tasks) == 1
    assert "not in technician logs" in q_tasks[0]["errors"][0]
    assert q_materials[0]["errors"]


def test_persist_quarantine_skips_file_when_empty(tmp_path, caplog):
    with caplog.at_level(logging.INFO, logger="pipeline"):
        path = persist_quarantine(tmp_path, "run1", [], [])
    assert path is None
    assert list(tmp_path.iterdir()) == []
    assert "No validation issues found" in caplog.text


def test_persist_quarantine_writes_json(tmp_path):
    path = persist_quarantine(
        tmp_path,
        "run1",
        [{"record": {"task_id": "1"}, "errors": ["bad"]}],
        [],
    )
    assert path == tmp_path / "run1.json"
    assert path.exists()


def test_build_warehouse_rows_delegates_to_transform():
    tasks = [
        {
            "task_id": "1",
            "technician_name": "Jan Kowalski",
            "duration_minutes": "60",
            "task_date": "2026-08-17",
            "task_type": "repair",
            "status": "completed",
        }
    ]
    materials = [
        {"task_id": "1", "material_name": "cable", "quantity": 2, "unit_cost": 10}
    ]
    tech_logs = [
        {"technician_name": "Jan Kowalski", "region": "Gdansk", "hire_date": "2020-01-01"}
    ]

    dim_tech, dim_mat, dim_date, facts = build_warehouse_rows(tasks, materials, tech_logs)

    assert dim_tech[0]["full_name"] == "Jan Kowalski"
    assert dim_mat[0]["material_name"] == "cable"
    assert dim_date[0]["full_date"] == "2026-08-17"
    assert facts[0]["task_id"] == 1
    assert facts[0]["total_cost"] == 20.0
