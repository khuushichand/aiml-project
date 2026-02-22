import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.config import API_V1_PREFIX


pytestmark = pytest.mark.unit


@pytest.fixture()
def client_with_user(monkeypatch, tmp_path):
    async def override_user():
        return User(id=913, username="wl-truth", email=None, is_active=True)

    base_dir = tmp_path / "watchlists_truthiness_dbs"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    monkeypatch.setenv("TEST_MODE", "0")
    monkeypatch.setenv("TLDW_TEST_MODE", "0")
    monkeypatch.delenv("WATCHLIST_FORUMS_ENABLED", raising=False)

    from tldw_Server_API.app.api.v1.endpoints.watchlists import router as watchlists_router

    app = FastAPI()
    app.include_router(watchlists_router, prefix=f"{API_V1_PREFIX}")
    app.dependency_overrides[get_request_user] = override_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_source_test_endpoint_accepts_tldw_test_mode_y(client_with_user, monkeypatch):
    monkeypatch.setenv("TEST_MODE", "0")
    monkeypatch.setenv("TLDW_TEST_MODE", "y")

    r = client_with_user.post(
        "/api/v1/watchlists/sources",
        json={"name": "Site", "url": "https://example.com/", "source_type": "site"},
    )
    assert r.status_code == 200, r.text
    source_id = r.json()["id"]

    preview = client_with_user.post(f"/api/v1/watchlists/sources/{source_id}/test", params={"limit": 3})
    assert preview.status_code == 200, preview.text
    payload = preview.json()
    assert payload["total"] >= 1
    assert payload["ingestable"] == payload["total"]


def test_forum_sources_enabled_flag_accepts_y(client_with_user, monkeypatch):
    monkeypatch.setenv("WATCHLIST_FORUMS_ENABLED", "y")

    r = client_with_user.post(
        "/api/v1/watchlists/sources",
        json={"name": "Forum", "url": "https://forum.example.com/", "source_type": "forum"},
    )
    assert r.status_code == 200, r.text
