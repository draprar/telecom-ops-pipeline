from datetime import date
from unittest.mock import MagicMock

import pytest
from psycopg2.extras import Json

from load import (
    commit_quarantine_records,
    get_connection,
    get_id_maps,
    load_dim_date,
    load_dim_material,
    load_dim_technician,
    load_facts,
    load_pipeline,
    load_quarantine_records,
    load_star_schema,
    replace_material_lines,
)


def test_get_connection_uses_env(monkeypatch):
    monkeypatch.setattr("load.os.getenv", lambda key: f"val-{key}")
    mock_connect = MagicMock()
    monkeypatch.setattr("load.psycopg2.connect", mock_connect)

    get_connection()

    mock_connect.assert_called_once_with(
        host="val-DB_HOST",
        port="val-DB_PORT",
        dbname="val-POSTGRES_DB",
        user="val-POSTGRES_USER",
        password="val-POSTGRES_PASSWORD",
    )


def test_load_dim_technician_inserts_rows():
    cur = MagicMock()
    load_dim_technician(
        cur,
        [{"full_name": "Jan Kowalski", "region": "Gdansk", "hire_date": "2020-01-01"}],
    )

    sql, params = cur.execute.call_args.args
    assert "INSERT INTO dim_technician" in sql
    assert "ON CONFLICT (full_name) DO UPDATE" in sql
    assert params == ("Jan Kowalski", "Gdansk", "2020-01-01")


def test_load_dim_material_inserts_rows():
    cur = MagicMock()
    load_dim_material(cur, [{"material_name": "cable", "unit_cost": 10}])

    sql, params = cur.execute.call_args.args
    assert "INSERT INTO dim_material" in sql
    assert "ON CONFLICT (material_name) DO UPDATE" in sql
    assert params == ("cable", 10)


def test_load_dim_date_inserts_rows():
    cur = MagicMock()
    load_dim_date(
        cur,
        [{"full_date": "2026-08-17", "year": 2026, "month": 8, "day": 17, "weekday": "Monday"}],
    )

    sql, params = cur.execute.call_args.args
    assert "INSERT INTO dim_date" in sql
    assert "ON CONFLICT (full_date) DO NOTHING" in sql
    assert params == ("2026-08-17", 2026, 8, 17, "Monday")


def test_get_id_maps_builds_lookup_dicts():
    cur = MagicMock()
    cur.fetchall.side_effect = [
        [(1, "Jan Kowalski")],
        [(10, "cable")],
        [(100, date(2026, 8, 17))],
    ]

    tech_map, material_map, date_map = get_id_maps(cur)

    assert tech_map == {"Jan Kowalski": 1}
    assert material_map == {"cable": 10}
    assert date_map == {"2026-08-17": 100}


def test_load_facts_maps_ids_and_upserts_without_material_columns():
    cur = MagicMock()
    load_facts(
        cur,
        [
            {
                "task_id": 1,
                "technician_name": "Jan Kowalski",
                "task_date": "2026-08-17",
                "task_type": "repair",
                "duration_minutes": 60,
                "status": "completed",
            }
        ],
        {"Jan Kowalski": 1},
        {"2026-08-17": 100},
    )

    sql, params = cur.execute.call_args.args
    assert "INSERT INTO fact_work_orders" in sql
    assert "ON CONFLICT (task_id) DO UPDATE" in sql
    assert "material_id" not in sql
    assert params == (1, 1, 100, "repair", 60, "completed")


def test_replace_material_lines_deletes_batch_then_inserts():
    cur = MagicMock()
    replace_material_lines(
        cur,
        [
            {
                "task_id": 1,
                "material_name": "cable",
                "quantity": 2.0,
                "line_cost": 20.0,
            }
        ],
        {"cable": 10},
        {1},
    )

    delete_sql, delete_params = cur.execute.call_args_list[0].args
    assert "DELETE FROM fact_work_order_materials" in delete_sql
    assert delete_params == ([1],)

    insert_sql, insert_params = cur.execute.call_args_list[1].args
    assert "INSERT INTO fact_work_order_materials" in insert_sql
    assert insert_params == (1, 10, 2.0, 20.0)


