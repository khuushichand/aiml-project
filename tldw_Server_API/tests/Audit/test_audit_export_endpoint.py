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

    async def _get_stub_service():
        """Return a stub audit service for dependency override.

        No parameters: FastAPI treats dependency override callables like
        dependencies and will try to resolve arguments from the request. Using
        *args/**kwargs here would cause FastAPI to require query params named
        'args' and 'kwargs', resulting in 422. Keep signature empty.
        """
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


def test_audit_export_filename_content_disposition(monkeypatch):
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

    async def _get_stub_service():
        return _StubAudit()

    client.app.dependency_overrides[audit_deps.get_audit_service_for_user] = _get_stub_service

    # JSON with filename
    r = client.get(
        "/api/v1/audit/export?format=json&filename=custom_audit.json",
        headers={"X-API-KEY": "test-api-key-12345"},
    )
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/json")
    cd = r.headers.get("content-disposition", "")
    assert "attachment" in cd.lower()
    assert "filename=custom_audit.json" in cd

    # CSV with filename
    r = client.get(
        "/api/v1/audit/export?format=csv&filename=export.csv",
        headers={"X-API-KEY": "test-api-key-12345"},
    )
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("text/csv")
    cd = r.headers.get("content-disposition", "")
    assert "attachment" in cd.lower()
    assert "filename=export.csv" in cd


def test_audit_export_parses_Z_timestamps(monkeypatch):
    client = _get_client(monkeypatch)

    # Override require_admin to pass
    from tldw_Server_API.app.api.v1.API_Deps import auth_deps
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
    client.app.dependency_overrides[get_request_user] = lambda: User(id=1, username="admin", is_active=True)
    client.app.dependency_overrides[auth_deps.require_admin] = lambda: {"role": "admin", "is_active": True, "is_verified": True}

    # Override audit service to a stub that captures parsed datetimes
    from tldw_Server_API.app.api.v1.API_Deps import Audit_DB_Deps as audit_deps
    captured = {}

    class _StubAudit:
        async def export_events(self, **kwargs):
            captured["start_time"] = kwargs.get("start_time")
            captured["end_time"] = kwargs.get("end_time")
            return "[]"

    async def _get_stub_service():
        return _StubAudit()

    client.app.dependency_overrides[audit_deps.get_audit_service_for_user] = _get_stub_service

    start_z = "2025-01-01T00:00:00Z"
    end_z = "2025-01-02T12:34:56Z"
    r = client.get(
        f"/api/v1/audit/export?format=json&start_time={start_z}&end_time={end_z}",
        headers={"X-API-KEY": "test-api-key-12345"},
    )
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/json")
    assert r.text.strip() == "[]"

    # Verify the stub received timezone-aware datetimes corresponding to UTC values
    from datetime import datetime, timezone
    assert captured.get("start_time") == datetime.fromisoformat("2025-01-01T00:00:00+00:00")
    assert captured.get("end_time") == datetime.fromisoformat("2025-01-02T12:34:56+00:00")
    assert captured["start_time"].tzinfo is not None and captured["end_time"].tzinfo is not None


def test_audit_export_streaming_json(monkeypatch):
    client = _get_client(monkeypatch)

    # Override require_admin to pass
    from tldw_Server_API.app.api.v1.API_Deps import auth_deps
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
    client.app.dependency_overrides[get_request_user] = lambda: User(id=1, username="admin", is_active=True)
    client.app.dependency_overrides[auth_deps.require_admin] = lambda: {"role": "admin", "is_active": True, "is_verified": True}

    # Override audit service to return an async generator when streaming is requested
    from tldw_Server_API.app.api.v1.API_Deps import Audit_DB_Deps as audit_deps
    captured = {"stream": None}

    class _StubAudit:
        async def export_events(self, **kwargs):
            captured["stream"] = kwargs.get("stream")

            async def _gen():
                import json as _json
                yield "["
                yield _json.dumps({"event_id": "1"})
                yield ","
                yield _json.dumps({"event_id": "2"})
                yield "]"

            if kwargs.get("stream"):
                return _gen()
            return "[]"

    async def _get_stub_service():
        return _StubAudit()

    client.app.dependency_overrides[audit_deps.get_audit_service_for_user] = _get_stub_service

    r = client.get(
        "/api/v1/audit/export?format=json&stream=true",
        headers={"X-API-KEY": "test-api-key-12345"},
    )

    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/json")
    assert "attachment" in r.headers.get("content-disposition", "").lower()
    assert r.text == "[{\"event_id\": \"1\"},{\"event_id\": \"2\"}]"
    assert captured["stream"] is True


