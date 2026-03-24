"""Runtime-owned wrappers for document-version and keyword helper methods."""

from __future__ import annotations

from typing import Any

from tldw_Server_API.app.core.DB_Management.media_db import api as media_db_api
from tldw_Server_API.app.core.DB_Management.media_db.repositories.document_versions_repository import (
    DocumentVersionsRepository,
)
from tldw_Server_API.app.core.DB_Management.media_db.repositories.keywords_repository import (
    KeywordsRepository,
)


def create_document_version(
    self,
    media_id: int,
    content: str,
    prompt: str | None = None,
    analysis_content: str | None = None,
    safe_metadata: str | None = None,
) -> dict[str, Any]:
    return media_db_api.create_document_version(
        self,
        media_id=media_id,
        content=content,
        prompt=prompt,
        analysis_content=analysis_content,
        safe_metadata=safe_metadata,
    )


def update_keywords_for_media(
    self,
    media_id: int,
    keywords: list[str],
    conn: Any | None = None,
):
    return media_db_api.update_keywords_for_media(
        self,
        media_id=media_id,
        keywords=keywords,
        conn=conn,
    )


def soft_delete_keyword(self, keyword: str) -> bool:
    return KeywordsRepository.from_legacy_db(self).soft_delete(keyword)


def soft_delete_document_version(self, version_uuid: str) -> bool:
    return DocumentVersionsRepository.from_legacy_db(self).soft_delete(version_uuid)


def get_all_document_versions(
    self,
    media_id: int,
    include_content: bool = False,
    include_deleted: bool = False,
    limit: int | None = None,
    offset: int | None = 0,
) -> list[dict[str, Any]]:
    return media_db_api.get_all_document_versions(
        self,
        media_id,
        include_content=include_content,
        include_deleted=include_deleted,
        limit=limit,
        offset=offset,
    )


__all__ = [
    "create_document_version",
    "get_all_document_versions",
    "soft_delete_document_version",
    "soft_delete_keyword",
    "update_keywords_for_media",
]
