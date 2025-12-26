import os
import pytest

from tldw_Server_API.app.core.AuthNZ.settings import Settings
from tldw_Server_API.app.core.AuthNZ.database import DatabasePool
from tldw_Server_API.app.core.AuthNZ.rate_limiter import RateLimiter
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.api.v1.endpoints import admin as admin_module
from tldw_Server_API.app.api.v1.schemas.admin_schemas import RateLimitResetRequest


@pytest.mark.asyncio
async def test_admin_reset_specific_endpoint_sqlite(tmp_path, monkeypatch):
    # Ensure multi_user mode with SQLite DB
    db_file = tmp_path / "rate_admin.db"
    settings = Settings(
        AUTH_MODE="multi_user",
        JWT_SECRET_KEY="k" * 64,
        DATABASE_URL=f"sqlite:///{db_file}",
        RATE_LIMIT_ENABLED=True,
    )
    db_pool = DatabasePool(settings)
    await db_pool.initialize()

    limiter = RateLimiter(settings=settings, db_pool=db_pool)
    await limiter.initialize()
    limiter.redis_client = None

    # Insert one request for ip:1.2.3.4 at endpoint /api/test
    ident = "ip:1.2.3.4"
    endpoint = "/api/test"
    ok, _ = await limiter.check_rate_limit(ident, endpoint, limit=5, burst=0, window_minutes=1)
    assert ok is True

    # Monkeypatch admin to use our pool/limiter
    async def _fake_get_authnz_rate_limiter():
        return limiter
    monkeypatch.setattr(admin_module, "get_authnz_rate_limiter", _fake_get_authnz_rate_limiter, raising=False)
    async def _fake_get_db_pool():
        return db_pool
    monkeypatch.setattr(admin_module, "get_db_pool", _fake_get_db_pool, raising=False)
    async def _fake_is_pg():
        return False
    monkeypatch.setattr(admin_module, "is_postgres_backend", _fake_is_pg, raising=False)

    # Call endpoint: specific endpoint reset
    req = RateLimitResetRequest(kind="ip", ip="1.2.3.4", endpoint=endpoint)
    principal = AuthPrincipal(
        kind="user",
        user_id=1,
        api_key_id=None,
        subject=None,
        token_type="access",
        jti=None,
        roles=["owner"],
        permissions=["system.configure"],
        is_admin=True,
        org_ids=[],
        team_ids=[],
    )
    resp = await admin_module.admin_reset_rate_limit(req, principal=principal)
    assert resp.ok is True
    assert resp.identifier == ident
    assert resp.endpoint == endpoint
    # Note: db_rows_deleted >= 1 because check_rate_limit creates rate limit records
    assert resp.db_rows_deleted >= 1
    assert resp.redis_keys_deleted == 0

    # Verify DB rows removed
    # Subsequent count should be 0
    rows_remaining = await db_pool.fetchval(
        "SELECT COUNT(*) FROM rate_limits WHERE identifier = ? AND endpoint = ?",
        ident, endpoint,
    )
    assert int(rows_remaining or 0) == 0

    await db_pool.close()


