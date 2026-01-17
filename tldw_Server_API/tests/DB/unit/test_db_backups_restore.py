from pathlib import Path

import pytest

from tldw_Server_API.app.core.DB_Management.DB_Backups import restore_single_db_backup


@pytest.fixture
def backup_env(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("TLDW_DB_BACKUP_PATH", str(tmp_path))
    monkeypatch.setenv("TLDW_DB_ALLOWED_BASE_DIRS", str(tmp_path))
    return tmp_path


def test_restore_snapshot_sanitizes_db_name(backup_env: Path):
    db_path = backup_env / "db.sqlite"
    db_path.write_text("original")

    backup_dir = backup_env / "backups"
    backup_dir.mkdir()
    backup_file = backup_dir / "test_backup.db"
    backup_file.write_text("backup")

    result = restore_single_db_backup(
        str(db_path),
        str(backup_dir),
        "../evil",
        "test_backup.db",
    )
    assert result.startswith("Database restored")

    pre_restore = list(backup_dir.glob("evil_pre_restore_*.db"))
    assert pre_restore, "Expected sanitized pre-restore snapshot in backup dir"
