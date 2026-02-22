import sqlite3

import pytest

from tldw_Server_API.app.core.DB_Management.DB_Backups import (
    create_backup,
    create_incremental_backup,
    list_backups,
    restore_single_db_backup,
)
from tldw_Server_API.app.core.DB_Management.db_migration import DatabaseMigrator


@pytest.fixture
def backup_env(monkeypatch, tmp_path):
    monkeypatch.setenv("TLDW_DB_BACKUP_PATH", str(tmp_path))
    monkeypatch.setenv("TLDW_DB_ALLOWED_BASE_DIRS", str(tmp_path))
    return tmp_path


def test_create_backup_missing_source_returns_error(backup_env):

    db_path = backup_env / "missing.db"
    backup_dir = backup_env / "backups"

    result = create_backup(str(db_path), str(backup_dir), "testdb")

    assert "not found" in result.lower()
    assert not backup_dir.exists()


def test_incremental_backup_handles_quoted_paths(backup_env):

    quoted_dir = backup_env / "owner's"
    quoted_dir.mkdir()
    db_path = quoted_dir / "data.db"

    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE test (val TEXT)")
        conn.execute("INSERT INTO test (val) VALUES ('hello')")
        conn.commit()

    backup_dir = backup_env / "incremental_backups's"
    backup_dir.mkdir()
    message = create_incremental_backup(str(db_path), str(backup_dir), "data")

    assert message.lower().startswith("incremental backup created")
    backups = list(backup_dir.glob("data_incremental_*.sqlib"))
    assert len(backups) == 1

    with sqlite3.connect(backups[0]) as conn:
        rows = conn.execute("SELECT val FROM test").fetchall()
    assert rows == [("hello",)]


def test_incremental_backup_creates_directory_when_missing(backup_env):

    db_path = backup_env / "data.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE entries (val TEXT)")
        conn.execute("INSERT INTO entries (val) VALUES ('content')")
        conn.commit()

    target_dir = backup_env / "nested" / "backups"
    message = create_incremental_backup(str(db_path), str(target_dir), "data")

    assert target_dir.exists()
    assert message.lower().startswith("incremental backup created")
    backups = list(target_dir.glob("data_incremental_*.sqlib"))
    assert len(backups) == 1


def test_create_backup_accepts_sqlite_file_uri(backup_env):

    db_path = backup_env / "uri_source.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE t (val TEXT)")
        conn.execute("INSERT INTO t (val) VALUES ('hello')")
        conn.commit()

    db_uri = f"file:{db_path}?mode=rw"
    backup_dir = backup_env / "uri_backups"
    message = create_backup(db_uri, str(backup_dir), "uri")

    assert message.lower().startswith("backup created")
    backups = list(backup_dir.glob("uri_backup_*.db"))
    assert len(backups) == 1

    with sqlite3.connect(backups[0]) as conn:
        rows = conn.execute("SELECT val FROM t").fetchall()
    assert rows == [("hello",)]


def test_incremental_backup_accepts_sqlite_file_uri(backup_env):

    db_path = backup_env / "uri_incremental.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE t (val TEXT)")
        conn.execute("INSERT INTO t (val) VALUES ('hello')")
        conn.commit()

    db_uri = f"file:{db_path}?mode=rw"
    backup_dir = backup_env / "uri_incremental_backups"
    message = create_incremental_backup(db_uri, str(backup_dir), "uri")

    assert message.lower().startswith("incremental backup created")
    backups = list(backup_dir.glob("uri_incremental_*.sqlib"))
    assert len(backups) == 1

    with sqlite3.connect(backups[0]) as conn:
        rows = conn.execute("SELECT val FROM t").fetchall()
    assert rows == [("hello",)]


def test_rollback_to_backup_restores_data(backup_env):

    db_path = backup_env / "waltest.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE entries (val TEXT)")
        conn.execute("INSERT INTO entries (val) VALUES ('original')")
        conn.commit()

    migrator = DatabaseMigrator(str(db_path))
    backup_path = migrator.create_backup("baseline")

    with sqlite3.connect(db_path) as conn:
        conn.execute("INSERT INTO entries (val) VALUES ('mutated')")
        conn.commit()

    result = migrator.rollback_to_backup(backup_path)

    assert result["status"] == "success"

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT val FROM entries ORDER BY rowid").fetchall()
    assert rows == [("original",)]


def test_restore_skips_snapshot_when_target_missing(backup_env):

    backup_dir = backup_env / "backups"
    backup_dir.mkdir()
    backup_name = "test_backup.db"
    backup_file = backup_dir / backup_name
    with sqlite3.connect(backup_file) as conn:
        conn.execute("CREATE TABLE entries (val TEXT)")
        conn.execute("INSERT INTO entries (val) VALUES ('restored content')")
        conn.commit()

    db_path = backup_env / "nested" / "restored.db"
    result = restore_single_db_backup(str(db_path), str(backup_dir), "testdb", backup_name)

    assert "restored" in result.lower()
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT val FROM entries").fetchall()
    assert rows == [("restored content",)]
    pre_restore = list(backup_dir.glob("testdb_pre_restore_*.db"))
    assert pre_restore == []


