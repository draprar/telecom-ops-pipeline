import pyarrow.parquet as pq
import pytest

from staging import (
    read_quarantine_entries,
    read_rows,
    write_quarantine_entries,
    write_rows,
)


def test_write_read_rows_roundtrip(tmp_path):
    rows = [
        {"task_id": "1", "duration_minutes": "60", "quantity": 2.5},
        {"task_id": "2", "duration_minutes": "30", "quantity": 1.0},
    ]
    path = tmp_path / "tasks.parquet"

    write_rows(path, rows)
    assert pq.read_table(path).num_rows == 2
    assert read_rows(str(path)) == rows


def test_write_read_rows_empty_list(tmp_path):
    path = tmp_path / "empty.parquet"
    write_rows(path, [])
    assert read_rows(str(path)) == []


def test_read_rows_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="Staging file not found"):
        read_rows(str(tmp_path / "missing.parquet"))


def test_read_quarantine_entries_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="Staging file not found"):
        read_quarantine_entries(str(tmp_path / "missing.parquet"))


def test_quarantine_entries_roundtrip(tmp_path):
    entries = [
        {
            "record": {"task_id": "9", "status": "open"},
            "errors": ["Invalid duration for task 9: 0", "Duplicate task ID found: 9"],
        }
    ]
    path = tmp_path / "quarantine_tasks.parquet"

    write_quarantine_entries(path, entries)
    assert read_quarantine_entries(str(path)) == entries


def test_quarantine_entries_empty_writes_readable_schema(tmp_path):
    path = tmp_path / "quarantine_empty.parquet"
    write_quarantine_entries(path, [])

    table = pq.read_table(path)
    assert table.num_rows == 0
    assert "record_json" in table.column_names
    assert read_quarantine_entries(str(path)) == []


def test_quarantine_record_json_serializes_with_default_str(tmp_path):
    entries = [{"record": {"task_id": "1", "note": "ok"}, "errors": ["bad"]}]
    path = tmp_path / "q.parquet"

    write_quarantine_entries(path, entries)
    assert read_quarantine_entries(str(path)) == entries