@pytest.mark.asyncio
async def test_admin_reset_all_endpoints_sqlite(tmp_path, monkeypatch):
    db_file = tmp_path / "rate_admin_all.db"
    settings = Settings(
        AUTH_MODE="multi_user",
        JWT_SECRET_KEY="k" * 64,
        DATABASE_URL=f"sqlite:///{db_file}",
        RATE_LIMIT_ENABLED=True,
    )
    db_pool = DatabasePool(settings)
    await db_pool.initialize()

    limiter = RateLimiter(settings=settings, db_pool=db_pool)
    await limiter.initialize()
    limiter.redis_client = None

    ident = "user:999"
    ep1 = "/api/one"
    ep2 = "/api/two"
    ok1, _ = await limiter.check_rate_limit(ident, ep1, limit=5, burst=0, window_minutes=1)
    ok2, _ = await limiter.check_rate_limit(ident, ep2, limit=5, burst=0, window_minutes=1)
    assert ok1 and ok2

    # Monkeypatch admin module
    async def _fake_get_authnz_rate_limiter2():
        return limiter
    monkeypatch.setattr(admin_module, "get_authnz_rate_limiter", _fake_get_authnz_rate_limiter2, raising=False)
    async def _fake_get_db_pool():
        return db_pool
    monkeypatch.setattr(admin_module, "get_db_pool", _fake_get_db_pool, raising=False)
    async def _fake_is_pg2():
        return False
    monkeypatch.setattr(admin_module, "is_postgres_backend", _fake_is_pg2, raising=False)

    req = RateLimitResetRequest(kind="raw", identifier=ident)
    principal = AuthPrincipal(
        kind="user",
        user_id=1,
        api_key_id=None,
        subject=None,
        token_type="access",
        jti=None,
        roles=["owner"],
        permissions=["system.configure"],
        is_admin=True,
        org_ids=[],
        team_ids=[],
    )
    resp = await admin_module.admin_reset_rate_limit(req, principal=principal)
    assert resp.ok is True
    assert resp.identifier == ident
    assert resp.endpoint is None
    # Note: db_rows_deleted >= 2 because check_rate_limit creates records for both endpoints
    assert resp.db_rows_deleted >= 2
    assert resp.redis_keys_deleted == 0

    # Verify no rows remain for this identifier
    rows_remaining = await db_pool.fetchval(
        "SELECT COUNT(*) FROM rate_limits WHERE identifier = ?",
        ident,
    )
    assert int(rows_remaining or 0) == 0

    await db_pool.close()


@pytest.mark.asyncio
async def test_admin_reset_dry_run_sqlite(tmp_path, monkeypatch):
    db_file = tmp_path / "rate_admin_dryrun.db"
    settings = Settings(
        AUTH_MODE="multi_user",
        JWT_SECRET_KEY="k" * 64,
        DATABASE_URL=f"sqlite:///{db_file}",
        RATE_LIMIT_ENABLED=True,
    )
    db_pool = DatabasePool(settings)
    await db_pool.initialize()

    limiter = RateLimiter(settings=settings, db_pool=db_pool)
    await limiter.initialize()
    limiter.redis_client = None

    ident = "user:777"
    ep = "/api/dry"
    ok, _ = await limiter.check_rate_limit(ident, ep, limit=5, burst=0, window_minutes=1)
    assert ok

    # Monkeypatch admin module services
    async def _fake_get_authnz_rate_limiter():
        return limiter
    monkeypatch.setattr(admin_module, "get_authnz_rate_limiter", _fake_get_authnz_rate_limiter, raising=False)
    async def _fake_get_db_pool():
        return db_pool
    monkeypatch.setattr(admin_module, "get_db_pool", _fake_get_db_pool, raising=False)
    async def _fake_is_pg():
        return False
    monkeypatch.setattr(admin_module, "is_postgres_backend", _fake_is_pg, raising=False)

    # Call with dry_run; ensure rows remain, counts reported
    req = RateLimitResetRequest(kind="raw", identifier=ident, dry_run=True)
    principal = AuthPrincipal(
        kind="user",
        user_id=1,
        api_key_id=None,
        subject=None,
        token_type="access",
        jti=None,
        roles=["owner"],
        permissions=["system.configure"],
        is_admin=True,
        org_ids=[],
        team_ids=[],
    )
    resp = await admin_module.admin_reset_rate_limit(req, principal=principal)
    assert resp.ok is True
    assert resp.note and "dry_run" in resp.note
    # dry_run reports what WOULD be deleted (1 record since rate limiter now creates records)
    assert resp.db_rows_deleted >= 1
    # Verify rows still exist (dry_run doesn't actually delete)
    rows_remaining = await db_pool.fetchval(
        "SELECT COUNT(*) FROM rate_limits WHERE identifier = ?",
        ident,
    )
    assert int(rows_remaining or 0) >= 1

    await db_pool.close()
