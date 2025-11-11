import os
from typing import Tuple

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def connectors_client() -> Tuple[TestClient, dict]:
    """Provide a TestClient with connectors routes enabled and X-API-KEY headers.

    We enable the experimental 'connectors' route via ROUTES_ENABLE before importing the app.
    """
    # Ensure single-user auth and enable connectors router
    os.environ.setdefault("AUTH_MODE", "single_user")
    os.environ.setdefault("TESTING", "true")
    # Append 'connectors' to ROUTES_ENABLE in a stable way
    cur = os.getenv("ROUTES_ENABLE", "")
    parts = [p.strip().lower() for p in cur.replace(" ", ",").split(",") if p.strip()]
    if "connectors" not in parts:
        parts.append("connectors")
    os.environ["ROUTES_ENABLE"] = ",".join(parts)

    from tldw_Server_API.app.core.AuthNZ.settings import get_settings
    from tldw_Server_API.app.main import app

    api_key = get_settings().SINGLE_USER_API_KEY
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    client = TestClient(app)
    return client, headers


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

