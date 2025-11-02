import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


class _FakeProviderManager:
    def get_health_report(self):
        return {
            'openai': {
                'status': 'healthy',
                'success_count': 42,
                'failure_count': 3,
                'consecutive_failures': 0,
                'average_response_time': 0.101,
                'circuit_breaker_state': 'CLOSED',
                'last_success': 123.0,
                'last_failure': None,
            }
        }


@pytest.mark.unit
def test_provider_details_includes_capabilities_and_health(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "true")
    with TestClient(app) as client:
        with patch("tldw_Server_API.app.api.v1.endpoints.llm_providers.get_provider_manager", return_value=_FakeProviderManager()):
            # First call list to ensure providers exist and health is attached
            lst = client.get("/api/v1/llm/providers").json()
            assert 'providers' in lst
            # Now details
            resp = client.get("/api/v1/llm/providers/openai")
            assert resp.status_code == 200
            detail = resp.json()
            assert 'capabilities' in detail and isinstance(detail['capabilities'], dict)
            assert 'requires_api_key' in detail
            # health should be present due to injection from manager
            assert 'health' in detail
            assert detail['health'].get('status') in ('healthy', 'degraded', 'unhealthy', 'circuit_open', 'CLOSED', 'OPEN', 'HALF_OPEN')
