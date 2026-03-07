import pytest

from tldw_Server_API.app.core.Text2SQL.sql_guard import SqlGuard, SqlPolicyViolation


def test_guard_accepts_select_and_injects_limit() -> None:
    guard = SqlGuard(default_limit=100, max_limit=500)
    out = guard.validate_and_rewrite("SELECT id FROM media")
    assert "LIMIT 100" in out.sql.upper()
    assert out.limit_injected is True
    assert out.limit_clamped is False


def test_guard_rejects_multi_statement() -> None:
    guard = SqlGuard(default_limit=100, max_limit=500)
    with pytest.raises(SqlPolicyViolation):
        guard.validate_and_rewrite("SELECT 1; SELECT 2")


def test_guard_rejects_write_statement() -> None:
    guard = SqlGuard(default_limit=100, max_limit=500)
    with pytest.raises(SqlPolicyViolation):
        guard.validate_and_rewrite("DELETE FROM media")


def test_guard_clamps_limit_to_max() -> None:
    guard = SqlGuard(default_limit=100, max_limit=500)
    out = guard.validate_and_rewrite("SELECT id FROM media LIMIT 1000")
    assert "LIMIT 500" in out.sql.upper()
    assert out.limit_injected is False
    assert out.limit_clamped is True


def test_guard_rejects_non_literal_limit() -> None:
    guard = SqlGuard(default_limit=100, max_limit=500)
    with pytest.raises(SqlPolicyViolation):
        guard.validate_and_rewrite("SELECT id FROM media LIMIT @limit")
