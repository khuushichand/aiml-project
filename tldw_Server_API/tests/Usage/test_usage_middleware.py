from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


def _ensure_usage_middleware():
    """Re-register usage logging middleware when TEST_MODE stripped it."""
    from tldw_Server_API.app.core.AuthNZ.usage_logging_middleware import UsageLoggingMiddleware

    if not any(getattr(m, "cls", None) is UsageLoggingMiddleware for m in getattr(app, "user_middleware", [])):
        app.add_middleware(UsageLoggingMiddleware)
        # Starlette requires rebuilding the stack after manual mutation
        app.middleware_stack = app.build_middleware_stack()


async def _ensure_usage_tables():
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool

    pool = await get_db_pool()
    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS usage_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER,
            key_id INTEGER,
            endpoint TEXT,
            status INTEGER,
            latency_ms INTEGER,
            bytes INTEGER,
            bytes_in INTEGER,
            meta TEXT,
            request_id TEXT
        )
        """
    )
    usage_log_cols = {row["name"] for row in await pool.fetchall("PRAGMA table_info(usage_log)")}
    if "bytes_in" not in usage_log_cols:
        await pool.execute("ALTER TABLE usage_log ADD COLUMN bytes_in INTEGER")
    if "request_id" not in usage_log_cols:
        await pool.execute("ALTER TABLE usage_log ADD COLUMN request_id TEXT")


async def _count_usage_rows():
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool

    pool = await get_db_pool()
    val = await pool.fetchval("SELECT COUNT(*) FROM usage_log")
    return int(val or 0)


@pytest.mark.asyncio
async def test_middleware_logs_usage(monkeypatch):
    # Configure single-user + enable usage logging
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("SINGLE_USER_API_KEY", "middleware-test-key")
    monkeypatch.setenv("USAGE_LOG_ENABLED", "true")
    # Keep exclusions default; /api/v1/health is not excluded by default

    # Reset settings/db/session
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool
    from tldw_Server_API.app.core.AuthNZ.session_manager import reset_session_manager

    reset_settings()
    await reset_db_pool()
    await reset_session_manager()

    headers = {"X-API-KEY": "middleware-test-key"}
    _ensure_usage_middleware()

    with TestClient(app, headers=headers) as client:
        await _ensure_usage_tables()
        before = await _count_usage_rows()

        # Hit a lightweight endpoint that is not excluded
        r = client.get("/api/v1/health/ready")
        assert r.status_code in (200, 503)

        after = await _count_usage_rows()
        assert after == before + 1


@pytest.mark.asyncio
async def test_middleware_excludes_prefix(monkeypatch):
    # Configure single-user + enable usage logging + exclude health prefix
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("SINGLE_USER_API_KEY", "middleware-test-key")
    monkeypatch.setenv("USAGE_LOG_ENABLED", "true")
    monkeypatch.setenv("USAGE_LOG_EXCLUDE_PREFIXES", "[\"/api/v1/health\"]")
    # Ensure exclusion even if middleware cached settings from previous test
    from tldw_Server_API.app.core.AuthNZ import usage_logging_middleware as ulm
    monkeypatch.setattr(ulm.UsageLoggingMiddleware, "_is_excluded", lambda self, p: p.startswith("/api/v1/health"))

    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool
    from tldw_Server_API.app.core.AuthNZ.session_manager import reset_session_manager

    reset_settings()
    await reset_db_pool()
    await reset_session_manager()

    headers = {"X-API-KEY": "middleware-test-key"}
    _ensure_usage_middleware()

    with TestClient(app, headers=headers) as client:
        await _ensure_usage_tables()
        before = await _count_usage_rows()

        r = client.get("/api/v1/health/ready")
        assert r.status_code in (200, 503)

        after = await _count_usage_rows()
        # No change due to exclusion
        assert after == before
