from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase


class MediaRepository:
    """Caller-facing seam for media persistence while internals migrate out of the shim."""

    def __init__(self, session: MediaDatabase):
        self.session = session

    @classmethod
    def from_legacy_db(cls, db: MediaDatabase) -> "MediaRepository":
        return cls(session=db)

    def add_text_media(
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
        return self.session.add_media_with_keywords(
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
