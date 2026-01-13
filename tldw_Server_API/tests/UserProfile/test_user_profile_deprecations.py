from __future__ import annotations

from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


def test_users_me_deprecation_headers(auth_headers) -> None:
    with TestClient(app) as client:
        resp = client.get("/api/v1/users/me", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.headers.get("Deprecation") == "true"
        assert resp.headers.get("Sunset")
        assert resp.headers.get("Link") == "</api/v1/users/me/profile>; rel=successor-version"
        payload = resp.json()
        assert payload.get("warning") == "deprecated_endpoint"
        assert payload.get("successor") == "/api/v1/users/me/profile"


def test_auth_me_deprecation_headers(auth_headers) -> None:
    with TestClient(app) as client:
        resp = client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.headers.get("Deprecation") == "true"
        assert resp.headers.get("Sunset")
        assert resp.headers.get("Link") == "</api/v1/users/me/profile>; rel=successor-version"
        payload = resp.json()
        assert payload.get("warning") == "deprecated_endpoint"
        assert payload.get("successor") == "/api/v1/users/me/profile"


def test_legacy_me_endpoints_disabled(auth_headers, monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_LEGACY_USER_ME_ENDPOINTS", "false")
    with TestClient(app) as client:
        resp = client.get("/api/v1/users/me", headers=auth_headers)
        assert resp.status_code == 410
        payload = resp.json()
        assert payload.get("warning") == "deprecated_endpoint"
        assert payload.get("successor") == "/api/v1/users/me/profile"

        resp = client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 410
        payload = resp.json()
        assert payload.get("warning") == "deprecated_endpoint"
        assert payload.get("successor") == "/api/v1/users/me/profile"
