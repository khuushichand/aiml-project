"""Shared runtime defaults for Media DB construction."""

from __future__ import annotations

import configparser
from contextlib import nullcontext
from typing import Optional

from loguru import logger

from tldw_Server_API.app.core.config import load_comprehensive_config
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType, DatabaseBackend
from tldw_Server_API.app.core.DB_Management.content_backend import (
    ContentDatabaseSettings,
    get_content_backend,
    load_content_db_settings,
)
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.DB_Management.media_db.runtime.factory import (
    MediaDbRuntimeConfig,
)

MEDIA_DB_RUNTIME_EXCEPTIONS = (
    OSError,
    RuntimeError,
    ValueError,
    TypeError,
    AttributeError,
    KeyError,
    configparser.Error,
)

single_user_config = load_comprehensive_config()
content_db_settings: ContentDatabaseSettings = load_content_db_settings(single_user_config)
postgres_content_mode = content_db_settings.backend_type == BackendType.POSTGRESQL
single_user_db_path: str = (
    content_db_settings.sqlite_path
    or str(DatabasePaths.get_media_db_path(DatabasePaths.get_single_user_id()))
)
content_db_backend: Optional[DatabaseBackend] = None
try:
    from threading import RLock

    _runtime_state_lock = RLock()
except Exception:  # pragma: no cover
    _runtime_state_lock = None  # type: ignore


def _runtime_state_context():
    if _runtime_state_lock is None:
        return nullcontext()
    return _runtime_state_lock


def _clear_content_backend_cache_inner() -> None:
    try:
        import tldw_Server_API.app.core.DB_Management.content_backend as cb

        if hasattr(cb, "_cache_lock") and cb._cache_lock:
            with cb._cache_lock:  # type: ignore[attr-defined]
                cb.clear_cached_backend()
        else:
            cb.clear_cached_backend()
    except ImportError as exc:
        logger.debug(f"reset_media_runtime_defaults: unable to import content_backend: {exc}")
    except MEDIA_DB_RUNTIME_EXCEPTIONS as exc:
        logger.debug(f"reset_media_runtime_defaults: failed to clear backend cache: {exc}")


def _clear_content_backend_cache() -> None:
    global content_db_backend

    with _runtime_state_context():
        content_db_backend = None
        _clear_content_backend_cache_inner()


def ensure_content_backend_loaded() -> Optional[DatabaseBackend]:
    """Lazily resolve the shared content backend when PostgreSQL mode is active."""
    global content_db_backend

    with _runtime_state_context():
        if postgres_content_mode and content_db_backend is None:
            try:
                content_db_backend = get_content_backend(single_user_config)
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"Unable to initialize PostgreSQL content backend lazily: {exc}")
                content_db_backend = None
        return content_db_backend


def get_content_backend_instance() -> Optional[DatabaseBackend]:
    """Return the shared content DatabaseBackend instance (if configured)."""
    with _runtime_state_context():
        backend = ensure_content_backend_loaded()
        if postgres_content_mode and backend is None:
            raise RuntimeError(
                "PostgreSQL content backend is required but was not initialized. "
                "Check TLDW_CONTENT_DB_BACKEND configuration."
            )
        return backend


def reset_media_runtime_defaults(
    *,
    config: configparser.ConfigParser | None = None,
    reload: bool = True,
) -> Optional[DatabaseBackend]:
    """Reset shared Media DB runtime defaults and optionally reload the backend."""
    global single_user_config, content_db_settings, postgres_content_mode
    global single_user_db_path, content_db_backend

    with _runtime_state_context():
        cfg = config or single_user_config
        content_db_backend = None
        _clear_content_backend_cache_inner()

        single_user_config = cfg
        content_db_settings = load_content_db_settings(cfg)
        postgres_content_mode = content_db_settings.backend_type == BackendType.POSTGRESQL
        single_user_db_path = (
            content_db_settings.sqlite_path
            or str(DatabasePaths.get_media_db_path(DatabasePaths.get_single_user_id()))
        )

        if reload:
            try:
                content_db_backend = get_content_backend(cfg)
            except MEDIA_DB_RUNTIME_EXCEPTIONS as exc:
                logger.debug(f"reset_media_runtime_defaults: unable to rebuild content backend: {exc}")
        return content_db_backend


def build_media_runtime_config() -> MediaDbRuntimeConfig:
    """Return the shared runtime configuration used to construct Media DB handles."""
    with _runtime_state_context():
        return MediaDbRuntimeConfig(
            default_db_path=str(single_user_db_path),
            default_config=single_user_config,
            postgres_content_mode=postgres_content_mode,
            backend_loader=ensure_content_backend_loaded,
        )


__all__ = [
    "MEDIA_DB_RUNTIME_EXCEPTIONS",
    "build_media_runtime_config",
    "content_db_backend",
    "content_db_settings",
    "ensure_content_backend_loaded",
    "get_content_backend_instance",
    "postgres_content_mode",
    "reset_media_runtime_defaults",
    "single_user_config",
    "single_user_db_path",
]
