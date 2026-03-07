import os
from typing import Tuple

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.External_Sources.sync_adapter import FileSyncWebhookSubscription


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
def test_add_onedrive_source_provisions_webhook_subscription(connectors_client, monkeypatch):
    client, headers = connectors_client

    import tldw_Server_API.app.api.v1.endpoints.connectors as ep

    subscribe_calls: list[dict] = []
    sync_state_updates: list[dict] = []

    async def _fake_create_source(db, *, account_id, provider, remote_id, type_, path, options, enabled=True):
        return {
            "id": 501,
            "account_id": account_id,
            "provider": provider,
            "remote_id": remote_id,
            "type": type_,
            "path": path,
            "options": options or {},
            "enabled": enabled,
            "last_synced_at": None,
        }

    async def _fake_get_account_for_user(db, user_id, account_id):
        return {"id": account_id, "user_id": user_id, "provider": "onedrive"}

    async def _fake_get_account_tokens(db, user_id, account_id):
        return {"access_token": "tok"}

    async def _fake_upsert_source_sync_state(db, *, source_id, **updates):
        payload = {"source_id": source_id, **updates}
        sync_state_updates.append(payload)
        return payload

    class _FakeConn:
        name = "onedrive"

        def authorize_url(self, *a, **kw):
            return ""

        async def exchange_code(self, *a, **kw):
            return {}

        async def subscribe_webhook(self, account, *, resource, callback_url):
            subscribe_calls.append(
                {
                    "account": dict(account),
                    "resource": dict(resource),
                    "callback_url": callback_url,
                }
            )
            return FileSyncWebhookSubscription(
                subscription_id="sub-501",
                expires_at="2026-03-10T00:00:00Z",
                metadata={"expirationDateTime": "2026-03-10T00:00:00Z"},
            )

    monkeypatch.setattr(ep, "create_source", _fake_create_source)
    monkeypatch.setattr(ep, "get_account_for_user", _fake_get_account_for_user)
    monkeypatch.setattr(ep, "get_account_tokens", _fake_get_account_tokens)
    monkeypatch.setattr(ep, "get_connector_by_name", lambda provider: _FakeConn())
    monkeypatch.setattr(ep, "evaluate_policy_constraints", lambda *a, **kw: (True, None))
    monkeypatch.setattr(ep, "upsert_source_sync_state", _fake_upsert_source_sync_state, raising=False)

    payload = {
        "account_id": 12,
        "provider": "onedrive",
        "remote_id": "root",
        "type": "folder",
        "path": "/",
        "options": {"recursive": True},
    }
    r = client.post("/api/v1/connectors/sources", json=payload, headers=headers)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == 501
    assert body["provider"] == "onedrive"
    assert len(subscribe_calls) == 1
    assert subscribe_calls[0]["callback_url"] == "http://testserver/api/v1/connectors/providers/onedrive/webhook"
    assert subscribe_calls[0]["resource"]["resource"] == "me/drive/root"
    assert subscribe_calls[0]["account"]["tokens"]["access_token"] == "tok"
    assert sync_state_updates[0]["source_id"] == 501
    assert sync_state_updates[0]["sync_mode"] == "hybrid"
    assert sync_state_updates[0]["webhook_status"] == "active"
    assert sync_state_updates[0]["webhook_subscription_id"] == "sub-501"
    assert sync_state_updates[0]["webhook_expires_at"] == "2026-03-10T00:00:00Z"


