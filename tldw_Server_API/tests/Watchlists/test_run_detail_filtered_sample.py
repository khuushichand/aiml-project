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
        return User(id=915, username="wluser", email=None, is_active=True)

    base_dir = Path.cwd() / "Databases" / "test_user_dbs_run_detail_filtered_sample"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
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


def _seed_run_with_filtered_items(user_id: int, *, filtered_count: int = 4) -> int:
    db = WatchlistsDatabase.for_user(user_id)
    # Create minimal source and job
    src = db.create_source(name="S", url="https://example.com/", source_type="site", active=True, settings_json=None, tags=None, group_ids=None)
    scope = {"sources": [src.id]}
    job = db.create_job(
        name="J",
        description=None,
        scope_json=json.dumps(scope),
        schedule_expr=None,
        schedule_timezone=None,
        active=True,
        max_concurrency=None,
        per_host_delay_ms=None,
        retry_policy_json=None,
        output_prefs_json=None,
        job_filters_json=None,
    )
    run = db.create_run(job.id, status="finished")
    # Insert some filtered items and a couple of ingested ones
    for i in range(filtered_count):
        db.record_scraped_item(
            run_id=run.id,
            job_id=job.id,
            source_id=src.id,
            media_id=None,
            media_uuid=None,
            url=f"https://example.com/item{i}",
            title=f"Item {i}",
            summary=None,
            published_at=None,
            tags=None,
            status="filtered",
        )
    for j in range(2):
        db.record_scraped_item(
            run_id=run.id,
            job_id=job.id,
            source_id=src.id,
            media_id=None,
            media_uuid=None,
            url=f"https://example.com/ing{j}",
            title=f"Ingested {j}",
            summary=None,
            published_at=None,
            tags=None,
            status="ingested",
        )
    return run.id


def test_run_detail_filtered_sample_toggle(client_with_user: TestClient):
    c = client_with_user
    run_id = _seed_run_with_filtered_items(915, filtered_count=5)

    # With filtered_sample_max = 0 → no sample (omitted or null)
    r0 = c.get(f"/api/v1/watchlists/runs/{run_id}/details", params={"filtered_sample_max": 0})
    assert r0.status_code == 200, r0.text
    data0 = r0.json()
    if "filtered_sample" in data0:
        assert not data0["filtered_sample"]

    # With filtered_sample_max > 0 → expect up to N items
    r = c.get(f"/api/v1/watchlists/runs/{run_id}/details", params={"filtered_sample_max": 3})
    assert r.status_code == 200, r.text
    data = r.json()
    assert "filtered_sample" in data
    assert isinstance(data["filtered_sample"], list)
    assert 1 <= len(data["filtered_sample"]) <= 3
    # Sample rows contain id/url/title/status
    row = data["filtered_sample"][0]
    assert "id" in row and "status" in row
    assert row["status"] == "filtered"
