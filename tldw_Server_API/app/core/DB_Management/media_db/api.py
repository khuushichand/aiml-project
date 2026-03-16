"""Public API for the incremental Media DB package."""

from typing import TYPE_CHECKING

from tldw_Server_API.app.core.DB_Management.media_db.repositories import (
    MediaRepository,
)
from tldw_Server_API.app.core.DB_Management.media_db.runtime.session import (
    MediaDbFactory,
    MediaDbSession,
)

if TYPE_CHECKING:
    from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase


def get_media_repository(db: "MediaDatabase") -> MediaRepository:
    """Return the repository-backed media ingest interface for a legacy DB session."""
    return MediaRepository.from_legacy_db(db)


__all__ = ["MediaDbFactory", "MediaDbSession", "MediaRepository", "get_media_repository"]
