import sqlite3
from pathlib import Path

from tldw_Server_API.app.core.DB_Management.DB_Backups import (
    create_backup,
    create_incremental_backup,
    list_backups,
    restore_single_db_backup,
)
from tldw_Server_API.app.core.DB_Management.db_migration import DatabaseMigrator


def test_create_backup_missing_source_returns_error(tmp_path):
    db_path = tmp_path / "missing.db"
    backup_dir = tmp_path / "backups"

    result = create_backup(str(db_path), str(backup_dir), "testdb")

    assert "not found" in result.lower()
    assert not backup_dir.exists()


def test_incremental_backup_handles_quoted_paths(tmp_path):
    quoted_dir = tmp_path / "owner's"
    quoted_dir.mkdir()
    db_path = quoted_dir / "data.db"

    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE test (val TEXT)")
        conn.execute("INSERT INTO test (val) VALUES ('hello')")
        conn.commit()

    backup_dir = tmp_path / "incremental_backups's"
    backup_dir.mkdir()
    message = create_incremental_backup(str(db_path), str(backup_dir), "data")

    assert message.lower().startswith("incremental backup created")
    backups = list(backup_dir.glob("data_incremental_*.sqlib"))
    assert len(backups) == 1

    with sqlite3.connect(backups[0]) as conn:
        rows = conn.execute("SELECT val FROM test").fetchall()
    assert rows == [("hello",)]


def test_incremental_backup_creates_directory_when_missing(tmp_path):
    db_path = tmp_path / "data.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE entries (val TEXT)")
        conn.execute("INSERT INTO entries (val) VALUES ('content')")
        conn.commit()

    target_dir = tmp_path / "nested" / "backups"
    message = create_incremental_backup(str(db_path), str(target_dir), "data")

    assert target_dir.exists()
    assert message.lower().startswith("incremental backup created")
    backups = list(target_dir.glob("data_incremental_*.sqlib"))
    assert len(backups) == 1


def test_rollback_to_backup_restores_wal_sidecars(tmp_path):
    db_path = tmp_path / "waltest.db"
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

    for suffix in ("-wal", "-shm"):
        backup_sidecar = Path(backup_path + suffix)
        current_sidecar = Path(str(db_path) + suffix)
        if backup_sidecar.exists():
            assert current_sidecar.exists()
            assert current_sidecar.read_bytes() == backup_sidecar.read_bytes()
        else:
            assert not current_sidecar.exists()

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT val FROM entries ORDER BY rowid").fetchall()
    assert rows == [("original",)]


def test_restore_skips_snapshot_when_target_missing(tmp_path):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    backup_name = "test_backup.db"
    backup_file = backup_dir / backup_name
    backup_file.write_text("restored content")

    db_path = tmp_path / "nested" / "restored.db"
    result = restore_single_db_backup(str(db_path), str(backup_dir), "testdb", backup_name)

    assert "restored" in result.lower()
    assert db_path.read_text() == "restored content"
    pre_restore = list(backup_dir.glob("testdb_pre_restore_*.db"))
    assert pre_restore == []


def test_restore_creates_snapshot_when_target_exists(tmp_path):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    backup_name = "test_backup.db"
    backup_file = backup_dir / backup_name
    backup_file.write_text("new data")

    db_path = tmp_path / "existing.db"
    db_path.write_text("old data")

    result = restore_single_db_backup(str(db_path), str(backup_dir), "testdb", backup_name)

    assert "restored" in result.lower()
    snapshot_files = list(backup_dir.glob("testdb_pre_restore_*.db"))
    assert len(snapshot_files) == 1
    assert snapshot_files[0].read_text() == "old data"
    assert db_path.read_text() == "new data"


def test_backup_round_trip_uses_flat_directory(tmp_path):
    db_path = tmp_path / "data.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE entries (val TEXT)")
        conn.execute("INSERT INTO entries (val) VALUES ('original')")
        conn.commit()

    backup_dir = tmp_path / "backups"
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
