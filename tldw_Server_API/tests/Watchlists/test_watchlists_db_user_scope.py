from __future__ import annotations

import json

import pytest

from tldw_Server_API.app.core.DB_Management.Watchlists_DB import WatchlistsDatabase
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType, DatabaseConfig
from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory

pytestmark = pytest.mark.unit


def _seed_user_job_run_item(db: WatchlistsDatabase, *, label: str) -> dict[str, int]:
    source = db.create_source(
        name=f"{label}-source",
        url=f"https://example.com/{label}/rss",
        source_type="rss",
        active=True,
        settings_json=None,
        tags=["news"],
        group_ids=[],
    )
    job = db.create_job(
        name=f"{label}-job",
        description=f"{label} job",
        scope_json=json.dumps({"sources": [int(source.id)]}),
        schedule_expr=None,
        schedule_timezone="UTC",
        active=True,
        max_concurrency=1,
        per_host_delay_ms=0,
        retry_policy_json=json.dumps({}),
        output_prefs_json=json.dumps({}),
        job_filters_json=None,
    )
    run = db.create_run(int(job.id), status="queued")
    item = db.record_scraped_item(
        run_id=int(run.id),
        job_id=int(job.id),
        source_id=int(source.id),
        media_id=None,
        media_uuid=None,
        url=f"https://example.com/{label}/story",
        title=f"{label} story",
        summary=f"{label} summary",
        published_at=None,
        tags=["news"],
        status="ingested",
    )
    return {
        "source_id": int(source.id),
        "job_id": int(job.id),
        "run_id": int(run.id),
        "item_id": int(item.id),
    }


@pytest.fixture()
def shared_watchlists_dbs(tmp_path):
    db_path = tmp_path / "shared_watchlists.db"
    backend = DatabaseBackendFactory.create_backend(
        DatabaseConfig(backend_type=BackendType.SQLITE, sqlite_path=str(db_path))
    )
    user1_db = WatchlistsDatabase(user_id=1, backend=backend)
    user2_db = WatchlistsDatabase(user_id=2, backend=backend)
    return user1_db, user2_db


def test_runs_are_scoped_per_user_in_shared_backend(shared_watchlists_dbs):
    user1_db, user2_db = shared_watchlists_dbs
    user1 = _seed_user_job_run_item(user1_db, label="u1")
    _seed_user_job_run_item(user2_db, label="u2")

    # Owner can read/update their own run.
    own_run = user1_db.get_run(user1["run_id"])
    assert int(own_run.id) == user1["run_id"]
    updated = user1_db.update_run(user1["run_id"], status="running")
    assert updated.status == "running"

    # Cross-user access is blocked.
    with pytest.raises(KeyError):
        user2_db.get_run(user1["run_id"])

    with pytest.raises(KeyError):
        user2_db.update_run(user1["run_id"], status="failed")

    rows, total = user2_db.list_runs_for_job(user1["job_id"], limit=10, offset=0)
    assert rows == []
    assert total == 0

    with pytest.raises(KeyError):
        user2_db.create_run(user1["job_id"], status="queued")


def test_scraped_items_are_scoped_per_user_in_shared_backend(shared_watchlists_dbs):
    user1_db, user2_db = shared_watchlists_dbs
    user1 = _seed_user_job_run_item(user1_db, label="u1-items")
    _seed_user_job_run_item(user2_db, label="u2-items")

    owner_item = user1_db.get_item(user1["item_id"])
    assert int(owner_item.id) == user1["item_id"]

    with pytest.raises(KeyError):
        user2_db.get_item(user1["item_id"])

    rows, total = user2_db.list_items(run_id=user1["run_id"], limit=50, offset=0)
    assert rows == []
    assert total == 0

    assert user2_db.get_items_by_ids([user1["item_id"]]) == []

    with pytest.raises(KeyError):
        user2_db.update_item_flags(user1["item_id"], reviewed=True)

    # Verify foreign user could not mutate the owner's row.
    owner_item_after = user1_db.get_item(user1["item_id"])
    assert int(owner_item_after.reviewed or 0) == 0


def test_watchlist_clusters_are_scoped_per_user_in_shared_backend(shared_watchlists_dbs):
    user1_db, user2_db = shared_watchlists_dbs
    user1 = _seed_user_job_run_item(user1_db, label="u1-clusters")
    user2 = _seed_user_job_run_item(user2_db, label="u2-clusters")

    user1_db.add_watchlist_cluster(user1["job_id"], 101)
    user2_db.add_watchlist_cluster(user2["job_id"], 202)

    # Foreign-job subscription writes are rejected.
    with pytest.raises(KeyError):
        user2_db.add_watchlist_cluster(user1["job_id"], 303)

    # Per-job read is scoped.
    user1_clusters = user1_db.list_watchlist_clusters(user1["job_id"])
    assert [int(row["cluster_id"]) for row in user1_clusters] == [101]
    assert user2_db.list_watchlist_clusters(user1["job_id"]) == []

    # Subscription and count aggregations are scoped.
    user1_subs = user1_db.list_watchlist_cluster_subscriptions()
    assert [int(row["job_id"]) for row in user1_subs] == [user1["job_id"]]
    assert user1_db.list_watchlist_cluster_counts() == {101: 1}

    user2_subs = user2_db.list_watchlist_cluster_subscriptions()
    assert [int(row["job_id"]) for row in user2_subs] == [user2["job_id"]]
    assert user2_db.list_watchlist_cluster_counts() == {202: 1}

    # Foreign delete is a no-op; owner delete succeeds.
    assert user2_db.remove_watchlist_cluster(user1["job_id"], 101) is False
    assert user1_db.remove_watchlist_cluster(user1["job_id"], 101) is True
