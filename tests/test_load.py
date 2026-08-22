from datetime import date
from unittest.mock import MagicMock

from load import (
    get_connection,
    get_id_maps,
    load_dim_date,
    load_dim_material,
    load_dim_technician,
    load_facts,
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
    assert params == ("Jan Kowalski", "Gdansk", "2020-01-01")


def test_load_dim_material_inserts_rows():
    cur = MagicMock()
    load_dim_material(cur, [{"material_name": "cable", "unit_cost": 10}])

    sql, params = cur.execute.call_args.args
    assert "INSERT INTO dim_material" in sql
    assert params == ("cable", 10)


def test_load_dim_date_inserts_rows():
    cur = MagicMock()
    load_dim_date(
        cur,
        [{"full_date": "2026-08-17", "year": 2026, "month": 8, "day": 17, "weekday": "Monday"}],
    )

    sql, params = cur.execute.call_args.args
    assert "INSERT INTO dim_date" in sql
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


def test_load_facts_maps_ids_and_inserts():
    cur = MagicMock()
    load_facts(
        cur,
        [
            {
                "technician_name": "Jan Kowalski",
                "material_name": "cable",
                "task_date": "2026-08-17",
                "task_type": "repair",
                "duration_minutes": 60,
                "material_quantity": 2.0,
                "total_cost": 20.0,
                "status": "completed",
            }
        ],
        {"Jan Kowalski": 1},
        {"cable": 10},
        {"2026-08-17": 100},
    )

    sql, params = cur.execute.call_args.args
    assert "INSERT INTO fact_work_orders" in sql
    assert params == (1, 10, 100, "repair", 60, 2.0, 20.0, "completed")


def test_load_facts_uses_none_for_missing_keys():
    cur = MagicMock()
    load_facts(
        cur,
        [
            {
                "technician_name": "Unknown",
                "material_name": None,
                "task_date": "2026-08-17",
                "task_type": "inspection",
                "duration_minutes": 30,
                "material_quantity": 0,
                "total_cost": 0,
                "status": "completed",
            }
        ],
        {},
        {},
        {"2026-08-17": 100},
    )

    _, params = cur.execute.call_args.args
    assert params[:3] == (None, None, 100)
