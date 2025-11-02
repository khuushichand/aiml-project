import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


class _FakeProviderManager:
    def get_health_report(self):
        return {}


@pytest.mark.unit
def test_llm_providers_includes_diagnostics_ui(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "true")
    with TestClient(app) as client:
        # Patch provider manager to avoid relying on background tasks
        with patch("tldw_Server_API.app.api.v1.endpoints.llm_providers.get_provider_manager", return_value=_FakeProviderManager()):
            resp = client.get("/api/v1/llm/providers")
            assert resp.status_code == 200
            data = resp.json()
            # diagnostics_ui should be present with interval bounds
            assert 'diagnostics_ui' in data
            ui = data['diagnostics_ui']
            assert 'queue_status_auto' in ui and 'queue_activity_auto' in ui
            qs = ui['queue_status_auto']
            qa = ui['queue_activity_auto']
            assert isinstance(qs.get('min'), int) and isinstance(qs.get('max'), int)
            assert isinstance(qa.get('min'), int) and isinstance(qa.get('max'), int)
            assert qs['min'] >= 1 and qs['max'] >= qs['min']
            assert qa['min'] >= 1 and qa['max'] >= qa['min']
