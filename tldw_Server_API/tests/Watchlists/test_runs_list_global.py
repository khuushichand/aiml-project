from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


pytestmark = pytest.mark.integration


def _build_app(override_user):
    from fastapi import FastAPI
    from tldw_Server_API.app.core.config import API_V1_PREFIX
    from tldw_Server_API.app.api.v1.endpoints.watchlists import router as watchlists_router
    app = FastAPI()
    app.include_router(watchlists_router, prefix=f"{API_V1_PREFIX}")
    app.dependency_overrides[get_request_user] = override_user
    return app


def test_runs_list_q_search_pagination_and_isolation(monkeypatch):
    base_dir = Path.cwd() / "Databases" / "test_user_dbs_runs_global"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    monkeypatch.setenv("TEST_MODE", "1")

    async def override_user_a():
        return User(id=910, username="userA", email=None, is_active=True)

    async def override_user_b():
        return User(id=911, username="userB", email=None, is_active=True)

    # Client A creates two sources, a job, and triggers two runs
    app_a = _build_app(override_user_a)
    with TestClient(app_a) as ca:
        s1 = ca.post("/api/v1/watchlists/sources", json={"name": "A1", "url": "https://example.com/a1.xml", "source_type": "rss"})
        assert s1.status_code == 200, s1.text
        s2 = ca.post("/api/v1/watchlists/sources", json={"name": "A2", "url": "https://example.com/a2.xml", "source_type": "rss"})
        assert s2.status_code == 200, s2.text
        j = ca.post(
            "/api/v1/watchlists/jobs",
            json={"name": "Job Alpha", "scope": {"sources": [s1.json()["id"], s2.json()["id"]]}, "active": True},
        )
        assert j.status_code == 200, j.text
        jid = j.json()["id"]
        r1 = ca.post(f"/api/v1/watchlists/jobs/{jid}/run")
        assert r1.status_code == 200, r1.text
        r2 = ca.post(f"/api/v1/watchlists/jobs/{jid}/run")
        assert r2.status_code == 200, r2.text

        # Global runs list with q matching job name
        lg = ca.get("/api/v1/watchlists/runs", params={"q": "Alpha", "page": 1, "size": 1})
        assert lg.status_code == 200, lg.text
        data = lg.json()
        assert data["total"] >= 2
        assert len(data["items"]) == 1  # page size 1

        # Next page should also have 1 item until exhausted
        lg2 = ca.get("/api/v1/watchlists/runs", params={"q": "Alpha", "page": 2, "size": 1})
        assert lg2.status_code == 200
        assert len(lg2.json()["items"]) == 1

        # Query by status
        by_status = ca.get("/api/v1/watchlists/runs", params={"q": "running"})
        assert by_status.status_code == 200
        # Depending on pipeline timing, latest may be finished; ensure response shape OK
        assert "items" in by_status.json()

    # Client B should not see A's runs (isolation)
    app_b = _build_app(override_user_b)
    with TestClient(app_b) as cb:
        glb = cb.get("/api/v1/watchlists/runs", params={"q": "Alpha"})
        assert glb.status_code == 200
        assert glb.json()["total"] == 0
        assert glb.json()["items"] == []
