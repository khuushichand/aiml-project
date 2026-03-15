"""End-to-end backup and restore verification tests.

Validates that the backup/restore cycle produces correct, intact databases
with matching schemas and data -- covering WAL mode, integrity checks, and
multi-table scenarios.
"""

import sqlite3
from pathlib import Path

import pytest

from tldw_Server_API.app.core.DB_Management.DB_Backups import (
    create_backup,
    restore_single_db_backup,
)


@pytest.fixture
def backup_env(monkeypatch, tmp_path):
    """Configure backup paths so all operations stay inside tmp_path."""
    monkeypatch.setenv("TLDW_DB_BACKUP_PATH", str(tmp_path))
    monkeypatch.setenv("TLDW_DB_ALLOWED_BASE_DIRS", str(tmp_path))
    return tmp_path


class TestBackupRestoreVerification:
    """End-to-end backup and restore verification tests."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _create_test_db(path: Path) -> None:
        """Create a test database with sample data."""
        conn = sqlite3.connect(str(path))
        conn.execute(
            "CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT, value REAL)"
        )
        conn.execute("INSERT INTO items VALUES (1, 'alpha', 1.0)")
        conn.execute("INSERT INTO items VALUES (2, 'beta', 2.0)")
        conn.execute("INSERT INTO items VALUES (3, 'gamma', 3.0)")
        conn.commit()
        conn.close()

    @staticmethod
    def _count_rows(path: Path, table: str = "items") -> int:
        conn = sqlite3.connect(str(path))
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        conn.close()
        return count

    @staticmethod
    def _read_all(path: Path, table: str = "items") -> list[tuple]:
        conn = sqlite3.connect(str(path))
        rows = conn.execute(
            f"SELECT * FROM {table} ORDER BY id"
        ).fetchall()
        conn.close()
        return rows

    @staticmethod
    def _get_schema(path: Path) -> list[str]:
        """Return sorted CREATE statements from sqlite_master."""
        conn = sqlite3.connect(str(path))
        rows = conn.execute(
            "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY name"
        ).fetchall()
        conn.close()
        return [r[0] for r in rows]

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_backup_creates_file(self, backup_env: Path) -> None:
        """Create a SQLite DB, insert data, back it up, verify backup file exists."""
        db_path = backup_env / "source.db"
        self._create_test_db(db_path)

        backup_dir = backup_env / "backups"
        result = create_backup(str(db_path), str(backup_dir), "source")

        assert result.lower().startswith("backup created"), f"Unexpected: {result}"
        backups = list(backup_dir.glob("source_backup_*.db"))
        assert len(backups) == 1
        assert backups[0].stat().st_size > 0

    def test_restore_recovers_data(self, backup_env: Path) -> None:
        """Back up, delete original data, restore, verify data recovered."""
        db_path = backup_env / "recover.db"
        self._create_test_db(db_path)

        backup_dir = backup_env / "backups"
        msg = create_backup(str(db_path), str(backup_dir), "recover")
        assert msg.lower().startswith("backup created")
        backup_file = list(backup_dir.glob("recover_backup_*.db"))[0]

        # Delete all rows from the live database
        conn = sqlite3.connect(str(db_path))
        conn.execute("DELETE FROM items")
        conn.commit()
        conn.close()
        assert self._count_rows(db_path) == 0

        # Restore
        result = restore_single_db_backup(
            str(db_path), str(backup_dir), "recover", backup_file.name
        )
        assert "restored" in result.lower(), f"Unexpected: {result}"
        assert self._count_rows(db_path) == 3
        rows = self._read_all(db_path)
        assert rows == [(1, "alpha", 1.0), (2, "beta", 2.0), (3, "gamma", 3.0)]

    def test_backup_integrity(self, backup_env: Path) -> None:
        """Run PRAGMA integrity_check on the backup file."""
        db_path = backup_env / "integrity.db"
        self._create_test_db(db_path)

        backup_dir = backup_env / "backups"
        msg = create_backup(str(db_path), str(backup_dir), "integrity")
        assert msg.lower().startswith("backup created")
        backup_file = list(backup_dir.glob("integrity_backup_*.db"))[0]

        conn = sqlite3.connect(str(backup_file))
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
        conn.close()
        assert result == "ok"

    def test_restore_preserves_schema(self, backup_env: Path) -> None:
        """Back up a multi-table DB, restore to a new location, verify schema matches."""
        db_path = backup_env / "schema.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT, value REAL)"
        )
        conn.execute(
            "CREATE TABLE metadata (key TEXT PRIMARY KEY, val TEXT)"
        )
        conn.execute(
            "CREATE INDEX idx_items_name ON items (name)"
        )
        conn.execute("INSERT INTO items VALUES (1, 'alpha', 1.0)")
        conn.execute("INSERT INTO metadata VALUES ('version', '1.0')")
        conn.commit()
        conn.close()

        backup_dir = backup_env / "backups"
        msg = create_backup(str(db_path), str(backup_dir), "schema")
        assert msg.lower().startswith("backup created")
        backup_file = list(backup_dir.glob("schema_backup_*.db"))[0]

        # Restore to a brand-new path
        restored_path = backup_env / "restored_schema.db"
        result = restore_single_db_backup(
            str(restored_path), str(backup_dir), "schema", backup_file.name
        )
        assert "restored" in result.lower(), f"Unexpected: {result}"

        original_schema = self._get_schema(db_path)
        restored_schema = self._get_schema(restored_path)
        assert original_schema == restored_schema

        # Also verify data survived
        conn = sqlite3.connect(str(restored_path))
        items = conn.execute("SELECT * FROM items").fetchall()
        meta = conn.execute("SELECT * FROM metadata").fetchall()
        conn.close()
        assert items == [(1, "alpha", 1.0)]
        assert meta == [("version", "1.0")]

    def test_backup_with_wal_mode(self, backup_env: Path) -> None:
        """Create a WAL-mode DB, back it up, verify backup is a valid database."""
        db_path = backup_env / "wal.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            "CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT, value REAL)"
        )
        conn.execute("INSERT INTO items VALUES (1, 'alpha', 1.0)")
        conn.execute("INSERT INTO items VALUES (2, 'beta', 2.0)")
        conn.execute("INSERT INTO items VALUES (3, 'gamma', 3.0)")
        conn.commit()
        conn.close()

        backup_dir = backup_env / "backups"
        msg = create_backup(str(db_path), str(backup_dir), "wal")
        assert msg.lower().startswith("backup created"), f"Unexpected: {msg}"
        backup_file = list(backup_dir.glob("wal_backup_*.db"))[0]

        # Backup should be a standalone DB (no WAL sidecar needed)
        wal_sidecar = backup_file.parent / (backup_file.name + "-wal")
        assert not wal_sidecar.exists(), "Backup should not have a WAL sidecar"

        # Integrity and data check
        conn = sqlite3.connect(str(backup_file))
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        count = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        conn.close()
        assert integrity == "ok"
        assert count == 3
