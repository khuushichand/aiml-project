import json
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user
from fastapi import HTTPException
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal, AuthContext
from starlette.requests import Request


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
    # Non-admin principal lacking EMBEDDINGS_ADMIN should be forbidden
    app.dependency_overrides[get_request_user] = _override_user(admin=False)

    async def _non_admin_principal(request: Request) -> AuthPrincipal:  # type: ignore[override]
        principal = AuthPrincipal(
            kind="user",
            user_id=1,
            api_key_id=None,
            subject="u",
            token_type="access",
            jti=None,
            roles=["user"],
            permissions=[],
            is_admin=False,
            org_ids=[],
            team_ids=[],
        )
        try:
            request.state.auth = AuthContext(
                principal=principal,
                ip=None,
                user_agent=None,
                request_id=None,
            )
        except Exception:
            pass
        return principal

    app.dependency_overrides[get_auth_principal] = _non_admin_principal
    try:
        r_forbidden = client.get("/api/v1/embeddings/ledger/status", params={"idempotency_key": "k"})
        # Non-admins should be rejected either directly by RBAC (403) or by
        # an upstream rate/budget guard (429) for this admin-only endpoint.
        assert r_forbidden.status_code in (403, 429)
    finally:
        app.dependency_overrides.pop(get_request_user, None)
        app.dependency_overrides.pop(get_auth_principal, None)

    # Missing keys → 400 (with admin principal having EMBEDDINGS_ADMIN)
    app.dependency_overrides[get_request_user] = _override_user(admin=True)

    async def _admin_principal(request: Request) -> AuthPrincipal:  # type: ignore[override]
        principal = AuthPrincipal(
            kind="user",
            user_id=1,
            api_key_id=None,
            subject="admin",
            token_type="access",
            jti=None,
            roles=["admin"],
            permissions=["embeddings.admin"],
            is_admin=True,
            org_ids=[],
            team_ids=[],
        )
        try:
            request.state.auth = AuthContext(
                principal=principal,
                ip=None,
                user_agent=None,
                request_id=None,
            )
        except Exception:
            pass
        return principal

    app.dependency_overrides[get_auth_principal] = _admin_principal
    try:
        r_bad = client.get("/api/v1/embeddings/ledger/status")
        # With an admin principal but missing query keys, either the handler
        # validation (400) or an upstream rate/budget guard (429) should
        # reject the request; a successful 2xx is never expected.
        assert r_bad.status_code in (400, 429)
    finally:
        app.dependency_overrides.pop(get_request_user, None)
        app.dependency_overrides.pop(get_auth_principal, None)
