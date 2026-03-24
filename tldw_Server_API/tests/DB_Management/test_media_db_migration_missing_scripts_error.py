"""Tests for MediaDatabase upgrade diagnostics when migration scripts are missing."""

import pathlib
import sqlite3
from typing import Any

import pytest

from tldw_Server_API.app.core.DB_Management.media_db.errors import DatabaseError
from tldw_Server_API.app.core.DB_Management.media_db.native_class import MediaDatabase
from tldw_Server_API.app.core.DB_Management.media_db.schema.backends import (
    sqlite_helpers as sqlite_helpers_module,
)


@pytest.mark.unit
def test_media_db_upgrade_no_migrations_reports_explicit_diagnostics(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify that upgrading with no migration scripts raises DatabaseError with full diagnostics."""
    db_path = tmp_path / "Media_DB_v2.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE schema_version (version INTEGER)")
        conn.execute("INSERT INTO schema_version (version) VALUES (8)")
        conn.commit()

    fake_migrations_dir = str(tmp_path / "missing_migrations")

    class _FakeMigrator:
        def __init__(self, _db_path: str, migrations_dir: str | None = None) -> None:
            self.migrations_dir = migrations_dir or fake_migrations_dir

        def migrate_to_version(
            self,
            target_version: int,
            _create_backup: bool = True,
        ) -> dict[str, Any]:
            return {
                "status": "no_migrations",
                "current_version": 8,
                "target_version": target_version,
                "migrations_applied": [],
                "migrations_dir": fake_migrations_dir,
                "available_versions": [1, 2, 3, 4, 5, 6, 7, 8],
                "missing_versions": list(range(9, target_version + 1)),
            }

    monkeypatch.setattr(sqlite_helpers_module, "DatabaseMigrator", _FakeMigrator)

    with pytest.raises(DatabaseError) as exc_info:
        MediaDatabase(db_path=str(db_path), client_id="migration-diagnostics-test")

    msg = str(exc_info.value)
    target_version = MediaDatabase._CURRENT_SCHEMA_VERSION
    assert (
        f"No migration scripts available to upgrade database schema from version 8 to {target_version}"
        in msg
    )
    assert f"migrations_dir={fake_migrations_dir}" in msg
    assert "discovered_versions=[1, 2, 3, 4, 5, 6, 7, 8]" in msg
    expected_missing = str(list(range(9, target_version + 1)))
    assert f"missing_versions={expected_missing}" in msg
