from __future__ import annotations

from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


def _get_user_id(client: TestClient, auth_headers) -> int:
    resp = client.get("/api/v1/users/me/profile", headers=auth_headers)
    assert resp.status_code == 200
    return resp.json()["user"]["id"]


def test_admin_user_profile_batch(auth_headers) -> None:
    with TestClient(app) as client:
        user_id = _get_user_id(client, auth_headers)
        resp = client.get(
            "/api/v1/admin/users/profile",
            params={"user_ids": str(user_id)},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        payload = resp.json()

    assert payload["total"] == 1
    assert len(payload.get("profiles", [])) == 1
    profile = payload["profiles"][0]
    assert profile.get("user", {}).get("id") == user_id
    assert "quotas" in profile
    assert "memberships" in profile
