import pytest
from fastapi.testclient import TestClient


def _admin_headers():
    # In single-user test mode, admin can be the same API key; tests elsewhere use X-API-KEY or Bearer
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings

    settings = get_settings()
    return {"X-API-KEY": settings.SINGLE_USER_API_KEY}


def test_audio_tiers_admin_get_set():
    from tldw_Server_API.app.main import app

    with TestClient(app) as client:
        # Get tier (default free)
        r = client.get("/api/v1/audio/jobs/admin/tiers/123", headers=_admin_headers())
        if r.status_code == 404:
            pytest.skip("audio jobs admin endpoints not mounted")
        if r.status_code == 429:
            pytest.skip("audio jobs admin endpoints rate-limited by ResourceGovernor")
        assert r.status_code == 200
        assert r.json().get("tier") in {"free", "standard", "premium"}

        # Set tier to standard
        r2 = client.put(
            "/api/v1/audio/jobs/admin/tiers/123",
            json={"tier": "standard"},
            headers=_admin_headers(),
        )
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
        if r.status_code == 404:
            pytest.skip("audio jobs admin endpoints not mounted")
        if r.status_code == 429:
            pytest.skip("audio jobs admin summary endpoint rate-limited by ResourceGovernor")
        assert r.status_code == 200
        body = r.json()
        assert "counts_by_status" in body
        assert "total" in body

        r2 = client.get("/api/v1/audio/jobs/admin/summary-by-owner", headers=_admin_headers())
        if r2.status_code == 404:
            pytest.skip("audio jobs admin endpoints not mounted")
        if r2.status_code == 429:
            pytest.skip("audio jobs admin summary-by-owner endpoint rate-limited by ResourceGovernor")
        assert r2.status_code == 200
        body2 = r2.json()
        assert "items" in body2


def test_audio_jobs_admin_list_and_processing_and_auth():
    from tldw_Server_API.app.main import app

    with TestClient(app) as client:
        # Submit a job as admin to ensure there is at least one audio job
        submit_resp = client.post(
            "/api/v1/audio/jobs/submit",
            json={"url": "https://example.com/audio.mp3", "model": "whisper-1"},
            headers=_admin_headers(),
        )
        if submit_resp.status_code == 404:
            pytest.skip("audio jobs endpoints not mounted")
        if submit_resp.status_code == 429:
            pytest.skip("audio jobs submit endpoint rate-limited by ResourceGovernor")
        assert submit_resp.status_code == 200

        # Admin list should succeed and return a jobs array
        list_resp = client.get("/api/v1/audio/jobs/admin/list", headers=_admin_headers())
        if list_resp.status_code == 429:
            pytest.skip("audio jobs admin list endpoint rate-limited by ResourceGovernor")
        assert list_resp.status_code == 200
        body = list_resp.json()
        assert "jobs" in body
        assert isinstance(body["jobs"], list)

        # Owner processing summary should succeed for an arbitrary owner id
        ops_resp = client.get(
            "/api/v1/audio/jobs/admin/owner/123/processing",
            headers=_admin_headers(),
        )
        if ops_resp.status_code == 429:
            pytest.skip("audio jobs admin owner/processing endpoint rate-limited by ResourceGovernor")
        assert ops_resp.status_code == 200
        ops_body = ops_resp.json()
        assert "owner_user_id" in ops_body
        assert "processing" in ops_body

        # Without auth, admin endpoints should not be accessible
        unauth_resp = client.get("/api/v1/audio/jobs/admin/list")
        assert unauth_resp.status_code in (401, 403, 429)
