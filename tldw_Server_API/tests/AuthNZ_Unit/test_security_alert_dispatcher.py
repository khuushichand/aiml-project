import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest

from tldw_Server_API.app.core.AuthNZ.alerting import SecurityAlertDispatcher


def test_security_alert_dispatcher_disabled(tmp_path):
    log_file = tmp_path / "alerts.log"
    settings = SimpleNamespace(
        SECURITY_ALERTS_ENABLED=False,
        SECURITY_ALERT_MIN_SEVERITY="medium",
        SECURITY_ALERT_FILE_PATH=str(log_file),
        SECURITY_ALERT_WEBHOOK_URL=None,
        SECURITY_ALERT_WEBHOOK_HEADERS=None,
        SECURITY_ALERT_EMAIL_TO=None,
        SECURITY_ALERT_EMAIL_FROM=None,
        SECURITY_ALERT_EMAIL_SUBJECT_PREFIX="[AuthNZ]",
        SECURITY_ALERT_SMTP_HOST=None,
        SECURITY_ALERT_SMTP_PORT=587,
        SECURITY_ALERT_SMTP_STARTTLS=True,
        SECURITY_ALERT_SMTP_USERNAME=None,
        SECURITY_ALERT_SMTP_PASSWORD=None,
        SECURITY_ALERT_SMTP_TIMEOUT=10,
    )

    async def _run():
        dispatcher = SecurityAlertDispatcher(settings=settings)
        dispatched = await dispatcher.dispatch("Subject", "Message", severity="high")
        assert dispatched is False
        assert not log_file.exists()

    asyncio.run(_run())


def test_security_alert_dispatcher_writes_file(tmp_path):
    log_file = tmp_path / "alerts.log"
    settings = SimpleNamespace(
        SECURITY_ALERTS_ENABLED=True,
        SECURITY_ALERT_MIN_SEVERITY="low",
        SECURITY_ALERT_FILE_PATH=str(log_file),
        SECURITY_ALERT_WEBHOOK_URL=None,
        SECURITY_ALERT_WEBHOOK_HEADERS=None,
        SECURITY_ALERT_EMAIL_TO=None,
        SECURITY_ALERT_EMAIL_FROM=None,
        SECURITY_ALERT_EMAIL_SUBJECT_PREFIX="[AuthNZ]",
        SECURITY_ALERT_SMTP_HOST=None,
        SECURITY_ALERT_SMTP_PORT=587,
        SECURITY_ALERT_SMTP_STARTTLS=True,
        SECURITY_ALERT_SMTP_USERNAME=None,
        SECURITY_ALERT_SMTP_PASSWORD=None,
        SECURITY_ALERT_SMTP_TIMEOUT=10,
    )

    async def _run():
        dispatcher = SecurityAlertDispatcher(settings=settings)
        dispatched = await dispatcher.dispatch(
            "Subject", "Message", severity="medium", metadata={"foo": "bar"}
        )
        assert dispatched is True
        assert log_file.exists()
        content = log_file.read_text(encoding="utf-8").strip()
        record = json.loads(content)
        assert record["subject"] == "Subject"
        assert record["severity"] == "medium"
        assert record["metadata"]["foo"] == "bar"

    asyncio.run(_run())


