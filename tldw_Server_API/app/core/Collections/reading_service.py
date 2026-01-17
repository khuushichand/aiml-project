from __future__ import annotations

import asyncio
import inspect
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from loguru import logger

from tldw_Server_API.app.core.Collections.embedding_queue import enqueue_embeddings_job_for_item
from tldw_Server_API.app.core.Collections.utils import hash_text_sha256, truncate_text, word_count
from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase, ContentItemRow
from tldw_Server_API.app.core.Collections.reading_importers import ReadingImportItem, normalize_import_items
from tldw_Server_API.app.core.Ingestion_Media_Processing.download_utils import (
    _enforce_max_bytes_from_headers,
    _resolve_max_bytes,
    _resolve_media_type_from_content_type,
    _resolve_media_type_from_suffix,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.stt_provider_adapter import (
    resolve_default_transcription_model,
)
from tldw_Server_API.app.core.Web_Scraping.url_utils import normalize_for_crawl
from tldw_Server_API.app.core.http_client import afetch


READING_DEFAULT_STATUS = "saved"


def _contains_html_tag(raw: str) -> bool:
    """Return True when raw includes a tag-like "<a>" sequence."""
    if not raw:
        return False
    tag_started = False
    length = len(raw)
    for idx, ch in enumerate(raw):
        if tag_started:
            if ch == ">":
                return True
            continue
        if ch == "<" and idx + 1 < length:
            next_char = raw[idx + 1]
            if ("A" <= next_char <= "Z") or ("a" <= next_char <= "z"):
                tag_started = True
    return False


def _utcnow_iso() -> str:
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()


@dataclass
class ReadingSaveResult:
    item: ContentItemRow
    media_id: Optional[int]
    media_uuid: Optional[str]
    created: bool


@dataclass
class ReadingImportResult:
    imported: int
    updated: int
    skipped: int
    errors: List[str]


class ReadingService:
    """Utilities for Reading List capture and updates."""

    def __init__(self, user_id: int | str) -> None:
        self.user_id = int(user_id)
        self.collections = CollectionsDatabase.for_user(self.user_id)

    @staticmethod
    def _normalize_url(value: str, source: str) -> str:
        try:
            normalized = normalize_for_crawl(value, source)
        except Exception:
            return value
        return normalized or value

    @staticmethod
    async def _close_response(resp: Any) -> None:
        if resp is None:
            return
        close = getattr(resp, "aclose", None)
        if callable(close):
            try:
                result = close()
                if inspect.isawaitable(result):
                    await result
                return
            except Exception:
                return
        close = getattr(resp, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                return

    @staticmethod
    def _sanitize_html_content(raw: str) -> tuple[str, Optional[str]]:
        """Sanitize HTML input and return (text, clean_html) when HTML is detected."""
        if not _contains_html_tag(raw):
            return raw, None
        try:
            from tldw_Server_API.app.core.Ingestion_Media_Processing.Upload_Sink import FileValidator
            from tldw_Server_API.app.core.Web_Scraping.Article_Extractor_Lib import convert_html_to_markdown
        except Exception:
            return raw, None
        try:
            validator = FileValidator()
            sanitized_html = validator.sanitize_html_content(raw)
            text = convert_html_to_markdown(sanitized_html)
            return text, sanitized_html
        except Exception:
            return raw, None

    @staticmethod
    def _map_media_type_key(media_type_key: Optional[str]) -> Optional[str]:
        if not media_type_key:
            return None
        key = str(media_type_key).lower()
        if key == "xml":
            return "document"
        if key in {"pdf", "ebook", "document"}:
            return key
        return None

    async def _probe_url_metadata(self, url: str) -> Dict[str, Any]:
        """Fetch headers to infer media type and enforce size limits."""
        parsed = urlparse(url)
        suffix = Path(parsed.path).suffix.lower()
        media_type_key = _resolve_media_type_from_suffix(suffix)
        resp = None
        content_type: Optional[str] = None
        content_length: Optional[str] = None
        resolved_url: Optional[str] = None
        error: Optional[str] = None
        status_code: Optional[int] = None
        size_exceeded = False

        try:
            resp = await afetch(method="HEAD", url=url, timeout=10.0, allow_redirects=True)
            status_code = getattr(resp, "status_code", None)
            headers = getattr(resp, "headers", {}) or {}
            raw_content_type = headers.get("content-type") or headers.get("Content-Type") or ""
            content_type = raw_content_type.split(";", 1)[0].strip().lower() or None
            content_length = headers.get("content-length") or headers.get("Content-Length")
            resolved_url = str(getattr(resp, "url", "")) or url
            if isinstance(status_code, int) and status_code >= 400:
                error = f"head_status_{status_code}"
        except Exception as exc:
            error = str(exc)
        finally:
            await self._close_response(resp)

        if content_type:
            media_type_key = _resolve_media_type_from_content_type(content_type) or media_type_key

        if content_length:
            try:
                max_bytes = _resolve_max_bytes(
                    max_bytes=None,
                    media_type_key=media_type_key,
                    effective_suffix=suffix,
                    content_type=content_type or "",
                )
                _enforce_max_bytes_from_headers(url, content_length, max_bytes)
            except Exception as exc:
                error = str(exc)
                size_exceeded = True

        return {
            "media_type_key": media_type_key,
            "content_type": content_type,
            "content_length": content_length,
            "resolved_url": resolved_url,
            "error": error,
            "status_code": str(status_code) if status_code is not None else None,
            "size_exceeded": size_exceeded,
        }

    async def _ingest_non_html(
        self,
        *,
        url: str,
        media_type_key: Optional[str],
        title_override: Optional[str],
    ) -> Dict[str, Any]:
        """Route non-HTML URLs into the document ingestion pipeline."""
        media_type = self._map_media_type_key(media_type_key)
        if not media_type:
            return {
                "url": url,
                "canonical_url": url,
                "title": title_override or url,
                "content": "",
                "summary": None,
                "author": None,
                "published": None,
                "media_id": None,
                "media_uuid": None,
                "media_type": media_type_key,
                "error": f"unsupported_content_type:{media_type_key or 'unknown'}",
            }

        try:
            from tldw_Server_API.app.api.v1.schemas.media_request_models import AddMediaForm
            from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
            from tldw_Server_API.app.core.Ingestion_Media_Processing.chunking_options import (
                prepare_chunking_options_dict,
            )
            from tldw_Server_API.app.core.Ingestion_Media_Processing.input_sourcing import TempDirManager
            from tldw_Server_API.app.core.Ingestion_Media_Processing.persistence import (
                process_document_like_item,
            )
        except Exception as exc:
            return {
                "url": url,
                "canonical_url": url,
                "title": title_override or url,
                "content": "",
                "summary": None,
                "author": None,
                "published": None,
                "media_id": None,
                "media_uuid": None,
                "media_type": media_type_key,
                "error": f"ingestion_import_failed:{exc}",
            }

        form_data = AddMediaForm(
            media_type=media_type,
            urls=[url],
            title=title_override,
            perform_analysis=False,
            transcription_model=resolve_default_transcription_model("whisper-large-v3"),
        )
        chunk_options = prepare_chunking_options_dict(form_data)
        db_path = str(DatabasePaths.get_media_db_path(self.user_id))

        loop = asyncio.get_running_loop()
        try:
            with TempDirManager(prefix="reading_ingest_") as temp_dir:
                result = await process_document_like_item(
                    item_input_ref=url,
                    processing_source=url,
                    media_type=media_type,
                    is_url=True,
                    form_data=form_data,
                    chunk_options=chunk_options,
                    temp_dir=temp_dir,
                    loop=loop,
                    db_path=db_path,
                    client_id=str(self.user_id),
                    user_id=self.user_id,
                )
        except Exception as exc:
            return {
                "url": url,
                "canonical_url": url,
                "title": title_override or url,
                "content": "",
                "summary": None,
                "author": None,
                "published": None,
                "media_id": None,
                "media_uuid": None,
                "media_type": media_type,
                "error": f"ingestion_failed:{exc}",
            }

        metadata = result.get("metadata") if isinstance(result, dict) else None
        metadata = metadata if isinstance(metadata, dict) else {}
        error = result.get("error") if isinstance(result, dict) else None
        title = title_override or metadata.get("title") or url
        author = metadata.get("author")
        content = result.get("content") if isinstance(result, dict) else None
        summary = None
        if isinstance(result, dict):
            summary = result.get("summary") or result.get("analysis")

        return {
            "url": url,
            "canonical_url": url,
            "title": title,
            "content": content or "",
            "summary": summary,
            "author": author,
            "published": None,
            "media_id": result.get("db_id") if isinstance(result, dict) else None,
            "media_uuid": result.get("media_uuid") if isinstance(result, dict) else None,
            "media_type": media_type,
            "error": error,
        }

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
        notes: Optional[str] = None,
        metadata: Optional[Dict[str, object]] = None,
    ) -> ReadingSaveResult:
        """Fetch, dedupe, and persist a reading item."""
        normalized_status = (status or READING_DEFAULT_STATUS).lower()
        tags = [t for t in (tags or []) if t]
        try:
            article = await self._fetch_article(
                url=url,
                title_override=title_override,
                content_override=content_override,
                summary_override=summary_override,
            )
        except Exception as exc:
            logger.debug(f"Reading article fetch failed for {url}: {exc}")
            article = {
                "url": url,
                "canonical_url": url,
                "title": title_override or url,
                "content": "",
                "summary": summary_override,
                "author": None,
                "published": None,
                "media_id": None,
                "media_uuid": None,
                "media_type": None,
                "content_type": None,
                "error": str(exc),
            }

        title = article.get("title") or title_override or url
        content = article.get("content") or summary_override or ""
        summary = summary_override or article.get("summary") or truncate_text(content, limit=600)
        raw_canonical = article.get("canonical_url") or article.get("url") or url
        canonical_url = self._normalize_url(raw_canonical, url)
        published_at = article.get("published") or None
        media_id = article.get("media_id")
        media_uuid = article.get("media_uuid")
        content_word_count = word_count(content)

        metadata_payload: Dict[str, object] = {
            "source": "reading_save",
            "tags": tags,
            "author": article.get("author"),
        }
        if article.get("media_type"):
            metadata_payload["media_type"] = article.get("media_type")
        if article.get("content_type"):
            metadata_payload["content_type"] = article.get("content_type")
        if article.get("status_code"):
            metadata_payload["fetch_status"] = article.get("status_code")
        if media_uuid:
            metadata_payload["media_uuid"] = media_uuid
        if article.get("clean_html"):
            metadata_payload["clean_html"] = article.get("clean_html")
        if content:
            metadata_payload["text"] = content
        if content_word_count:
            metadata_payload["reading_time_seconds"] = max(1, int(content_word_count / 200 * 60))
        if article.get("error"):
            metadata_payload["fetch_error"] = article.get("error")
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
            notes=notes,
            content_hash=hash_text_sha256(content),
            word_count=content_word_count,
            published_at=published_at,
            status=normalized_status,
            favorite=favorite,
            metadata=metadata_payload,
            media_id=media_id if isinstance(media_id, int) else None,
            job_id=None,
            run_id=None,
            source_id=None,
            read_at=None,
            tags=tags,
            merge_tags=True,
        )

        if item_row.is_new or item_row.content_changed:
            embedding_metadata = {
                "origin": "reading",
                "item_id": item_row.id,
                "url": url,
                "canonical_url": canonical_url,
                "title": title,
                "author": article.get("author"),
                "tags": tags,
            }
            try:
                await enqueue_embeddings_job_for_item(
                    user_id=self.user_id,
                    item_id=item_row.id,
                    content=content,
                    metadata=embedding_metadata,
                )
            except Exception as exc:
                logger.debug(f"Embedding enqueue failed for reading item {item_row.id}: {exc}")
            try:
                self.collections.reanchor_highlights_for_item(
                    item_row.id,
                    content_text=content,
                    content_hash=item_row.content_hash,
                )
            except Exception as exc:
                logger.debug(f"Highlight re-anchoring failed for item {item_row.id}: {exc}")

        return ReadingSaveResult(
            item=item_row,
            media_id=item_row.media_id,
            media_uuid=media_uuid,
            created=item_row.is_new,
        )

    async def _fetch_article(
        self,
        *,
        url: str,
        title_override: Optional[str],
        content_override: Optional[str],
        summary_override: Optional[str],
    ) -> Dict[str, Any]:
        """Fetch, normalize, and sanitize content for reading list items."""
        if content_override is not None:
            content, clean_html = self._sanitize_html_content(content_override)
            return {
                "url": url,
                "canonical_url": url,
                "title": title_override or url,
                "content": content,
                "summary": summary_override,
                "author": None,
                "published": None,
                "media_id": None,
                "media_uuid": None,
                "media_type": None,
                "content_type": None,
                "clean_html": clean_html,
            }

        probe = await self._probe_url_metadata(url)
        content_type = probe.get("content_type")
        media_type_key = probe.get("media_type_key")
        resolved_url = probe.get("resolved_url") or url
        if probe.get("size_exceeded"):
            return {
                "url": url,
                "canonical_url": self._normalize_url(resolved_url, url),
                "title": title_override or url,
                "content": "",
                "summary": summary_override,
                "author": None,
                "published": None,
                "media_id": None,
                "media_uuid": None,
                "media_type": media_type_key,
                "content_type": content_type,
                "error": probe.get("error"),
                "status_code": probe.get("status_code"),
            }

        if media_type_key and str(media_type_key).lower() != "html":
            non_html = await self._ingest_non_html(
                url=url,
                media_type_key=media_type_key,
                title_override=title_override,
            )
            non_html["canonical_url"] = self._normalize_url(resolved_url, url)
            non_html["content_type"] = content_type
            non_html["status_code"] = probe.get("status_code")
            if probe.get("error") and not non_html.get("error"):
                non_html["error"] = probe.get("error")
            return non_html

        try:
            from tldw_Server_API.app.core.Web_Scraping.Article_Extractor_Lib import (
                scrape_article,
                ContentMetadataHandler,
            )
        except Exception as exc:
            return {
                "url": url,
                "canonical_url": self._normalize_url(resolved_url, url),
                "title": title_override or url,
                "content": "",
                "summary": summary_override,
                "author": None,
                "published": None,
                "media_id": None,
                "media_uuid": None,
                "media_type": "html",
                "content_type": content_type,
                "error": f"scrape_import_failed:{exc}",
                "status_code": probe.get("status_code"),
            }

        try:
            data = await scrape_article(url)
        except Exception as exc:
            return {
                "url": url,
                "canonical_url": self._normalize_url(resolved_url, url),
                "title": title_override or url,
                "content": "",
                "summary": summary_override,
                "author": None,
                "published": None,
                "media_id": None,
                "media_uuid": None,
                "media_type": "html",
                "content_type": content_type,
                "error": f"article_fetch_failed:{exc}",
                "status_code": probe.get("status_code"),
            }

        if not data or not data.get("extraction_successful"):
            error = data.get("error") if isinstance(data, dict) else "article_fetch_failed"
            return {
                "url": url,
                "canonical_url": self._normalize_url(resolved_url, url),
                "title": title_override or url,
                "content": "",
                "summary": summary_override,
                "author": None,
                "published": None,
                "media_id": None,
                "media_uuid": None,
                "media_type": "html",
                "content_type": content_type,
                "error": error,
                "status_code": probe.get("status_code"),
            }

        content = data.get("content") or ""
        try:
            content = ContentMetadataHandler.strip_metadata(content)  # type: ignore[attr-defined]
        except Exception:
            pass
        content, clean_html = self._sanitize_html_content(content)
        canonical_raw = data.get("canonical_url") or data.get("url") or resolved_url or url

        return {
            "url": data.get("url") or url,
            "canonical_url": self._normalize_url(canonical_raw, url),
            "title": data.get("title") or title_override or url,
            "content": content,
            "summary": data.get("summary"),
            "author": data.get("author"),
            "published": data.get("date") or data.get("published"),
            "media_id": None,
            "media_uuid": None,
            "media_type": "html",
            "content_type": content_type,
            "clean_html": clean_html,
            "status_code": probe.get("status_code"),
        }

    def list_items(
        self,
        *,
        status: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        favorite: Optional[bool] = None,
        q: Optional[str] = None,
        domain: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        page: int = 1,
        size: int = 20,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        sort: Optional[str] = None,
    ) -> tuple[List[ContentItemRow], int]:
        return self.collections.list_content_items(
            origin="reading",
            status=status,
            tags=tags,
            favorite=favorite,
            q=q,
            domain=domain,
            date_from=date_from,
            date_to=date_to,
            page=page,
            size=size,
            offset=offset,
            limit=limit,
            sort=sort,
        )

    def get_item(self, item_id: int) -> ContentItemRow:
        return self.collections.get_content_item(item_id)

    def update_item(
        self,
        item_id: int,
        *,
        status: Optional[str] = None,
        favorite: Optional[bool] = None,
        tags: Optional[List[str]] = None,
        notes: Optional[str] = None,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, object]] = None,
    ) -> ContentItemRow:
        normalized_tags = tags if tags is None else [t for t in tags if t]
        metadata = metadata or {}
        read_at: Optional[str] = None
        clear_read_at = False
        if status is not None:
            try:
                current = self.collections.get_content_item(item_id)
            except KeyError:
                raise
            status_lower = status.lower()
            if status_lower == "read":
                if not current.read_at:
                    read_at = _utcnow_iso()
            else:
                if current.read_at:
                    clear_read_at = True

        return self.collections.update_content_item(
            item_id,
            status=status,
            favorite=favorite,
            tags=normalized_tags,
            notes=notes,
            metadata=metadata if metadata else None,
            title=title,
            read_at=read_at,
            clear_read_at=clear_read_at,
        )

    def delete_item(self, item_id: int) -> None:
        self.collections.delete_content_item(item_id)

    def import_items(
        self,
        *,
        items: List[ReadingImportItem],
        merge_tags: bool = True,
        origin_type: str = "import",
    ) -> ReadingImportResult:
        normalized = normalize_import_items(items)
        imported = 0
        updated = 0
        skipped = 0
        errors: List[str] = []

        for item in normalized:
            url = item.url.strip() if item.url else ""
            if not url:
                skipped += 1
                continue
            tags = item.tags or []
            metadata_payload = {"source": "reading_import"}
            metadata_payload.update(item.metadata or {})
            try:
                row = self.collections.upsert_content_item(
                    origin="reading",
                    origin_type=origin_type,
                    origin_id=None,
                    url=url,
                    canonical_url=url,
                    domain=None,
                    title=item.title or None,
                    summary=None,
                    notes=item.notes,
                    content_hash=None,
                    word_count=None,
                    published_at=None,
                    status=item.status or "saved",
                    favorite=item.favorite,
                    metadata=metadata_payload,
                    media_id=None,
                    job_id=None,
                    run_id=None,
                    source_id=None,
                    read_at=item.read_at,
                    tags=tags,
                    merge_tags=merge_tags,
                    preserve_existing_on_null=True,
                )
                if row.is_new:
                    imported += 1
                else:
                    updated += 1
            except Exception as exc:
                errors.append(f"{url}: {exc}")
        return ReadingImportResult(imported=imported, updated=updated, skipped=skipped, errors=errors)
