from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
import os

from tldw_Server_API.app.core.AuthNZ.repos.token_blacklist_repo import (
    AuthnzTokenBlacklistRepo,
)
from tldw_Server_API.app.core.AuthNZ.database import DatabasePool
from tldw_Server_API.app.core.AuthNZ.settings import Settings


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_authnz_token_blacklist_repo_postgres(isolated_test_environment):
    """AuthnzTokenBlacklistRepo helpers should work on Postgres."""
    # Use the per-test Postgres database created by isolated_test_environment
    _client, _db_name = isolated_test_environment  # client/db name not needed directly here

    database_url = os.getenv("DATABASE_URL")
    assert database_url, "DATABASE_URL must be set by isolated_test_environment fixture"

    test_settings = Settings(
        AUTH_MODE="multi_user",
        DATABASE_URL=database_url,
        JWT_SECRET_KEY=os.getenv("JWT_SECRET_KEY", "test-secret-key-for-testing-only"),
        ENABLE_REGISTRATION=True,
        REQUIRE_REGISTRATION_CODE=False,
        RATE_LIMIT_ENABLED=False,
    )

    pool = DatabasePool(test_settings)
    await pool.initialize()

    repo = AuthnzTokenBlacklistRepo(pool)

    now = datetime.now(timezone.utc).replace(microsecond=0)
    future = now + timedelta(hours=2)

    # Insert a blacklisted token
    await repo.insert_blacklisted_token(
        jti="pg-test-jti",
        user_id=None,
        token_type="refresh",
        expires_at=future,
        reason="integration-test",
        revoked_by=None,
        ip_address=None,
    )

    # Active expiry lookup should find it
    expiry = await repo.get_active_expiry_for_jti("pg-test-jti", now=now)
    assert expiry is not None

    # Global stats should see at least one token
    stats = await repo.get_blacklist_stats(now=now, user_id=None)
    assert stats["total"] >= 1
    assert stats["refresh_tokens"] >= 1

    # Cleanup with past cutoff should keep it
    deleted_none = await repo.cleanup_expired(now=now - timedelta(hours=1))
    assert deleted_none == 0

    # Cleanup with future cutoff should be able to delete it
    deleted_some = await repo.cleanup_expired(now=now + timedelta(days=1))
    assert deleted_some >= 1
