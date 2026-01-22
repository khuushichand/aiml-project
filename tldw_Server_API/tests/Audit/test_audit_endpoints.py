import pytest

from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import get_audit_service_for_user


class _StubAuditService:
    async def export_events(self, **_kwargs):
        return "[]"

    async def count_events(self, **_kwargs):
        return 0


@pytest.mark.usefixtures("client_user_only")
def test_audit_export_rejects_invalid_event_type(client_user_only):
    async def _override_audit_service(current_user=None):
        return _StubAuditService()

    app = client_user_only.app
    app.dependency_overrides[get_audit_service_for_user] = _override_audit_service
    try:
        resp = client_user_only.get(
            "/api/v1/audit/export",
            params={"event_type": "not.a.valid.type"},
        )
        assert resp.status_code == 400
        assert "Invalid event_type" in resp.json().get("detail", "")
    finally:
        app.dependency_overrides.pop(get_audit_service_for_user, None)


@pytest.mark.usefixtures("client_user_only")
def test_audit_count_rejects_invalid_category(client_user_only):
    async def _override_audit_service(current_user=None):
        return _StubAuditService()

    app = client_user_only.app
    app.dependency_overrides[get_audit_service_for_user] = _override_audit_service
    try:
        resp = client_user_only.get(
            "/api/v1/audit/count",
            params={"category": "not_a_category"},
        )
        assert resp.status_code == 400
        assert "Invalid category" in resp.json().get("detail", "")
    finally:
        app.dependency_overrides.pop(get_audit_service_for_user, None)
