import json

from quarantine import split_materials, split_tasks, write_quarantine_file


def test_split_tasks_keeps_clean_rows():
    tasks = [{"task_id": "1"}, {"task_id": "2"}]
    clean, quarantined = split_tasks(tasks, task_errors=[])

    assert clean == tasks
    assert quarantined == []


def test_split_tasks_quarantines_flagged_rows():
    tasks = [{"task_id": "1"}, {"task_id": "2"}]
    task_errors = [("2", "Invalid duration for task 2: 0")]

    clean, quarantined = split_tasks(tasks, task_errors)

    assert clean == [{"task_id": "1"}]
    assert quarantined == [
        {"record": {"task_id": "2"}, "errors": ["Invalid duration for task 2: 0"]}
    ]


def test_split_tasks_groups_multiple_errors_for_same_task():
    tasks = [{"task_id": "1"}]
    task_errors = [
        ("1", "Technician name is missing for task 1"),
        ("1", "Duplicate task ID found: 1"),
    ]

    clean, quarantined = split_tasks(tasks, task_errors)

    assert clean == []
    assert len(quarantined) == 1
    assert quarantined[0]["errors"] == [
        "Technician name is missing for task 1",
        "Duplicate task ID found: 1",
    ]


def test_split_tasks_keeps_every_duplicate_source_row():
    tasks = [{"task_id": "1", "status": "open"}, {"task_id": "1", "status": "done"}]
    task_errors = [("1", "Duplicate task ID found: 1")]

    clean, quarantined = split_tasks(tasks, task_errors)

    assert clean == []
    assert [entry["record"] for entry in quarantined] == tasks
    assert all(entry["errors"] == ["Duplicate task ID found: 1"] for entry in quarantined)


def test_split_materials_keeps_clean_rows():
    materials = [{"task_id": "1", "material_name": "cable"}]
    clean, quarantined = split_materials(materials, material_errors=[], clean_task_ids={"1"})

    assert clean == materials
    assert quarantined == []


def test_split_materials_quarantines_flagged_rows():
    materials = [{"task_id": "99", "material_name": "cable"}]
    material_errors = [(0, "Task ID 99 not found in CRM tasks")]

    clean, quarantined = split_materials(materials, material_errors, clean_task_ids={"1"})

    assert clean == []
    assert quarantined[0]["record"] == materials[0]
    assert "not found" in quarantined[0]["errors"][0]


def test_split_materials_cascades_when_task_was_quarantined():
    # Task "2" existed in CRM (so validate_materials wouldn't flag it) but
    # was itself quarantined for an unrelated reason - its material should
    # be quarantined too, since it has no valid task left to attach to.
    materials = [{"task_id": "2", "material_name": "cable"}]

    clean, quarantined = split_materials(materials, material_errors=[], clean_task_ids={"1"})

    assert clean == []
    assert "quarantined" in quarantined[0]["errors"][0]


def test_split_materials_quarantines_only_the_flagged_row():
    materials = [
        {"task_id": "1", "material_name": "cable", "quantity": 2},
        {"task_id": "1", "material_name": "connector", "quantity": 0},
    ]

    clean, quarantined = split_materials(
        materials,
        material_errors=[(1, "Invalid quantity for material on task 1: 0")],
        clean_task_ids={"1"},
    )

    assert clean == [materials[0]]
    assert quarantined[0]["record"] == materials[1]


def test_write_quarantine_file_creates_parent_dir_and_valid_json(tmp_path):
    path = tmp_path / "nested" / "run123.json"
    quarantined_tasks = [{"record": {"task_id": "1"}, "errors": ["bad"]}]
    quarantined_materials = [{"record": {"task_id": "2"}, "errors": ["worse"]}]

    write_quarantine_file(path, quarantined_tasks, quarantined_materials)

    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["quarantined_tasks"] == quarantined_tasks
    assert data["quarantined_materials"] == quarantined_materials