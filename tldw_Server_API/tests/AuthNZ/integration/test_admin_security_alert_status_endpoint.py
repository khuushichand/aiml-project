import pytest

from tldw_Server_API.tests.AuthNZ.integration.test_rbac_admin_endpoints import _admin_headers

pytestmark = pytest.mark.integration


def test_admin_security_alert_status_endpoint(isolated_test_environment):
    client, db_name = isolated_test_environment
    headers = _admin_headers(client, db_name)

    response = client.get("/api/v1/admin/security/alert-status", headers=headers)
    assert response.status_code == 200, response.text
    payload = response.json()

    assert "health" in payload
    assert "sinks" in payload and isinstance(payload["sinks"], list)
    for sink in payload["sinks"]:
        assert {"sink", "configured", "min_severity", "last_status", "last_error"}.issubset(sink.keys())
