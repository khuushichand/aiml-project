"""Operational limits boundary tests for Watchlists API.

Validates that Pydantic Query(le=…) constraints and business-rule gating
produce the expected 422/400/403 rejections, and that normal workflows are
unaffected.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.Watchlists_DB import WatchlistsDatabase


pytestmark = pytest.mark.unit

USER_DB_BASE_DIR_NAME = "test_user_dbs_op_limits"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_minimal_dataset(user_id: int) -> dict:
    """Create 1 source + 1 job + 1 run — enough for routing to succeed."""
    db = WatchlistsDatabase.for_user(user_id)
    db.ensure_schema()
    unique = uuid4().hex[:8]
    src = db.create_source(
        name=f"OpLim-Source-{unique}",
        url=f"https://example.com/{user_id}/feed-{unique}.xml",
        source_type="rss",
        active=True,
        settings_json=None,
        tags=[],
        group_ids=[],
    )
    job = db.create_job(
        name=f"OpLim-Job-{unique}",
        description="test job",
        scope_json=json.dumps({"sources": [src.id]}),
        schedule_expr=None,
        schedule_timezone=None,
        active=True,
        max_concurrency=None,
        per_host_delay_ms=None,
        retry_policy_json=None,
        output_prefs_json=None,
        job_filters_json=None,
    )
    run = db.create_run(job_id=job.id)
    return {"source_id": int(src.id), "job_id": int(job.id), "run_id": int(run.id)}


def _seed_source_with_seen(user_id: int) -> int:
    db = WatchlistsDatabase.for_user(user_id)
    db.ensure_schema()
    unique = uuid4().hex[:8]
    src = db.create_source(
        name=f"Seen-{unique}",
        url=f"https://example.com/{user_id}/seen-{unique}.xml",
        source_type="rss",
        active=True,
        settings_json=None,
        tags=[],
        group_ids=[],
    )
    db.mark_seen_item(src.id, "key-a")
    db.mark_seen_item(src.id, "key-b")
    db.update_source_scrape_meta(
        src.id,
        defer_until=datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(),
        status="not_modified_backoff:60",
        consec_not_modified=3,
    )
    return int(src.id)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def user_client(monkeypatch):
    async def override_user():
        return User(id=9400, username="op-limits-user", email=None, is_active=True)

    base_dir = Path.cwd() / "Databases" / USER_DB_BASE_DIR_NAME
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))

    mod = import_module("tldw_Server_API.app.main")
    app = getattr(mod, "app")
    app.dependency_overrides[get_request_user] = override_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture()
def admin_client(monkeypatch):
    async def override_user():
        u = User(id=9401, username="op-limits-admin", email=None, is_active=True)
        setattr(u, "is_admin", True)
        return u

    base_dir = Path.cwd() / "Databases" / USER_DB_BASE_DIR_NAME
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))

    mod = import_module("tldw_Server_API.app.main")
    app = getattr(mod, "app")
    app.dependency_overrides[get_request_user] = override_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _ensure_data(user_client):
    """Seed minimal data so 200 responses have at least one item."""
    _seed_minimal_dataset(user_id=9400)


# ═══════════════════════════════════════════════════════════════════════════
# Test Classes
# ═══════════════════════════════════════════════════════════════════════════


class TestListEndpointSizeLimits:
    """Each list endpoint rejects size > 200 with 422."""

    ENDPOINTS = [
        "/api/v1/watchlists/sources",
        "/api/v1/watchlists/jobs",
        "/api/v1/watchlists/runs",
        "/api/v1/watchlists/tags",
        "/api/v1/watchlists/groups",
    ]

    @pytest.mark.parametrize("endpoint", ENDPOINTS)
    def test_max_size_accepted(self, user_client, endpoint):
        r = user_client.get(endpoint, params={"size": 200})
        assert r.status_code == 200, f"{endpoint} size=200 → {r.status_code}: {r.text}"

    @pytest.mark.parametrize("endpoint", ENDPOINTS)
    def test_over_max_size_rejected(self, user_client, endpoint):
        r = user_client.get(endpoint, params={"size": 201})
        assert r.status_code == 422, f"{endpoint} size=201 → {r.status_code}: {r.text}"


class TestPreviewEndpointLimits:
    """Preview rejects limit > 200 and per_source > 100."""

    def _get_job_id(self, user_client) -> int:
        r = user_client.get("/api/v1/watchlists/jobs", params={"size": 1})
        assert r.status_code == 200
        items = r.json().get("items", [])
        assert items, "No jobs seeded"
        return items[0]["id"]

    def test_preview_limit_accepted(self, user_client):
        job_id = self._get_job_id(user_client)
        r = user_client.post(
            f"/api/v1/watchlists/jobs/{job_id}/preview",
            params={"limit": 200},
        )
        assert r.status_code == 200, r.text

    def test_preview_limit_rejected(self, user_client):
        job_id = self._get_job_id(user_client)
        r = user_client.post(
            f"/api/v1/watchlists/jobs/{job_id}/preview",
            params={"limit": 201},
        )
        assert r.status_code == 422, r.text

    def test_preview_per_source_accepted(self, user_client):
        job_id = self._get_job_id(user_client)
        r = user_client.post(
            f"/api/v1/watchlists/jobs/{job_id}/preview",
            params={"per_source": 100},
        )
        assert r.status_code == 200, r.text

    def test_preview_per_source_rejected(self, user_client):
        job_id = self._get_job_id(user_client)
        r = user_client.post(
            f"/api/v1/watchlists/jobs/{job_id}/preview",
            params={"per_source": 101},
        )
        assert r.status_code == 422, r.text


class TestCsvExportLimits:
    """CSV export rejects size > 1000."""

    def test_csv_max_size_accepted(self, user_client):
        r = user_client.get(
            "/api/v1/watchlists/runs/export.csv",
            params={"size": 1000},
        )
        assert r.status_code == 200, r.text

    def test_csv_over_max_size_rejected(self, user_client):
        r = user_client.get(
            "/api/v1/watchlists/runs/export.csv",
            params={"size": 1001},
        )
        assert r.status_code == 422, r.text


class TestTalliesAggregationScope:
    """Aggregate tallies mode only allowed with scope=global."""

    def test_global_aggregate_accepted(self, user_client):
        r = user_client.get(
            "/api/v1/watchlists/runs/export.csv",
            params={
                "scope": "global",
                "include_tallies": True,
                "tallies_mode": "aggregate",
            },
        )
        assert r.status_code == 200, r.text

    def test_job_aggregate_rejected(self, user_client):
        r = user_client.get(
            "/api/v1/watchlists/runs/export.csv",
            params={
                "scope": "job",
                "include_tallies": True,
                "tallies_mode": "aggregate",
                "job_id": 1,
            },
        )
        assert r.status_code == 400, r.text
        assert "tallies_aggregation_global_only" in r.text


class TestDedupSeenAuthGating:
    """Dedup/seen endpoints enforce admin gating for target_user_id."""

    def test_own_user_get_succeeds(self, user_client):
        source_id = _seed_source_with_seen(user_id=9400)
        r = user_client.get(f"/api/v1/watchlists/sources/{source_id}/seen")
        assert r.status_code == 200, r.text

    def test_own_user_delete_succeeds(self, user_client):
        source_id = _seed_source_with_seen(user_id=9400)
        r = user_client.delete(f"/api/v1/watchlists/sources/{source_id}/seen")
        assert r.status_code == 200, r.text

    def test_non_admin_target_user_get_forbidden(self, user_client):
        source_id = _seed_source_with_seen(user_id=9402)
        r = user_client.get(
            f"/api/v1/watchlists/sources/{source_id}/seen",
            params={"target_user_id": 9402},
        )
        assert r.status_code == 403
        assert "watchlists_admin_required_for_target_user" in r.text

    def test_non_admin_target_user_delete_forbidden(self, user_client):
        source_id = _seed_source_with_seen(user_id=9402)
        r = user_client.delete(
            f"/api/v1/watchlists/sources/{source_id}/seen",
            params={"target_user_id": 9402},
        )
        assert r.status_code == 403
        assert "watchlists_admin_required_for_target_user" in r.text

    def test_admin_target_user_get_succeeds(self, admin_client):
        source_id = _seed_source_with_seen(user_id=9403)
        r = admin_client.get(
            f"/api/v1/watchlists/sources/{source_id}/seen",
            params={"target_user_id": 9403},
        )
        assert r.status_code == 200, r.text

    def test_admin_target_user_delete_succeeds(self, admin_client):
        source_id = _seed_source_with_seen(user_id=9403)
        r = admin_client.delete(
            f"/api/v1/watchlists/sources/{source_id}/seen",
            params={"target_user_id": 9403},
        )
        assert r.status_code == 200, r.text


class TestRegressionNormalWorkflows:
    """Default-params list calls still work correctly."""

    def test_sources_default_params(self, user_client):
        r = user_client.get("/api/v1/watchlists/sources")
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data

    def test_jobs_default_params(self, user_client):
        r = user_client.get("/api/v1/watchlists/jobs")
        assert r.status_code == 200
        data = r.json()
        assert "items" in data

    def test_runs_default_params(self, user_client):
        r = user_client.get("/api/v1/watchlists/runs")
        assert r.status_code == 200
        data = r.json()
        assert "items" in data


class TestPaginationParity:
    """Two identical reads return the same first/last IDs."""

    def test_sources_pagination_stable(self, user_client):
        r1 = user_client.get("/api/v1/watchlists/sources", params={"size": 10})
        r2 = user_client.get("/api/v1/watchlists/sources", params={"size": 10})
        assert r1.status_code == 200
        assert r2.status_code == 200
        items1 = r1.json()["items"]
        items2 = r2.json()["items"]
        if items1 and items2:
            assert items1[0]["id"] == items2[0]["id"]
            assert items1[-1]["id"] == items2[-1]["id"]

    def test_runs_pagination_stable(self, user_client):
        r1 = user_client.get("/api/v1/watchlists/runs", params={"size": 10})
        r2 = user_client.get("/api/v1/watchlists/runs", params={"size": 10})
        assert r1.status_code == 200
        assert r2.status_code == 200
        items1 = r1.json()["items"]
        items2 = r2.json()["items"]
        if items1 and items2:
            assert items1[0]["id"] == items2[0]["id"]
            assert items1[-1]["id"] == items2[-1]["id"]
