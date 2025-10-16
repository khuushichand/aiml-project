import os

from fastapi.testclient import TestClient


def test_config_jobs_endpoint_shape(monkeypatch):
    # Force test mode to avoid heavy startup
    monkeypatch.setenv("TEST_MODE", "true")
    # Reset settings and import app after env is set
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    reset_settings()
    from tldw_Server_API.app.main import app

    with TestClient(app) as client:
        r = client.get("/api/v1/config/jobs")
        assert r.status_code == 200
        data = r.json()
        # Required top-level keys
        assert "backend" in data
        assert data["backend"] in ("sqlite", "postgres")
        assert "configured" in data
        assert "flags" in data and isinstance(data["flags"], dict)
        flags = data["flags"]
        for k in ("JOBS_LEASE_SECONDS", "JOBS_LEASE_RENEW_SECONDS", "JOBS_LEASE_RENEW_JITTER_SECONDS", "JOBS_LEASE_MAX_SECONDS"):
            assert k in flags
            assert isinstance(flags[k], int)
        # Ensure no secrets/DSN are exposed
        s = str(data)
        assert "JOBS_DB_URL" not in s
        assert "postgresql://" not in s
        assert "password" not in s.lower()
