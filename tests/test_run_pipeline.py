import sys
from pathlib import Path
from unittest.mock import MagicMock

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import run_pipeline  # noqa: E402


def _connection_with_cursor():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    return conn, cur


def _stub_pipeline_inputs(monkeypatch, *, validation_errors=None):
    tasks = [{"task_id": "1", "technician_name": "Jan Kowalski"}]
    materials = [{"task_id": "1", "material_name": "cable"}]
    tech_logs = [{"technician_name": "Jan Kowalski", "region": "Gdansk", "hire_date": "2020-01-01"}]
    fact_rows = [{"task_id": "1"}]

    monkeypatch.setattr(run_pipeline, "load_crm_tasks", lambda: tasks)
    monkeypatch.setattr(run_pipeline, "load_erp_materials", lambda: materials)
    monkeypatch.setattr(run_pipeline, "load_technician_logs", lambda: tech_logs)
    monkeypatch.setattr(
        run_pipeline,
        "validate_tasks",
        lambda _tasks: validation_errors or [],
    )
    monkeypatch.setattr(run_pipeline, "validate_materials", lambda _materials, _ids: [])
    monkeypatch.setattr(run_pipeline, "build_dim_technician", lambda _logs: [{"full_name": "Jan Kowalski"}])
    monkeypatch.setattr(run_pipeline, "build_dim_material", lambda _materials: [{"material_name": "cable"}])
    monkeypatch.setattr(run_pipeline, "build_dim_date", lambda _tasks: [{"full_date": "2026-08-17"}])
    monkeypatch.setattr(run_pipeline, "build_fact_rows", lambda _tasks, _materials: fact_rows)
    return fact_rows


def test_run_pipeline_commits_on_success(monkeypatch, capsys):
    fact_rows = _stub_pipeline_inputs(monkeypatch)
    conn, cur = _connection_with_cursor()
    maps = ({"Jan Kowalski": 1}, {"cable": 10}, {"2026-08-17": 100})

    monkeypatch.setattr(run_pipeline, "get_connection", lambda: conn)
    monkeypatch.setattr(run_pipeline, "get_id_maps", lambda _cur: maps)
    monkeypatch.setattr(run_pipeline, "load_dim_technician", MagicMock())
    monkeypatch.setattr(run_pipeline, "load_dim_material", MagicMock())
    monkeypatch.setattr(run_pipeline, "load_dim_date", MagicMock())
    load_facts = MagicMock()
    monkeypatch.setattr(run_pipeline, "load_facts", load_facts)

    run_pipeline.run()

    load_facts.assert_called_once_with(cur, fact_rows, *maps)
    conn.commit.assert_called_once()
    conn.rollback.assert_not_called()
    conn.close.assert_called_once()
    assert "No errors found" in capsys.readouterr().out


def test_run_pipeline_prints_validation_errors_and_still_loads(monkeypatch, capsys):
    _stub_pipeline_inputs(monkeypatch, validation_errors=["Duplicate task ID found: 1"])
    conn, _cur = _connection_with_cursor()

    monkeypatch.setattr(run_pipeline, "get_connection", lambda: conn)
    monkeypatch.setattr(run_pipeline, "get_id_maps", lambda _cur: ({}, {}, {}))
    monkeypatch.setattr(run_pipeline, "load_dim_technician", MagicMock())
    monkeypatch.setattr(run_pipeline, "load_dim_material", MagicMock())
    monkeypatch.setattr(run_pipeline, "load_dim_date", MagicMock())
    monkeypatch.setattr(run_pipeline, "load_facts", MagicMock())

    run_pipeline.run()

    conn.commit.assert_called_once()
    assert "Errors found" in capsys.readouterr().out


def test_run_pipeline_rolls_back_on_error(monkeypatch):
    _stub_pipeline_inputs(monkeypatch)
    conn, _cur = _connection_with_cursor()

    monkeypatch.setattr(run_pipeline, "get_connection", lambda: conn)
    monkeypatch.setattr(run_pipeline, "load_dim_technician", MagicMock())
    monkeypatch.setattr(run_pipeline, "load_dim_material", MagicMock())
    monkeypatch.setattr(run_pipeline, "load_dim_date", MagicMock())
    monkeypatch.setattr(
        run_pipeline,
        "get_id_maps",
        MagicMock(side_effect=RuntimeError("db down")),
    )

    run_pipeline.run()

    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()
    conn.close.assert_called_once()
