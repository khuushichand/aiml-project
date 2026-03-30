"""Bootstrap lifecycle helpers owned by the package-native Media DB runtime."""

from __future__ import annotations

import sqlite3
import threading
from configparser import ConfigParser
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from tldw_Server_API.app.core.DB_Management.backends.base import (
    BackendType,
    DatabaseBackend,
)
from tldw_Server_API.app.core.DB_Management.backends.base import (
    DatabaseError as BackendDatabaseError,
)
from tldw_Server_API.app.core.DB_Management.media_db.errors import (
    DatabaseError,
    SchemaError,
)
from tldw_Server_API.app.core.DB_Management.media_db.runtime.noncritical import (
    MEDIA_NONCRITICAL_EXCEPTIONS,
)

try:
    from loguru import logger

    logging = logger
except ImportError:  # pragma: no cover - defensive fallback
    import logging as _stdlib_logging

    logger = _stdlib_logging.getLogger("media_db_bootstrap_lifecycle")
    logging = logger

_MEDIA_NONCRITICAL_EXCEPTIONS: tuple[type[BaseException], ...] = MEDIA_NONCRITICAL_EXCEPTIONS


def initialize_media_database(
    self: Any,
    db_path: str | Path,
    client_id: str,
    *,
    backend: DatabaseBackend | None = None,
    config: ConfigParser | None = None,
    default_org_id: int | None = None,
    default_team_id: int | None = None,
) -> None:
    """Initialize the Media DB instance and bootstrap its schema."""

    if isinstance(db_path, str) and db_path.strip() == "":
        raise ValueError("db_path cannot be an empty string; pass an explicit path or ':memory:'")  # noqa: TRY003

    if isinstance(db_path, Path):
        self.is_memory_db = False
        self.db_path = db_path.resolve()
    else:
        self.is_memory_db = db_path == ":memory:"
        if self.is_memory_db:
            self.db_path = Path(":memory:")
        else:
            self.db_path = Path(db_path).resolve()

    self.db_path_str = str(self.db_path) if not self.is_memory_db else ":memory:"

    if not client_id:
        raise ValueError("Client ID cannot be empty or None.")  # noqa: TRY003
    self.client_id = client_id

    if not self.is_memory_db:
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise DatabaseError(
                f"Failed to create database directory {self.db_path.parent}: {exc}"
            ) from exc  # noqa: TRY003

    logging.info(
        f"Initializing Database object for path: {self.db_path_str} [Client ID: {self.client_id}]"
    )

    self.backend = self._resolve_backend(backend=backend, config=config)
    self.backend_type = self.backend.backend_type
    self.default_org_id = default_org_id
    self.default_team_id = default_team_id

    self._txn_conn_var = ContextVar(
        f"media_db_txn_conn_{id(self)}",
        default=None,
    )
    self._tx_depth_var = ContextVar(
        f"media_db_tx_depth_{id(self)}",
        default=0,
    )
    self._persistent_conn_var = ContextVar(
        f"media_db_persistent_conn_{id(self)}",
        default=None,
    )
    self._persistent_conn = None

    if self.backend_type == BackendType.SQLITE and self.is_memory_db:
        persistent_conn = sqlite3.connect(
            self.db_path_str,
            check_same_thread=False,
            isolation_level=None,
        )
        try:
            persistent_conn.row_factory = sqlite3.Row
            self._apply_sqlite_connection_pragmas(persistent_conn)
        except sqlite3.Error:
            pass
        self._persistent_conn = persistent_conn

    self._media_insert_lock = threading.Lock()
    self._scope_cache = (self.default_org_id, self.default_team_id)

    initialization_successful = False
    try:
        self._initialize_schema()
        initialization_successful = True
    except (DatabaseError, SchemaError, sqlite3.Error, BackendDatabaseError) as exc:
        logging.critical(
            f"FATAL: DB Initialization failed for {self.db_path_str}: {exc}",
            exc_info=True,
        )
        self.close_connection()
        raise DatabaseError(f"Database initialization failed: {exc}") from exc  # noqa: TRY003
    except _MEDIA_NONCRITICAL_EXCEPTIONS as exc:
        logging.critical(
            f"FATAL: Unexpected error during DB Initialization for {self.db_path_str}: {exc}",
            exc_info=True,
        )
        self.close_connection()
        raise DatabaseError(f"Unexpected database initialization error: {exc}") from exc  # noqa: TRY003
    finally:
        if initialization_successful:
            logging.debug(
                f"Database initialization completed successfully for {self.db_path_str}"
            )
        else:
            logging.error(
                f"Database initialization block finished for {self.db_path_str}, but failed."
            )


def initialize_db(self: Any):
    """Revalidate schema state for legacy callers and return ``self``."""

    try:
        self._initialize_schema()
    except _MEDIA_NONCRITICAL_EXCEPTIONS as exc:
        raise DatabaseError(f"Database initialization failed: {exc}") from exc  # noqa: TRY003
    return self


def _ensure_sqlite_backend(self: Any) -> None:
    """Compatibility no-op retained for legacy bootstrap callers."""

    if self.backend_type != BackendType.SQLITE:
        return


__all__ = [
    "initialize_media_database",
    "initialize_db",
    "_ensure_sqlite_backend",
]
