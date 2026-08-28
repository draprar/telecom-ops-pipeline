import logging
import sys


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logging for standalone script entry points.

    Call this ONLY from `scripts/run_pipeline.py` (or other standalone
    entry points run outside Airflow). Do NOT call this from the Airflow
    DAG module: Airflow configures its own root logging and captures
    per-task logs into its own handlers/UI. Task modules should simply use
    `logging.getLogger(__name__)` and let whichever environment they run
    in (plain script vs. Airflow) own the handler configuration.
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )