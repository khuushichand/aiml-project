import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


class _FakeProviderManager:
    def get_health_report(self):
        return {
            'openai': {
                'status': 'healthy',
                'success_count': 10,
                'failure_count': 1,
                'consecutive_failures': 0,
                'average_response_time': 0.12,
                'circuit_breaker_state': 'CLOSED',
                'last_success': 123.0,
                'last_failure': None,
            }
        }


@pytest.mark.unit
def test_llm_providers_includes_health(monkeypatch):
    # Force TEST_MODE to ensure deterministic behavior
    monkeypatch.setenv("TEST_MODE", "true")

    with TestClient(app) as client:
        with patch("tldw_Server_API.app.api.v1.endpoints.llm_providers.get_provider_manager", return_value=_FakeProviderManager()):
            resp = client.get("/api/v1/llm/providers")
            assert resp.status_code == 200
            data = resp.json()
            assert 'providers' in data
            # Find openai entry; health should be attached
            openai = next((p for p in data['providers'] if p.get('name') == 'openai'), None)
            assert openai is not None
            assert 'health' in openai
            assert openai['health']['status'] in ('healthy', 'degraded', 'unhealthy', 'circuit_open', 'CLOSED', 'OPEN', 'HALF_OPEN')
