import os
import json
from pathlib import Path

import tldw_Server_API.app.core.Monitoring.notification_service as notification_service
from tldw_Server_API.app.core.Monitoring.notification_service import NotificationService
from tldw_Server_API.app.core.DB_Management.TopicMonitoring_DB import TopicAlert


def test_notification_threshold_and_file_sink(tmp_path, monkeypatch):


     out = tmp_path / "notifs.log"
    monkeypatch.setenv("MONITORING_NOTIFY_ENABLED", "true")
    monkeypatch.setenv("MONITORING_NOTIFY_MIN_SEVERITY", "critical")
    monkeypatch.setenv("MONITORING_NOTIFY_FILE", str(out))

    svc = NotificationService()
    assert svc.get_notification_file_path() == str(out)

    # Below threshold (warning) should not write
    a1 = TopicAlert(
        user_id="u",
        scope_type="user",
        scope_id="u",
        source="chat.input",
        watchlist_id="w",
        rule_category="adult",
        rule_severity="warning",
        pattern="nsfw",
        text_snippet="...nsfw...",
    )
    result = svc.notify(a1)
    assert result == "skipped"
    assert not out.exists() or out.read_text() == ""

    # Meets threshold (critical) should write
    a2 = TopicAlert(
        user_id="u",
        scope_type="user",
        scope_id="u",
        source="chat.input",
        watchlist_id="w",
        rule_category="self_harm",
        rule_severity="critical",
        pattern="suicide",
        text_snippet="...",
    )
    result = svc.notify(a2)
    assert result == "logged"
    text = out.read_text()
    assert "self_harm" in text and "critical" in text


def test_notification_handles_invalid_smtp_port(monkeypatch):


     monkeypatch.setenv("MONITORING_NOTIFY_SMTP_PORT", "not-a-number")

    svc = NotificationService()
    assert svc.smtp_port == 587


def test_notification_splits_email_recipients(monkeypatch):


     monkeypatch.setenv("MONITORING_NOTIFY_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("MONITORING_NOTIFY_SMTP_PORT", "2525")
    monkeypatch.setenv("MONITORING_NOTIFY_EMAIL_TO", "a@example.com, b@example.com")
    monkeypatch.setenv("MONITORING_NOTIFY_EMAIL_FROM", "sender@example.com")

    sent: dict[str, object] = {}

    class _FakeSMTP:
        def __init__(self, host, port, timeout=None):
                     sent["host"] = host
            sent["port"] = port
            sent["timeout"] = timeout

        def __enter__(self):

                     return self

        def __exit__(self, exc_type, exc, tb):

                     return False

        def starttls(self):

                     sent["starttls"] = True

        def login(self, user, password):

                     sent["login"] = (user, password)

        def sendmail(self, from_addr, to_addrs, msg):

                     sent["from"] = from_addr
            sent["to"] = list(to_addrs)
            sent["msg"] = msg

    monkeypatch.setattr(notification_service.smtplib, "SMTP", _FakeSMTP)

    svc = NotificationService()
    alert = TopicAlert(
        user_id="u",
        scope_type="user",
        scope_id="u",
        source="chat.input",
        watchlist_id="w",
        rule_category="adult",
        rule_severity="critical",
        pattern="nsfw",
        text_snippet="...nsfw...",
    )
    svc._send_email(alert)

    assert sent["to"] == ["a@example.com", "b@example.com"]
    assert sent["from"] == "sender@example.com"


def test_notification_update_settings_normalizes_relative_file(tmp_path, monkeypatch):


     from tldw_Server_API.app.core.Utils import Utils as utils_module

    svc = NotificationService()
    monkeypatch.setattr(utils_module, "get_project_root", lambda: str(tmp_path))

    relative = "logs/monitoring.jsonl"
    updated = svc.update_settings(file=relative)

    expected = tmp_path / relative
    assert svc.file_path == str(expected)
    assert updated["file"] == str(expected)
    assert expected.parent.exists()


def test_notification_send_webhook_invokes_fetch(monkeypatch):


     import tldw_Server_API.app.core.http_client as http_client

    svc = NotificationService()
    svc.webhook_url = "https://example.com/hook"

    calls: dict[str, object] = {}

    class _FakeClient:
        def __enter__(self):
                     return self

        def __exit__(self, exc_type, exc, tb):

                     return False

    def _fake_create_client(timeout=None):

             calls["client_timeout"] = timeout
        return _FakeClient()

    def _fake_fetch(method, url, client, headers, json, timeout=None):

             calls["method"] = method
        calls["url"] = url
        calls["headers"] = headers
        calls["json"] = json
        calls["timeout"] = timeout

    monkeypatch.setattr(http_client, "create_client", _fake_create_client)
    monkeypatch.setattr(http_client, "fetch", _fake_fetch)

    svc._send_webhook({"event": "test"})

    assert calls["url"] == "https://example.com/hook"
    assert calls["method"] == "POST"
