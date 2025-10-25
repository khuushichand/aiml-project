"""Utilities for loading and instantiating content database backends.

This module centralises configuration handling for the Media/ChaCha content
stores so they can run on either SQLite or PostgreSQL backends using the
shared DatabaseBackend abstraction.
"""

from __future__ import annotations

import os
from configparser import ConfigParser
from dataclasses import dataclass
from typing import Optional

from tldw_Server_API.app.core.DB_Management.backends.base import (
    BackendType,
    DatabaseConfig,
)
from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory


_DEFAULT_SQLITE_PATH = ""
_DEFAULT_BACKUP_PATH = "./tldw_DB_Backups/"


@dataclass
class ContentDatabaseSettings:
    """Resolved configuration for the content database backend."""

    raw_backend_type: str
    backend_type: Optional[BackendType]
    database_config: Optional[DatabaseConfig]
    sqlite_path: Optional[str]
    backup_path: Optional[str]


def _normalise_backend_name(raw_backend: str) -> str:
    """Normalise backend identifier from config/environment."""
    if not raw_backend:
        return "sqlite"
    return raw_backend.strip().lower()


def _backend_type_from_raw(raw_backend: str) -> Optional[BackendType]:
    """Map textual backend identifiers to BackendType enum where supported."""
    if raw_backend in {"sqlite", "sqlite3"}:
        return BackendType.SQLITE
    if raw_backend in {"postgres", "postgresql"}:
        return BackendType.POSTGRESQL
    # elasticsearch / opensearch are planned but handled elsewhere for now
    return None


def load_content_db_settings(config: ConfigParser) -> ContentDatabaseSettings:
    """Build ContentDatabaseSettings from config parser and environment."""
    raw_backend = _normalise_backend_name(
        os.getenv("TLDW_CONTENT_DB_BACKEND")
        or config.get("Database", "type", fallback="sqlite")
    )

    backend_type = _backend_type_from_raw(raw_backend)

    sqlite_path = os.getenv("TLDW_CONTENT_SQLITE_PATH") or config.get(
        "Database", "sqlite_path", fallback=_DEFAULT_SQLITE_PATH
    )
    backup_path = os.getenv("TLDW_DB_BACKUP_PATH") or config.get(
        "Database", "backup_path", fallback=_DEFAULT_BACKUP_PATH
    )

    database_config: Optional[DatabaseConfig]
    if backend_type == BackendType.SQLITE:
        database_config = DatabaseConfig(
            backend_type=BackendType.SQLITE,
            sqlite_path=sqlite_path,
            sqlite_wal_mode=config.getboolean(
                "Database", "sqlite_wal_mode", fallback=True
            ),
            sqlite_foreign_keys=config.getboolean(
                "Database", "sqlite_foreign_keys", fallback=True
            ),
            pool_size=config.getint("Database", "pool_size", fallback=10),
            max_overflow=config.getint("Database", "max_overflow", fallback=20),
            pool_timeout=config.getfloat("Database", "pool_timeout", fallback=30.0),
        )
    elif backend_type == BackendType.POSTGRESQL:
        # Allow multiple environment variable conventions so local test suites
        # (which historically relied on POSTGRES_TEST_* values) work without
        # extra configuration. Explicit TLDW_* overrides always win.
        pg_dsn = os.getenv("TLDW_CONTENT_PG_DSN") or os.getenv("POSTGRES_TEST_DSN")

        def _env_chain(*names: str, fallback: Optional[str] = None) -> Optional[str]:
            for name in names:
                value = os.getenv(name)
                if value:
                    return value
            return fallback

        database_config = DatabaseConfig(
            backend_type=BackendType.POSTGRESQL,
            connection_string=pg_dsn
            or config.get("Database", "pg_connection_string", fallback=None),
            pg_host=_env_chain(
                "TLDW_CONTENT_PG_HOST",
                "TLDW_PG_HOST",
                "POSTGRES_TEST_HOST",
                fallback=config.get("Database", "pg_host", fallback="localhost"),
            ),
            pg_port=int(
                _env_chain(
                    "TLDW_CONTENT_PG_PORT",
                    "TLDW_PG_PORT",
                    "POSTGRES_TEST_PORT",
                )
                or config.get("Database", "pg_port", fallback=5432)
            ),
            pg_database=_env_chain(
                "TLDW_CONTENT_PG_DATABASE",
                "TLDW_PG_DATABASE",
                "POSTGRES_TEST_DATABASE",
                fallback=config.get("Database", "pg_database", fallback="tldw_content"),
            ),
            pg_user=_env_chain(
                "TLDW_CONTENT_PG_USER",
                "TLDW_PG_USER",
                "POSTGRES_TEST_USER",
                fallback=config.get("Database", "pg_user", fallback="tldw_user"),
            ),
            pg_password=_env_chain(
                "TLDW_CONTENT_PG_PASSWORD",
                "TLDW_PG_PASSWORD",
                "POSTGRES_TEST_PASSWORD",
                fallback=config.get("Database", "pg_password", fallback=""),
            ),
            pg_sslmode=_env_chain(
                "TLDW_CONTENT_PG_SSLMODE",
                "TLDW_PG_SSLMODE",
                fallback=config.get("Database", "pg_sslmode", fallback="prefer"),
            ),
            pool_size=config.getint("Database", "pg_pool_size", fallback=20),
            max_overflow=config.getint("Database", "pg_max_overflow", fallback=40),
            pool_timeout=config.getfloat("Database", "pg_pool_timeout", fallback=30.0),
        )
    else:
        database_config = None

    return ContentDatabaseSettings(
        raw_backend_type=raw_backend,
        backend_type=backend_type,
        database_config=database_config,
        sqlite_path=sqlite_path,
        backup_path=backup_path,
    )


_cached_backend = None
_cached_backend_signature: Optional[tuple] = None
try:
    from threading import RLock
    _cache_lock = RLock()
except Exception:  # pragma: no cover
    _cache_lock = None  # type: ignore


def get_content_backend(config: ConfigParser):
    """Return a DatabaseBackend instance for content storage if supported.

    Thread-safe around cache check and creation to handle concurrent reloads.
    """
    global _cached_backend, _cached_backend_signature

    settings = load_content_db_settings(config)
    if not settings.database_config:
        return None

    # Only create a backend for PostgreSQL content mode. For SQLite, return None
    # so callers resolve per-user file paths instead of a root-level DB.
    if settings.backend_type != BackendType.POSTGRESQL:
        return None

    signature = (
        settings.backend_type,
        settings.database_config.connection_string,
        settings.database_config.sqlite_path,
        settings.database_config.pg_host,
        settings.database_config.pg_port,
        settings.database_config.pg_database,
        settings.database_config.pg_user,
    )

    if _cache_lock is not None:
        with _cache_lock:
            if _cached_backend and _cached_backend_signature == signature:
                return _cached_backend
            backend = DatabaseBackendFactory.create_backend(settings.database_config)
            _cached_backend = backend
            _cached_backend_signature = signature
            return backend

    # Fallback without lock (environments without threading)
    if _cached_backend and _cached_backend_signature == signature:
        return _cached_backend
    backend = DatabaseBackendFactory.create_backend(settings.database_config)
    _cached_backend = backend
    _cached_backend_signature = signature
    return backend
