from validate import validate_materials, validate_tasks


def make_task(task_id="1", technician_name="Jan Kowalski", duration_minutes="60"):
    return {
        "task_id": task_id,
        "technician_name": technician_name,
        "duration_minutes": duration_minutes,
    }


def test_valid_tasks_have_no_errors():
    tasks = [make_task(task_id="1"), make_task(task_id="2")]
    assert validate_tasks(tasks) == []


def test_duplicate_task_id_is_detected():
    tasks = [make_task(task_id="1"), make_task(task_id="1")]
    errors = validate_tasks(tasks)
    assert any("Duplicate" in e for e in errors)


def test_missing_technician_is_detected():
    tasks = [make_task(technician_name="")]
    errors = validate_tasks(tasks)
    assert any("missing" in e for e in errors)


def test_invalid_duration_is_detected():
    tasks = [make_task(duration_minutes="0")]
    errors = validate_tasks(tasks)
    assert any("Invalid duration" in e for e in errors)


def test_non_numeric_duration_is_detected():
    tasks = [make_task(duration_minutes="abc")]
    errors = validate_tasks(tasks)
    assert any("Invalid duration format" in e for e in errors)


def test_material_referencing_unknown_task_is_detected():
    materials = [{"task_id": 99, "material_name": "cable"}]
    errors = validate_materials(materials, valid_task_ids={"1", "2"})
    assert len(errors) == 1


def test_valid_materials_have_no_errors():
    materials = [{"task_id": 1, "material_name": "cable"}]
    assert validate_materials(materials, valid_task_ids={"1"}) == []


def test_material_task_id_is_stripped():
    materials = [{"task_id": " 1 ", "material_name": "cable"}]
    assert validate_materials(materials, valid_task_ids={"1"}) == []