def test_security_alert_dispatcher_handles_webhook_failure(tmp_path, monkeypatch):
    log_file = tmp_path / "alerts.log"

    class FailingClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            raise httpx.HTTPError("boom")

    monkeypatch.setattr(
        "tldw_Server_API.app.core.AuthNZ.alerting.httpx.AsyncClient", FailingClient
    )

    settings = SimpleNamespace(
        SECURITY_ALERTS_ENABLED=True,
        SECURITY_ALERT_MIN_SEVERITY="low",
        SECURITY_ALERT_FILE_PATH=str(log_file),
        SECURITY_ALERT_WEBHOOK_URL="https://example.invalid/webhook",
        SECURITY_ALERT_WEBHOOK_HEADERS=None,
        SECURITY_ALERT_EMAIL_TO=None,
        SECURITY_ALERT_EMAIL_FROM=None,
        SECURITY_ALERT_EMAIL_SUBJECT_PREFIX="[AuthNZ]",
        SECURITY_ALERT_SMTP_HOST=None,
        SECURITY_ALERT_SMTP_PORT=587,
        SECURITY_ALERT_SMTP_STARTTLS=True,
        SECURITY_ALERT_SMTP_USERNAME=None,
        SECURITY_ALERT_SMTP_PASSWORD=None,
        SECURITY_ALERT_SMTP_TIMEOUT=10,
    )

    async def _run():
        dispatcher = SecurityAlertDispatcher(settings=settings)
        dispatched = await dispatcher.dispatch(
            "Subject", "Message", severity="critical"
        )
        assert dispatched is False
        assert log_file.exists()

    asyncio.run(_run())


def test_security_alert_validation_requires_sink(tmp_path):
    settings = SimpleNamespace(
        SECURITY_ALERTS_ENABLED=True,
        SECURITY_ALERT_MIN_SEVERITY="high",
        SECURITY_ALERT_FILE_PATH="",
        SECURITY_ALERT_WEBHOOK_URL="",
        SECURITY_ALERT_WEBHOOK_HEADERS=None,
        SECURITY_ALERT_EMAIL_TO="",
        SECURITY_ALERT_EMAIL_FROM="",
        SECURITY_ALERT_EMAIL_SUBJECT_PREFIX="[AuthNZ]",
        SECURITY_ALERT_SMTP_HOST="",
        SECURITY_ALERT_SMTP_PORT=587,
        SECURITY_ALERT_SMTP_STARTTLS=True,
        SECURITY_ALERT_SMTP_USERNAME="",
        SECURITY_ALERT_SMTP_PASSWORD="",
        SECURITY_ALERT_SMTP_TIMEOUT=10,
    )

    dispatcher = SecurityAlertDispatcher(settings=settings)
    with pytest.raises(ValueError):
        dispatcher.validate_configuration()


def test_security_alert_status_snapshot(tmp_path):
    log_file = tmp_path / "alerts.log"
    settings = SimpleNamespace(
        SECURITY_ALERTS_ENABLED=True,
        SECURITY_ALERT_MIN_SEVERITY="low",
        SECURITY_ALERT_FILE_PATH=str(log_file),
        SECURITY_ALERT_WEBHOOK_URL=None,
        SECURITY_ALERT_WEBHOOK_HEADERS=None,
        SECURITY_ALERT_EMAIL_TO=None,
        SECURITY_ALERT_EMAIL_FROM=None,
        SECURITY_ALERT_EMAIL_SUBJECT_PREFIX="[AuthNZ]",
        SECURITY_ALERT_SMTP_HOST=None,
        SECURITY_ALERT_SMTP_PORT=587,
        SECURITY_ALERT_SMTP_STARTTLS=True,
        SECURITY_ALERT_SMTP_USERNAME=None,
        SECURITY_ALERT_SMTP_PASSWORD=None,
        SECURITY_ALERT_SMTP_TIMEOUT=10,
    )

    dispatcher = SecurityAlertDispatcher(settings=settings)
    dispatcher.validate_configuration()

    async def _run():
        await dispatcher.dispatch("Subject", "Message", severity="medium")

    asyncio.run(_run())

    status = dispatcher.get_status()
    assert status["enabled"] is True
    assert status["dispatch_count"] == 1
    assert status["last_sink_status"]["file"] is True
    assert status["last_sink_errors"]["file"] is None
    assert status["sink_thresholds"]["file"] is None


