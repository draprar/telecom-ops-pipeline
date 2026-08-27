"""Persistence for records rejected by validation.

Rather than only printing/logging validation errors (which get lost once the
container exits), rejected rows are written to a `pipeline_quarantine` table
so they can be inspected, reprocessed, or reported on later. See the
`add_quarantine_table` Alembic migration for the schema.
"""

import json
import logging

logger = logging.getLogger(__name__)


def write_quarantine(cur, run_id, record_type, row, reason):
    """Insert a single rejected record into the quarantine table.

    Args:
        cur: an open psycopg2 cursor (part of the same transaction as the
             rest of the load, so quarantine writes and fact/dim loads
             commit or roll back together).
        run_id: identifier for this pipeline run (Airflow run_id, or
                "standalone" for the CLI entrypoint).
        record_type: short label, e.g. "crm_task" or "erp_material".
        row: the original (rejected) record, JSON-serializable.
        reason: human-readable reason(s) the record was rejected.
    """
    cur.execute(
        """
        INSERT INTO pipeline_quarantine (run_id, record_type, payload, reason)
        VALUES (%s, %s, %s, %s)
        """,
        (run_id, record_type, json.dumps(row, default=str), reason),
    )


def write_quarantine_batch(cur, run_id, record_type, rejected_rows):
    """Convenience wrapper for a list of {"row": ..., "reasons": [...]} items,
    as produced by validate.validate_tasks / validate_materials.
    """
    for item in rejected_rows:
        write_quarantine(cur, run_id, record_type, item["row"], "; ".join(item["reasons"]))
    if rejected_rows:
        logger.warning(
            "Quarantined %d %s record(s) for run_id=%s", len(rejected_rows), record_type, run_id
        )
