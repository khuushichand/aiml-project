from pathlib import Path

from tldw_Server_API.app.core.DB_Management.DB_Backups import restore_single_db_backup


def test_restore_snapshot_sanitizes_db_name(tmp_path: Path):
    db_path = tmp_path / "db.sqlite"
    db_path.write_text("original")

    backup_dir = tmp_path / "backups"
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
