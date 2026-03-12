from __future__ import annotations

from tldw_Server_API.app.services.admin_monitoring_alerts_service import (
    build_alert_identity,
    merge_runtime_alert_with_overlay,
)


def test_build_alert_identity_prefers_existing_runtime_alert_id() -> None:
    raw_alert = {
        "id": 7,
        "source": "watchlist",
        "text_snippet": "CPU high",
        "created_at": "2026-03-10T10:00:00Z",
    }

    assert build_alert_identity(raw_alert) == "alert:7"


def test_build_alert_identity_falls_back_to_deterministic_fingerprint() -> None:
    raw_alert = {
        "source": "watchlist",
        "watchlist_id": "wl-1",
        "rule_id": "rule-7",
        "source_id": "src-1",
        "chunk_id": "chunk-9",
        "chunk_seq": 2,
        "text_snippet": "CPU high",
        "created_at": "2026-03-10T10:00:00Z",
    }

    first = build_alert_identity(raw_alert)
    second = build_alert_identity(dict(raw_alert))

    assert first == second
    assert first.startswith("fingerprint:")


def test_merge_runtime_alert_with_overlay_applies_assignment_snooze_and_escalation() -> None:
    raw_alert = {
        "id": 7,
        "created_at": "2026-03-10T10:00:00Z",
        "source": "watchlist",
        "rule_severity": "warning",
        "text_snippet": "CPU high",
        "is_read": 0,
        "read_at": None,
    }
    overlay = {
        "alert_identity": "alert:7",
        "assigned_to_user_id": 12,
        "snoozed_until": "2026-03-10T11:00:00Z",
        "escalated_severity": "critical",
        "acknowledged_at": "2026-03-10T10:05:00Z",
    }

    merged = merge_runtime_alert_with_overlay(raw_alert, overlay)

    assert merged["alert_identity"] == "alert:7"
    assert merged["assigned_to_user_id"] == 12
    assert merged["snoozed_until"] == "2026-03-10T11:00:00Z"
    assert merged["escalated_severity"] == "critical"
    assert merged["acknowledged_at"] == "2026-03-10T10:05:00Z"
    assert merged["is_read"] is True


def test_merge_runtime_alert_with_overlay_preserves_dismissed_alert_state() -> None:
    raw_alert = {
        "id": 8,
        "created_at": "2026-03-10T10:00:00Z",
        "source": "watchlist",
        "rule_severity": "warning",
        "text_snippet": "Disk high",
        "is_read": 1,
        "read_at": "2026-03-10T10:01:00Z",
    }
    overlay = {
        "alert_identity": "alert:8",
        "dismissed_at": "2026-03-10T10:10:00Z",
    }

    merged = merge_runtime_alert_with_overlay(raw_alert, overlay)

    assert merged["alert_identity"] == "alert:8"
    assert merged["dismissed_at"] == "2026-03-10T10:10:00Z"
    assert merged["read_at"] == "2026-03-10T10:01:00Z"
    assert merged["is_read"] is True
