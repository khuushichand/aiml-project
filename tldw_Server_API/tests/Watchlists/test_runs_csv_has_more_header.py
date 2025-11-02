import os
from pathlib import Path
import json

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.DB_Management.Watchlists_DB import WatchlistsDatabase
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


pytestmark = pytest.mark.integration


@pytest.fixture()
def client_with_user(monkeypatch):
    async def override_user():
        return User(id=910, username="wluser", email=None, is_active=True)

    base_dir = Path.cwd() / "Databases" / "test_user_dbs_runs_csv_has_more"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    monkeypatch.setenv("TEST_MODE", "1")

    # Fresh DB for this user id
    try:
        base_env = os.environ.get("USER_DB_BASE_DIR")
        user_db_base = Path(base_env) if base_env else (Path.cwd() / "Databases" / "user_databases")
        user_db_path = user_db_base / "910" / "Media_DB_v2.db"
        if user_db_path.exists():
            user_db_path.unlink()
    except Exception:
        pass

    from fastapi import FastAPI
    from tldw_Server_API.app.core.config import API_V1_PREFIX
    from tldw_Server_API.app.api.v1.endpoints.watchlists import router as watchlists_router

    app = FastAPI()
    app.include_router(watchlists_router, prefix=f"{API_V1_PREFIX}")
    app.dependency_overrides[get_request_user] = override_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _seed_run_with_stats(job_id: int, stats: dict) -> int:
    db = WatchlistsDatabase.for_user(910)
    run = db.create_run(job_id, status="finished")
    db.update_run(run.id, status="finished", stats_json=json.dumps(stats))
    return run.id


def test_global_runs_csv_sets_has_more_header_when_paginated(client_with_user: TestClient):
    c = client_with_user
    # Create a source/job and two runs so page=1,size=1 has more
    s = c.post(
        "/api/v1/watchlists/sources",
        json={"name": "FeedHM", "url": "https://example.com/hm.csv.xml", "source_type": "rss"},
    )
    assert s.status_code == 200, s.text
    j = c.post(
        "/api/v1/watchlists/jobs",
        json={"name": "JobHM", "scope": {"sources": [s.json()["id"]]}},
    )
    assert j.status_code == 200, j.text
    jid = j.json()["id"]

    _ = _seed_run_with_stats(jid, {"items_found": 1, "items_ingested": 1})
    _ = _seed_run_with_stats(jid, {"items_found": 2, "items_ingested": 1})

    r = c.get(
        "/api/v1/watchlists/runs/export.csv",
        params={"scope": "global", "page": 1, "size": 1},
    )
    assert r.status_code == 200, r.text
    assert r.headers.get("X-Has-More") == "true"
