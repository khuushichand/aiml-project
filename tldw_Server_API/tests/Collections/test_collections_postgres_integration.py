from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase
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


def test_collections_postgres_round_trip(request: pytest.FixtureRequest, monkeypatch, tmp_path):
    _client, db_name = request.getfixturevalue("isolated_test_environment")  # type: ignore[assignment]
    monkeypatch.setenv("USER_DB_BASE_DIR", str((tmp_path / "user_dbs").resolve()))

    backend = _pg_backend(db_name)
    db = CollectionsDatabase.from_backend(user_id="1", backend=backend)

    item = db.upsert_content_item(
        origin="reading",
        url="https://example.com/article",
        canonical_url="https://example.com/article",
        domain="example.com",
        title="Postgres Collections",
        summary="Testing collections on Postgres",
        notes=None,
        content_hash="hash-123",
        word_count=42,
        published_at=None,
        status="saved",
        favorite=True,
        metadata={"source": "test"},
        media_id=None,
        job_id=None,
        run_id=None,
        source_id=None,
        read_at=None,
        tags=["news", "postgres"],
    )
    assert item.id > 0
    assert item.is_new is True

    tpl = db.create_output_template(
        name="Default Summary",
        type_="summary",
        format_="markdown",
        body="Example body",
        description="test",
        is_default=True,
    )
    assert tpl.id > 0
    assert tpl.is_default is True

    expired_at = datetime(2000, 1, 1, tzinfo=timezone.utc).isoformat()
    output = db.create_output_artifact(
        type_="summary",
        title="Expired Output",
        format_="markdown",
        storage_path="expired.md",
        metadata_json=None,
        retention_until=expired_at,
    )
    assert output.id > 0

    purged = db.purge_expired_outputs()
    assert purged >= 1
