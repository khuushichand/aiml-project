import os
import json
from pathlib import Path
import pytest

from tldw_Server_API.app.core.Monitoring.topic_monitoring_service import (
    get_topic_monitoring_service,
    _reset_topic_monitoring_service,
)
from tldw_Server_API.app.api.v1.schemas.monitoring_schemas import Watchlist, WatchlistRule
from tldw_Server_API.app.core.DB_Management.TopicMonitoring_DB import TopicMonitoringDB, TopicAlert


pytestmark = pytest.mark.unit


def test_topic_monitoring_alert_creation(tmp_path, monkeypatch):


    # Point alerts DB to a temp file
    db_file = tmp_path / "alerts.db"
    monkeypatch.setenv("MONITORING_ALERTS_DB", str(db_file))
    monkeypatch.setenv("MONITORING_ENABLED", "true")
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


def test_topic_monitoring_regex_pattern_with_flags(tmp_path, monkeypatch):


    db_file = tmp_path / "alerts.db"
    monkeypatch.setenv("MONITORING_ALERTS_DB", str(db_file))
    monkeypatch.setenv("MONITORING_ENABLED", "true")
    wl_file = tmp_path / "watchlists.json"
    wl_file.write_text(json.dumps({"watchlists": []}), encoding="utf-8")
    monkeypatch.setenv("MONITORING_WATCHLISTS_FILE", str(wl_file))

    _reset_topic_monitoring_service()
    svc = get_topic_monitoring_service()
    svc.reload()

    wl = Watchlist(
        name="Regex WL",
        description="Detect regex with flags",
        enabled=True,
        scope_type="user",
        scope_id="u1",
        rules=[WatchlistRule(pattern="/badword/i", category="custom", severity="warning")],
    )
    svc.upsert_watchlist(wl)

    count = svc.evaluate_and_alert(user_id="u1", text="BADWORD here", source="chat.input")
    assert count >= 1

    db = TopicMonitoringDB(db_path=str(db_file))
    items = db.list_alerts(user_id="u1")
    assert any((it.get("pattern") or "") == "badword" for it in items)


def test_topic_monitoring_skips_empty_pattern(tmp_path, monkeypatch):


    db_file = tmp_path / "alerts.db"
    monkeypatch.setenv("MONITORING_ALERTS_DB", str(db_file))
    monkeypatch.setenv("MONITORING_ENABLED", "true")
    wl_file = tmp_path / "watchlists.json"
    wl_file.write_text(json.dumps({"watchlists": []}), encoding="utf-8")
    monkeypatch.setenv("MONITORING_WATCHLISTS_FILE", str(wl_file))

    _reset_topic_monitoring_service()
    svc = get_topic_monitoring_service()
    svc.reload()

    wl = Watchlist(
        name="Empty Pattern WL",
        description="Should be ignored",
        enabled=True,
        scope_type="user",
        scope_id="u1",
        rules=[WatchlistRule(pattern="", category="custom", severity="warning")],
    )
    svc.upsert_watchlist(wl)

    count = svc.evaluate_and_alert(user_id="u1", text="anything", source="chat.input")
    assert count == 0

    db = TopicMonitoringDB(db_path=str(db_file))
    items = db.list_alerts(user_id="u1")
    assert items == []


def test_topic_monitoring_streaming_dedupe(tmp_path, monkeypatch):
    db_file = tmp_path / "alerts.db"
    monkeypatch.setenv("MONITORING_ALERTS_DB", str(db_file))
    monkeypatch.setenv("MONITORING_ENABLED", "true")
    wl_file = tmp_path / "watchlists.json"
    wl_file.write_text(json.dumps({"watchlists": []}), encoding="utf-8")
    monkeypatch.setenv("MONITORING_WATCHLISTS_FILE", str(wl_file))

    _reset_topic_monitoring_service()
    svc = get_topic_monitoring_service()
    svc.reload()

    wl = Watchlist(
        name="Streaming WL",
        description="Detect 'alert'",
        enabled=True,
        scope_type="user",
        scope_id="u1",
        rules=[WatchlistRule(pattern="alert", category="custom", severity="warning")],
    )
    svc.upsert_watchlist(wl)

    created1 = svc.evaluate_and_alert(
        user_id="u1",
        text="alert me please",
        source="chat.output",
        source_id="stream-1",
        chunk_id="stream-1:1",
        chunk_seq=1,
    )
    created2 = svc.evaluate_and_alert(
        user_id="u1",
        text="alert me please",
        source="chat.output",
        source_id="stream-1",
        chunk_id="stream-1:2",
        chunk_seq=2,
    )

    assert created1 == 1
    assert created2 == 0

    db = TopicMonitoringDB(db_path=str(db_file))
    items = db.list_alerts(user_id="u1")
    assert len(items) == 1


