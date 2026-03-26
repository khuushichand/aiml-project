"""Package-owned compat entrypoint helpers for Media DB read/write shims."""

from __future__ import annotations

from typing import Any

from tldw_Server_API.app.core.DB_Management.media_db import api as media_db_api
from tldw_Server_API.app.core.DB_Management.media_db.repositories.media_repository import (
    MediaRepository,
)


def run_search_media_db(
    self,
    search_query: str | None,
    search_fields: list[str] | None = None,
    media_types: list[str] | None = None,
    date_range: dict[str, Any] | None = None,
    must_have_keywords: list[str] | None = None,
    must_not_have_keywords: list[str] | None = None,
    sort_by: str | None = "last_modified_desc",
    boost_fields: dict[str, float] | None = None,
    media_ids_filter: list[int | str] | None = None,
    page: int = 1,
    results_per_page: int = 20,
    include_trash: bool = False,
    include_deleted: bool = False,
) -> tuple[list[dict[str, Any]], int]:
    """Forward media search through the package API seam."""
    return media_db_api.search_media(
        self,
        search_query=search_query,
        search_fields=search_fields,
        media_types=media_types,
        date_range=date_range,
        must_have_keywords=must_have_keywords,
        must_not_have_keywords=must_not_have_keywords,
        sort_by=sort_by,
        boost_fields=boost_fields,
        media_ids_filter=media_ids_filter,
        page=page,
        results_per_page=results_per_page,
        include_trash=include_trash,
        include_deleted=include_deleted,
    )


def run_add_media_with_keywords(
    self,
    *,
    url: str | None = None,
    title: str | None = None,
    media_type: str | None = None,
    content: str | None = None,
    keywords: list[str] | None = None,
    prompt: str | None = None,
    analysis_content: str | None = None,
    safe_metadata: str | None = None,
    source_hash: str | None = None,
    transcription_model: str | None = None,
    author: str | None = None,
    ingestion_date: str | None = None,
    overwrite: bool = False,
    chunk_options: dict[str, Any] | None = None,
    chunks: list[dict[str, Any]] | None = None,
    visibility: str | None = None,
    owner_user_id: int | None = None,
) -> tuple[int | None, str | None, str]:
    """Forward media ingest through the repository compatibility seam."""
    return MediaRepository.from_legacy_db(self).add_media_with_keywords(
        url=url,
        title=title,
        media_type=media_type,
        content=content,
        keywords=keywords,
        prompt=prompt,
        analysis_content=analysis_content,
        safe_metadata=safe_metadata,
        source_hash=source_hash,
        transcription_model=transcription_model,
        author=author,
        ingestion_date=ingestion_date,
        overwrite=overwrite,
        chunk_options=chunk_options,
        chunks=chunks,
        visibility=visibility,
        owner_user_id=owner_user_id,
    )


__all__ = [
    "run_add_media_with_keywords",
    "run_search_media_db",
]
