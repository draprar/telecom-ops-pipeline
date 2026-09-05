"""Parquet read/write helpers for Airflow DAG task handoffs.

The DAG passes paths through XCom, not row payloads — Parquet keeps types
and stays smaller than JSON at higher volumes.
"""

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


def _empty_quarantine_table() -> pa.Table:
    return pa.table(
        {
            "record_json": pa.array([], type=pa.string()),
            "errors": pa.array([], type=pa.list_(pa.string())),
        }
    )


def write_rows(path: Path, rows: list[dict]) -> str:
    """Write a list of flat dict rows to Parquet. Returns the path string."""
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(rows) if rows else pa.table({})
    pq.write_table(table, path)
    return str(path)


def _require_staging_file(path_str: str) -> Path:
    """Return the staging path or raise if a DAG handoff file is missing."""
    path = Path(path_str)
    if not path.exists():
        raise FileNotFoundError(f"Staging file not found: {path}")
    return path


def read_rows(path_str: str) -> list[dict]:
    """Read flat dict rows written by write_rows()."""
    return pq.read_table(_require_staging_file(path_str)).to_pylist()


def write_quarantine_entries(path: Path, entries: list[dict]) -> str:
    """Persist {"record": ..., "errors": [...]} payloads for load_task."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if entries:
        rows = [
            {
                "record_json": json.dumps(entry["record"], default=str),
                "errors": list(entry.get("errors") or []),
            }
            for entry in entries
        ]
        table = pa.Table.from_pylist(rows)
    else:
        table = _empty_quarantine_table()
    pq.write_table(table, path)
    return str(path)


def read_quarantine_entries(path_str: str) -> list[dict]:
    """Rebuild quarantine entry dicts from write_quarantine_entries()."""
    rows = pq.read_table(_require_staging_file(path_str)).to_pylist()
    return [
        {
            "record": json.loads(row["record_json"]),
            "errors": list(row.get("errors") or []),
        }
        for row in rows
    ]
