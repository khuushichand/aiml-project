from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.AuthNZ import rate_limiter as rate_limiter_module
from tldw_Server_API.app.core.AuthNZ.rate_limiter import RateLimiter


class _ControlledDatetime(rate_limiter_module.datetime):
    current = rate_limiter_module.datetime(2024, 1, 1, 0, 0, 0)

    @classmethod
    def utcnow(cls):
        return cls.current


class _Cursor:
    def __init__(self, rows=None, rowcount=0):
        self._rows = rows or []
        self.rowcount = rowcount

    async def fetchone(self):
        if not self._rows:
            return None
        return self._rows.pop(0)


class _MemoryConn:
    def __init__(self, store):
        self._store = store

    async def execute(self, sql, params=None):
        params = params or ()
        normalized = " ".join(sql.lower().split())

        if normalized.startswith("create table"):
            return _Cursor()

        if "insert into failed_attempts" in normalized:
            identifier, attempt_type, window_start_iso = params[:3]
            lockout_minutes = int(params[3])
            now_iso = params[4]
            now_dt = datetime.fromisoformat(now_iso)
            new_window_iso = params[7]
            key = (identifier, attempt_type)
            current = self._store["failed_attempts"].get(key)
            if (
                current is None
                or current["window_start"] + timedelta(minutes=lockout_minutes) < now_dt
            ):
                attempt_count = 1
                window_start = datetime.fromisoformat(new_window_iso)
            else:
                attempt_count = current["attempt_count"] + 1
                window_start = current["window_start"]
            self._store["failed_attempts"][key] = {
                "attempt_count": attempt_count,
                "window_start": window_start,
            }
            return _Cursor(rowcount=1)

        if normalized.startswith("select attempt_count from failed_attempts"):
            identifier, attempt_type = params
            current = self._store["failed_attempts"].get((identifier, attempt_type))
            if not current:
                return _Cursor()
            return _Cursor(rows=[(current["attempt_count"],)])

        if "insert or replace into account_lockouts" in normalized:
            identifier, locked_until_iso, reason = params
            self._store["account_lockouts"][identifier] = {
                "locked_until": datetime.fromisoformat(locked_until_iso),
                "reason": reason,
            }
            return _Cursor(rowcount=1)

        if normalized.startswith("select locked_until from account_lockouts"):
            identifier, cutoff_iso = params
            cutoff = datetime.fromisoformat(cutoff_iso)
            entry = self._store["account_lockouts"].get(identifier)
            if entry and entry["locked_until"] > cutoff:
                return _Cursor(rows=[(entry["locked_until"].isoformat(),)])
            return _Cursor()

        if normalized.startswith("delete from account_lockouts"):
            identifier, cutoff_iso = params
            cutoff = datetime.fromisoformat(cutoff_iso)
            entry = self._store["account_lockouts"].get(identifier)
            if entry and entry["locked_until"] <= cutoff:
                del self._store["account_lockouts"][identifier]
                return _Cursor(rowcount=1)
            return _Cursor(rowcount=0)

        return _Cursor()

    async def commit(self):
        return


class _ConnContext:
    def __init__(self, store):
        self._conn = _MemoryConn(store)

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _MemoryPool:
    """Minimal pool stub that exercises the SQLite code paths."""

    def __init__(self):
        self.pool = None  # Signal SQLite path
        self._store = {"failed_attempts": {}, "account_lockouts": {}}

    def transaction(self):
        return _ConnContext(self._store)

    def acquire(self):
        return _ConnContext(self._store)


@pytest.mark.asyncio
async def test_lockout_recovers_after_window(monkeypatch):
    original_datetime = rate_limiter_module.datetime
    monkeypatch.setattr(rate_limiter_module, "datetime", _ControlledDatetime)

    pool = _MemoryPool()
    settings = SimpleNamespace(
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_PER_MINUTE=60,
        RATE_LIMIT_BURST=10,
        SERVICE_ACCOUNT_RATE_LIMIT=60,
        REDIS_URL=None,
        MAX_LOGIN_ATTEMPTS=3,
        LOCKOUT_DURATION_MINUTES=5,
        PII_REDACT_LOGS=False,
    )
    limiter = RateLimiter(db_pool=pool, settings=settings)
    await limiter.initialize()

    identifier = "ip:127.0.0.1"

    for _ in range(settings.MAX_LOGIN_ATTEMPTS):
        result = await limiter.record_failed_attempt(identifier, attempt_type="login")

    assert result["is_locked"] is True

    _ControlledDatetime.current = original_datetime(2024, 1, 1, 0, 6, 0)
    is_locked, _ = await limiter.check_lockout(identifier)
    assert is_locked is False

    result_after = await limiter.record_failed_attempt(identifier, attempt_type="login")
    assert result_after["is_locked"] is False
    assert result_after["attempt_count"] == 1
    assert result_after["remaining_attempts"] == settings.MAX_LOGIN_ATTEMPTS - 1
