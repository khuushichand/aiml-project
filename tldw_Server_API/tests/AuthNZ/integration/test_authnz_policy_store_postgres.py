import pytest
from datetime import datetime, timezone, timedelta

from tldw_Server_API.app.core.Resource_Governance.authnz_policy_store import AuthNZPolicyStore
from tldw_Server_API.app.core.Resource_Governance.seed_helpers import seed_rg_policies_postgres


@pytest.mark.asyncio
async def test_authnz_policy_store_postgres_integration(test_db_pool):
    # Seed two policies including tenant row
    now = datetime.now(timezone.utc)
    await seed_rg_policies_postgres(
        test_db_pool,
        [
            {
                "id": "chat.default",
                "payload": {"requests": {"rpm": 200, "burst": 2.0}},
                "version": 4,
                "updated_at": now,
            },
            {
                "id": "tenant",
                "payload": {"enabled": True, "header": "X-Tenant", "jwt_claim": "tenant"},
                "version": 1,
                "updated_at": now - timedelta(minutes=2),
            },
        ],
    )

    store = AuthNZPolicyStore()
    version, policies, tenant, updated_at = await store.get_latest_policy()

    assert version >= 4
    assert policies.get("chat.default", {}).get("requests", {}).get("rpm") == 200
    assert tenant.get("enabled") is True
    assert isinstance(updated_at, float)
