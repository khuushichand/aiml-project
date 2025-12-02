import os
from typing import Any, Dict

import pytest
from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import (
    get_auth_principal,
    get_current_user,
)
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal


pytestmark = pytest.mark.integration


def _attach_api_key_whoami_router(app: FastAPI) -> None:
    """
    Attach a lightweight whoami endpoint that exercises both get_auth_principal
    and get_current_user when authenticating via X-API-KEY in multi-user mode.

    This router is wired dynamically inside the test so that the production app
    remains unchanged outside of test contexts.
    """
    router = APIRouter()

    @router.get("/authnz/api-key-happy")
    async def whoami_api_key_happy(
        request: Request,
        principal: AuthPrincipal = Depends(get_auth_principal),
        user: Dict[str, Any] = Depends(get_current_user),
    ) -> Dict[str, Any]:
        return {
            "principal": {
                "principal_id": principal.principal_id,
                "kind": principal.kind,
                "user_id": principal.user_id,
                "api_key_id": principal.api_key_id,
                "roles": principal.roles,
                "permissions": principal.permissions,
                "org_ids": principal.org_ids,
                "team_ids": principal.team_ids,
            },
            "user": {
                "id": user.get("id"),
                "role": user.get("role"),
                "roles": user.get("roles"),
                "permissions": user.get("permissions"),
                "is_active": user.get("is_active"),
                "is_verified": user.get("is_verified"),
            },
            "state": {
                "user_id": getattr(request.state, "user_id", None),
                "api_key_id": getattr(request.state, "api_key_id", None),
                "org_ids": getattr(request.state, "org_ids", None),
                "team_ids": getattr(request.state, "team_ids", None),
            },
            "state_auth_principal": (
                {
                    "principal_id": getattr(getattr(request.state, "auth", None).principal, "principal_id", None),
                    "kind": getattr(getattr(request.state, "auth", None).principal, "kind", None),
                    "user_id": getattr(getattr(request.state, "auth", None).principal, "user_id", None),
                    "api_key_id": getattr(getattr(request.state, "auth", None).principal, "api_key_id", None),
                    "roles": getattr(getattr(request.state, "auth", None).principal, "roles", None),
                    "permissions": getattr(getattr(request.state, "auth", None).principal, "permissions", None),
                    "org_ids": getattr(getattr(request.state, "auth", None).principal, "org_ids", None),
                    "team_ids": getattr(getattr(request.state, "auth", None).principal, "team_ids", None),
                }
                if getattr(request.state, "auth", None) is not None
                else None
            ),
        }

    paths = {getattr(r, "path", "") for r in app.router.routes}
    if "/api/v1/authnz/api-key-happy" not in paths:
        app.include_router(router, prefix="/api/v1")


@pytest.mark.asyncio
async def test_multi_user_api_key_happy_path_principal_matches_state(
    isolated_test_environment,
) -> None:
    """
    Multi-user happy path for API key authentication:

    - Create a user and an API key via the real AuthNZ stack.
    - Call a protected endpoint that depends on both get_auth_principal and
      get_current_user using X-API-KEY.
    - Assert that the AuthPrincipal mirrors request.state and user data,
      especially api_key_id.
    """
    client, _db_name = isolated_test_environment
    assert isinstance(client, TestClient)

    app = client.app
    assert isinstance(app, FastAPI)

    _attach_api_key_whoami_router(app)

    # Ensure we are in multi-user mode
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings

    settings = get_settings()
    assert settings.AUTH_MODE == "multi_user"

    # Create a user and API key using the real DB/repo stack
    from uuid import uuid4

    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
    from tldw_Server_API.app.core.DB_Management.Users_DB import UsersDB
    from tldw_Server_API.app.core.AuthNZ.api_key_manager import APIKeyManager

    pool = await get_db_pool()

    users_db = UsersDB(pool)
    await users_db.initialize()
    created_user = await users_db.create_user(
        username="api-key-user",
        email="api-key-user@example.com",
        password_hash="x",
        role="user",
        is_active=True,
        is_superuser=False,
        storage_quota_mb=5120,
        uuid_value=uuid4(),
    )
    user_id = int(created_user["id"])

    mgr = APIKeyManager(pool)
    await mgr.initialize()
    key_rec = await mgr.create_api_key(user_id=user_id, name="api-key-happy")
    api_key = key_rec["key"]

    # Hit the whoami endpoint with X-API-KEY
    resp = client.get(
        "/api/v1/authnz/api-key-happy",
        headers={"X-API-KEY": api_key},
    )
    assert resp.status_code == 200, f"Unexpected status: {resp.status_code} body={resp.text}"

    payload = resp.json()
    principal = payload["principal"]
    user = payload["user"]
    state = payload["state"]
    state_auth_principal = payload["state_auth_principal"]

    # Identity consistency
    assert principal["kind"] == "api_key"
    assert principal["user_id"] is not None
    assert str(principal["user_id"]) == str(user["id"])

    # request.state mirrors principal identity
    assert str(state["user_id"]) == str(principal["user_id"])
    assert state["api_key_id"] is not None

    # AuthContext principal matches both principal and request.state
    assert state_auth_principal is not None
    assert state_auth_principal["kind"] == principal["kind"]
    assert str(state_auth_principal["user_id"]) == str(principal["user_id"])
    assert state_auth_principal["api_key_id"] == principal["api_key_id"]

    # api_key_id must stay in sync between request.state and AuthPrincipal
    assert principal["api_key_id"] == state["api_key_id"]
    assert state_auth_principal["api_key_id"] == state["api_key_id"]

