# tldw_Server_API/tests/kanban/test_kanban_deps_rate_limit.py
"""
Unit tests for Kanban dependency helpers.

Focused on:
- In-memory rate limiting behavior and cleanup
- Closing cached KanbanDB instances on shutdown
"""

from collections import deque

import pytest
from cachetools import LRUCache

from tldw_Server_API.app.api.v1.API_Deps import kanban_deps


@pytest.fixture(autouse=True)
def _reset_rate_limit_state(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(kanban_deps, "_rate_limit_windows", {})
    monkeypatch.setattr(kanban_deps, "_rate_limit_last_cleanup_ts", 0.0)
    monkeypatch.setattr(kanban_deps, "_RATE_LIMIT_CLEANUP_INTERVAL_SECONDS", 0.0)
    yield


class TestKanbanRateLimiting:
    def test_blocks_after_limit(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setitem(kanban_deps.KANBAN_RATE_LIMITS, "test.action", 2)
        monkeypatch.setattr(kanban_deps.time, "time", lambda: 1000.0)

        allowed, _ = kanban_deps.check_kanban_rate_limit(user_id=1, action="test.action")
        assert allowed is True

        allowed, _ = kanban_deps.check_kanban_rate_limit(user_id=1, action="test.action")
        assert allowed is True

        allowed, info = kanban_deps.check_kanban_rate_limit(user_id=1, action="test.action")
        assert allowed is False
        assert info["limit"] == 2

    def test_resets_after_window(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setitem(kanban_deps.KANBAN_RATE_LIMITS, "test.action", 1)

        monkeypatch.setattr(kanban_deps.time, "time", lambda: 1000.0)
        allowed, _ = kanban_deps.check_kanban_rate_limit(user_id=1, action="test.action")
        assert allowed is True

        allowed, _ = kanban_deps.check_kanban_rate_limit(user_id=1, action="test.action")
        assert allowed is False

        monkeypatch.setattr(kanban_deps.time, "time", lambda: 1061.0)
        allowed, _ = kanban_deps.check_kanban_rate_limit(user_id=1, action="test.action")
        assert allowed is True

    def test_cleanup_removes_stale_keys(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(kanban_deps.time, "time", lambda: 1000.0)

        with kanban_deps._rate_limit_lock:
            kanban_deps._rate_limit_windows["stale:action"] = deque([0.0])

        allowed, _ = kanban_deps.check_kanban_rate_limit(user_id=1, action="test.action")
        assert allowed is True
        assert "stale:action" not in kanban_deps._rate_limit_windows


class TestKanbanDbCacheShutdown:
    def test_close_all_kanban_db_instances_calls_close(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(kanban_deps, "_kanban_db_instances", LRUCache(maxsize=10))
        monkeypatch.setattr(kanban_deps, "_kanban_db_health_checks", {})

        class DummyDB:
            def __init__(self) -> None:
                self.closed = False

            def close(self) -> None:
                self.closed = True

        dummy = DummyDB()

        with kanban_deps._kanban_db_lock:
            kanban_deps._kanban_db_instances["kanban::1"] = dummy
            kanban_deps._kanban_db_health_checks["kanban::1"] = 123.0

        kanban_deps.close_all_kanban_db_instances()
        assert dummy.closed is True
        assert len(kanban_deps._kanban_db_instances) == 0
        assert kanban_deps._kanban_db_health_checks == {}
