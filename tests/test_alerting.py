from unittest.mock import MagicMock, patch

from alerting import notify_on_failure


def _fake_context(exception="boom"):
    dag = MagicMock()
    dag.dag_id = "telecom_ops_etl"

    task_instance = MagicMock()
    task_instance.task_id = "load"
    task_instance.log_url = "http://localhost:8080/log?dag_id=telecom_ops_etl"

    return {
        "dag": dag,
        "task_instance": task_instance,
        "run_id": "manual__2026-08-30T10:00:00",
        "exception": exception,
    }


def test_skips_silently_when_webhook_url_not_set(monkeypatch):
    monkeypatch.delenv("ALERT_WEBHOOK_URL", raising=False)

    with patch("alerting.requests.post") as mock_post:
        notify_on_failure(_fake_context())

    mock_post.assert_not_called()


def test_posts_discord_shaped_payload_by_default(monkeypatch):
    monkeypatch.setenv("ALERT_WEBHOOK_URL", "https://discord.com/api/webhooks/fake")
    monkeypatch.delenv("ALERT_WEBHOOK_TYPE", raising=False)

    with patch("alerting.requests.post") as mock_post:
        mock_post.return_value.raise_for_status.return_value = None
        notify_on_failure(_fake_context(exception="RuntimeError: db down"))

    mock_post.assert_called_once()
    url, kwargs = mock_post.call_args.args[0], mock_post.call_args.kwargs
    assert url == "https://discord.com/api/webhooks/fake"
    assert "content" in kwargs["json"]
    message = kwargs["json"]["content"]
    assert "telecom_ops_etl" in message
    assert "load" in message
    assert "RuntimeError: db down" in message


def test_posts_slack_shaped_payload_when_configured(monkeypatch):
    monkeypatch.setenv("ALERT_WEBHOOK_URL", "https://hooks.slack.com/services/fake")
    monkeypatch.setenv("ALERT_WEBHOOK_TYPE", "slack")

    with patch("alerting.requests.post") as mock_post:
        mock_post.return_value.raise_for_status.return_value = None
        notify_on_failure(_fake_context())

    _url, kwargs = mock_post.call_args.args[0], mock_post.call_args.kwargs
    assert "text" in kwargs["json"]


def test_never_raises_when_the_http_call_itself_fails(monkeypatch):
    monkeypatch.setenv("ALERT_WEBHOOK_URL", "https://discord.com/api/webhooks/fake")

    with patch("alerting.requests.post", side_effect=ConnectionError("no network")):
        notify_on_failure(_fake_context())  # must not raise


def test_never_raises_when_webhook_returns_error_status(monkeypatch):
    monkeypatch.setenv("ALERT_WEBHOOK_URL", "https://discord.com/api/webhooks/fake")

    with patch("alerting.requests.post") as mock_post:
        mock_post.return_value.raise_for_status.side_effect = Exception("HTTP 404")
        notify_on_failure(_fake_context())  # must not raise