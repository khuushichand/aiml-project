import importlib
import os

from fastapi.testclient import TestClient

# Keep module import stable in environments that set ALLOWED_ORIGINS='*'.
os.environ["ALLOWED_ORIGINS"] = "http://localhost:3000"

from tldw_Server_API.app.core import config as config_mod

def _reload_main_with_allowed_origins(allowed_origins: str = "http://localhost:3000"):
    os.environ["ALLOWED_ORIGINS"] = allowed_origins
    importlib.reload(config_mod)
    from tldw_Server_API.app import main as app_main
    return importlib.reload(app_main)


def test_openapi_includes_config_jobs(monkeypatch):
    # Ensure OpenAPI is enabled and heavy startup skipped
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("ENABLE_OPENAPI", "true")
    monkeypatch.delenv("tldw_production", raising=False)
    reloaded_main = _reload_main_with_allowed_origins()

    with TestClient(reloaded_main.app) as client:
        res = client.get("/openapi.json")
        assert res.status_code == 200
        spec = res.json()
        assert "paths" in spec
        assert "/api/v1/config/jobs" in spec["paths"], "config/jobs path missing from OpenAPI"
        assert "/api/v1/admin/config/effective" in spec["paths"], "admin/config/effective path missing from OpenAPI"

        jobs_get = spec["paths"]["/api/v1/config/jobs"].get("get")
        assert jobs_get is not None, "GET operation missing for config/jobs"
        assert "tags" in jobs_get and "config" in jobs_get["tags"], "config/jobs not tagged as 'config'"

        effective_get = spec["paths"]["/api/v1/admin/config/effective"].get("get")
        assert effective_get is not None, "GET operation missing for admin/config/effective"
        assert "tags" in effective_get and "config" in effective_get["tags"], "admin/config/effective not tagged as 'config'"


def test_openapi_cors_disallowed_origin_not_reflected(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("ENABLE_OPENAPI", "true")
    monkeypatch.delenv("tldw_production", raising=False)
    reloaded_main = _reload_main_with_allowed_origins("http://localhost:3000")

    disallowed_origin = "https://evil.example.invalid"

    with TestClient(reloaded_main.app) as client:
        res = client.get("/openapi.json", headers={"Origin": disallowed_origin})
        assert res.status_code == 200
        assert res.headers.get("access-control-allow-origin") != disallowed_origin


def test_openapi_wildcard_origin_allowed_when_credentials_disabled(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("ENABLE_OPENAPI", "true")
    monkeypatch.setenv("CORS_ALLOW_CREDENTIALS", "false")
    monkeypatch.delenv("tldw_production", raising=False)
    reloaded_main = _reload_main_with_allowed_origins("*")

    with TestClient(reloaded_main.app) as client:
        res = client.get("/openapi.json", headers={"Origin": "https://any.example.invalid"})
        assert res.status_code == 200
        assert res.headers.get("access-control-allow-origin") == "*"


def test_openapi_jobs_requeue_aliases_have_unique_operation_ids(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("ENABLE_OPENAPI", "true")
    monkeypatch.delenv("tldw_production", raising=False)
    reloaded_main = _reload_main_with_allowed_origins()

    with TestClient(reloaded_main.app) as client:
        res = client.get("/openapi.json")
        assert res.status_code == 200
        spec = res.json()

    underscore = spec["paths"]["/api/v1/jobs/batch/requeue_quarantined"]["post"]["operationId"]
    hyphen = spec["paths"]["/api/v1/jobs/batch/requeue-quarantined"]["post"]["operationId"]
    assert underscore
    assert hyphen
    assert underscore != hyphen
