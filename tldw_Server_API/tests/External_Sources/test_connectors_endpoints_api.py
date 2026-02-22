import os
from typing import Tuple

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def connectors_client() -> Tuple[TestClient, dict]:
    """Provide a TestClient with connectors routes enabled and X-API-KEY headers.

    We enable the experimental 'connectors' route via ROUTES_ENABLE before importing the app.
    """
    # Ensure single-user auth and enable connectors router before importing the app
    # so the route gating logic sees the toggles during app construction.
    os.environ.setdefault("TEST_MODE", "true")
    os.environ.setdefault("ROUTES_STABLE_ONLY", "false")
    # Explicitly allow connectors (experimental) in case stable_only is true
    os.environ["ROUTES_ENABLE"] = "connectors"
    os.environ.setdefault("AUTH_MODE", "single_user")
    os.environ.setdefault("TESTING", "true")

    from tldw_Server_API.app.core.AuthNZ.settings import get_settings
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.api.v1.endpoints import connectors as connectors_router

    # Ensure connectors router is mounted even if a prior import cached the app without it.
    paths = {route.path for route in app.routes}
    if "/api/v1/connectors/sources" not in paths:
        app.include_router(connectors_router.router, prefix="/api/v1", tags=["connectors"])

    api_key = get_settings().SINGLE_USER_API_KEY
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    client = TestClient(app)
    return client, headers


@pytest.mark.integration
def test_list_providers_hides_gmail_when_feature_flag_disabled(connectors_client, monkeypatch):
    client, headers = connectors_client
    import tldw_Server_API.app.api.v1.endpoints.connectors as ep

    monkeypatch.setitem(ep.settings, "EMAIL_GMAIL_CONNECTOR_ENABLED", False)
    response = client.get("/api/v1/connectors/providers", headers=headers)
    assert response.status_code == 200, response.text
    names = {str(item.get("name")) for item in response.json()}
    assert "drive" in names
    assert "notion" in names
    assert "gmail" not in names


@pytest.mark.integration
def test_list_providers_includes_gmail_when_feature_flag_enabled(connectors_client, monkeypatch):
    client, headers = connectors_client
    import tldw_Server_API.app.api.v1.endpoints.connectors as ep

    monkeypatch.setitem(ep.settings, "EMAIL_GMAIL_CONNECTOR_ENABLED", True)
    response = client.get("/api/v1/connectors/providers", headers=headers)
    assert response.status_code == 200, response.text
    names = {str(item.get("name")) for item in response.json()}
    assert "gmail" in names


@pytest.mark.integration
def test_add_source_blocks_gmail_when_feature_flag_disabled(connectors_client, monkeypatch):
    client, headers = connectors_client
    import tldw_Server_API.app.api.v1.endpoints.connectors as ep

    monkeypatch.setitem(ep.settings, "EMAIL_GMAIL_CONNECTOR_ENABLED", False)
    payload = {
        "account_id": 1,
        "provider": "gmail",
        "remote_id": "INBOX",
        "type": "folder",
    }
    response = client.post("/api/v1/connectors/sources", json=payload, headers=headers)
    assert response.status_code == 404


