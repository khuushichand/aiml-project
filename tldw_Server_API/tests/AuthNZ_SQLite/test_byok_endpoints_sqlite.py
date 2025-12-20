import base64
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from loguru import logger


def _b64_key(byte_char: bytes) -> str:
    return base64.b64encode(byte_char * 32).decode("ascii")


async def _setup_byok_sqlite(tmp_path, monkeypatch):
    db_path = tmp_path / "users.db"
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("BYOK_ENABLED", "1")
    monkeypatch.setenv("BYOK_ENCRYPTION_KEY", _b64_key(b"k"))
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-jwt-key-please-change-1234567890")
    monkeypatch.setenv("DEFAULT_MODEL_OPENAI", "gpt-4o-mini")

    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool, get_db_pool
    from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables
    from tldw_Server_API.app.core.DB_Management.Users_DB import UsersDB
    from tldw_Server_API.app.core.AuthNZ.orgs_teams import (
        create_organization,
        create_team,
        add_org_member,
        add_team_member,
    )

    reset_settings()
    await reset_db_pool()

    pool = await get_db_pool()
    ensure_authnz_tables(Path(pool.db_path))

    users_db = UsersDB(pool)
    await users_db.initialize()

    admin = await users_db.create_user(
        username="byok-admin",
        email="byok-admin@example.com",
        password_hash="hashed-admin",
        role="admin",
        is_active=True,
        is_superuser=True,
        storage_quota_mb=5120,
        uuid_value=uuid.uuid4(),
    )
    user = await users_db.create_user(
        username="byok-user",
        email="byok-user@example.com",
        password_hash="hashed-user",
        role="user",
        is_active=True,
        is_superuser=False,
        storage_quota_mb=5120,
        uuid_value=uuid.uuid4(),
    )

    org = await create_organization(name="BYOK Org", owner_user_id=int(admin["id"]))
    team = await create_team(org_id=int(org["id"]), name="BYOK Team")

    await add_org_member(org_id=int(org["id"]), user_id=int(user["id"]), role="lead")
    await add_team_member(team_id=int(team["id"]), user_id=int(user["id"]), role="lead")

    return {
        "pool": pool,
        "admin": admin,
        "user": user,
        "org": org,
        "team": team,
    }


