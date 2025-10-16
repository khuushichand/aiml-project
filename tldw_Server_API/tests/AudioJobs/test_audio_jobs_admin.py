import pytest
from fastapi.testclient import TestClient


def _admin_headers():
    # In single-user test mode, admin can be the same API key; tests elsewhere use X-API-KEY or Bearer
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings
    s = get_settings()
    return {"X-API-KEY": s.SINGLE_USER_API_KEY}


def test_audio_tiers_admin_get_set():
    from tldw_Server_API.app.main import app
    with TestClient(app) as client:
        # Get tier (default free)
        r = client.get("/api/v1/audio/jobs/admin/tiers/123", headers=_admin_headers())
        if r.status_code == 404:
            pytest.skip("audio jobs admin endpoints not mounted")
        assert r.status_code == 200
        assert r.json().get("tier") in {"free", "standard", "premium"}
        # Set tier to standard
        r2 = client.put("/api/v1/audio/jobs/admin/tiers/123", json={"tier": "standard"}, headers=_admin_headers())
        assert r2.status_code == 200
        assert r2.json().get("tier") == "standard"
        # Verify round-trip
        r3 = client.get("/api/v1/audio/jobs/admin/tiers/123", headers=_admin_headers())
        assert r3.status_code == 200
        assert r3.json().get("tier") == "standard"


def test_audio_jobs_admin_summaries_smoke():
    from tldw_Server_API.app.main import app
    with TestClient(app) as client:
        r = client.get("/api/v1/audio/jobs/admin/summary", headers=_admin_headers())
        assert r.status_code == 200
        r2 = client.get("/api/v1/audio/jobs/admin/summary-by-owner", headers=_admin_headers())
        if r2.status_code == 404:
            pytest.skip("audio jobs admin endpoints not mounted")
        assert r2.status_code == 200
