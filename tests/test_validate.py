from validate import validate_materials, validate_tasks

KNOWN_TECHNICIANS = {"Jan Kowalski"}


def make_task(
    task_id="1",
    technician_name="Jan Kowalski",
    duration_minutes="60",
    task_date="2026-08-17",
    task_type="repair",
    status="completed",
):
    return {
        "task_id": task_id,
        "technician_name": technician_name,
        "duration_minutes": duration_minutes,
        "task_date": task_date,
        "task_type": task_type,
        "status": status,
    }


def make_material(task_id=1, material_name="cable", quantity=2, unit_cost=10):
    return {
        "task_id": task_id,
        "material_name": material_name,
        "quantity": quantity,
        "unit_cost": unit_cost,
    }


def test_valid_tasks_have_no_errors():
    tasks = [make_task(task_id="1"), make_task(task_id="2")]
    assert validate_tasks(tasks, KNOWN_TECHNICIANS) == []


def test_duplicate_task_id_is_detected():
    tasks = [make_task(task_id="1"), make_task(task_id="1")]
    errors = validate_tasks(tasks, KNOWN_TECHNICIANS)
    assert any(task_id == "1" and "Duplicate" in message for task_id, message in errors)


def test_missing_technician_is_detected():
    tasks = [make_task(technician_name="")]
    errors = validate_tasks(tasks, KNOWN_TECHNICIANS)
    assert any("missing" in message for _task_id, message in errors)


def test_unknown_technician_is_detected():
    tasks = [make_task(technician_name="Anna Nowak")]
    errors = validate_tasks(tasks, KNOWN_TECHNICIANS)
    assert any("not in technician logs" in message for _task_id, message in errors)


def test_invalid_duration_is_detected():
    tasks = [make_task(duration_minutes="0")]
    errors = validate_tasks(tasks, KNOWN_TECHNICIANS)
    assert any("Invalid duration" in message for _task_id, message in errors)


def test_non_numeric_duration_is_detected():
    tasks = [make_task(duration_minutes="abc")]
    errors = validate_tasks(tasks, KNOWN_TECHNICIANS)
    assert any("Invalid duration format" in message for _task_id, message in errors)


def test_invalid_task_date_is_detected():
    tasks = [make_task(task_date="17/08/2026")]
    errors = validate_tasks(tasks, KNOWN_TECHNICIANS)
    assert any("Invalid task_date" in message for _task_id, message in errors)


def test_non_integer_task_id_is_detected():
    tasks = [make_task(task_id="WO-1")]
    errors = validate_tasks(tasks, KNOWN_TECHNICIANS)
    assert any("Invalid task_id format" in message for _task_id, message in errors)


def test_missing_task_column_is_detected():
    row = make_task()
    del row["task_date"]
    errors = validate_tasks([row], KNOWN_TECHNICIANS)
    assert any("Missing field task_date" in message for _task_id, message in errors)


def test_errors_are_tagged_with_their_task_id():
    tasks = [make_task(task_id="42", duration_minutes="0")]
    errors = validate_tasks(tasks, KNOWN_TECHNICIANS)
    assert errors == [("42", "Invalid duration for task 42: 0")]


def test_material_referencing_unknown_task_is_detected():
    materials = [make_material(task_id=99)]
    errors = validate_materials(materials, valid_task_ids={"1", "2"})
    assert len(errors) == 1
    index, message = errors[0]
    assert index == 0
    assert "not found" in message


def test_valid_materials_have_no_errors():
    materials = [make_material(task_id=1)]
    assert validate_materials(materials, valid_task_ids={"1"}) == []


def test_material_task_id_is_stripped():
    materials = [make_material(task_id=" 1 ")]
    assert validate_materials(materials, valid_task_ids={"1"}) == []


def test_invalid_material_quantity_is_detected():
    materials = [make_material(quantity=0)]
    errors = validate_materials(materials, valid_task_ids={"1"})
    assert any("Invalid quantity" in message for _index, message in errors)


def test_non_numeric_unit_cost_is_detected():
    materials = [make_material(unit_cost="free")]
    errors = validate_materials(materials, valid_task_ids={"1"})
    assert any("Invalid unit_cost" in message for _index, message in errors)


def test_negative_unit_cost_is_detected():
    materials = [make_material(unit_cost=-1)]
    errors = validate_materials(materials, valid_task_ids={"1"})
    assert any("Invalid unit_cost" in message for _index, message in errors)


def test_bad_quantity_is_tagged_with_row_index():
    materials = [make_material(quantity=2), make_material(quantity="x")]
    errors = validate_materials(materials, valid_task_ids={"1"})
    assert errors == [(1, "Invalid quantity for material on task 1: x")]
