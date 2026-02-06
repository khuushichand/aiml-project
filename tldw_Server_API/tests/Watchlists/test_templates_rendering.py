import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


pytestmark = pytest.mark.integration


@pytest.fixture()
def client_with_user(monkeypatch, tmp_path):
    async def override_user():
        return User(id=944, username="wluser", email="wl@example.com", is_active=True)

    base_dir = tmp_path / "test_user_dbs_template_rendering"
    base_dir.mkdir(parents=True, exist_ok=True)
    template_dir = tmp_path / "watchlist_templates"
    template_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    monkeypatch.setenv("WATCHLIST_TEMPLATE_DIR", str(template_dir))
    monkeypatch.setenv("TEST_MODE", "1")

    from fastapi import FastAPI
    from tldw_Server_API.app.core.config import API_V1_PREFIX
    from tldw_Server_API.app.api.v1.endpoints.watchlists import router as watchlists_router

    app = FastAPI()
    app.include_router(watchlists_router, prefix=f"{API_V1_PREFIX}")
    app.dependency_overrides[get_request_user] = override_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _create_run(c: TestClient) -> int:
    source = c.post(
        "/api/v1/watchlists/sources",
        json={"name": "Feed", "url": "https://example.com/rss.xml", "source_type": "rss"},
    )
    assert source.status_code == 200, source.text
    source_id = source.json()["id"]

    job = c.post(
        "/api/v1/watchlists/jobs",
        json={"name": "Digest", "scope": {"sources": [source_id]}, "active": True},
    )
    assert job.status_code == 200, job.text
    job_id = job.json()["id"]

    run = c.post(f"/api/v1/watchlists/jobs/{job_id}/run")
    assert run.status_code == 200, run.text
    return run.json()["id"]


def test_watchlists_template_versions_and_render_selection(client_with_user: TestClient):
    c = client_with_user
    run_id = _create_run(c)

    first_payload = {
        "name": "daily_md",
        "format": "md",
        "content": "V1 {{ title }}",
        "description": "First draft",
    }
    r = c.post("/api/v1/watchlists/templates", json=first_payload)
    assert r.status_code == 200, r.text
    created = r.json()
    assert created["version"] == 1
    assert created["history_count"] == 0

    second_payload = {
        "name": "daily_md",
        "format": "md",
        "content": "V2 {{ title }}",
        "description": "Second draft",
        "overwrite": True,
    }
    r = c.post("/api/v1/watchlists/templates", json=second_payload)
    assert r.status_code == 200, r.text
    updated = r.json()
    assert updated["version"] == 2
    assert updated["history_count"] == 1
    assert updated["available_versions"] == [1, 2]

    r = c.get("/api/v1/watchlists/templates/daily_md")
    assert r.status_code == 200, r.text
    latest = r.json()
    assert latest["version"] == 2
    assert latest["content"].startswith("V2")

    r = c.get("/api/v1/watchlists/templates/daily_md", params={"version": 1})
    assert r.status_code == 200, r.text
    v1 = r.json()
    assert v1["version"] == 1
    assert v1["content"].startswith("V1")

    r = c.get("/api/v1/watchlists/templates/daily_md/versions")
    assert r.status_code == 200, r.text
    versions = r.json()["items"]
    assert [item["version"] for item in versions] == [1, 2]
    assert versions[-1]["is_current"] is True

    r = c.post(
        "/api/v1/watchlists/outputs",
        json={"run_id": run_id, "template_name": "daily_md", "template_version": 1, "temporary": True},
    )
    assert r.status_code == 200, r.text
    output = r.json()
    assert output["metadata"]["template_name"] == "daily_md"
    assert output["metadata"]["template_source"] == "watchlists_templates"
    assert output["metadata"]["template_version"] == 1
    assert output["content"].startswith("V1")

