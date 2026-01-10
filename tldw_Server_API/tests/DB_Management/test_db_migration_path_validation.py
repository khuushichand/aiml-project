import sqlite3
from pathlib import Path

import pytest

from tldw_Server_API.app.core.DB_Management.db_migration import (
    DatabaseMigrator,
    MigrationError,
)


def test_migrations_dir_allows_db_subdir(tmp_path):


     db_path = tmp_path / "data.db"
    db_path.touch()
    migrations_dir = tmp_path / "migrations"

    migrator = DatabaseMigrator(str(db_path), str(migrations_dir))

    assert Path(migrator.migrations_dir) == migrations_dir.resolve()


def test_migrations_dir_rejects_outside_db_and_package(tmp_path):


     db_path = tmp_path / "data.db"
    db_path.touch()
    outside_dir = tmp_path.parent / "outside_migrations"
    outside_dir.mkdir()

    with pytest.raises(MigrationError):
        DatabaseMigrator(str(db_path), str(outside_dir))


def test_rollback_rejects_backup_outside_backup_dir(tmp_path):


     db_path = tmp_path / "data.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE entries (val TEXT)")
        conn.execute("INSERT INTO entries (val) VALUES ('baseline')")
        conn.commit()

    migrator = DatabaseMigrator(str(db_path))

    outside_backup = tmp_path.parent / "outside_backup.db"
    outside_backup.write_text("backup content")

    with pytest.raises(MigrationError):
        migrator.rollback_to_backup(str(outside_backup))


def test_in_memory_db_path_rejected():


     with pytest.raises(MigrationError):
        DatabaseMigrator(":memory:")
