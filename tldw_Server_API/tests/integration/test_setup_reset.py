from fastapi.testclient import TestClient
from fastapi import HTTPException

from tldw_Server_API.app.main import app
import tldw_Server_API.app.api.v1.endpoints.setup as setup_endpoint
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import require_admin


def _make_client():
    return TestClient(app)


def test_admin_reset_calls_reset_flags(mocker):
    # Override admin requirement
    app.dependency_overrides[require_admin] = lambda: {"role": "admin", "is_active": True, "is_verified": True}

    called = {"count": 0}
    def fake_reset():
        called["count"] += 1

    mocker.patch.object(setup_endpoint.setup_manager, 'reset_setup_flags', side_effect=fake_reset)

    with _make_client() as client:
        resp = client.post('/api/v1/setup/reset')

    # Cleanup override
    app.dependency_overrides.pop(require_admin, None)

    assert resp.status_code == 200
    assert called["count"] == 1
    body = resp.json()
    assert body.get('success') is True
    assert body.get('requires_restart') is True