def test_audit_export_streaming_csv_rejected(monkeypatch):
    client = _get_client(monkeypatch)

    # Override require_admin to pass
    from tldw_Server_API.app.api.v1.API_Deps import auth_deps
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
    client.app.dependency_overrides[get_request_user] = lambda: User(id=1, username="admin", is_active=True)
    client.app.dependency_overrides[auth_deps.require_admin] = lambda: {"role": "admin", "is_active": True, "is_verified": True}

    r = client.get(
        "/api/v1/audit/export?format=csv&stream=true",
        headers={"X-API-KEY": "test-api-key-12345"},
    )
    assert r.status_code == 400
    assert "Streaming is only supported for JSON" in r.text


def test_audit_export_jsonl_streaming(monkeypatch):
    client = _get_client(monkeypatch)

    # Override require_admin to pass
    from tldw_Server_API.app.api.v1.API_Deps import auth_deps
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
    client.app.dependency_overrides[get_request_user] = lambda: User(id=1, username="admin", is_active=True)
    client.app.dependency_overrides[auth_deps.require_admin] = lambda: {"role": "admin", "is_active": True, "is_verified": True}

    # Override audit service to return an async generator when streaming jsonl is requested
    from tldw_Server_API.app.api.v1.API_Deps import Audit_DB_Deps as audit_deps

    class _StubAudit:
        async def export_events(self, **kwargs):
            fmt = (kwargs.get("format") or "json").lower()
            if fmt == "jsonl" and kwargs.get("stream") and kwargs.get("file_path") is None:
                async def _gen():
                    yield '{"event_id": "1"}\n'
                    yield '{"event_id": "2"}\n'
                return _gen()
            if fmt == "jsonl":
                return '{"event_id": "1"}\n{"event_id": "2"}\n'
            return "[]"

    async def _get_stub_service():
        return _StubAudit()

    client.app.dependency_overrides[audit_deps.get_audit_service_for_user] = _get_stub_service

    r = client.get(
        "/api/v1/audit/export?format=jsonl&stream=true",
        headers={"X-API-KEY": "test-api-key-12345"},
    )

    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/x-ndjson")
    assert "attachment" in r.headers.get("content-disposition", "").lower()
    assert r.text == '{"event_id": "1"}\n{"event_id": "2"}\n'


def test_audit_export_filters_and_max_rows(monkeypatch):
    client = _get_client(monkeypatch)

    # Override require_admin to pass
    from tldw_Server_API.app.api.v1.API_Deps import auth_deps
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
    client.app.dependency_overrides[get_request_user] = lambda: User(id=1, username="admin", is_active=True)
    client.app.dependency_overrides[auth_deps.require_admin] = lambda: {"role": "admin", "is_active": True, "is_verified": True}

    # Capture kwargs passed to service
    from tldw_Server_API.app.api.v1.API_Deps import Audit_DB_Deps as audit_deps
    captured = {}

    class _StubAudit:
        async def export_events(self, **kwargs):
            captured.update(kwargs)
            return "[]"

    async def _get_stub_service():
        return _StubAudit()

    client.app.dependency_overrides[audit_deps.get_audit_service_for_user] = _get_stub_service

    qs = (
        "format=json"
        "&user_id=u1&request_id=req123&correlation_id=corr7"
        "&ip_address=10.0.0.1&session_id=sess9&endpoint=/api/x&method=GET"
        "&max_rows=42"
    )
    r = client.get(f"/api/v1/audit/export?{qs}", headers={"X-API-KEY": "test-api-key-12345"})
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/json")
    # Verify filters propagated to export_events
    assert captured.get("user_id") == "u1"
    assert captured.get("request_id") == "req123"
    assert captured.get("correlation_id") == "corr7"
    assert captured.get("ip_address") == "10.0.0.1"
    assert captured.get("session_id") == "sess9"
    assert captured.get("endpoint") == "/api/x"
    assert captured.get("method") == "GET"
    assert captured.get("max_rows") == 42
    # Non-stream path ensured
    assert captured.get("stream") in (False, None)


def test_audit_count_endpoint_filters(monkeypatch):
    client = _get_client(monkeypatch)

    # Override require_admin to pass
    from tldw_Server_API.app.api.v1.API_Deps import auth_deps
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
    client.app.dependency_overrides[get_request_user] = lambda: User(id=1, username="admin", is_active=True)
    client.app.dependency_overrides[auth_deps.require_admin] = lambda: {"role": "admin", "is_active": True, "is_verified": True}

    from tldw_Server_API.app.api.v1.API_Deps import Audit_DB_Deps as audit_deps
    captured = {}

    class _StubAudit:
        async def count_events(self, **kwargs):
            captured.update(kwargs)
            return 123

    async def _get_stub_service():
        return _StubAudit()

    client.app.dependency_overrides[audit_deps.get_audit_service_for_user] = _get_stub_service

    qs = (
        "user_id=u7&request_id=r9&correlation_id=c1&ip_address=1.2.3.4"
        "&session_id=sxy&endpoint=/api/z&method=POST&min_risk_score=50"
        "&event_type=DATA_READ,AUTH_LOGIN_SUCCESS&category=SECURITY,api_call"
    )
    r = client.get(f"/api/v1/audit/count?{qs}", headers={"X-API-KEY": "test-api-key-12345"})
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 123
    # Verify propagation
    assert captured.get("user_id") == "u7"
    assert captured.get("request_id") == "r9"
    assert captured.get("correlation_id") == "c1"
    assert captured.get("ip_address") == "1.2.3.4"
    assert captured.get("session_id") == "sxy"
    assert captured.get("endpoint") == "/api/z"
    assert captured.get("method") == "POST"
    assert captured.get("min_risk_score") == 50


