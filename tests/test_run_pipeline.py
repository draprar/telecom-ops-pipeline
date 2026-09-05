import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import run_pipeline


def _stub_pipeline_inputs(monkeypatch, *, task_errors=None):
    tasks = [{"task_id": "1", "technician_name": "Jan Kowalski"}]
    materials = [{"task_id": "1", "material_name": "cable"}]
    tech_logs = [{"technician_name": "Jan Kowalski", "region": "Gdansk", "hire_date": "2020-01-01"}]
    fact_rows = [{"task_id": "1"}]
    q_tasks = []
    q_materials = []

    monkeypatch.setattr(run_pipeline, "load_crm_tasks", lambda: tasks)
    monkeypatch.setattr(run_pipeline, "load_erp_materials", lambda: materials)
    monkeypatch.setattr(run_pipeline, "load_technician_logs", lambda: tech_logs)

    if task_errors:
        q_tasks = [{"record": {"task_id": "1"}, "errors": [task_errors[0][1]]}]
        q_materials = [{"record": {"task_id": "1"}, "errors": ["cascaded"]}]
        monkeypatch.setattr(
            run_pipeline,
            "split_extracted",
            lambda _tasks, _materials, _logs: ([], [], q_tasks, q_materials),
        )
    else:
        monkeypatch.setattr(
            run_pipeline,
            "split_extracted",
            lambda _tasks, _materials, _logs: (tasks, materials, [], []),
        )

    monkeypatch.setattr(
        run_pipeline,
        "build_warehouse_rows",
        lambda _tasks, _materials, _logs: (
            [{"full_name": "Jan Kowalski"}],
            [{"material_name": "cable"}],
            [{"full_date": "2026-08-17"}],
            fact_rows,
            [{"task_id": 1, "material_name": "cable", "quantity": 2.0, "line_cost": 20.0}],
        ),
    )
    return fact_rows, q_tasks, q_materials


def _stub_db(monkeypatch):
    conn = MagicMock()
    monkeypatch.setattr(run_pipeline, "get_connection", lambda: conn)
    load_pipe = MagicMock()
    monkeypatch.setattr(run_pipeline, "load_pipeline", load_pipe)
    return conn, load_pipe


def test_run_pipeline_commits_on_success(monkeypatch, caplog):
    fact_rows, q_tasks, q_materials = _stub_pipeline_inputs(monkeypatch)
    conn, load_pipe = _stub_db(monkeypatch)

    with caplog.at_level(logging.INFO, logger="pipeline"):
        run_pipeline.run()

    load_pipe.assert_called_once()
    args = load_pipe.call_args.args
    assert args[0] is conn
    assert isinstance(args[1], str)
    assert args[2] == q_tasks
    assert args[3] == q_materials
    assert args[4] == [{"full_name": "Jan Kowalski"}]
    assert args[7] == fact_rows
    conn.close.assert_called_once()
    assert "No validation issues found" in caplog.text


def test_run_pipeline_quarantines_bad_task_and_still_loads_clean_rows(monkeypatch, caplog):
    _fact_rows, q_tasks, q_materials = _stub_pipeline_inputs(
        monkeypatch, task_errors=[("1", "Invalid duration for task 1: 0")]
    )
    conn, load_pipe = _stub_db(monkeypatch)

    with caplog.at_level(logging.INFO, logger="pipeline"):
        run_pipeline.run()

    load_pipe.assert_called_once()
    args = load_pipe.call_args.args
    assert args[0] is conn
    assert args[2] == q_tasks
    assert args[3] == q_materials
    assert "Quarantined 1 task(s) and 1 material row(s)" in caplog.text


def test_run_pipeline_propagates_load_error(monkeypatch, caplog):
    _stub_pipeline_inputs(monkeypatch)
    conn, load_pipe = _stub_db(monkeypatch)
    load_pipe.side_effect = RuntimeError("db down")

    with caplog.at_level(logging.INFO, logger="run_pipeline"), pytest.raises(
        RuntimeError, match="db down"
    ):
        run_pipeline.run()

    conn.close.assert_called_once()
    assert "Pipeline run failed" in caplog.text
