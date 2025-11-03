import os
from datetime import datetime, timezone, timedelta

import pytest

from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool, get_db_pool
from tldw_Server_API.app.core.Resource_Governance.authnz_policy_store import AuthNZPolicyStore
from tldw_Server_API.app.core.Resource_Governance.seed_helpers import seed_rg_policies_sqlite


@pytest.mark.asyncio
async def test_authnz_policy_store_sqlite(tmp_path, monkeypatch):
    # Configure AuthNZ to use a temporary SQLite DB
    db_path = tmp_path / "users_test.db"
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    await reset_db_pool()
    pool = await get_db_pool()

    # Seed policies
    now = datetime.now(timezone.utc)
    await seed_rg_policies_sqlite(
        pool,
        [
            {
                "id": "chat.default",
                "payload": {"requests": {"rpm": 120, "burst": 2.0}},
                "version": 2,
                "updated_at": now,
            },
            {
                "id": "mcp.ingestion",
                "payload": {"requests": {"rpm": 60, "burst": 1.0}},
                "version": 1,
                "updated_at": now - timedelta(minutes=5),
            },
            {
                "id": "tenant",
                "payload": {"enabled": True, "header": "X-TLDW-Tenant", "jwt_claim": "tenant_id"},
                "version": 1,
                "updated_at": now - timedelta(minutes=10),
            },
        ],
    )

    store = AuthNZPolicyStore()
    version, policies, tenant, updated_at = await store.get_latest_policy()

    # Validate snapshot
    assert isinstance(version, int)
    assert version >= 2
    assert "chat.default" in policies
    assert policies["chat.default"]["requests"]["rpm"] == 120
    assert "mcp.ingestion" in policies
    assert tenant.get("enabled") is True
    # updated_at should be a float epoch seconds
    assert isinstance(updated_at, float)

