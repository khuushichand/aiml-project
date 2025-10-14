import os

from fastapi.testclient import TestClient


def _set_env(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    # Remove API key so settings provides deterministic test key
    monkeypatch.delenv("SINGLE_USER_API_KEY", raising=False)
    # Force domain-scoped RBAC path even in single-user mode
    monkeypatch.setenv("JOBS_DOMAIN_SCOPED_RBAC", "true")
    monkeypatch.setenv("JOBS_RBAC_FORCE", "true")
    monkeypatch.setenv("JOBS_REQUIRE_DOMAIN_FILTER", "true")


def test_rbac_requires_domain_filter_and_allowlist(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _set_env(monkeypatch)

    from tldw_Server_API.app.core.AuthNZ.settings import get_settings, reset_settings
    reset_settings()
    from tldw_Server_API.app.main import app
    # Ensure no leaked dependency overrides from other tests
    try:
        app.dependency_overrides.clear()
    except Exception:
        pass

    headers = {"X-API-KEY": get_settings().SINGLE_USER_API_KEY}
    with TestClient(app, headers=headers) as client:
        # Missing domain should be rejected when required
        r = client.get("/api/v1/jobs/stats")
        assert r.status_code == 403

        # Domain provided but not in allowlist -> 403
        # Single-user id defaults to 1, configure allowlist for id=1 to only chatbooks
        monkeypatch.setenv("JOBS_DOMAIN_ALLOWLIST_1", "chatbooks")
        r2 = client.get("/api/v1/jobs/stats", params={"domain": "other"})
        assert r2.status_code == 403

        # Allowed domain -> 200
        r3 = client.get("/api/v1/jobs/stats", params={"domain": "chatbooks"})
        assert r3.status_code == 200

        # TTL sweep without domain -> 403
        r4 = client.post("/api/v1/jobs/ttl/sweep", json={"age_seconds": 60, "action": "cancel"})
        assert r4.status_code == 403

        # TTL sweep with disallowed domain -> 403
        r5 = client.post("/api/v1/jobs/ttl/sweep", json={"age_seconds": 60, "action": "cancel", "domain": "other"})
        assert r5.status_code == 403

        # TTL sweep with allowed domain -> 200 (may affect 0 rows)
        r6 = client.post("/api/v1/jobs/ttl/sweep", json={"age_seconds": 60, "action": "cancel", "domain": "chatbooks"})
        assert r6.status_code == 200

        # Prune must include domain -> 403
        body = {"statuses": ["completed"], "older_than_days": 30, "dry_run": True}
        rp1 = client.post("/api/v1/jobs/prune", json=body)
        assert rp1.status_code == 403
        # With disallowed domain -> 403
        body2 = {"statuses": ["completed"], "older_than_days": 30, "dry_run": True, "domain": "other"}
        rp2 = client.post("/api/v1/jobs/prune", json=body2)
        assert rp2.status_code == 403
        # Allowed domain -> 200
        body3 = {"statuses": ["completed"], "older_than_days": 30, "dry_run": True, "domain": "chatbooks"}
        rp3 = client.post("/api/v1/jobs/prune", json=body3)
        assert rp3.status_code == 200
