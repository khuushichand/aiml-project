"""Public API for the incremental Media DB package."""

import contextlib
from collections.abc import Iterator
from typing import Any, Protocol

from tldw_Server_API.app.core.DB_Management.media_db.repositories import (
    MediaRepository,
)
from tldw_Server_API.app.core.DB_Management.media_db.runtime.factory import (
    MediaDbRuntimeConfig,
)
from tldw_Server_API.app.core.DB_Management.media_db.runtime.factory import (
    create_media_database as runtime_create_media_database,
)
from tldw_Server_API.app.core.DB_Management.media_db.runtime.session import (
    MediaDbFactory,
    MediaDbSession,
)
from tldw_Server_API.app.core.DB_Management.media_db.runtime.validation import (
    MediaDbLike,
)


class MediaWriterLike(Protocol):
    """Structural contract for repository-like media writers."""

    def add_media_with_keywords(self, **kwargs: Any) -> tuple[Any, Any, Any]:
        """Persist media content and return the legacy result tuple."""


def create_media_database(
    client_id: str,
    *,
    db_path: str | None = None,
    backend: Any = None,
    config: Any = None,
) -> MediaDbLike:
    """Create a MediaDatabase using the shared content runtime defaults."""
    from tldw_Server_API.app.core.DB_Management import DB_Manager

    runtime = MediaDbRuntimeConfig(
        default_db_path=str(DB_Manager.single_user_db_path),
        default_config=DB_Manager.single_user_config,
        postgres_content_mode=DB_Manager._POSTGRES_CONTENT_MODE,
        backend_loader=DB_Manager._ensure_content_backend_loaded,
    )
    return runtime_create_media_database(
        client_id,
        db_path=db_path,
        backend=backend,
        config=config,
        runtime=runtime,
    )


@contextlib.contextmanager
def managed_media_database(
    client_id: str,
    *,
    db_path: str | None = None,
    backend=None,
    config=None,
    initialize: bool = True,
    suppress_init_exceptions: tuple[type[BaseException], ...] = (),
    suppress_close_exceptions: tuple[type[BaseException], ...] = (),
) -> Iterator[MediaDbLike]:
    """Create a MediaDatabase, optionally initialize it, and always close it on exit."""
    db = create_media_database(
        client_id,
        db_path=db_path,
        backend=backend,
        config=config,
    )
    try:
        if initialize:
            if suppress_init_exceptions:
                with contextlib.suppress(*suppress_init_exceptions):
                    db.initialize_db()
            else:
                db.initialize_db()
        yield db
    finally:
        if suppress_close_exceptions:
            with contextlib.suppress(*suppress_close_exceptions):
                db.close_connection()
        else:
            db.close_connection()


def get_media_repository(db: MediaDbLike | MediaWriterLike) -> MediaRepository | MediaWriterLike:
    """Return a repository-backed media ingest interface for DB sessions or writer doubles."""
    add_media = getattr(db, "add_media_with_keywords", None)
    transaction = getattr(db, "transaction", None)
    if callable(add_media) and not callable(transaction):
        return db
    return MediaRepository.from_legacy_db(db)


__all__ = [
    "MediaDbFactory",
    "MediaDbRuntimeConfig",
    "MediaDbSession",
    "MediaWriterLike",
    "MediaRepository",
    "create_media_database",
    "managed_media_database",
    "get_media_repository",
]
