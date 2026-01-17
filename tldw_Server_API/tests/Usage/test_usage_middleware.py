from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from tldw_Server_API.app.core.AuthNZ.principal_model import AuthContext, AuthPrincipal


def _build_usage_test_app() -> FastAPI:
    """Build a minimal app with usage logging middleware for tests."""
    from tldw_Server_API.app.core.AuthNZ.usage_logging_middleware import UsageLoggingMiddleware

    app_local = FastAPI()

    @app_local.get("/api/v1/health/ready")
    def _ready():
        return {"ok": True}

    app_local.add_middleware(UsageLoggingMiddleware)
    return app_local


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


async def _latest_usage_row():
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool

    pool = await get_db_pool()
    return await pool.fetchrow(
        "SELECT user_id, key_id FROM usage_log ORDER BY id DESC LIMIT 1"
    )


class _PrincipalInjectorMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, principal: AuthPrincipal, override_user_id: int, override_key_id: int | None):
        super().__init__(app)
        self._principal = principal
        self._override_user_id = override_user_id
        self._override_key_id = override_key_id

    async def dispatch(self, request, call_next):
        request.state.user_id = self._override_user_id
        request.state.api_key_id = self._override_key_id
        request.state.auth = AuthContext(
            principal=self._principal,
            ip="127.0.0.1",
            user_agent="pytest-agent",
            request_id="usage-mw-test",
        )
        return await call_next(request)


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
    app_local = _build_usage_test_app()

    with TestClient(app_local, headers=headers) as client:
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
    app_local = _build_usage_test_app()

    with TestClient(app_local, headers=headers) as client:
        await _ensure_usage_tables()
        before = await _count_usage_rows()

        r = client.get("/api/v1/health/ready")
        assert r.status_code in (200, 503)

        after = await _count_usage_rows()
        # No change due to exclusion
        assert after == before


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "auth_mode, principal_kind, principal_user_id, principal_key_id",
    [
        ("single_user", "user", 101, None),
        ("multi_user", "api_key", 202, 303),
    ],
)
async def test_usage_logging_prefers_auth_principal_ids(
    tmp_path,
    monkeypatch,
    auth_mode,
    principal_kind,
    principal_user_id,
    principal_key_id,
):
    monkeypatch.setenv("AUTH_MODE", auth_mode)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / f'usage_{auth_mode}.db'}")
    monkeypatch.setenv("USAGE_LOG_ENABLED", "true")

    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool
    from tldw_Server_API.app.core.AuthNZ.usage_logging_middleware import UsageLoggingMiddleware

    reset_settings()
    await reset_db_pool()

    app_local = FastAPI()

    @app_local.get("/ping")
    def _ping():
        return {"ok": True}

    app_local.add_middleware(UsageLoggingMiddleware)
    principal = AuthPrincipal(
        kind=principal_kind,
        user_id=principal_user_id,
        api_key_id=principal_key_id,
        subject="usage-test",
        token_type="api_key",
        jti=None,
        roles=[],
        permissions=[],
        is_admin=False,
        org_ids=[],
        team_ids=[],
    )
    app_local.add_middleware(
        _PrincipalInjectorMiddleware,
        principal=principal,
        override_user_id=999,
        override_key_id=888,
    )

    await _ensure_usage_tables()

    with TestClient(app_local) as client:
        resp = client.get("/ping")
        assert resp.status_code == 200

    row = await _latest_usage_row()
    assert row["user_id"] == principal_user_id
    assert row["key_id"] == principal_key_id
