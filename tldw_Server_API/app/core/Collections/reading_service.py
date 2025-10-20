from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Dict, List, Optional

from loguru import logger

from tldw_Server_API.app.core.Collections.embedding_queue import enqueue_embeddings_job_for_item
from tldw_Server_API.app.core.Collections.utils import hash_text_sha256, truncate_text, word_count
from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase, ContentItemRow


READING_DEFAULT_STATUS = "saved"


@dataclass
class ReadingSaveResult:
    item: ContentItemRow
    media_id: Optional[int]
    media_uuid: Optional[str]
    created: bool


class ReadingService:
    """Utilities for Reading List capture and updates."""

    def __init__(self, user_id: int | str) -> None:
        self.user_id = int(user_id)
        self.collections = CollectionsDatabase.for_user(self.user_id)

    async def save_url(
        self,
        *,
        url: str,
        tags: Optional[List[str]] = None,
        status: Optional[str] = None,
        favorite: bool = False,
        title_override: Optional[str] = None,
        summary_override: Optional[str] = None,
        content_override: Optional[str] = None,
        metadata: Optional[Dict[str, object]] = None,
    ) -> ReadingSaveResult:
        """Fetch, dedupe, and persist a reading item."""
        normalized_status = (status or READING_DEFAULT_STATUS).lower()
        tags = [t for t in (tags or []) if t]
        article = await self._fetch_article(
            url=url,
            title_override=title_override,
            content_override=content_override,
            summary_override=summary_override,
        )

        title = article.get("title") or title_override or url
        content = article.get("content") or summary_override or ""
        summary = summary_override or article.get("summary") or truncate_text(content, limit=600)
        canonical_url = article.get("canonical_url") or article.get("url") or url
        published_at = article.get("published") or None

        metadata_payload: Dict[str, object] = {
            "source": "reading_save",
            "tags": tags,
            "author": article.get("author"),
        }
        if metadata:
            metadata_payload.update(metadata)

        item_row = self.collections.upsert_content_item(
            origin="reading",
            origin_type="manual",
            origin_id=None,
            url=url,
            canonical_url=canonical_url,
            domain=None,
            title=title,
            summary=summary,
            content_hash=hash_text_sha256(content),
            word_count=word_count(content),
            published_at=published_at,
            status=normalized_status,
            favorite=favorite,
            metadata=metadata_payload,
            media_id=None,
            job_id=None,
            run_id=None,
            source_id=None,
            read_at=None,
            tags=tags,
        )

        if item_row.is_new or item_row.content_changed:
            try:
                await enqueue_embeddings_job_for_item(
                    user_id=self.user_id,
                    item_id=item_row.id,
                    content=content,
                    metadata={
                        "origin": "reading",
                        "tags": tags,
                    },
                )
            except Exception as exc:
                logger.debug(f"Embedding enqueue failed for reading item {item_row.id}: {exc}")

        return ReadingSaveResult(
            item=item_row,
            media_id=None,
            media_uuid=None,
            created=item_row.is_new,
        )

    async def _fetch_article(
        self,
        *,
        url: str,
        title_override: Optional[str],
        content_override: Optional[str],
        summary_override: Optional[str],
    ) -> Dict[str, Optional[str]]:
        if content_override is not None:
            return {
                "url": url,
                "canonical_url": url,
                "title": title_override or url,
                "content": content_override,
                "summary": summary_override,
                "author": None,
                "published": None,
            }

        loop = asyncio.get_running_loop()

        def _scrape() -> Dict[str, Optional[str]]:
            from tldw_Server_API.app.core.Web_Scraping.Article_Extractor_Lib import (
                scrape_article_blocking,
                ContentMetadataHandler,
            )

            data = scrape_article_blocking(url)
            if not data:
                raise ValueError("article_fetch_failed")
            content = data.get("content") or ""
            try:
                content = ContentMetadataHandler.strip_metadata(content)  # type: ignore[attr-defined]
            except Exception:
                pass
            return {
                "url": data.get("url") or url,
                "canonical_url": data.get("canonical_url") or data.get("url") or url,
                "title": data.get("title") or title_override or url,
                "content": content,
                "summary": data.get("summary"),
                "author": data.get("author"),
                "published": data.get("date") or data.get("published"),
            }

        try:
            return await loop.run_in_executor(None, _scrape)
        except Exception as exc:
            logger.debug(f"Reading article fetch failed for {url}: {exc}")
            raise

    def list_items(
        self,
        *,
        status: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        favorite: Optional[bool] = None,
        q: Optional[str] = None,
        domain: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[List[ContentItemRow], int]:
        return self.collections.list_content_items(
            origin="reading",
            status=status,
            tags=tags,
            favorite=favorite,
            q=q,
            domain=domain,
            page=page,
            size=size,
        )

    def update_item(
        self,
        item_id: int,
        *,
        status: Optional[str] = None,
        favorite: Optional[bool] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, object]] = None,
    ) -> ContentItemRow:
        normalized_tags = tags if tags is None else [t for t in tags if t]
        metadata = metadata or {}
        return self.collections.update_content_item(
            item_id,
            status=status,
            favorite=favorite,
            tags=normalized_tags,
            metadata=metadata if metadata else None,
        )
