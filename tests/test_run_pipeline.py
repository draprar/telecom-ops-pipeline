import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import run_pipeline


def _connection_with_cursor():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    return conn, cur


def _stub_pipeline_inputs(monkeypatch, *, task_errors=None, material_errors=None):
    tasks = [{"task_id": "1", "technician_name": "Jan Kowalski"}]
    materials = [{"task_id": "1", "material_name": "cable"}]
    tech_logs = [{"technician_name": "Jan Kowalski", "region": "Gdansk", "hire_date": "2020-01-01"}]
    fact_rows = [{"task_id": "1"}]

    monkeypatch.setattr(run_pipeline, "load_crm_tasks", lambda: tasks)
    monkeypatch.setattr(run_pipeline, "load_erp_materials", lambda: materials)
    monkeypatch.setattr(run_pipeline, "load_technician_logs", lambda: tech_logs)
    monkeypatch.setattr(run_pipeline, "validate_tasks", lambda _tasks, _names: task_errors or [])
    monkeypatch.setattr(
        run_pipeline, "validate_materials", lambda _materials, _ids: material_errors or []
    )
    monkeypatch.setattr(run_pipeline, "build_dim_technician", lambda _logs: [{"full_name": "Jan Kowalski"}])
    monkeypatch.setattr(run_pipeline, "build_dim_material", lambda _materials: [{"material_name": "cable"}])
    monkeypatch.setattr(run_pipeline, "build_dim_date", lambda _tasks: [{"full_date": "2026-08-17"}])
    monkeypatch.setattr(run_pipeline, "build_fact_rows", lambda _tasks, _materials: fact_rows)
    return fact_rows


def _stub_db(monkeypatch):
    conn, cur = _connection_with_cursor()
    monkeypatch.setattr(run_pipeline, "get_connection", lambda: conn)
    load_star = MagicMock()
    monkeypatch.setattr(run_pipeline, "load_star_schema", load_star)
    return conn, cur, load_star


def test_run_pipeline_commits_on_success(monkeypatch, caplog, tmp_path):
    fact_rows = _stub_pipeline_inputs(monkeypatch)
    monkeypatch.setattr(run_pipeline, "QUARANTINE_ROOT", tmp_path)
    conn, _cur, load_star = _stub_db(monkeypatch)

    with caplog.at_level(logging.INFO, logger="run_pipeline"):
        run_pipeline.run()

    load_star.assert_called_once_with(
        conn,
        [{"full_name": "Jan Kowalski"}],
        [{"material_name": "cable"}],
        [{"full_date": "2026-08-17"}],
        fact_rows,
    )
    conn.close.assert_called_once()
    assert "No validation issues found" in caplog.text
    assert list(tmp_path.iterdir()) == []  # nothing quarantined -> no file written


def test_run_pipeline_quarantines_bad_task_and_still_loads_clean_rows(monkeypatch, caplog, tmp_path):
    # task "1" is bad; its one material row (which points at task "1")
    # cascades into quarantine too, since it has nothing valid to attach
    # to. build_fact_rows is stubbed so we can't see which rows actually
    # reached it from here, but we CAN assert the quarantine file was
    # written and the run still completes (commits) instead of aborting.
    _stub_pipeline_inputs(monkeypatch, task_errors=[("1", "Invalid duration for task 1: 0")])
    monkeypatch.setattr(run_pipeline, "QUARANTINE_ROOT", tmp_path)
    _conn, _cur, load_star = _stub_db(monkeypatch)

    with caplog.at_level(logging.INFO, logger="run_pipeline"):
        run_pipeline.run()

    load_star.assert_called_once()
    assert "Quarantined 1 task(s) and 1 material row(s)" in caplog.text
    written = list(tmp_path.iterdir())
    assert len(written) == 1
    assert written[0].suffix == ".json"


def test_run_pipeline_propagates_load_error(monkeypatch, caplog, tmp_path):
    _stub_pipeline_inputs(monkeypatch)
    monkeypatch.setattr(run_pipeline, "QUARANTINE_ROOT", tmp_path)
    conn, _cur, load_star = _stub_db(monkeypatch)
    load_star.side_effect = RuntimeError("db down")

    with caplog.at_level(logging.INFO, logger="run_pipeline"), pytest.raises(
        RuntimeError, match="db down"
    ):
        run_pipeline.run()

    conn.close.assert_called_once()
    assert "Pipeline run failed" in caplog.text