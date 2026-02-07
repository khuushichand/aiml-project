import sqlite3

import pytest

import tldw_Server_API.app.core.DB_Management.Media_DB_v2 as media_db_mod
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import DatabaseError, MediaDatabase


def test_media_db_upgrade_no_migrations_reports_explicit_diagnostics(tmp_path, monkeypatch):
    db_path = tmp_path / "Media_DB_v2.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE schema_version (version INTEGER)")
        conn.execute("INSERT INTO schema_version (version) VALUES (8)")
        conn.commit()

    fake_migrations_dir = str(tmp_path / "missing_migrations")

    def _fake_migrate_to_version(self, target_version, create_backup=True):
        return {
            "status": "no_migrations",
            "current_version": 8,
            "target_version": target_version,
            "migrations_applied": [],
            "migrations_dir": fake_migrations_dir,
            "available_versions": [1, 2, 3, 4, 5, 6, 7, 8],
            "missing_versions": list(range(9, target_version + 1)),
        }

    monkeypatch.setattr(
        media_db_mod.DatabaseMigrator,
        "migrate_to_version",
        _fake_migrate_to_version,
    )

    with pytest.raises(DatabaseError) as exc_info:
        MediaDatabase(db_path=str(db_path), client_id="migration-diagnostics-test")

    msg = str(exc_info.value)
    assert "No migration scripts available to upgrade database schema from version 8 to 20" in msg
    assert f"migrations_dir={fake_migrations_dir}" in msg
    assert "discovered_versions=[1, 2, 3, 4, 5, 6, 7, 8]" in msg
    assert "missing_versions=[9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]" in msg
