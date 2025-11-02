import os
import json
from pathlib import Path

from tldw_Server_API.app.core.Monitoring.notification_service import NotificationService
from tldw_Server_API.app.core.DB_Management.TopicMonitoring_DB import TopicAlert


def test_notification_threshold_and_file_sink(tmp_path, monkeypatch):
    out = tmp_path / "notifs.log"
    monkeypatch.setenv("MONITORING_NOTIFY_ENABLED", "true")
    monkeypatch.setenv("MONITORING_NOTIFY_MIN_SEVERITY", "critical")
    monkeypatch.setenv("MONITORING_NOTIFY_FILE", str(out))

    svc = NotificationService()

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
    svc.notify(a1)
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
    svc.notify(a2)
    text = out.read_text()
    assert "self_harm" in text and "critical" in text