def test_topic_monitoring_streaming_dedupe_is_per_watchlist(tmp_path, monkeypatch):
    db_file = tmp_path / "alerts.db"
    monkeypatch.setenv("MONITORING_ALERTS_DB", str(db_file))
    monkeypatch.setenv("MONITORING_ENABLED", "true")
    wl_file = tmp_path / "watchlists.json"
    wl_file.write_text(json.dumps({"watchlists": []}), encoding="utf-8")
    monkeypatch.setenv("MONITORING_WATCHLISTS_FILE", str(wl_file))

    _reset_topic_monitoring_service()
    svc = get_topic_monitoring_service()
    svc.reload()

    rule = WatchlistRule(rule_id="shared-rule", pattern="alert", category="custom", severity="warning")
    wl1 = Watchlist(
        name="Streaming WL One",
        description="First watchlist",
        enabled=True,
        scope_type="user",
        scope_id="u1",
        rules=[rule],
    )
    wl2 = Watchlist(
        name="Streaming WL Two",
        description="Second watchlist",
        enabled=True,
        scope_type="user",
        scope_id="u1",
        rules=[rule],
    )
    svc.upsert_watchlist(wl1)
    svc.upsert_watchlist(wl2)

    created = svc.evaluate_and_alert(
        user_id="u1",
        text="alert me please",
        source="chat.output",
        source_id="stream-1",
        chunk_id="stream-1:1",
        chunk_seq=1,
    )

    assert created == 2

    db = TopicMonitoringDB(db_path=str(db_file))
    items = db.list_alerts(user_id="u1")
    assert len(items) == 2


def test_topic_monitoring_allows_duplicate_rule_ids_across_watchlists(tmp_path, monkeypatch):
    db_file = tmp_path / "alerts.db"
    monkeypatch.setenv("MONITORING_ALERTS_DB", str(db_file))
    monkeypatch.setenv("MONITORING_ENABLED", "true")
    wl_file = tmp_path / "watchlists.json"
    wl_file.write_text(json.dumps({"watchlists": []}), encoding="utf-8")
    monkeypatch.setenv("MONITORING_WATCHLISTS_FILE", str(wl_file))

    _reset_topic_monitoring_service()
    svc = get_topic_monitoring_service()
    svc.reload()

    rule = WatchlistRule(pattern="shared", category="custom", severity="warning")
    wl1 = Watchlist(
        name="WL One",
        description="First watchlist",
        enabled=True,
        scope_type="user",
        scope_id="u1",
        rules=[rule],
    )
    wl2 = Watchlist(
        name="WL Two",
        description="Second watchlist",
        enabled=True,
        scope_type="user",
        scope_id="u2",
        rules=[rule],
    )

    svc.upsert_watchlist(wl1)
    svc.upsert_watchlist(wl2)

    db = TopicMonitoringDB(db_path=str(db_file))
    watchlists = db.list_watchlists(include_rules=True)
    by_name = {wl.get("name"): wl for wl in watchlists}
    rule_id_1 = by_name["WL One"]["rules"][0]["rule_id"]
    rule_id_2 = by_name["WL Two"]["rules"][0]["rule_id"]
    assert rule_id_1 == rule_id_2


def test_topic_monitoring_global_watchlist_without_user_id(tmp_path, monkeypatch):
    db_file = tmp_path / "alerts.db"
    monkeypatch.setenv("MONITORING_ALERTS_DB", str(db_file))
    monkeypatch.setenv("MONITORING_ENABLED", "true")
    wl_file = tmp_path / "watchlists.json"
    wl_file.write_text(json.dumps({"watchlists": []}), encoding="utf-8")
    monkeypatch.setenv("MONITORING_WATCHLISTS_FILE", str(wl_file))

    _reset_topic_monitoring_service()
    svc = get_topic_monitoring_service()
    svc.reload()

    wl = Watchlist(
        name="Global WL",
        description="Global watchlist",
        enabled=True,
        scope_type="global",
        scope_id=None,
        rules=[WatchlistRule(pattern="needle", category="custom", severity="warning")],
    )
    svc.upsert_watchlist(wl)

    created = svc.evaluate_and_alert(user_id=None, text="find the needle here", source="ingestion")
    assert created >= 1

    db = TopicMonitoringDB(db_path=str(db_file))
    items = db.list_alerts(scope_type="global")
    assert len(items) >= 1
    assert items[0].get("user_id") is None


