from fastapi.testclient import TestClient
import pytest


def _get_client(monkeypatch):
    # Ensure test-friendly startup
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("DISABLE_HEAVY_STARTUP", "1")
    from tldw_Server_API.app.main import app
    return TestClient(app)


def test_audit_export_requires_admin(monkeypatch):
    client = _get_client(monkeypatch)

    # Override require_admin to deny
    from tldw_Server_API.app.api.v1.API_Deps import auth_deps
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
    # Avoid auth 401 from get_request_user by overriding to a dummy user
    client.app.dependency_overrides[get_request_user] = lambda: User(id=1, username="tester", is_active=True)

    async def _deny():
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    client.app.dependency_overrides[auth_deps.require_admin] = _deny

    r = client.get("/api/v1/audit/export", headers={"X-API-KEY": "test-api-key-12345"})
    assert r.status_code == 403
    assert "Admin access required" in r.text


def test_audit_export_allows_admin_and_returns_payload(monkeypatch):
    client = _get_client(monkeypatch)

    # Override require_admin to pass
    from tldw_Server_API.app.api.v1.API_Deps import auth_deps
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
    client.app.dependency_overrides[get_request_user] = lambda: User(id=1, username="admin", is_active=True)
    client.app.dependency_overrides[auth_deps.require_admin] = lambda: {"role": "admin", "is_active": True, "is_verified": True}

    # Override audit service to a stub
    from tldw_Server_API.app.api.v1.API_Deps import Audit_DB_Deps as audit_deps

    class _StubAudit:
        async def export_events(self, **kwargs):
            fmt = (kwargs.get("format") or "json").lower()
            if fmt == "csv":
                return "event_id,timestamp\n1,2025-01-01T00:00:00Z\n"
            return "[]"

    async def _get_stub_service(*args, **kwargs):
        return _StubAudit()

    client.app.dependency_overrides[audit_deps.get_audit_service_for_user] = _get_stub_service

    # JSON
    r = client.get("/api/v1/audit/export?format=json", headers={"X-API-KEY": "test-api-key-12345"})
    try:
        print("JSON export response:", r.status_code, r.json())
    except Exception:
        print("JSON export response (raw):", r.status_code, r.text)
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/json")
    assert r.text.strip() == "[]"
    assert "attachment" in r.headers.get("content-disposition", "").lower()

    # CSV
    r = client.get("/api/v1/audit/export?format=csv", headers={"X-API-KEY": "test-api-key-12345"})
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("text/csv")
    assert r.text.splitlines()[0].startswith("event_id,")
    assert "attachment" in r.headers.get("content-disposition", "").lower()
