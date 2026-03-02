from __future__ import annotations

from tldw_Server_API.app.core.Moderation.conflict_resolution import resolve_conflicts


def test_strictest_wins_for_shared_dependent() -> None:
    merged = resolve_conflicts(
        [
            {"id": "p1", "action": "warn", "severity": "warning"},
            {"id": "p2", "action": "block", "severity": "warning"},
        ]
    )
    assert merged is not None
    assert merged["action"] == "block"
    assert merged["id"] == "p2"


def test_tie_breaks_on_severity_then_id() -> None:
    merged = resolve_conflicts(
        [
            {"id": "b", "action": "warn", "severity": "warning"},
            {"id": "a", "action": "warn", "severity": "critical"},
        ]
    )
    assert merged is not None
    assert merged["severity"] == "critical"
    assert merged["id"] == "a"


def test_empty_conflict_set_returns_none() -> None:
    assert resolve_conflicts([]) is None
