"""Repository-backed legacy wrapper functions extracted from the media DB shim."""

from __future__ import annotations

from typing import Any

import yaml
from loguru import logger

from tldw_Server_API.app.core.DB_Management.media_db.errors import InputError
from tldw_Server_API.app.core.DB_Management.media_db.repositories.document_versions_repository import (
    DocumentVersionsRepository,
)
from tldw_Server_API.app.core.DB_Management.media_db.repositories.media_repository import (
    MediaRepository,
)
from tldw_Server_API.app.core.DB_Management.media_db.runtime.validation import (
    MediaDbLike,
    require_media_database_like,
)


def get_document_version(
    db_instance: MediaDbLike,
    media_id: int,
    version_number: int | None = None,
    include_content: bool = True,
) -> dict[str, Any] | None:
    db_instance = require_media_database_like(
        db_instance,
        error_message="db_instance must be a Database object.",
    )
    return DocumentVersionsRepository.from_legacy_db(db_instance).get(
        media_id=media_id,
        version_number=version_number,
        include_content=include_content,
    )


def ingest_article_to_db_new(
    db_instance: MediaDbLike,
    *,
    url: str,
    title: str,
    content: str,
    author: str | None = None,
    keywords: list[str] | None = None,
    summary: str | None = None,
    ingestion_date: str | None = None,
    custom_prompt: str | None = None,
    overwrite: bool = False,
) -> tuple[int | None, str | None, str]:
    db_instance = require_media_database_like(
        db_instance,
        error_message="db_instance required.",
    )
    if not url or not title or content is None:
        raise InputError("URL, Title, and Content are required.")  # noqa: TRY003
    media_repo = MediaRepository.from_legacy_db(db_instance)
    return media_repo.add_media_with_keywords(
        url=url,
        title=title,
        media_type="article",
        content=content,
        keywords=keywords,
        prompt=custom_prompt,
        analysis_content=summary,
        author=author,
        ingestion_date=ingestion_date,
        overwrite=overwrite,
    )


def import_obsidian_note_to_db(
    db_instance: MediaDbLike,
    note_data: dict[str, Any],
) -> tuple[int | None, str | None, str]:
    db_instance = require_media_database_like(
        db_instance,
        error_message="db_instance required.",
    )
    required = ["title", "content"]
    missing = [k for k in required if k not in note_data or note_data[k] is None]
    if missing:
        raise InputError(f"Obsidian note missing required keys: {missing}")  # noqa: TRY003

    url_id = f"obsidian://note/{note_data['title']}"
    keywords = note_data.get("tags", [])
    keywords = [str(k) for k in keywords if isinstance(k, (str, int))]

    frontmatter = note_data.get("frontmatter")
    author = None
    frontmatter_str = None
    if isinstance(frontmatter, dict):
        author = frontmatter.get("author")
        try:
            frontmatter_str = yaml.dump(frontmatter, default_flow_style=False)
        except (TypeError, ValueError, yaml.YAMLError):
            logger.exception("Error dumping frontmatter")

    media_repo = MediaRepository.from_legacy_db(db_instance)
    return media_repo.add_media_with_keywords(
        url=url_id,
        title=note_data["title"],
        media_type="obsidian_note",
        content=note_data["content"],
        keywords=keywords,
        author=author,
        prompt="Obsidian Frontmatter" if frontmatter_str else None,
        analysis_content=frontmatter_str,
        ingestion_date=note_data.get("file_created_date"),
        overwrite=note_data.get("overwrite", False),
    )


__all__ = [
    "get_document_version",
    "import_obsidian_note_to_db",
    "ingest_article_to_db_new",
]