def test_topic_monitoring_global_dedupe(tmp_path, monkeypatch):
    db_file = tmp_path / "alerts.db"
    monkeypatch.setenv("MONITORING_ALERTS_DB", str(db_file))
    monkeypatch.setenv("MONITORING_ENABLED", "true")
    wl_file = tmp_path / "watchlists.json"
    wl_file.write_text(json.dumps({"watchlists": []}), encoding="utf-8")
    monkeypatch.setenv("MONITORING_WATCHLISTS_FILE", str(wl_file))

    _reset_topic_monitoring_service()
    svc = get_topic_monitoring_service()
    svc.reload()

    wl = Watchlist(
        name="Global WL Dedupe",
        description="Global watchlist",
        enabled=True,
        scope_type="global",
        scope_id=None,
        rules=[WatchlistRule(pattern="needle", category="custom", severity="warning")],
    )
    svc.upsert_watchlist(wl)

    created1 = svc.evaluate_and_alert(user_id=None, text="needle here", source="ingestion")
    created2 = svc.evaluate_and_alert(user_id=None, text="needle here", source="ingestion")

    assert created1 == 1
    assert created2 == 0


def test_list_alerts_without_user_id_returns_all(tmp_path: Path) -> None:
    db_file = tmp_path / "alerts.db"
    db = TopicMonitoringDB(db_path=str(db_file))
    db.insert_alert(
        TopicAlert(
            user_id=None,
            scope_type="global",
            scope_id=None,
            source="ingestion",
            watchlist_id="w1",
            rule_category="test",
            rule_severity="warning",
            pattern="needle",
            text_snippet="needle",
        )
    )
    db.insert_alert(
        TopicAlert(
            user_id="u1",
            scope_type="user",
            scope_id="u1",
            source="chat.input",
            watchlist_id="w2",
            rule_category="test",
            rule_severity="warning",
            pattern="badword",
            text_snippet="badword",
        )
    )

    all_items = db.list_alerts()
    assert len(all_items) == 2

    user_items = db.list_alerts(user_id="u1")
    assert len(user_items) == 1
    assert user_items[0].get("user_id") == "u1"


def test_topic_monitoring_reload_updates_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db1 = tmp_path / "db1" / "alerts.db"
    wl1 = tmp_path / "wl1" / "watchlists.json"
    wl1.parent.mkdir(parents=True, exist_ok=True)
    wl1.write_text(json.dumps({"watchlists": []}), encoding="utf-8")
    monkeypatch.setenv("MONITORING_ALERTS_DB", str(db1))
    monkeypatch.setenv("MONITORING_WATCHLISTS_FILE", str(wl1))
    monkeypatch.setenv("MONITORING_ENABLED", "true")

    _reset_topic_monitoring_service()
    svc = get_topic_monitoring_service()

    db2 = tmp_path / "db2" / "alerts.db"
    wl2 = tmp_path / "wl2" / "watchlists.json"
    wl2.parent.mkdir(parents=True, exist_ok=True)
    wl2.write_text(json.dumps({"watchlists": []}), encoding="utf-8")
    monkeypatch.setenv("MONITORING_ALERTS_DB", str(db2))
    monkeypatch.setenv("MONITORING_WATCHLISTS_FILE", str(wl2))

    svc.reload()

    assert Path(svc._db_path) == db2
    assert Path(svc._watchlists_path) == wl2

    wl = Watchlist(
        name="Reload WL",
        description="Reload target",
        enabled=True,
        scope_type="user",
        scope_id="u1",
        rules=[WatchlistRule(pattern="reload", category="custom", severity="warning")],
    )
    svc.upsert_watchlist(wl)
    created = svc.evaluate_and_alert(user_id="u1", text="reload", source="chat.input")
    assert created == 1

    db = TopicMonitoringDB(db_path=str(db2))
    items = db.list_alerts(user_id="u1")
    assert len(items) == 1


def test_topic_monitoring_dedupe_prunes_stale_streams(tmp_path, monkeypatch):
    import tldw_Server_API.app.core.Monitoring.topic_monitoring_service as tms

    db_file = tmp_path / "alerts.db"
    monkeypatch.setenv("MONITORING_ALERTS_DB", str(db_file))
    monkeypatch.setenv("MONITORING_ENABLED", "true")
    monkeypatch.setenv("TOPIC_MONITOR_DEDUP_SECONDS", "1")
    wl_file = tmp_path / "watchlists.json"
    wl_file.write_text(json.dumps({"watchlists": []}), encoding="utf-8")
    monkeypatch.setenv("MONITORING_WATCHLISTS_FILE", str(wl_file))

    _reset_topic_monitoring_service()
    svc = get_topic_monitoring_service()
    svc.reload()

    monkeypatch.setattr(tms.time, "monotonic", lambda: 0.0)
    svc._dedupe_should_skip(stream_id="s1", rule_id="r1", text="alpha")
    assert "s1" in svc._dedupe_state

    monkeypatch.setattr(tms.time, "monotonic", lambda: 2.0)
    svc._dedupe_should_skip(stream_id="s2", rule_id="r1", text="beta")
    assert "s1" not in svc._dedupe_state
