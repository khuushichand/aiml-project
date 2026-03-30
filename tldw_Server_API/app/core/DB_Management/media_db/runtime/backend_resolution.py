"""Backend resolution helpers owned by the package-native Media DB runtime."""

from __future__ import annotations

import os
from configparser import ConfigParser
from typing import Any

from tldw_Server_API.app.core.DB_Management.backends.base import (
    BackendType,
    DatabaseBackend,
    DatabaseConfig,
)
from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory
from tldw_Server_API.app.core.DB_Management.content_backend import (
    get_content_backend,
    load_content_db_settings,
)
from tldw_Server_API.app.core.DB_Management.media_db.errors import DatabaseError
from tldw_Server_API.app.core.DB_Management.media_db.runtime.noncritical import (
    MEDIA_NONCRITICAL_EXCEPTIONS,
)
from tldw_Server_API.app.core.config import load_comprehensive_config
from tldw_Server_API.app.core.testing import is_test_mode

_MEDIA_NONCRITICAL_EXCEPTIONS: tuple[type[BaseException], ...] = MEDIA_NONCRITICAL_EXCEPTIONS


def _resolve_backend(
    self: Any,
    *,
    backend: DatabaseBackend | None,
    config: ConfigParser | None,
) -> DatabaseBackend:
    """Resolve the backend used by a MediaDatabase instance."""

    if backend is not None:
        return backend

    parser: ConfigParser | None = config
    if parser is None:
        try:
            parser = load_comprehensive_config()
        except _MEDIA_NONCRITICAL_EXCEPTIONS:
            parser = None

    backend_mode_env = (os.getenv("CONTENT_DB_MODE") or os.getenv("TLDW_CONTENT_DB_BACKEND") or "").strip().lower()
    forced_postgres = backend_mode_env in {"postgres", "postgresql"}

    if not forced_postgres and parser is not None:
        try:
            content_settings = load_content_db_settings(parser)
            forced_postgres = content_settings.backend_type == BackendType.POSTGRESQL
        except _MEDIA_NONCRITICAL_EXCEPTIONS:
            pass

    try:
        test_mode = (
            os.getenv("PYTEST_CURRENT_TEST") is not None
            or is_test_mode()
        )
    except _MEDIA_NONCRITICAL_EXCEPTIONS:
        test_mode = False
    if forced_postgres and test_mode and self.db_path_str and self.db_path_str != ":memory:":
        forced_postgres = False

    if forced_postgres:
        if parser is None:
            raise DatabaseError("PostgreSQL content backend requested but configuration could not be loaded")  # noqa: TRY003
        resolved_backend = get_content_backend(parser)
        if resolved_backend is None or resolved_backend.backend_type != BackendType.POSTGRESQL:
            raise DatabaseError("PostgreSQL content backend requested but could not be initialized")  # noqa: TRY003
        return resolved_backend

    provided_path = self.db_path_str
    if provided_path:
        fallback_config = DatabaseConfig(
            backend_type=BackendType.SQLITE,
            sqlite_path=provided_path,
        )
        return DatabaseBackendFactory.create_backend(fallback_config)

    resolved = get_content_backend(parser) if parser else None
    if resolved is not None:
        return resolved

    raise DatabaseError(  # noqa: TRY003
        "MediaDatabase backend could not be resolved. "
        "Pass an explicit db_path or configure the content backend."
    )


__all__ = ["_resolve_backend"]
