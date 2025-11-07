import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.tests.AuthNZ.integration.test_rbac_admin_endpoints import _admin_headers


@pytest.mark.asyncio
async def test_policy_admin_upsert_delete_postgres(monkeypatch, isolated_test_environment):
    # Ensure DB policy store is active for this app instance
    monkeypatch.setenv("RG_POLICY_STORE", "db")
    monkeypatch.setenv("RG_POLICY_RELOAD_ENABLED", "false")

    client, db_name = isolated_test_environment
    headers = _admin_headers(client, db_name)

    # Upsert a policy via admin API (requires admin auth)
    policy_id = "pg.test.policy"
    up = client.put(
        f"/api/v1/resource-governor/policy/{policy_id}",
        headers=headers,
        json={"payload": {"requests": {"rpm": 9}}, "version": 1},
    )
    assert up.status_code == 200, up.text

    # Snapshot should include the new policy ID
    snap = client.get("/api/v1/resource-governor/policy?include=ids", headers=headers)
    assert snap.status_code == 200, snap.text
    ids = snap.json().get("policy_ids") or []
    assert policy_id in ids

    # Admin GET returns the policy record
    gp = client.get(f"/api/v1/resource-governor/policy/{policy_id}", headers=headers)
    assert gp.status_code == 200, gp.text
    rec = gp.json()
    assert rec.get("id") == policy_id
    assert (rec.get("payload") or {}).get("requests", {}).get("rpm") == 9

    # Delete and verify removal from snapshot
    de = client.delete(f"/api/v1/resource-governor/policy/{policy_id}", headers=headers)
    assert de.status_code == 200, de.text
    snap2 = client.get("/api/v1/resource-governor/policy?include=ids", headers=headers)
    assert policy_id not in (snap2.json().get("policy_ids") or [])
