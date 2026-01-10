import asyncio
import json
import smtplib
from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.AuthNZ.alerting import SecurityAlertDispatcher
from tldw_Server_API.app.core.exceptions import (
    SecurityAlertWebhookError,
    SecurityAlertEmailError,
    SecurityAlertFileError,
)


def _make_record():


    return {
        "subject": "Test",
        "message": "Test message",
        "severity": "high",
        "timestamp": "2025-01-01T00:00:00Z",
        "metadata": {"k": "v"},
    }


def _make_settings_with_file(path: str):
    return SimpleNamespace(
        SECURITY_ALERTS_ENABLED=True,
        SECURITY_ALERT_MIN_SEVERITY="low",
        SECURITY_ALERT_FILE_PATH=path,
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


def _make_settings_with_email(to: str, from_addr: str, host: str):
    return SimpleNamespace(
        SECURITY_ALERTS_ENABLED=True,
        SECURITY_ALERT_MIN_SEVERITY="low",
        SECURITY_ALERT_FILE_PATH=None,
        SECURITY_ALERT_WEBHOOK_URL=None,
        SECURITY_ALERT_WEBHOOK_HEADERS=None,
        SECURITY_ALERT_EMAIL_TO=to,
        SECURITY_ALERT_EMAIL_FROM=from_addr,
        SECURITY_ALERT_EMAIL_SUBJECT_PREFIX="[AuthNZ]",
        SECURITY_ALERT_SMTP_HOST=host,
        SECURITY_ALERT_SMTP_PORT=587,
        SECURITY_ALERT_SMTP_STARTTLS=True,
        SECURITY_ALERT_SMTP_USERNAME=None,
        SECURITY_ALERT_SMTP_PASSWORD=None,
        SECURITY_ALERT_SMTP_TIMEOUT=5,
    )


def _make_settings_with_webhook(url: str):
    return SimpleNamespace(
        SECURITY_ALERTS_ENABLED=True,
        SECURITY_ALERT_MIN_SEVERITY="low",
        SECURITY_ALERT_FILE_PATH=None,
        SECURITY_ALERT_WEBHOOK_URL=url,
        SECURITY_ALERT_WEBHOOK_HEADERS=None,
        SECURITY_ALERT_EMAIL_TO=None,
        SECURITY_ALERT_EMAIL_FROM=None,
        SECURITY_ALERT_EMAIL_SUBJECT_PREFIX="[AuthNZ]",
        SECURITY_ALERT_SMTP_HOST=None,
        SECURITY_ALERT_SMTP_PORT=587,
        SECURITY_ALERT_SMTP_STARTTLS=True,
        SECURITY_ALERT_SMTP_USERNAME=None,
        SECURITY_ALERT_SMTP_PASSWORD=None,
        SECURITY_ALERT_SMTP_TIMEOUT=5,
    )


def test_file_sink_raises_custom_error(tmp_path):


    # Make file_path a directory so opening it as a file fails
    bad_path = tmp_path / "alerts_dir"
    bad_path.mkdir()
    dispatcher = SecurityAlertDispatcher(settings=_make_settings_with_file(str(bad_path)))
    with pytest.raises(SecurityAlertFileError):
        dispatcher._write_file_sync(_make_record())


def test_email_sink_raises_custom_error_on_starttls(monkeypatch):


    class FakeSMTP:
        def __init__(self, host, port, timeout):
            self.host = host
            self.port = port
            self.timeout = timeout

        def __enter__(self):

            return self

        def __exit__(self, exc_type, exc, tb):

            return False

        def ehlo(self):

            pass

        def starttls(self):

            raise smtplib.SMTPException("starttls failed")

        def login(self, user, pwd):

            pass

        def send_message(self, message):

            pass

    monkeypatch.setattr("smtplib.SMTP", FakeSMTP)

    dispatcher = SecurityAlertDispatcher(
        settings=_make_settings_with_email("ops@example.com", "noreply@example.com", "smtp.example.com")
    )

    with pytest.raises(SecurityAlertEmailError):
        dispatcher._send_email_sync(_make_record())


@pytest.mark.asyncio
async def test_webhook_sink_raises_custom_error(monkeypatch):
    class FakeResponse:
        status_code = 500
        text = "webhook error body"

    async def fake_afetch(*args, **kwargs):
        return FakeResponse()

    monkeypatch.setattr(
        "tldw_Server_API.app.core.AuthNZ.alerting.afetch", fake_afetch
    )

    dispatcher = SecurityAlertDispatcher(settings=_make_settings_with_webhook("https://example.invalid/hook"))

    with pytest.raises(SecurityAlertWebhookError):
        await dispatcher._send_webhook(_make_record())