@pytest.mark.integration
def test_add_source_success(connectors_client, monkeypatch):
    client, headers = connectors_client

    # Patch the service call used by the endpoint to avoid DB work
    async def _fake_create_source(db, *, account_id, provider, remote_id, type_, path, options, enabled=True):
        return {
            "id": 101,
            "account_id": account_id,
            "provider": provider,
            "remote_id": remote_id,
            "type": type_,
            "path": path,
            "options": options or {},
            "enabled": enabled,
            "last_synced_at": None,
        }

    import tldw_Server_API.app.api.v1.endpoints.connectors as ep
    monkeypatch.setattr(ep, "create_source", _fake_create_source)
    async def _fake_get_account_for_user(db, user_id, account_id):
        return {"id": account_id, "user_id": user_id, "provider": "drive"}
    monkeypatch.setattr(ep, "get_account_for_user", _fake_get_account_for_user)

    payload = {
        "account_id": 1,
        "provider": "drive",
        "remote_id": "root",
        "type": "folder",
        "path": "/",
        "options": {"recursive": True},
    }
    r = client.post("/api/v1/connectors/sources", json=payload, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == 101
    assert body["provider"] == "drive"
    assert body["options"]["recursive"] is True


@pytest.mark.integration
def test_add_source_rejects_missing_account(connectors_client, monkeypatch):
    client, headers = connectors_client

    async def _fake_get_account_for_user(db, user_id, account_id):
        return None

    import tldw_Server_API.app.api.v1.endpoints.connectors as ep
    monkeypatch.setattr(ep, "get_account_for_user", _fake_get_account_for_user)

    payload = {
        "account_id": 999,
        "provider": "drive",
        "remote_id": "root",
        "type": "folder",
    }
    r = client.post("/api/v1/connectors/sources", json=payload, headers=headers)
    assert r.status_code == 404


@pytest.mark.integration
def test_add_source_rejects_provider_mismatch(connectors_client, monkeypatch):
    client, headers = connectors_client

    async def _fake_get_account_for_user(db, user_id, account_id):
        return {"id": account_id, "user_id": user_id, "provider": "notion"}

    import tldw_Server_API.app.api.v1.endpoints.connectors as ep
    monkeypatch.setattr(ep, "get_account_for_user", _fake_get_account_for_user)

    payload = {
        "account_id": 1,
        "provider": "drive",
        "remote_id": "root",
        "type": "folder",
    }
    r = client.post("/api/v1/connectors/sources", json=payload, headers=headers)
    assert r.status_code == 400


@pytest.mark.integration
def test_add_source_forbid_extra_fields(connectors_client, monkeypatch):
    client, headers = connectors_client

    # No patch needed; we expect validation to fail before hitting service
    payload = {
        "account_id": 1,
        "provider": "drive",
        "remote_id": "root",
        "type": "folder",
        "unexpected": "nope",  # extra field should be rejected by extra='forbid'
    }
    r = client.post("/api/v1/connectors/sources", json=payload, headers=headers)
    assert r.status_code == 422


@pytest.mark.integration
def test_patch_source_success(connectors_client, monkeypatch):
    client, headers = connectors_client

    async def _fake_update_source(db, user_id, source_id, *, enabled=None, options=None):
        return {
            "id": source_id,
            "account_id": 1,
            "provider": "notion",
            "remote_id": "abc",
            "type": "page",
            "path": None,
            "options": options or {"recursive": False},
            "enabled": bool(enabled) if enabled is not None else True,
            "last_synced_at": None,
        }

    import tldw_Server_API.app.api.v1.endpoints.connectors as ep
    monkeypatch.setattr(ep, "update_source", _fake_update_source)

    r = client.patch(
        "/api/v1/connectors/sources/55",
        json={"enabled": False, "options": {"recursive": False}},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == 55
    assert body["enabled"] is False
    assert body["options"]["recursive"] is False


@pytest.mark.integration
def test_patch_source_404(connectors_client, monkeypatch):
    client, headers = connectors_client

    async def _fake_update_source_none(db, user_id, source_id, *, enabled=None, options=None):
        return None

    import tldw_Server_API.app.api.v1.endpoints.connectors as ep
    monkeypatch.setattr(ep, "update_source", _fake_update_source_none)

    r = client.patch(
        "/api/v1/connectors/sources/9999",
        json={"enabled": True},
        headers=headers,
    )
    assert r.status_code == 404


@pytest.mark.integration
def test_patch_source_forbid_extra_fields(connectors_client):
    client, headers = connectors_client
    r = client.patch(
        "/api/v1/connectors/sources/55",
        json={"enabled": True, "extra": "bad"},
        headers=headers,
    )
    assert r.status_code == 422


@pytest.mark.integration
def test_oauth_callback_rejects_invalid_state(connectors_client, monkeypatch):
    client, headers = connectors_client

    import tldw_Server_API.app.api.v1.endpoints.connectors as ep

    async def _fake_consume_oauth_state(db, *, user_id, provider, state, max_age_minutes=10):
        return False

    class _FakeConn:
        name = "notion"
        def authorize_url(self, *a, **kw):
            return ""
        async def exchange_code(self, *a, **kw):
            raise AssertionError("exchange_code should not be called on invalid state")

    monkeypatch.setattr(ep, "consume_oauth_state", _fake_consume_oauth_state)
    monkeypatch.setattr(ep, "get_connector_by_name", lambda provider: _FakeConn())

    r = client.get(
        "/api/v1/connectors/providers/notion/callback",
        params={"code": "abc", "state": "bad"},
        headers=headers,
    )
    assert r.status_code == 403


@pytest.mark.integration
def test_oauth_callback_accepts_valid_state(connectors_client, monkeypatch):
    client, headers = connectors_client

    import tldw_Server_API.app.api.v1.endpoints.connectors as ep

    async def _fake_consume_oauth_state(db, *, user_id, provider, state, max_age_minutes=10):
        return True

    class _FakeConn:
        name = "notion"
        def authorize_url(self, *a, **kw):
            return ""
        async def exchange_code(self, code, redirect_uri):
            return {
                "access_token": "tok",
                "refresh_token": "rtok",
                "provider": "notion",
                "display_name": "Notion Account",
                "workspace_id": "ws1",
                "workspace_name": "Workspace",
            }

    async def _fake_create_account(db, user_id, provider, display_name, email, tokens):
        return {"id": 123, "display_name": display_name, "email": email, "created_at": "now"}

    monkeypatch.setattr(ep, "consume_oauth_state", _fake_consume_oauth_state)
    monkeypatch.setattr(ep, "get_connector_by_name", lambda provider: _FakeConn())
    monkeypatch.setattr(ep, "create_account", _fake_create_account)
    monkeypatch.setenv("ORG_CONNECTORS_ACCOUNT_LINKING_ROLE", "member")

    r = client.get(
        "/api/v1/connectors/providers/notion/callback",
        params={"code": "abc", "state": "good"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == 123
    assert body["provider"] == "notion"
