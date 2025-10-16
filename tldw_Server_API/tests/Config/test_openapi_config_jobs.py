from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


def test_openapi_includes_config_jobs(monkeypatch):
    # Ensure OpenAPI is enabled and heavy startup skipped
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("ENABLE_OPENAPI", "true")
    monkeypatch.delenv("tldw_production", raising=False)

    with TestClient(app) as client:
        res = client.get("/openapi.json")
        assert res.status_code == 200
        spec = res.json()
        assert "paths" in spec
        assert "/api/v1/config/jobs" in spec["paths"], "config/jobs path missing from OpenAPI"

        jobs_get = spec["paths"]["/api/v1/config/jobs"].get("get")
        assert jobs_get is not None, "GET operation missing for config/jobs"
        assert "tags" in jobs_get and "config" in jobs_get["tags"], "config/jobs not tagged as 'config'"
