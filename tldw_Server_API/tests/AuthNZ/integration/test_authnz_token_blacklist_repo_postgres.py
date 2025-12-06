from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from tldw_Server_API.app.core.AuthNZ.repos.token_blacklist_repo import (
    AuthnzTokenBlacklistRepo,
)
from tldw_Server_API.app.core.AuthNZ.token_blacklist import TokenBlacklist


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_authnz_token_blacklist_repo_postgres(test_db_pool):
    """AuthnzTokenBlacklistRepo helpers should work on Postgres."""
    pool = test_db_pool

    # Ensure token_blacklist table exists in the shared Postgres test DB.
    # Use the real TokenBlacklist service bootstrap against this pool.
    service = TokenBlacklist(db_pool=pool)
    await service.initialize()

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