def test_audit_count_integration_live(monkeypatch):
    """Integration test for /api/v1/audit/count using the real service instance.

    Creates a DI-provisioned audit service for a test user, inserts events
    via the actual UnifiedAuditService, then verifies count reflects them.
    """
    client = _get_client(monkeypatch)

    # Admin auth overrides
    from tldw_Server_API.app.api.v1.API_Deps import auth_deps
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
    user_id_int = 777
    client.app.dependency_overrides[get_request_user] = lambda: User(id=user_id_int, username="admin", is_active=True)
    client.app.dependency_overrides[auth_deps.require_admin] = lambda: {"role": "admin", "is_active": True, "is_verified": True}

    # First call to ensure the service is initialized and cached
    r0 = client.get(f"/api/v1/audit/count?user_id={user_id_int}", headers={"X-API-KEY": "test-api-key-12345"})
    assert r0.status_code == 200
    assert r0.json()["count"] in (0, int(r0.json()["count"]))  # allow 0+

    # Retrieve the real service instance from the DI cache and log events
    from tldw_Server_API.app.api.v1.API_Deps import Audit_DB_Deps as audit_deps
    from tldw_Server_API.app.core.Audit.unified_audit_service import UnifiedAuditService, AuditContext, AuditEventType
    # Try to fetch cached service; if absent, create one via helper
    with audit_deps._audit_service_lock:
        svc: UnifiedAuditService = audit_deps._user_audit_instances.get(user_id_int)  # type: ignore[attr-defined]

    import asyncio as _asyncio
    async def _ensure_and_log():
        nonlocal svc
        if svc is None:
            svc = await audit_deps._create_audit_service_for_user(user_id_int)
        await svc.log_event(
            event_type=AuditEventType.DATA_READ,
            context=AuditContext(user_id=str(user_id_int)),
            resource_type="doc", resource_id="int1",
        )
        await svc.log_event(
            event_type=AuditEventType.DATA_WRITE,
            context=AuditContext(user_id=str(user_id_int)),
            resource_type="doc", resource_id="int2",
        )
        await svc.flush()

    _asyncio.run(_ensure_and_log())

    # Count again; should be >= 2 for this user
    r1 = client.get(f"/api/v1/audit/count?user_id={user_id_int}", headers={"X-API-KEY": "test-api-key-12345"})
    assert r1.status_code == 200
    assert r1.json()["count"] >= 2


def test_audit_export_filename_extension_normalization(monkeypatch):
    client = _get_client(monkeypatch)

    # Override require_admin to pass
    from tldw_Server_API.app.api.v1.API_Deps import auth_deps
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
    client.app.dependency_overrides[get_request_user] = lambda: User(id=1, username="admin", is_active=True)
    client.app.dependency_overrides[auth_deps.require_admin] = lambda: {"role": "admin", "is_active": True, "is_verified": True}

    from tldw_Server_API.app.api.v1.API_Deps import Audit_DB_Deps as audit_deps

    class _StubAudit:
        async def export_events(self, **kwargs):
            fmt = (kwargs.get("format") or "json").lower()
            if fmt == "csv":
                return "event_id,timestamp\n1,2025-01-01T00:00:00Z\n"
            return "[]"

    async def _get_stub_service():
        return _StubAudit()

    client.app.dependency_overrides[audit_deps.get_audit_service_for_user] = _get_stub_service

    # Ask for CSV but pass a .json filename; expect .csv
    r = client.get(
        "/api/v1/audit/export?format=csv&filename=my_export.json",
        headers={"X-API-KEY": "test-api-key-12345"},
    )
    cd = r.headers.get("content-disposition", "")
    assert "filename=my_export.csv" in cd

    # Ask for JSON but pass a .txt filename; expect .json
    r = client.get(
        "/api/v1/audit/export?format=json&filename=report.txt",
        headers={"X-API-KEY": "test-api-key-12345"},
    )
    cd = r.headers.get("content-disposition", "")
    assert "filename=report.json" in cd