def test_load_star_schema_commits_once():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    cur.fetchall.side_effect = [
        [(1, "Jan Kowalski")],
        [(10, "cable")],
        [(100, date(2026, 8, 17))],
    ]

    load_star_schema(
        conn,
        [{"full_name": "Jan Kowalski", "region": "Gdansk", "hire_date": "2020-01-01"}],
        [{"material_name": "cable", "unit_cost": 10}],
        [{"full_date": "2026-08-17", "year": 2026, "month": 8, "day": 17, "weekday": "Monday"}],
        [
            {
                "task_id": 1,
                "technician_name": "Jan Kowalski",
                "task_date": "2026-08-17",
                "task_type": "repair",
                "duration_minutes": 60,
                "status": "completed",
            }
        ],
        [
            {
                "task_id": 1,
                "material_name": "cable",
                "quantity": 2.0,
                "line_cost": 20.0,
            }
        ],
    )

    conn.commit.assert_called_once()
    conn.rollback.assert_not_called()
    assert cur.execute.call_count == 9


def test_load_star_schema_rolls_back_on_error():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    cur.execute.side_effect = RuntimeError("db down")

    with pytest.raises(RuntimeError, match="db down"):
        load_star_schema(conn, [], [], [], [], [])

    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()


def test_load_quarantine_records_inserts_task_and_material_rows():
    cur = MagicMock()
    load_quarantine_records(
        cur,
        "run-1",
        [{"record": {"task_id": "9", "status": "open"}, "errors": ["bad duration"]}],
        [{"record": {"task_id": "9", "material_name": "cable"}, "errors": ["cascaded"]}],
    )

    assert cur.execute.call_count == 2
    first_sql, first_params = cur.execute.call_args_list[0].args
    assert "INSERT INTO quarantine_records" in first_sql
    assert first_params[0] == "run-1"
    assert first_params[1] == "crm_tasks"
    assert first_params[2] == "9"
    assert isinstance(first_params[3], Json)
    assert first_params[3].adapted == {"task_id": "9", "status": "open"}
    assert first_params[4] == ["bad duration"]

    _, second_params = cur.execute.call_args_list[1].args
    assert second_params[1] == "erp_materials"
    assert second_params[2] == "9"
    assert second_params[4] == ["cascaded"]


def test_commit_quarantine_records_skips_empty_batch():
    conn = MagicMock()
    commit_quarantine_records(conn, "run-1", [], [])
    conn.cursor.assert_not_called()
    conn.commit.assert_not_called()


def test_commit_quarantine_records_commits_then_star_can_fail_separately():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur

    commit_quarantine_records(
        conn,
        "run-1",
        [{"record": {"task_id": "1"}, "errors": ["bad"]}],
        [],
    )
    conn.commit.assert_called_once()
    conn.rollback.assert_not_called()


def test_commit_quarantine_records_rolls_back_on_error():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    cur.execute.side_effect = RuntimeError("dq down")

    with pytest.raises(RuntimeError, match="dq down"):
        commit_quarantine_records(
            conn,
            "run-1",
            [{"record": {"task_id": "1"}, "errors": ["bad"]}],
            [],
        )

    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()


def test_load_pipeline_commits_quarantine_before_star(monkeypatch):
    conn = MagicMock()
    commit_dq = MagicMock()
    load_star = MagicMock()
    monkeypatch.setattr("load.commit_quarantine_records", commit_dq)
    monkeypatch.setattr("load.load_star_schema", load_star)

    q_tasks = [{"record": {"task_id": "1"}, "errors": ["bad"]}]
    load_pipeline(conn, "run-1", q_tasks, [], [], [], [], [], [])

    commit_dq.assert_called_once_with(conn, "run-1", q_tasks, [])
    load_star.assert_called_once()
    assert commit_dq.call_args[0][0] is conn
    assert load_star.call_args[0][0] is conn


def test_load_pipeline_does_not_load_star_if_quarantine_fails(monkeypatch):
    conn = MagicMock()
    monkeypatch.setattr(
        "load.commit_quarantine_records",
        MagicMock(side_effect=RuntimeError("dq down")),
    )
    load_star = MagicMock()
    monkeypatch.setattr("load.load_star_schema", load_star)

    with pytest.raises(RuntimeError, match="dq down"):
        load_pipeline(
            conn,
            "run-1",
            [{"record": {"task_id": "1"}, "errors": ["bad"]}],
            [],
            [],
            [],
            [],
            [],
            [],
        )

    load_star.assert_not_called()


def test_load_pipeline_star_failure_happens_after_quarantine_commit(monkeypatch):
    conn = MagicMock()
    commit_dq = MagicMock()
    monkeypatch.setattr("load.commit_quarantine_records", commit_dq)
    monkeypatch.setattr(
        "load.load_star_schema", MagicMock(side_effect=RuntimeError("star down"))
    )

    with pytest.raises(RuntimeError, match="star down"):
        load_pipeline(
            conn,
            "run-1",
            [{"record": {"task_id": "1"}, "errors": ["bad"]}],
            [],
            [],
            [],
            [],
            [],
            [],
        )

    commit_dq.assert_called_once()