@pytest.mark.asyncio
async def test_byok_endpoints_sqlite(tmp_path, monkeypatch):
    state = await _setup_byok_sqlite(tmp_path, monkeypatch)
    admin_id = int(state["admin"]["id"])
    user_id = int(state["user"]["id"])
    org_id = int(state["org"]["id"])
    team_id = int(state["team"]["id"])

    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_current_user, get_auth_principal
    from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal, AuthContext
    from starlette.requests import Request

    async def _current_user_override(request: Request):  # type: ignore[override]
        user_dict = {
            "id": user_id,
            "role": "user",
            "is_active": True,
            "is_verified": True,
        }
        try:
            request.state._auth_user = user_dict
            request.state.user_id = user_id
        except Exception as exc:
            logger.debug(f"Could not set request.state for current user override: {exc}")
        return user_dict

    async def _principal_override(request: Request):  # type: ignore[override]
        principal = AuthPrincipal(
            kind="user",
            user_id=admin_id,
            api_key_id=None,
            subject="byok-admin",
            token_type="access",
            jti=None,
            roles=["admin"],
            permissions=["system.configure"],
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
        except Exception as exc:
            logger.debug(f"Could not set request.state.auth in admin override: {exc}")
        return principal

    app.dependency_overrides[get_current_user] = _current_user_override
    app.dependency_overrides[get_auth_principal] = _principal_override

    try:
        with TestClient(app) as client:
            r = client.post(
                "/api/v1/users/keys",
                json={"provider": "unknown-provider", "api_key": "sk-unknown-0000"},
            )
            assert r.status_code == 403

            r = client.post(
                "/api/v1/users/keys",
                json={
                    "provider": "openai",
                    "api_key": "sk-invalid-0000",
                    "credential_fields": {"unsupported": "value"},
                },
            )
            assert r.status_code == 400

            r = client.post(
                "/api/v1/users/keys",
                json={"provider": "openai", "api_key": "sk-user-openai-1234"},
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["provider"] == "openai"
            assert body["status"] == "stored"
            assert body["key_hint"] == "1234"
            assert "api_key" not in body

            r = client.post(
                "/api/v1/users/keys",
                json={"provider": "cohere", "api_key": "sk-user-cohere-5678"},
            )
            assert r.status_code == 200, r.text
            assert r.json()["key_hint"] == "5678"

            r = client.post(
                "/api/v1/users/keys/test",
                json={"provider": "openai", "api_key": "sk-test-openai-0001"},
            )
            assert r.status_code == 200, r.text
            assert r.json()["status"] == "valid"

            r = client.post(
                "/api/v1/users/keys/test",
                json={"provider": "openai", "api_key": "invalid-test-key"},
            )
            assert r.status_code == 401

            listing = client.get("/api/v1/users/keys")
            assert listing.status_code == 200
            items = {item["provider"]: item for item in listing.json()["items"]}
            assert items["openai"]["source"] == "user"
            assert items["openai"]["has_key"] is True
            assert items["cohere"]["source"] == "user"

            r = client.delete("/api/v1/users/keys/cohere")
            assert r.status_code == 204

            listing = client.get("/api/v1/users/keys")
            items = {item["provider"]: item for item in listing.json()["items"]}
            assert items["cohere"]["source"] != "user"

            r = client.post(
                f"/api/v1/orgs/{org_id}/keys/shared",
                json={"provider": "anthropic", "api_key": "sk-org-9999"},
            )
            assert r.status_code == 200, r.text
            org_resp = r.json()
            assert org_resp["scope_type"] == "org"
            assert org_resp["scope_id"] == org_id
            assert org_resp["key_hint"] == "9999"

            r = client.post(
                f"/api/v1/teams/{team_id}/keys/shared",
                json={"provider": "openrouter", "api_key": "sk-team-4321"},
            )
            assert r.status_code == 200, r.text
            assert r.json()["key_hint"] == "4321"

            r = client.post(
                f"/api/v1/orgs/{org_id}/keys/shared/test",
                json={"provider": "openai", "api_key": "sk-org-test-0002"},
            )
            assert r.status_code == 200, r.text
            assert r.json()["status"] == "valid"

            r = client.post(
                f"/api/v1/teams/{team_id}/keys/shared/test",
                json={"provider": "openai", "api_key": "sk-team-test-0003"},
            )
            assert r.status_code == 200, r.text
            assert r.json()["status"] == "valid"

            r = client.get(f"/api/v1/orgs/{org_id}/keys/shared")
            assert r.status_code == 200
            org_items = {item["provider"]: item for item in r.json()["items"]}
            assert "anthropic" in org_items

            r = client.get(f"/api/v1/teams/{team_id}/keys/shared")
            assert r.status_code == 200
            team_items = {item["provider"]: item for item in r.json()["items"]}
            assert "openrouter" in team_items

            listing = client.get("/api/v1/users/keys")
            items = {item["provider"]: item for item in listing.json()["items"]}
            assert items["anthropic"]["source"] == "shared"
            assert items["anthropic"]["has_key"] is False
            assert items["openrouter"]["source"] == "shared"

            admin_list = client.get(f"/api/v1/admin/keys/users/{user_id}")
            assert admin_list.status_code == 200
            admin_items = {item["provider"]: item for item in admin_list.json()["items"]}
            assert "openai" in admin_items
            assert admin_items["openai"]["allowed"] is True

            r = client.post(
                "/api/v1/admin/keys/shared/test",
                json={
                    "scope_type": "org",
                    "scope_id": org_id,
                    "provider": "openai",
                    "api_key": "sk-admin-test-0004",
                },
            )
            assert r.status_code == 200, r.text
            assert r.json()["status"] == "valid"

            r = client.post(
                "/api/v1/admin/keys/shared",
                json={
                    "scope_type": "org",
                    "scope_id": org_id,
                    "provider": "groq",
                    "api_key": "sk-admin-3333",
                },
            )
            assert r.status_code == 200, r.text

            r = client.get("/api/v1/admin/keys/shared", params={"scope_type": "org", "scope_id": org_id})
            assert r.status_code == 200
            shared_items = {item["provider"]: item for item in r.json()["items"]}
            assert "groq" in shared_items

            r = client.delete(f"/api/v1/admin/keys/shared/org/{org_id}/groq")
            assert r.status_code == 204

            r = client.delete(f"/api/v1/admin/keys/users/{user_id}/openai")
            assert r.status_code == 204

            r = client.delete(f"/api/v1/orgs/{org_id}/keys/shared/anthropic")
            assert r.status_code == 204

            r = client.delete(f"/api/v1/teams/{team_id}/keys/shared/openrouter")
            assert r.status_code == 204

            listing = client.get("/api/v1/users/keys")
            items = {item["provider"]: item for item in listing.json()["items"]}
            assert items["openai"]["source"] != "user"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_shared_keys_scoped_requires_manager_sqlite(tmp_path, monkeypatch):
    state = await _setup_byok_sqlite(tmp_path, monkeypatch)
    pool = state["pool"]
    org_id = int(state["org"]["id"])
    team_id = int(state["team"]["id"])

    from tldw_Server_API.app.core.DB_Management.Users_DB import UsersDB
    from tldw_Server_API.app.core.AuthNZ.orgs_teams import add_org_member, add_team_member

    users_db = UsersDB(pool)
    await users_db.initialize()

    member = await users_db.create_user(
        username="byok-member",
        email="byok-member@example.com",
        password_hash="hashed-member",
        role="user",
        is_active=True,
        is_superuser=False,
        storage_quota_mb=5120,
        uuid_value=uuid.uuid4(),
    )
    member_id = int(member["id"])
    await add_org_member(org_id=org_id, user_id=member_id, role="member")
    await add_team_member(team_id=team_id, user_id=member_id, role="member")

    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_current_user
    from starlette.requests import Request

    async def _current_user_override(request: Request):  # type: ignore[override]
        user_dict = {
            "id": member_id,
            "role": "user",
            "is_active": True,
            "is_verified": True,
        }
        try:
            request.state._auth_user = user_dict
            request.state.user_id = member_id
        except Exception as exc:
            logger.debug(f"Could not set request.state for member override: {exc}")
        return user_dict

    app.dependency_overrides[get_current_user] = _current_user_override

    try:
        with TestClient(app) as client:
            r = client.post(
                f"/api/v1/orgs/{org_id}/keys/shared",
                json={"provider": "openai", "api_key": "sk-org-0000"},
            )
            assert r.status_code == 403

            r = client.post(
                f"/api/v1/teams/{team_id}/keys/shared",
                json={"provider": "openai", "api_key": "sk-team-0000"},
            )
            assert r.status_code == 403
    finally:
        app.dependency_overrides.clear()
