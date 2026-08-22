import json

from extract import load_crm_tasks, load_erp_materials, load_technician_logs


def test_load_crm_tasks_reads_csv(tmp_path, monkeypatch):
    (tmp_path / "crm_tasks.csv").write_text(
        "task_id,technician_name\n1,Jan Kowalski\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("extract.RAW_DIR", tmp_path)

    rows = load_crm_tasks()

    assert rows == [{"task_id": "1", "technician_name": "Jan Kowalski"}]


def test_load_erp_materials_reads_json(tmp_path, monkeypatch):
    (tmp_path / "erp_materials.json").write_text(
        json.dumps([{"task_id": 1, "material_name": "cable", "quantity": 2}]),
        encoding="utf-8",
    )
    monkeypatch.setattr("extract.RAW_DIR", tmp_path)

    rows = load_erp_materials()

    assert rows == [{"task_id": 1, "material_name": "cable", "quantity": 2}]


def test_load_technician_logs_reads_csv(tmp_path, monkeypatch):
    (tmp_path / "technician_logs.csv").write_text(
        "technician_name,region,hire_date\nJan Kowalski,Gdansk,2020-01-01\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("extract.RAW_DIR", tmp_path)

    rows = load_technician_logs()

    assert rows == [
        {"technician_name": "Jan Kowalski", "region": "Gdansk", "hire_date": "2020-01-01"}
    ]
