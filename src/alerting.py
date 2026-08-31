"""Sends a chat notification when an Airflow task fails, via
`on_failure_callback`.

Deliberately decoupled from any one chat platform: ALERT_WEBHOOK_TYPE picks
the payload shape ("discord" or "slack"), ALERT_WEBHOOK_URL is the webhook
URL itself. Swapping providers is a .env change, not a code change - the
two payload shapes are the only thing that differs between them.

A failing alert must never make DAG failure handling fail further: every
exception in notify_on_failure() is caught and logged, never re-raised.
Airflow calls on_failure_callback functions as part of its own failure
handling, so an unhandled exception here would compound the original
failure instead of just reporting it.
"""

import logging
import os

import requests

logger = logging.getLogger(__name__)

ALERT_WEBHOOK_URL_ENV = "ALERT_WEBHOOK_URL"
ALERT_WEBHOOK_TYPE_ENV = "ALERT_WEBHOOK_TYPE"
DEFAULT_WEBHOOK_TYPE = "discord"
REQUEST_TIMEOUT_SECONDS = 10


def _build_message(context: dict) -> str:
    dag_id = context["dag"].dag_id
    task_id = context["task_instance"].task_id
    run_id = context["run_id"]
    exception = context.get("exception")
    log_url = context["task_instance"].log_url

    return (
        "\U0001F6A8 Airflow task failed\n"
        f"DAG: {dag_id}\n"
        f"Task: {task_id}\n"
        f"Run: {run_id}\n"
        f"Error: {exception}\n"
        f"Logs: {log_url}"
    )


def _build_payload(message: str, webhook_type: str) -> dict:
    if webhook_type == "slack":
        return {"text": message}
    # Discord and anything else fall back to Discord's shape, since that's
    # the platform this was actually tested against end-to-end.
    return {"content": message}


def notify_on_failure(context: dict) -> None:
    """on_failure_callback entry point. Never raises."""
    webhook_url = os.getenv(ALERT_WEBHOOK_URL_ENV)
    if not webhook_url:
        logger.info(
            "%s is not set - skipping failure alert.", ALERT_WEBHOOK_URL_ENV
        )
        return

    webhook_type = os.getenv(ALERT_WEBHOOK_TYPE_ENV, DEFAULT_WEBHOOK_TYPE).lower()

    try:
        message = _build_message(context)
        payload = _build_payload(message, webhook_type)
        response = requests.post(webhook_url, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        logger.info("Sent failure alert via %s webhook.", webhook_type)
    except Exception:
        logger.exception("Failed to send failure alert - continuing without raising.")