@pytest.mark.integration
def test_add_drive_source_provisions_webhook_subscription_and_cursor(connectors_client, monkeypatch):
    client, headers = connectors_client

    import tldw_Server_API.app.api.v1.endpoints.connectors as ep

    subscribe_calls: list[dict] = []
    sync_state_updates: list[dict] = []

    async def _fake_create_source(db, *, account_id, provider, remote_id, type_, path, options, enabled=True):
        return {
            "id": 601,
            "account_id": account_id,
            "provider": provider,
            "remote_id": remote_id,
            "type": type_,
            "path": path,
            "options": options or {},
            "enabled": enabled,
            "last_synced_at": None,
        }

    async def _fake_get_account_for_user(db, user_id, account_id):
        return {"id": account_id, "user_id": user_id, "provider": "drive"}

    async def _fake_get_account_tokens(db, user_id, account_id):
        return {"access_token": "tok"}

    async def _fake_upsert_source_sync_state(db, *, source_id, **updates):
        payload = {"source_id": source_id, **updates}
        sync_state_updates.append(payload)
        return payload

    class _FakeConn:
        name = "drive"

        def authorize_url(self, *a, **kw):
            return ""

        async def exchange_code(self, *a, **kw):
            return {}

        async def subscribe_webhook(self, account, *, resource, callback_url):
            subscribe_calls.append(
                {
                    "account": dict(account),
                    "resource": dict(resource),
                    "callback_url": callback_url,
                }
            )
            return FileSyncWebhookSubscription(
                subscription_id="drive-chan-1",
                expires_at="2026-03-10T00:00:00Z",
                metadata={
                    "resourceId": "drive-resource-1",
                    "pageToken": "drive-cursor-1",
                    "callback_url": callback_url,
                    "clientState": "drive-state-1",
                },
            )

    monkeypatch.setattr(ep, "create_source", _fake_create_source)
    monkeypatch.setattr(ep, "get_account_for_user", _fake_get_account_for_user)
    monkeypatch.setattr(ep, "get_account_tokens", _fake_get_account_tokens)
    monkeypatch.setattr(ep, "get_connector_by_name", lambda provider: _FakeConn())
    monkeypatch.setattr(ep, "evaluate_policy_constraints", lambda *a, **kw: (True, None))
    monkeypatch.setattr(ep, "upsert_source_sync_state", _fake_upsert_source_sync_state, raising=False)

    payload = {
        "account_id": 13,
        "provider": "drive",
        "remote_id": "root",
        "type": "folder",
        "path": "/",
        "options": {"recursive": True},
    }
    r = client.post("/api/v1/connectors/sources", json=payload, headers=headers)

    assert r.status_code == 200, r.text
    assert len(subscribe_calls) == 1
    assert subscribe_calls[0]["callback_url"] == "http://testserver/api/v1/connectors/providers/drive/webhook"
    assert sync_state_updates[0]["source_id"] == 601
    assert sync_state_updates[0]["sync_mode"] == "hybrid"
    assert sync_state_updates[0]["cursor"] == "drive-cursor-1"
    assert sync_state_updates[0]["cursor_kind"] == "drive_start_page_token"
    assert sync_state_updates[0]["webhook_status"] == "active"
    assert sync_state_updates[0]["webhook_subscription_id"] == "drive-chan-1"
    assert sync_state_updates[0]["webhook_expires_at"] == "2026-03-10T00:00:00Z"
    assert sync_state_updates[0]["webhook_metadata"]["resourceId"] == "drive-resource-1"


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
def test_get_sources_includes_sync_summary(connectors_client, monkeypatch):
    client, headers = connectors_client

    import tldw_Server_API.app.api.v1.endpoints.connectors as ep

    async def _fake_list_sources(db, user_id):
        return [
            {
                "id": 22,
                "account_id": 5,
                "provider": "onedrive",
                "remote_id": "root",
                "type": "folder",
                "path": "/",
                "options": {"recursive": True},
                "enabled": True,
                "last_synced_at": None,
            }
        ]

    async def _fake_get_source_sync_state(db, *, source_id):
        assert source_id == 22
        return {
            "source_id": source_id,
            "sync_mode": "hybrid",
            "last_sync_failed_at": "2026-03-06 10:02:00",
            "last_error": "delta cursor invalid",
            "webhook_status": "active",
            "needs_full_rescan": True,
            "active_job_id": "88",
        }

    monkeypatch.setattr(ep, "list_sources", _fake_list_sources)
    monkeypatch.setattr(ep, "get_source_sync_state", _fake_get_source_sync_state)

    response = client.get("/api/v1/connectors/sources", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == 22
    assert body[0]["sync"]["state"] == "needs_full_rescan"
    assert body[0]["sync"]["sync_mode"] == "hybrid"
    assert body[0]["sync"]["last_error"] == "delta cursor invalid"
    assert body[0]["sync"]["webhook_status"] == "active"
    assert body[0]["sync"]["needs_full_rescan"] is True
    assert body[0]["sync"]["active_job_id"] == "88"


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


@pytest.mark.integration
def test_get_source_sync_status_returns_state_and_active_job(connectors_client, monkeypatch):
    client, headers = connectors_client

    import tldw_Server_API.app.api.v1.endpoints.connectors as ep
    import tldw_Server_API.app.core.Jobs.manager as jobs_manager

    async def _fake_get_source_by_id(db, user_id, source_id):
        return {
            "id": source_id,
            "provider": "drive",
            "enabled": True,
        }

    async def _fake_get_source_sync_state(db, *, source_id):
        return {
            "source_id": source_id,
            "sync_mode": "hybrid",
            "cursor": "delta-1",
            "cursor_kind": "drive_start_page_token",
            "last_sync_started_at": "2026-03-06 10:00:00",
            "last_sync_succeeded_at": "2026-03-06 10:01:00",
            "last_error": None,
            "retry_backoff_count": 0,
            "webhook_status": "active",
            "webhook_expires_at": "2026-03-07 10:00:00",
            "needs_full_rescan": False,
            "active_job_id": "77",
            "active_job_started_at": "2026-03-06 10:00:00",
        }

    class _FakeJobManager:
        def get_job(self, job_id: int):
            assert job_id == 77
            return {
                "id": job_id,
                "job_type": "import",
                "status": "processing",
                "progress_percent": 35,
                "result": {"processed": 7, "failed": 0, "skipped": 0},
            }

    monkeypatch.setattr(ep, "get_source_by_id", _fake_get_source_by_id)
    monkeypatch.setattr(ep, "get_source_sync_state", _fake_get_source_sync_state)
    monkeypatch.setattr(jobs_manager, "JobManager", _FakeJobManager)

    response = client.get("/api/v1/connectors/sources/22/sync", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source_id"] == 22
    assert body["provider"] == "drive"
    assert body["state"] == "running"
    assert body["sync_mode"] == "hybrid"
    assert body["cursor"] == "delta-1"
    assert body["active_job_id"] == "77"
    assert body["active_job"]["id"] == "77"
    assert body["active_job"]["status"] == "processing"
    assert body["active_job"]["progress_pct"] == 35


@pytest.mark.integration
def test_trigger_source_sync_endpoint_queues_job(connectors_client, monkeypatch):
    client, headers = connectors_client

    import tldw_Server_API.app.api.v1.endpoints.connectors as ep

    queued_requests: list[dict] = []

    async def _fake_get_source_by_id(db, user_id, source_id):
        return {
            "id": source_id,
            "provider": "onedrive",
            "enabled": True,
        }

    async def _fake_create_import_job(user_id, source_id, *, request_id=None, job_type="import"):
        queued_requests.append(
            {
                "user_id": user_id,
                "source_id": source_id,
                "request_id": request_id,
                "job_type": job_type,
            }
        )
        return {
            "id": "job-123",
            "source_id": source_id,
            "type": job_type,
            "status": "queued",
            "progress_pct": 0,
            "counts": {"processed": 0, "skipped": 0, "failed": 0},
        }

    monkeypatch.setattr(ep, "get_source_by_id", _fake_get_source_by_id)
    monkeypatch.setattr(ep, "create_import_job", _fake_create_import_job)

    response = client.post("/api/v1/connectors/sources/22/sync", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source_id"] == 22
    assert body["provider"] == "onedrive"
    assert body["status"] == "queued"
    assert body["job"]["id"] == "job-123"
    assert body["job"]["type"] == "incremental_sync"
    assert queued_requests[0]["job_type"] == "incremental_sync"
