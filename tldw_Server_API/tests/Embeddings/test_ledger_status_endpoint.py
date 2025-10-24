import json
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user
from fastapi import HTTPException


def _override_user(admin=False):
    async def _f():
        from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
        return User(id=1, username="admin" if admin else "u", email="u@x", is_active=True, is_admin=admin)
    return _f


@pytest.mark.unit
def test_ledger_status_happy_path(disable_heavy_startup, admin_user, redis_client):
    client = TestClient(app)
    client.cookies.set("csrf_token", "x")
    client.headers["X-CSRF-Token"] = "x"
    client.headers["Authorization"] = "Bearer key"
    # Seed fake redis with both keys
    idk = "idem:abc"
    ddk = "dedupe:def"
    # Values can be JSON objects with status, ts, job_id
    async def _seed():
        await redis_client.set(
            f"embeddings:ledger:idemp:{idk}",
            json.dumps({"status": "completed", "ts": 123, "job_id": "job-x"}),
        )
        await redis_client.set(
            f"embeddings:ledger:dedupe:{ddk}",
            json.dumps({"status": "in_progress", "ts": 456}),
        )

    redis_client.run(_seed())

    r = client.get("/api/v1/embeddings/ledger/status", params={"idempotency_key": idk, "dedupe_key": ddk})
    assert r.status_code == 200
    body = r.json()
    assert body["idempotency"]["status"] == "completed"
    assert body["idempotency"]["job_id"] == "job-x"
    assert body["dedupe"]["status"] in {"in_progress", "in-progress", "in_progress"}


@pytest.mark.unit
def test_ledger_status_requires_key_and_admin(disable_heavy_startup, monkeypatch):
    client = TestClient(app)
    client.cookies.set("csrf_token", "x")
    client.headers["X-CSRF-Token"] = "x"
    client.headers["Authorization"] = "Bearer key"
    # Non-admin → simulate 403 by patching require_admin used in endpoint
    import tldw_Server_API.app.api.v1.endpoints.embeddings_v5_production_enhanced as emb_mod
    app.dependency_overrides[get_request_user] = _override_user(admin=False)
    def _deny(_user):
        raise HTTPException(status_code=403, detail="forbidden")
    monkeypatch.setattr(emb_mod, "require_admin", _deny, raising=False)
    try:
        r_forbidden = client.get("/api/v1/embeddings/ledger/status", params={"idempotency_key": "k"})
        assert r_forbidden.status_code in (401, 403)
    finally:
        app.dependency_overrides.pop(get_request_user, None)

    # Missing keys → 400 (with admin)
    app.dependency_overrides[get_request_user] = _override_user(admin=True)
    # Restore require_admin to pass-through for admin
    monkeypatch.setattr(emb_mod, "require_admin", lambda u: u, raising=False)
    try:
        r_bad = client.get("/api/v1/embeddings/ledger/status")
        assert r_bad.status_code == 400
    finally:
        app.dependency_overrides.pop(get_request_user, None)
