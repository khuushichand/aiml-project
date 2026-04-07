"""SQLite bootstrap helpers owned by the package-native Media DB runtime."""

from __future__ import annotations

from typing import Any

from tldw_Server_API.app.core.DB_Management.backends.base import BackendType
from tldw_Server_API.app.core.DB_Management.media_db.runtime.noncritical import (
    MEDIA_NONCRITICAL_EXCEPTIONS,
)
from tldw_Server_API.app.core.DB_Management.sqlite_policy import configure_sqlite_connection

try:
    from loguru import logger

    logging = logger
except ImportError:  # pragma: no cover - defensive fallback
    import logging as _stdlib_logging

    logger = _stdlib_logging.getLogger("media_db_sqlite_bootstrap")
    logging = logger

_MEDIA_NONCRITICAL_EXCEPTIONS: tuple[type[BaseException], ...] = MEDIA_NONCRITICAL_EXCEPTIONS


def apply_sqlite_connection_pragmas(db: Any, conn: Any) -> None:
    """Apply SQLite PRAGMAs through the native runtime seam."""

    if db.backend_type != BackendType.SQLITE:
        return
    try:
        cfg = getattr(db.backend, "config", None)
        wal_mode = True
        foreign_keys = True
        if cfg is not None:
            wal_mode = bool(getattr(cfg, "sqlite_wal_mode", True))
            foreign_keys = bool(getattr(cfg, "sqlite_foreign_keys", True))

        configure_sqlite_connection(
            conn,
            use_wal=wal_mode,
            synchronous="NORMAL" if wal_mode else None,
            foreign_keys=foreign_keys,
            busy_timeout_ms=10000,
            cache_size=-2000,
        )
    except _MEDIA_NONCRITICAL_EXCEPTIONS:
        pass


__all__ = ["apply_sqlite_connection_pragmas"]
