import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_policy_snapshot_endpoint(monkeypatch):
    base = Path(__file__).resolve().parents[3]
    stub = base / "Config_Files" / "resource_governor_policies.yaml"

    monkeypatch.setenv("RG_POLICY_STORE", "db")
    monkeypatch.setenv("RG_POLICY_PATH", str(stub))
    monkeypatch.setenv("RG_POLICY_RELOAD_ENABLED", "false")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    # Ensure deterministic single-user API key in tests and use it for auth
    monkeypatch.setenv("SINGLE_USER_API_KEY", "test-api-key-12345")
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{base / 'Databases' / 'users_test_rg_endpoint.db'}")

    from tldw_Server_API.app.main import app
    headers = {"X-API-KEY": "test-api-key-12345"}
    # Seed a few known policies via admin API to ensure snapshot exists in DB store
    with TestClient(app) as client:
        seeds = {
            "chat.default": {"requests": {"rpm": 12}},
            "embeddings.default": {"tokens": {"per_min": 1000}},
            "audio.default": {"streams": {"max_concurrent": 2}},
        }
        for pid, payload in seeds.items():
            client.put(
                f"/api/v1/resource-governor/policy/{pid}",
                headers=headers,
                json={"payload": payload, "version": 1},
            )
    with TestClient(app) as client:
        r = client.get("/api/v1/resource-governor/policy?include=ids", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "ok"
        assert data.get("store") in ("db", "file")
        assert data.get("version") >= 1
        ids = data.get("policy_ids") or []
        assert isinstance(ids, list) and len(ids) >= 3
        assert any(i == "chat.default" for i in ids)

        # Basic get (admin-gated; single_user treated as admin)
        # Ensure endpoint is reachable; result may be 404 in file store
        g = client.get(f"/api/v1/resource-governor/policy/{ids[0]}", headers=headers)
        assert g.status_code in (200, 404)


@pytest.mark.asyncio
async def test_policy_admin_upsert_and_delete_sqlite(monkeypatch):
    # Use DB policy store so admin writes update the snapshot on refresh
    base = Path(__file__).resolve().parents[3]
    monkeypatch.setenv("RG_POLICY_STORE", "db")
    monkeypatch.setenv("RG_POLICY_RELOAD_ENABLED", "false")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("SINGLE_USER_API_KEY", "test-api-key-12345")
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{base / 'Databases' / 'users_test_rg_admin.db'}")

    from tldw_Server_API.app.main import app
    headers = {"X-API-KEY": "test-api-key-12345"}
    with TestClient(app) as client:
        # Upsert a policy
        new_policy_id = "test.policy"
        up = client.put(
            f"/api/v1/resource-governor/policy/{new_policy_id}",
            headers=headers,
            json={
                "payload": {"requests": {"rpm": 42, "burst": 1.0}},
                "version": 1,
            },
        )
        assert up.status_code == 200
        # Verify it's included in snapshot ids
        r = client.get("/api/v1/resource-governor/policy?include=ids", headers=headers)
        assert r.status_code == 200
        ids = r.json().get("policy_ids") or []
        assert new_policy_id in ids
        # Delete it
        de = client.delete(f"/api/v1/resource-governor/policy/{new_policy_id}", headers=headers)
        assert de.status_code == 200
        r2 = client.get("/api/v1/resource-governor/policy?include=ids", headers=headers)
        assert new_policy_id not in (r2.json().get("policy_ids") or [])

        # List policies (admin)
        lst = client.get("/api/v1/resource-governor/policies", headers=headers)
        assert lst.status_code == 200
        items = lst.json().get("items")
        assert isinstance(items, list)
