import base64
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _b64_key(byte_char: bytes) -> str:
    return base64.b64encode(byte_char * 32).decode("ascii")


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _issue_access_token(
    user_row: dict,
    *,
    active_org_id: int | None = None,
    active_team_id: int | None = None,
) -> str:
    from tldw_Server_API.app.core.AuthNZ.jwt_service import get_jwt_service
    from tldw_Server_API.app.core.AuthNZ.orgs_teams import list_memberships_for_user

    user_id = int(user_row["id"])
    memberships = await list_memberships_for_user(user_id)
    team_ids = sorted({m.get("team_id") for m in memberships if m.get("team_id") is not None})
    org_ids = sorted({m.get("org_id") for m in memberships if m.get("org_id") is not None})

    claims = {"team_ids": team_ids, "org_ids": org_ids}
    if active_org_id is not None:
        claims["active_org_id"] = int(active_org_id)
    if active_team_id is not None:
        claims["active_team_id"] = int(active_team_id)

    jwt_service = get_jwt_service()
    return jwt_service.create_access_token(
        user_id=user_id,
        username=str(user_row.get("username") or user_id),
        role=str(user_row.get("role") or "user"),
        additional_claims=claims,
    )


async def _setup_byok_sqlite(tmp_path, monkeypatch):
    db_path = tmp_path / "users.db"
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("BYOK_ENABLED", "1")
    monkeypatch.setenv("BYOK_ENCRYPTION_KEY", _b64_key(b"k"))
    monkeypatch.setenv("BYOK_ALLOWED_BASE_URL_PROVIDERS", "openai")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-jwt-key-please-change-1234567890")
    monkeypatch.setenv("DEFAULT_MODEL_OPENAI", "gpt-4o-mini")
    monkeypatch.setenv("DEFAULT_MODEL_ANTHROPIC", "claude-3-haiku")
    monkeypatch.setenv("DEFAULT_MODEL_COHERE", "command-r")
    monkeypatch.setenv("DEFAULT_MODEL_GROQ", "llama-3.1-8b-instant")
    monkeypatch.setenv("DEFAULT_MODEL_OPENROUTER", "openrouter/test-model")

    from tldw_Server_API.app.core.AuthNZ.jwt_service import reset_jwt_service
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool, get_db_pool
    from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables
    from tldw_Server_API.app.core.DB_Management.Users_DB import UsersDB, reset_users_db
    from tldw_Server_API.app.core.AuthNZ.orgs_teams import (
        create_organization,
        create_team,
        add_org_member,
        add_team_member,
    )

    reset_settings()
    reset_jwt_service()
    await reset_db_pool()
    await reset_users_db()

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
        is_verified=True,
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
        is_verified=True,
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
    user_id = int(state["user"]["id"])
    org_id = int(state["org"]["id"])
    team_id = int(state["team"]["id"])

    from tldw_Server_API.app.main import app
    user_token = await _issue_access_token(
        state["user"],
        active_org_id=org_id,
        active_team_id=team_id,
    )
    admin_token = await _issue_access_token(state["admin"])
    user_headers = _auth_headers(user_token)
    admin_headers = _auth_headers(admin_token)

    with TestClient(app) as client:
        r = client.post(
            "/api/v1/users/keys",
            json={"provider": "unknown-provider", "api_key": "sk-unknown-0000"},
            headers=user_headers,
        )
        assert r.status_code == 403

        r = client.post(
            "/api/v1/users/keys",
            json={
                "provider": "openai",
                "api_key": "sk-invalid-0000",
                "credential_fields": {"unsupported": "value"},
            },
            headers=user_headers,
        )
        assert r.status_code == 400

        r = client.post(
            "/api/v1/users/keys",
            json={"provider": "openai", "api_key": "sk-user-openai-1234"},
            headers=user_headers,
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
            headers=user_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["key_hint"] == "5678"

        r = client.post(
            "/api/v1/users/keys",
            json={"provider": "openai", "api_key": "invalid-test-key"},
            headers=user_headers,
        )
        assert r.status_code == 401

        r = client.post(
            "/api/v1/users/keys/test",
            json={"provider": "openai"},
            headers=user_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "valid"

        listing = client.get("/api/v1/users/keys", headers=user_headers)
        assert listing.status_code == 200
        items = {item["provider"]: item for item in listing.json()["items"]}
        assert items["openai"]["source"] == "user"
        assert items["openai"]["has_key"] is True
        assert items["cohere"]["source"] == "user"

        r = client.delete("/api/v1/users/keys/cohere", headers=user_headers)
        assert r.status_code == 204

        listing = client.get("/api/v1/users/keys", headers=user_headers)
        items = {item["provider"]: item for item in listing.json()["items"]}
        assert items["cohere"]["source"] != "user"

        r = client.post(
            f"/api/v1/orgs/{org_id}/keys/shared",
            json={"provider": "anthropic", "api_key": "sk-org-9999"},
            headers=user_headers,
        )
        assert r.status_code == 200, r.text
        org_resp = r.json()
        assert org_resp["scope_type"] == "org"
        assert org_resp["scope_id"] == org_id
        assert org_resp["key_hint"] == "9999"

        r = client.post(
            f"/api/v1/teams/{team_id}/keys/shared",
            json={"provider": "openrouter", "api_key": "sk-team-4321"},
            headers=user_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["key_hint"] == "4321"

        r = client.post(
            f"/api/v1/orgs/{org_id}/keys/shared/test",
            json={"provider": "anthropic"},
            headers=user_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "valid"

        r = client.post(
            f"/api/v1/teams/{team_id}/keys/shared/test",
            json={"provider": "openrouter"},
            headers=user_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "valid"

        r = client.get(f"/api/v1/orgs/{org_id}/keys/shared", headers=user_headers)
        assert r.status_code == 200
        org_items = {item["provider"]: item for item in r.json()["items"]}
        assert "anthropic" in org_items

        r = client.get(f"/api/v1/teams/{team_id}/keys/shared", headers=user_headers)
        assert r.status_code == 200
        team_items = {item["provider"]: item for item in r.json()["items"]}
        assert "openrouter" in team_items

        listing = client.get("/api/v1/users/keys", headers=user_headers)
        items = {item["provider"]: item for item in listing.json()["items"]}
        assert items["anthropic"]["source"] == "org"
        assert items["anthropic"]["has_key"] is False
        assert items["openrouter"]["source"] == "team"

        admin_list = client.get(f"/api/v1/admin/keys/users/{user_id}", headers=admin_headers)
        assert admin_list.status_code == 200
        admin_items = {item["provider"]: item for item in admin_list.json()["items"]}
        assert "openai" in admin_items
        assert admin_items["openai"]["allowed"] is True

        r = client.post(
            "/api/v1/admin/keys/shared/test",
            json={
                "scope_type": "org",
                "scope_id": org_id,
                "provider": "anthropic",
            },
            headers=admin_headers,
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
            headers=admin_headers,
        )
        assert r.status_code == 200, r.text

        r = client.get(
            "/api/v1/admin/keys/shared",
            params={"scope_type": "org", "scope_id": org_id},
            headers=admin_headers,
        )
        assert r.status_code == 200
        shared_items = {item["provider"]: item for item in r.json()["items"]}
        assert "groq" in shared_items

        r = client.delete(f"/api/v1/admin/keys/shared/org/{org_id}/groq", headers=admin_headers)
        assert r.status_code == 204

        r = client.delete(f"/api/v1/admin/keys/users/{user_id}/openai", headers=admin_headers)
        assert r.status_code == 204

        r = client.delete(f"/api/v1/orgs/{org_id}/keys/shared/anthropic", headers=user_headers)
        assert r.status_code == 204

        r = client.delete(f"/api/v1/teams/{team_id}/keys/shared/openrouter", headers=user_headers)
        assert r.status_code == 204

        listing = client.get("/api/v1/users/keys", headers=user_headers)
        items = {item["provider"]: item for item in listing.json()["items"]}
        assert items["openai"]["source"] != "user"


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
        is_verified=True,
        is_superuser=False,
        storage_quota_mb=5120,
        uuid_value=uuid.uuid4(),
    )
    member_id = int(member["id"])
    await add_org_member(org_id=org_id, user_id=member_id, role="member")
    await add_team_member(team_id=team_id, user_id=member_id, role="member")

    from tldw_Server_API.app.main import app

    member_token = await _issue_access_token(
        member,
        active_org_id=org_id,
        active_team_id=team_id,
    )
    member_headers = _auth_headers(member_token)

    with TestClient(app) as client:
        r = client.post(
            f"/api/v1/orgs/{org_id}/keys/shared",
            json={"provider": "openai", "api_key": "sk-org-0000"},
            headers=member_headers,
        )
        assert r.status_code == 403

        r = client.post(
            f"/api/v1/teams/{team_id}/keys/shared",
            json={"provider": "openai", "api_key": "sk-team-0000"},
            headers=member_headers,
        )
        assert r.status_code == 403