def test_security_alert_per_sink_thresholds(tmp_path, monkeypatch):
    log_file = tmp_path / "alerts.log"

    class BombClient:
        async def __aenter__(self):
            raise AssertionError("webhook should not be invoked")

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "tldw_Server_API.app.core.AuthNZ.alerting.httpx.AsyncClient",
        BombClient,
    )

    settings = SimpleNamespace(
        SECURITY_ALERTS_ENABLED=True,
        SECURITY_ALERT_MIN_SEVERITY="low",
        SECURITY_ALERT_FILE_PATH=str(log_file),
        SECURITY_ALERT_WEBHOOK_URL="https://example.invalid/webhook",
        SECURITY_ALERT_WEBHOOK_HEADERS=None,
        SECURITY_ALERT_WEBHOOK_MIN_SEVERITY="critical",
        SECURITY_ALERT_EMAIL_TO=None,
        SECURITY_ALERT_EMAIL_FROM=None,
        SECURITY_ALERT_EMAIL_SUBJECT_PREFIX="[AuthNZ]",
        SECURITY_ALERT_SMTP_HOST=None,
        SECURITY_ALERT_SMTP_PORT=587,
        SECURITY_ALERT_SMTP_STARTTLS=True,
        SECURITY_ALERT_SMTP_USERNAME=None,
        SECURITY_ALERT_SMTP_PASSWORD=None,
        SECURITY_ALERT_SMTP_TIMEOUT=10,
        SECURITY_ALERT_EMAIL_MIN_SEVERITY=None,
        SECURITY_ALERT_FILE_MIN_SEVERITY=None,
    )

    dispatcher = SecurityAlertDispatcher(settings=settings)
    dispatcher.validate_configuration()

    asyncio.run(dispatcher.dispatch("Subject", "Message", severity="medium"))

    status = dispatcher.get_status()
    assert status["dispatch_count"] == 1
    assert status["last_sink_status"]["file"] is True
    assert status["last_sink_status"]["webhook"] is None
    assert status["sink_thresholds"]["webhook"] == "critical"


def test_security_alert_backoff(tmp_path, monkeypatch):
    log_file = tmp_path / "alerts.log"

    class FailingClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            raise httpx.HTTPError("boom")

    monkeypatch.setattr(
        "tldw_Server_API.app.core.AuthNZ.alerting.httpx.AsyncClient",
        FailingClient,
    )

    settings = SimpleNamespace(
        SECURITY_ALERTS_ENABLED=True,
        SECURITY_ALERT_MIN_SEVERITY="low",
        SECURITY_ALERT_FILE_PATH=str(log_file),
        SECURITY_ALERT_WEBHOOK_URL="https://example.invalid/webhook",
        SECURITY_ALERT_WEBHOOK_HEADERS=None,
        SECURITY_ALERT_BACKOFF_SECONDS=60,
        SECURITY_ALERT_EMAIL_TO=None,
        SECURITY_ALERT_EMAIL_FROM=None,
        SECURITY_ALERT_EMAIL_SUBJECT_PREFIX="[AuthNZ]",
        SECURITY_ALERT_SMTP_HOST=None,
        SECURITY_ALERT_SMTP_PORT=587,
        SECURITY_ALERT_SMTP_STARTTLS=True,
        SECURITY_ALERT_SMTP_USERNAME=None,
        SECURITY_ALERT_SMTP_PASSWORD=None,
        SECURITY_ALERT_SMTP_TIMEOUT=10,
        SECURITY_ALERT_WEBHOOK_MIN_SEVERITY=None,
        SECURITY_ALERT_EMAIL_MIN_SEVERITY=None,
        SECURITY_ALERT_FILE_MIN_SEVERITY=None,
    )

    dispatcher = SecurityAlertDispatcher(settings=settings)
    dispatcher.validate_configuration()

    async def _run_sequence():
        first = await dispatcher.dispatch("Subject", "Message", severity="critical")
        second = await dispatcher.dispatch("Subject", "Message", severity="critical")
        return first, second

    first_ok, second_ok = asyncio.run(_run_sequence())
    assert first_ok is False
    assert second_ok is False

    info = dispatcher.get_status()
    assert info["last_sink_errors"]["webhook"] in {"boom", "backoff"}
    assert info["sink_backoff_until"]["webhook"] is not None
