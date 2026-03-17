"""Legacy backup helpers extracted from Media_DB_v2."""

from __future__ import annotations

from typing import Any

from loguru import logger


_BACKUP_NONCRITICAL_EXCEPTIONS: tuple[type[BaseException], ...] = (
    AttributeError,
    ImportError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)


def create_automated_backup(db_path: Any, backup_dir: Any) -> str:
    """Create a full backup using the DB_Backups helper."""
    try:
        from tldw_Server_API.app.core.DB_Management.DB_Backups import (
            create_backup as _create_backup,
        )

        return _create_backup(db_path, backup_dir, "media")
    except _BACKUP_NONCRITICAL_EXCEPTIONS as exc:
        logger.exception("create_automated_backup failed")
        return f"Failed to create backup: {exc}"


__all__ = ["create_automated_backup"]
