from __future__ import annotations

import os
import json

import pytest

from tldw_Server_API.app.core.DB_Management.Watchlists_DB import WatchlistsDatabase
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType, DatabaseConfig
from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory

pytest_plugins = ["tldw_Server_API.tests.AuthNZ.conftest"]


def _pg_backend(db_name: str):
    return DatabaseBackendFactory.create_backend(
        DatabaseConfig(
            backend_type=BackendType.POSTGRESQL,
            pg_host=os.getenv("TEST_DB_HOST", "localhost"),
            pg_port=int(os.getenv("TEST_DB_PORT", "5432")),
            pg_database=db_name,
            pg_user=os.getenv("TEST_DB_USER", "tldw_user"),
            pg_password=os.getenv("TEST_DB_PASSWORD", "TestPassword123!"),
            pg_sslmode=os.getenv("TEST_DB_SSLMODE", "prefer"),
        )
    )


def test_watchlists_postgres_round_trip(request: pytest.FixtureRequest):
    _client, db_name = request.getfixturevalue("isolated_test_environment")  # type: ignore[assignment]

    backend = _pg_backend(db_name)
    db = WatchlistsDatabase(user_id="1", backend=backend)

    source = db.create_source(
        name="Example Feed",
        url="https://example.com/rss",
        source_type="rss",
        active=True,
        settings_json=None,
        tags=["news"],
    )
    assert source.id > 0

    group = db.create_group(name="Default", description=None, parent_group_id=None)
    assert group.id > 0

    job = db.create_job(
        name="Daily Watch",
        description=None,
        scope_json=json.dumps({"source_ids": [source.id]}),
        schedule_expr="0 * * * *",
        schedule_timezone="UTC",
        active=True,
        max_concurrency=1,
        per_host_delay_ms=1000,
        retry_policy_json=None,
        output_prefs_json=None,
        job_filters_json=None,
    )
    assert job.id > 0

    run = db.create_run(job.id, status="queued")
    assert run.id > 0

    item = db.record_scraped_item(
        run_id=run.id,
        job_id=job.id,
        source_id=source.id,
        media_id=None,
        media_uuid=None,
        url="https://example.com/post",
        title="Example Post",
        summary="Summary",
        published_at=None,
        tags=["news"],
        status="new",
    )
    assert item.id > 0

    output = db.create_output(
        run_id=run.id,
        job_id=job.id,
        type="summary",
        format="markdown",
        title="Daily Summary",
        content="Hello",
    )
    assert output.id > 0