def test_restore_creates_snapshot_when_target_exists(backup_env):

    backup_dir = backup_env / "backups"
    backup_dir.mkdir()
    backup_name = "test_backup.db"
    backup_file = backup_dir / backup_name
    with sqlite3.connect(backup_file) as conn:
        conn.execute("CREATE TABLE entries (val TEXT)")
        conn.execute("INSERT INTO entries (val) VALUES ('new data')")
        conn.commit()

    db_path = backup_env / "existing.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE entries (val TEXT)")
        conn.execute("INSERT INTO entries (val) VALUES ('old data')")
        conn.commit()

    result = restore_single_db_backup(str(db_path), str(backup_dir), "testdb", backup_name)

    assert "restored" in result.lower()
    snapshot_files = list(backup_dir.glob("testdb_pre_restore_*.db"))
    assert len(snapshot_files) == 1
    with sqlite3.connect(snapshot_files[0]) as conn:
        snapshot_rows = conn.execute("SELECT val FROM entries").fetchall()
    assert snapshot_rows == [("old data",)]
    with sqlite3.connect(db_path) as conn:
        restored_rows = conn.execute("SELECT val FROM entries").fetchall()
    assert restored_rows == [("new data",)]


def test_restore_allows_target_db_outside_backup_root(monkeypatch, tmp_path):
    backup_root = tmp_path / "backups_root"
    db_root = tmp_path / "runtime_db_root"
    backup_root.mkdir()
    db_root.mkdir()

    monkeypatch.setenv("TLDW_DB_BACKUP_PATH", str(backup_root))
    monkeypatch.setenv("TLDW_DB_ALLOWED_BASE_DIRS", str(db_root))

    backup_dir = backup_root / "authnz"
    backup_dir.mkdir()
    backup_name = "authnz_backup.db"
    backup_file = backup_dir / backup_name
    with sqlite3.connect(backup_file) as conn:
        conn.execute("CREATE TABLE entries (val TEXT)")
        conn.execute("INSERT INTO entries (val) VALUES ('restored')")
        conn.commit()

    db_path = db_root / "users.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE entries (val TEXT)")
        conn.execute("INSERT INTO entries (val) VALUES ('live')")
        conn.commit()

    result = restore_single_db_backup(str(db_path), str(backup_dir), "authnz", backup_name)

    assert "restored" in result.lower()
    with sqlite3.connect(db_path) as conn:
        restored_rows = conn.execute("SELECT val FROM entries").fetchall()
    assert restored_rows == [("restored",)]

    snapshot_files = list(backup_dir.glob("authnz_pre_restore_*.db"))
    assert len(snapshot_files) == 1
    with sqlite3.connect(snapshot_files[0]) as conn:
        snapshot_rows = conn.execute("SELECT val FROM entries").fetchall()
    assert snapshot_rows == [("live",)]


def test_restore_busy_target_fails_without_overwrite(backup_env):
    db_path = backup_env / "busy.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE entries (val TEXT)")
        conn.execute("INSERT INTO entries (val) VALUES ('live')")
        conn.commit()

    backup_dir = backup_env / "backups"
    backup_dir.mkdir()
    backup_name = "busy_backup.db"
    backup_file = backup_dir / backup_name
    with sqlite3.connect(backup_file) as conn:
        conn.execute("CREATE TABLE entries (val TEXT)")
        conn.execute("INSERT INTO entries (val) VALUES ('backup')")
        conn.commit()

    blocker = sqlite3.connect(db_path, timeout=0.1)
    blocker.execute("BEGIN EXCLUSIVE")
    try:
        result = restore_single_db_backup(str(db_path), str(backup_dir), "busy", backup_name)
    finally:
        blocker.rollback()
        blocker.close()

    assert "busy/locked" in result.lower()
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT val FROM entries").fetchall()
    assert rows == [("live",)]


def test_restore_rejects_invalid_backup_name(backup_env):

    backup_dir = backup_env / "backups"
    backup_dir.mkdir()
    db_path = backup_env / "restore.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE entries (val TEXT)")
        conn.execute("INSERT INTO entries (val) VALUES ('existing data')")
        conn.commit()

    result = restore_single_db_backup(str(db_path), str(backup_dir), "data", "../evil.db")

    assert "invalid backup name" in result.lower()
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT val FROM entries").fetchall()
    assert rows == [("existing data",)]


def test_backup_round_trip_uses_flat_directory(backup_env):

    db_path = backup_env / "data.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE entries (val TEXT)")
        conn.execute("INSERT INTO entries (val) VALUES ('original')")
        conn.commit()

    backup_dir = backup_env / "backups"
    message = create_backup(str(db_path), str(backup_dir), "data")
    assert message.lower().startswith("backup created")

    backups = sorted(backup_dir.glob("*.db"))
    assert len(backups) == 1
    backup_file = backups[0]
    assert backup_file.parent == backup_dir
    assert backup_file.name.startswith("data_backup_")

    listing = list_backups(str(backup_dir))
    assert backup_file.name in listing.splitlines()

    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM entries")
        conn.commit()

    result = restore_single_db_backup(str(db_path), str(backup_dir), "data", backup_file.name)
    assert "restored" in result.lower()

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT val FROM entries").fetchall()
    assert rows == [("original",)]


def test_create_backup_rejects_absolute_db_path_outside_allowed_root(backup_env):
    outside_db = backup_env.parent / "outside.db"
    outside_db.write_text("data")
    backup_dir = backup_env / "backups"

    result = create_backup(str(outside_db), str(backup_dir), "testdb")

    assert "invalid database path" in result.lower()


def test_create_backup_rejects_traversal_backup_dir(backup_env):
    db_path = backup_env / "data.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE entries (val TEXT)")
        conn.execute("INSERT INTO entries (val) VALUES ('data')")
        conn.commit()
    backup_dir = "../escape"

    result = create_backup(str(db_path), backup_dir, "testdb")

    assert "invalid backup directory" in result.lower()
