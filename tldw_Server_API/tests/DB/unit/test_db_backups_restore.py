from pathlib import Path
import sqlite3

import pytest

from tldw_Server_API.app.core.DB_Management.DB_Backups import restore_single_db_backup


@pytest.fixture
def backup_env(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("TLDW_DB_BACKUP_PATH", str(tmp_path))
    monkeypatch.setenv("TLDW_DB_ALLOWED_BASE_DIRS", str(tmp_path))
    return tmp_path


def test_restore_snapshot_sanitizes_db_name(backup_env: Path):
    db_path = backup_env / "db.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE entries (val TEXT)")
        conn.execute("INSERT INTO entries (val) VALUES ('original')")
        conn.commit()

    backup_dir = backup_env / "backups"
    backup_dir.mkdir()
    backup_file = backup_dir / "test_backup.db"
    with sqlite3.connect(backup_file) as conn:
        conn.execute("CREATE TABLE entries (val TEXT)")
        conn.execute("INSERT INTO entries (val) VALUES ('backup')")
        conn.commit()

    result = restore_single_db_backup(
        str(db_path),
        str(backup_dir),
        "../evil",
        "test_backup.db",
    )
    assert result.startswith("Database restored")

    pre_restore = list(backup_dir.glob("evil_pre_restore_*.db"))
    assert pre_restore, "Expected sanitized pre-restore snapshot in backup dir"
    with sqlite3.connect(pre_restore[0]) as conn:
        rows = conn.execute("SELECT val FROM entries").fetchall()
    assert rows == [("original",)]
