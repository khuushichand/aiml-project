import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.tests.AuthNZ.integration.test_rbac_admin_endpoints import _admin_headers


@pytest.mark.asyncio
async def test_policy_admin_list_count_and_metadata_postgres(monkeypatch, isolated_test_environment):
    """
    Seed multiple rg_policies rows via the admin API and verify:
      - /api/v1/resource-governor/policies returns expected count
      - Each item has id/version/updated_at
      - Snapshot endpoint includes the seeded IDs when include=ids
    """
    # Use DB-backed policy store for this app instance
    monkeypatch.setenv("RG_POLICY_STORE", "db")
    monkeypatch.setenv("RG_POLICY_RELOAD_ENABLED", "false")

    client, db_name = isolated_test_environment
    headers = _admin_headers(client, db_name)

    # Upsert multiple distinct policies
    seeds = {
        "pg.multiple.p1": {"requests": {"rpm": 10, "burst": 1.0}},
        "pg.multiple.p2": {"tokens": {"per_min": 2000, "burst": 1.2}},
        "pg.multiple.p3": {"streams": {"max_concurrent": 2, "ttl_sec": 60}},
    }

    for pid, payload in seeds.items():
        r = client.put(
            f"/api/v1/resource-governor/policy/{pid}",
            headers=headers,
            json={"payload": payload, "version": 1},
        )
        assert r.status_code == 200, r.text

    # Verify policies list count and metadata
    lst = client.get("/api/v1/resource-governor/policies", headers=headers)
    assert lst.status_code == 200, lst.text
    body = lst.json()
    items = body.get("items") or []
    count = int(body.get("count") or 0)
    assert isinstance(items, list)
    # Ensure at least the seeded policies are present; isolated DB per test → exact match
    assert count >= len(seeds)
    ids = {it.get("id") for it in items}
    for pid in seeds.keys():
        assert pid in ids
    # Metadata expectations
    for it in items:
        assert isinstance(it.get("id"), str) and it.get("id")
        assert int(it.get("version") or 0) >= 1
        assert it.get("updated_at") is not None

    # Snapshot endpoint should include the seeded IDs (ids only)
    snap = client.get("/api/v1/resource-governor/policy?include=ids")
    assert snap.status_code == 200, snap.text
    sids = set(snap.json().get("policy_ids") or [])
    for pid in seeds.keys():
        assert pid in sids

