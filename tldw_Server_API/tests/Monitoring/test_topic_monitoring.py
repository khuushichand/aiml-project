import os
import json
import pytest

from tldw_Server_API.app.core.Monitoring.topic_monitoring_service import (
    get_topic_monitoring_service,
    _reset_topic_monitoring_service,
)
from tldw_Server_API.app.api.v1.schemas.monitoring_schemas import Watchlist, WatchlistRule
from tldw_Server_API.app.core.DB_Management.TopicMonitoring_DB import TopicMonitoringDB


pytestmark = pytest.mark.unit


def test_topic_monitoring_alert_creation(tmp_path, monkeypatch):
    # Point alerts DB to a temp file
    db_file = tmp_path / "alerts.db"
    monkeypatch.setenv("MONITORING_ALERTS_DB", str(db_file))
    # Use an in-memory watchlists file to avoid writing to repo
    wl_file = tmp_path / "watchlists.json"
    wl_file.write_text(json.dumps({"watchlists": []}), encoding="utf-8")
    monkeypatch.setenv("MONITORING_WATCHLISTS_FILE", str(wl_file))

    # Ensure the singleton picks up the temp paths for this test run
    _reset_topic_monitoring_service()
    svc = get_topic_monitoring_service()
    svc.reload()

    # Create watchlist for user 'u1' with a literal pattern
    wl = Watchlist(
        name="Test WL",
        description="Detect 'badword'",
        enabled=True,
        scope_type="user",
        scope_id="u1",
        rules=[WatchlistRule(pattern="badword", category="custom", severity="warning")],
    )
    wl = svc.upsert_watchlist(wl)

    # Evaluate input text and generate alert
    count = svc.evaluate_and_alert(user_id="u1", text="This has a badword here.", source="chat.input")
    assert count >= 1

    # Check the alert persisted
    db = TopicMonitoringDB(db_path=str(db_file))
    items = db.list_alerts(user_id="u1")
    assert len(items) >= 1
    assert any("badword" in (it.get("pattern") or "") for it in items)
