import os
import tempfile

from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps.Watchlists_DB_Deps import get_watchlists_db_for_user
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user
from tldw_Server_API.app.core.DB_Management.Watchlists_DB import WatchlistsDatabase
from tldw_Server_API.app.core.DB_Management.backends.base import DatabaseConfig, BackendType
from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory


def _make_watchlists_db() -> WatchlistsDatabase:


     tmpdir = tempfile.mkdtemp(prefix="watchlists_clusters_")
    db_path = os.path.join(tmpdir, "watchlists.db")
    backend = DatabaseBackendFactory.create_backend(
        DatabaseConfig(backend_type=BackendType.SQLITE, sqlite_path=db_path)
    )
    return WatchlistsDatabase(user_id=1, backend=backend)


def test_watchlist_cluster_subscription():


     from tldw_Server_API.app.main import app as fastapi_app

    class _User:
        def __init__(self) -> None:
                     self.id = 1
            self.username = "watcher"
            self.is_admin = False

    async def _override_user():
        return _User()

    db = _make_watchlists_db()
    job = db.create_job(
        name="Test Watchlist",
        description=None,
        scope_json="{}",
        schedule_expr=None,
        schedule_timezone="UTC",
        active=True,
        max_concurrency=None,
        per_host_delay_ms=None,
        retry_policy_json=None,
        output_prefs_json=None,
        job_filters_json=None,
    )
    job_id = int(job.id)

    async def _override_db() -> WatchlistsDatabase:
        return db

    fastapi_app.dependency_overrides[get_request_user] = _override_user
    fastapi_app.dependency_overrides[get_watchlists_db_for_user] = _override_db

    try:
        with TestClient(fastapi_app) as client:
            r = client.post(f"/api/v1/watchlists/{job_id}/clusters", json={"cluster_id": 42})
            assert r.status_code == 200, r.text
            assert r.json()["cluster_id"] == 42

            r2 = client.get(f"/api/v1/watchlists/{job_id}/clusters")
            assert r2.status_code == 200, r2.text
            clusters = r2.json().get("clusters") or []
            assert any(int(item["cluster_id"]) == 42 for item in clusters)

            r3 = client.delete(f"/api/v1/watchlists/{job_id}/clusters/42")
            assert r3.status_code == 200, r3.text
            assert r3.json()["status"] == "removed"
    finally:
        fastapi_app.dependency_overrides.pop(get_request_user, None)
        fastapi_app.dependency_overrides.pop(get_watchlists_db_for_user, None)
