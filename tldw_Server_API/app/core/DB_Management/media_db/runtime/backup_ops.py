"""Backup helpers owned by the package-native Media DB runtime."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from tldw_Server_API.app.core.DB_Management.backends.base import BackendType

try:
    from loguru import logger

    logging = logger
except ImportError:  # pragma: no cover - defensive fallback
    import logging as _stdlib_logging

    logger = _stdlib_logging.getLogger("media_db_backup")
    logging = logger


def backup_database(self: Any, backup_file_path: str) -> bool | None:
    """Create a backup for the current database."""

    logger.info("Starting database backup from '{}' to '{}'", self.db_path_str, backup_file_path)

    if self.backend_type != BackendType.SQLITE:
        return _backup_non_sqlite_database(self, backup_file_path)

    src_conn = None
    backup_conn = None
    try:
        if not self.is_memory_db and Path(self.db_path_str).resolve() == Path(backup_file_path).resolve():
            logger.error("Backup path cannot be the same as the source database path.")
            raise ValueError("Backup path cannot be the same as the source database path.")  # noqa: TRY003, TRY301

        src_conn = self.get_connection()

        backup_db_path = Path(backup_file_path)
        backup_db_path.parent.mkdir(parents=True, exist_ok=True)

        backup_conn = sqlite3.connect(backup_file_path)

        logger.debug("Source DB connection: {}", src_conn)
        logger.debug("Backup DB connection: {} to file {}", backup_conn, backup_file_path)

        src_conn.backup(backup_conn, pages=0, progress=None)
        logger.info("Database backup successful from '{}' to '{}'", self.db_path_str, backup_file_path)
    except sqlite3.Error as exc:
        logger.error("SQLite error during database backup: {}", exc, exc_info=True)
        return False
    except ValueError as exc:
        logger.error("ValueError during database backup: {}", exc, exc_info=True)
        return False
    except Exception as exc:
        logger.error("Unexpected error during database backup: {}", exc, exc_info=True)
        return False
    else:
        return True
    finally:
        if backup_conn:
            try:
                backup_conn.close()
                logger.debug("Closed backup database connection.")
            except sqlite3.Error as exc:
                logger.warning("Error closing backup database connection: {}", exc)


def _backup_non_sqlite_database(self: Any, backup_file_path: str) -> bool:
    """Best-effort handler for backends without native SQLite backup support."""

    if self.backend_type == BackendType.POSTGRESQL:
        logging.warning(
            "Automatic backups are not implemented inside MediaDatabase for PostgreSQL. "
            "Use DB_Backups.create_postgres_backup(backend, backup_dir) to invoke pg_dump. Target requested: {}",
            backup_file_path,
        )
        return False

    logging.warning(
        "Automatic backups are only supported for SQLite. Backend {} is not handled (target: {}).",
        self.backend_type,
        backup_file_path,
    )
    return False


__all__ = ["backup_database", "_backup_non_sqlite_database"]
