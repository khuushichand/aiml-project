import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.tests.AuthNZ.integration.test_rbac_admin_endpoints import _admin_headers


@pytest.mark.asyncio
async def test_policy_admin_put_optimistic_concurrency_conflict(monkeypatch, isolated_test_environment):
    """
    Verify that PUT /api/v1/resource-governor/policy/{id} enforces optimistic
    concurrency when an explicit version is supplied:

    - First upsert (no existing row) with version=1 succeeds.
    - Second upsert with matching version=1 bumps version (no conflict).
    - Third upsert with a stale version (1) after bump returns 409 with a
      version_conflict payload.
    """
    # Ensure DB-backed policy store for this app instance
    monkeypatch.setenv("RG_POLICY_STORE", "db")
    monkeypatch.setenv("RG_POLICY_RELOAD_ENABLED", "false")

    client, db_name = isolated_test_environment
    assert isinstance(client, TestClient)
    headers = _admin_headers(client, db_name)

    policy_id = "pg.optimistic.test"

    # 1) Initial create with explicit version=1 should succeed.
    r1 = client.put(
        f"/api/v1/resource-governor/policy/{policy_id}",
        headers=headers,
        json={"payload": {"requests": {"rpm": 10}}, "version": 1},
    )
    assert r1.status_code == 200, r1.text

    # 2) Second update with matching expected version=1 (current) should succeed.
    r2 = client.put(
        f"/api/v1/resource-governor/policy/{policy_id}",
        headers=headers,
        json={"payload": {"requests": {"rpm": 20}}, "version": 1},
    )
    assert r2.status_code == 200, r2.text

    # Fetch record and confirm version has advanced beyond 1.
    rec = client.get(f"/api/v1/resource-governor/policy/{policy_id}", headers=headers)
    assert rec.status_code == 200, rec.text
    body = rec.json()
    current_version = int(body.get("version") or 0)
    assert current_version >= 2

    # 3) Stale update: still sending version=1 should now conflict.
    r3 = client.put(
        f"/api/v1/resource-governor/policy/{policy_id}",
        headers=headers,
        json={"payload": {"requests": {"rpm": 30}}, "version": 1},
    )
    assert r3.status_code == 409, r3.text
    payload = r3.json()
    assert payload.get("status") == "conflict"
    assert payload.get("error") == "version_conflict"
    assert payload.get("policy_id") == policy_id
