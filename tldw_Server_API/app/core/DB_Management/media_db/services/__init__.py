"""Focused read services extracted from Media DB."""

from tldw_Server_API.app.core.DB_Management.media_db.services.media_details_service import (
    get_full_media_details,
    get_full_media_details_rich,
)

__all__ = [
    "get_full_media_details",
    "get_full_media_details_rich",
]
