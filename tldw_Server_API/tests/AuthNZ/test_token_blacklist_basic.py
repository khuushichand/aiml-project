import asyncio
from datetime import datetime, timedelta
import pytest

from tldw_Server_API.app.core.AuthNZ.token_blacklist import get_token_blacklist, reset_token_blacklist
from tldw_Server_API.app.core.AuthNZ.settings import reset_settings


@pytest.mark.asyncio
async def test_blacklist_revoke_and_check_no_redis(monkeypatch):
    # Force local SQLite to avoid leftover Postgres env from other tests
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./Databases/users.db")
    reset_settings()
    await reset_token_blacklist()
    bl = get_token_blacklist()
    await bl.initialize()

    jti = "test-jti-1"
    ok = await bl.revoke_token(jti=jti, expires_at=datetime.utcnow() + timedelta(hours=1), user_id=1)
    assert ok is True
    assert await bl.is_blacklisted(jti) is True


@pytest.mark.asyncio
async def test_blacklist_handles_redis_unavailable(monkeypatch):
    # Force local SQLite and a bad Redis URL to exercise fallback
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./Databases/users.db")
    reset_settings()
    monkeypatch.setenv("REDIS_URL", "redis://localhost:1/0")
    await reset_token_blacklist()
    bl = get_token_blacklist()
    await bl.initialize()

    jti = "test-jti-2"
    ok = await bl.revoke_token(jti=jti, expires_at=datetime.utcnow() + timedelta(hours=1), user_id=1)
    assert ok is True
    assert await bl.is_blacklisted(jti) is True
