from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
from typing import Dict, List, Optional

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response, StreamingResponse
from loguru import logger

from tldw_Server_API.app.api.v1.schemas.reading_schemas import (
    ReadingCitation,
    ReadingDeleteResponse,
    ReadingItem,
    ReadingItemDetail,
    ReadingImportResponse,
    ReadingItemsListResponse,
    ReadingSaveRequest,
    ReadingSummarizeRequest,
    ReadingSummaryResponse,
    ReadingTTSRequest,
    ReadingUpdateRequest,
)
from tldw_Server_API.app.api.v1.schemas.items_schemas import ItemsBulkRequest, ItemsBulkResponse
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import rbac_rate_limit
from tldw_Server_API.app.api.v1.API_Deps.Collections_DB_Deps import get_collections_db_for_user
from tldw_Server_API.app.api.v1.schemas.chat_request_schemas import DEFAULT_LLM_PROVIDER
from tldw_Server_API.app.api.v1.schemas.audio_schemas import OpenAISpeechRequest
from tldw_Server_API.app.api.v1.endpoints.items import bulk_update_items as bulk_update_items_handler
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.Collections.reading_service import ReadingService
from tldw_Server_API.app.core.Collections.reading_importers import (
    detect_import_source,
    parse_reading_import,
)
from tldw_Server_API.app.core.DB_Management.Collections_DB import ContentItemRow
from tldw_Server_API.app.core.LLM_Calls.Summarization_General_Lib import analyze as summarize_analyze
from tldw_Server_API.app.core.TTS.tts_config import get_tts_config
from tldw_Server_API.app.core.TTS.tts_exceptions import (
    TTSError,
    TTSAuthenticationError,
    TTSProviderNotConfiguredError,
    TTSQuotaExceededError,
    TTSRateLimitError,
    TTSValidationError,
)
from tldw_Server_API.app.core.TTS.tts_service_v2 import get_tts_service_v2
from tldw_Server_API.app.core.TTS.tts_validation import TTSInputValidator


MAX_READING_IMPORT_BYTES = 10 * 1024 * 1024

router = APIRouter(prefix="/reading", tags=["reading"])


def _service_for_user(user: User) -> ReadingService:
    if not user or user.id is None:
        raise HTTPException(status_code=500, detail="user_missing")
    return ReadingService(user.id)


def _parse_metadata(row: ContentItemRow) -> Dict[str, object]:
    if getattr(row, "metadata_json", None):
        try:
            return json.loads(row.metadata_json) if row.metadata_json else {}
        except Exception:
            return {}
    return {}


def _derive_processing_status(row: ContentItemRow, metadata: Dict[str, object]) -> str:
    status_raw = str(metadata.get("processing_status", "")).lower()
    if status_raw in {"processing", "ready"}:
        return status_raw
    if metadata.get("fetch_error"):
        return "ready"
    if row.media_id or row.content_hash or row.summary or metadata.get("text"):
        return "ready"
    return "processing"


def _to_reading_item(row) -> ReadingItem:
    metadata = _parse_metadata(row)
    return ReadingItem(
        id=int(row.id),
        media_id=row.media_id,
        media_uuid=metadata.get("media_uuid") if metadata else None,
        title=row.title or "Untitled",
        url=row.url or row.canonical_url,
        canonical_url=row.canonical_url,
        domain=row.domain,
        summary=row.summary,
        notes=row.notes,
        published_at=row.published_at,
        status=row.status,
        processing_status=_derive_processing_status(row, metadata),
        favorite=bool(row.favorite),
        tags=row.tags,
        created_at=row.created_at,
        updated_at=row.updated_at,
        read_at=row.read_at,
    )


def _to_reading_detail(row: ContentItemRow) -> ReadingItemDetail:
    metadata = _parse_metadata(row)
    return ReadingItemDetail(
        **_to_reading_item(row).model_dump(),
        text=metadata.get("text") if metadata else None,
        clean_html=metadata.get("clean_html") if metadata else None,
        metadata=metadata,
    )


def _select_text_for_action(
    row: ContentItemRow,
    metadata: Dict[str, object],
    text_source: Optional[str],
) -> str:
    if text_source == "summary":
        return row.summary or ""
    if text_source == "notes":
        return row.notes or ""
    if text_source == "text":
        return str(metadata.get("text") or "")
    return str(metadata.get("text") or row.summary or row.notes or "")


def _build_reading_citation(row: ContentItemRow) -> ReadingCitation:
    return ReadingCitation(
        item_id=int(row.id),
        url=row.url or row.canonical_url,
        canonical_url=row.canonical_url,
        title=row.title or None,
        source="reading",
    )


def _tts_content_type(response_format: str) -> Optional[str]:
    mapping = {
        "mp3": "audio/mpeg",
        "opus": "audio/opus",
        "aac": "audio/aac",
        "flac": "audio/flac",
        "wav": "audio/wav",
        "pcm": "audio/L16; rate=24000; channels=1",
    }
    return mapping.get(response_format)


def _raise_for_tts_error(exc: Exception) -> None:
    if isinstance(exc, TTSValidationError):
        raise HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, TTSProviderNotConfiguredError):
        raise HTTPException(status_code=503, detail=f"TTS service unavailable: {str(exc)}")
    if isinstance(exc, TTSAuthenticationError):
        raise HTTPException(status_code=502, detail="TTS provider authentication failed")
    if isinstance(exc, TTSRateLimitError):
        raise HTTPException(status_code=429, detail="TTS provider rate limit exceeded")
    if isinstance(exc, TTSQuotaExceededError):
        raise HTTPException(status_code=402, detail="TTS quota exceeded")
    if isinstance(exc, TTSError):
        raise HTTPException(status_code=500, detail=f"TTS error: {str(exc)}")
    raise HTTPException(status_code=500, detail="TTS generation failed")


@router.post(
    "/save",
    response_model=ReadingItem,
    summary="Save a URL into the reading list",
    dependencies=[Depends(rbac_rate_limit("reading.save"))],
)
async def save_reading_item(
    payload: ReadingSaveRequest = Body(
        ...,
        examples={
            "basic": {
                "summary": "Save a URL",
                "value": {
                    "url": "https://example.com/article",
                    "title": "Example Article",
                    "tags": ["ai", "reading"],
                    "notes": "Why it matters",
                },
            },
            "inline_content": {
                "summary": "Save inline content (offline/testing)",
                "value": {
                    "url": "https://example.com/article",
                    "title": "Example Article",
                    "content": "Inline article content used for tests.",
                },
            },
        },
    ),
    current_user: User = Depends(get_request_user),
) -> ReadingItem:
    service = _service_for_user(current_user)
    try:
        result = await service.save_url(
            url=str(payload.url),
            tags=payload.tags,
            status=payload.status,
            favorite=payload.favorite,
            title_override=payload.title,
            summary_override=payload.summary,
            content_override=payload.content,
            notes=payload.notes,
        )
        return _to_reading_item(result.item)
    except Exception as exc:
        logger.error(f"reading_save_failed: {exc}")
        raise HTTPException(status_code=400, detail="reading_save_failed")


@router.get(
    "/items",
    response_model=ReadingItemsListResponse,
    summary="List reading items",
    dependencies=[Depends(rbac_rate_limit("reading.list"))],
)
async def list_reading_items(
    status: Optional[List[str]] = Query(None),
    tags: Optional[List[str]] = Query(None),
    favorite: Optional[bool] = Query(None),
    q: Optional[str] = Query(None),
    domain: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    offset: Optional[int] = Query(None, ge=0),
    limit: Optional[int] = Query(None, ge=1, le=200),
    sort: Optional[str] = Query(
        None,
        description="updated_desc|updated_asc|created_desc|created_asc|title_asc|title_desc|relevance",
    ),
    current_user: User = Depends(get_request_user),
) -> ReadingItemsListResponse:
    service = _service_for_user(current_user)
    resolved_limit = limit if limit is not None else size
    resolved_offset = offset if offset is not None else max(0, (page - 1) * size)
    if limit is not None:
        page = int(resolved_offset / resolved_limit) + 1 if resolved_limit else page
        size = resolved_limit
    rows, total = service.list_items(
        status=status,
        tags=tags,
        favorite=favorite,
        q=q,
        domain=domain,
        page=page,
        size=size,
        offset=resolved_offset,
        limit=resolved_limit,
        sort=sort,
    )
    return ReadingItemsListResponse(
        items=[_to_reading_item(row) for row in rows],
        total=total,
        page=page,
        size=size,
        offset=resolved_offset,
        limit=resolved_limit,
    )


@router.post("/items/bulk", response_model=ItemsBulkResponse, summary="Bulk update reading items (alias)")
async def bulk_update_reading_items(
    payload: ItemsBulkRequest,
    current_user: User = Depends(get_request_user),
    collections_db = Depends(get_collections_db_for_user),
) -> ItemsBulkResponse:
    return await bulk_update_items_handler(
        payload,
        current_user=current_user,
        collections_db=collections_db,
    )


@router.post(
    "/import",
    response_model=ReadingImportResponse,
    summary="Import Pocket/Instapaper export into reading list",
    dependencies=[Depends(rbac_rate_limit("reading.import"))],
)
async def import_reading_items(
    file: UploadFile = File(...),
    source: str = Form("auto"),
    merge_tags: bool = Form(True),
    current_user: User = Depends(get_request_user),
) -> ReadingImportResponse:
    service = _service_for_user(current_user)
    try:
        raw = await file.read()
    except Exception as exc:
        logger.error(f"reading_import_read_failed: {exc}")
        raise HTTPException(status_code=400, detail="reading_import_failed")
    if not raw:
        raise HTTPException(status_code=400, detail="reading_import_empty")
    if len(raw) > MAX_READING_IMPORT_BYTES:
        raise HTTPException(status_code=413, detail="reading_import_too_large")

    if source == "auto":
        source = detect_import_source(file.filename, raw)

    try:
        items = parse_reading_import(raw, source=source, filename=file.filename)
        result = service.import_items(items=items, merge_tags=merge_tags, origin_type=source)
    except ValueError as exc:
        logger.error(f"reading_import_invalid: {exc}")
        raise HTTPException(status_code=400, detail="reading_import_invalid")
    except Exception as exc:
        logger.error(f"reading_import_failed: {exc}")
        raise HTTPException(status_code=500, detail="reading_import_failed")
    return ReadingImportResponse(
        source=source,
        imported=result.imported,
        updated=result.updated,
        skipped=result.skipped,
        errors=result.errors,
    )


@router.get(
    "/items/{item_id}",
    response_model=ReadingItemDetail,
    summary="Get reading item detail",
    dependencies=[Depends(rbac_rate_limit("reading.read"))],
)
async def get_reading_item(
    item_id: int,
    current_user: User = Depends(get_request_user),
) -> ReadingItemDetail:
    service = _service_for_user(current_user)
    try:
        row = service.get_item(item_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="reading_item_not_found")
    except Exception as exc:
        logger.error(f"reading_get_failed: {exc}")
        raise HTTPException(status_code=400, detail="reading_get_failed")
    return _to_reading_detail(row)


@router.post(
    "/items/{item_id}/summarize",
    response_model=ReadingSummaryResponse,
    summary="Summarize a reading item",
    dependencies=[Depends(rbac_rate_limit("reading.summarize"))],
)
async def summarize_reading_item(
    item_id: int,
    payload: ReadingSummarizeRequest = Body(
        ...,
        examples={
            "default": {
                "summary": "Summarize with provider",
                "value": {
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                    "prompt": "Summarize for a product brief.",
                },
            }
        },
    ),
    current_user: User = Depends(get_request_user),
) -> ReadingSummaryResponse:
    service = _service_for_user(current_user)
    try:
        row = service.get_item(item_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="reading_item_not_found")
    except Exception as exc:
        logger.error(f"reading_summary_get_failed: {exc}")
        raise HTTPException(status_code=400, detail="reading_item_fetch_failed")

    metadata = _parse_metadata(row)
    text = _select_text_for_action(row, metadata, None)
    if not text.strip():
        raise HTTPException(status_code=400, detail="reading_item_no_content")

    if payload.recursive and payload.chunked:
        raise HTTPException(status_code=400, detail="reading_summary_invalid_strategy")

    provider = (payload.provider or DEFAULT_LLM_PROVIDER).strip()
    if not provider:
        provider = DEFAULT_LLM_PROVIDER
    loop = asyncio.get_running_loop()
    try:
        summary = await loop.run_in_executor(
            None,
            lambda: summarize_analyze(
                api_name=provider,
                input_data=text,
                custom_prompt_arg=payload.prompt,
                api_key=None,
                system_message=payload.system_prompt,
                temp=payload.temperature,
                streaming=False,
                recursive_summarization=payload.recursive,
                chunked_summarization=payload.chunked,
                chunk_options=None,
                model_override=payload.model,
            ),
        )
    except Exception as exc:
        logger.error(f"reading_summarize_failed: {exc}")
        raise HTTPException(status_code=503, detail="reading_summarize_failed")

    if not isinstance(summary, str):
        summary = str(summary)
    if not summary or summary.strip().lower().startswith("error:"):
        logger.error(f"reading_summarize_error: {summary}")
        raise HTTPException(status_code=503, detail="reading_summarize_failed")

    citation = _build_reading_citation(row)
    generated_at = datetime.now(tz=timezone.utc).isoformat()
    return ReadingSummaryResponse(
        item_id=int(row.id),
        summary=summary,
        provider=str(provider),
        model=payload.model,
        citations=[citation],
        generated_at=generated_at,
    )


@router.post(
    "/items/{item_id}/tts",
    response_class=StreamingResponse,
    summary="Generate TTS audio for a reading item",
    dependencies=[Depends(rbac_rate_limit("reading.tts"))],
)
async def tts_reading_item(
    item_id: int,
    payload: ReadingTTSRequest = Body(
        ...,
        examples={
            "stream_mp3": {
                "summary": "Stream MP3 audio",
                "value": {
                    "model": "kokoro",
                    "voice": "af_heart",
                    "response_format": "mp3",
                    "stream": True,
                    "text_source": "text",
                },
            }
        },
    ),
    current_user: User = Depends(get_request_user),
) -> Response:
    service = _service_for_user(current_user)
    try:
        row = service.get_item(item_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="reading_item_not_found")
    except Exception as exc:
        logger.error(f"reading_tts_get_failed: {exc}")
        raise HTTPException(status_code=400, detail="reading_item_fetch_failed")

    metadata = _parse_metadata(row)
    text = _select_text_for_action(row, metadata, payload.text_source)
    if payload.text_source and not text.strip():
        raise HTTPException(status_code=400, detail="reading_item_text_source_empty")
    if not text.strip():
        raise HTTPException(status_code=400, detail="reading_item_no_content")
    if payload.max_chars:
        text = text[: payload.max_chars]

    tts_config = get_tts_config()
    validator = TTSInputValidator({"strict_validation": tts_config.strict_validation})
    try:
        sanitized_text = validator.sanitize_text(text)
    except TTSValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not sanitized_text.strip():
        raise HTTPException(status_code=400, detail="reading_tts_empty_input")

    response_format = payload.response_format
    content_type = _tts_content_type(response_format)
    if not content_type:
        raise HTTPException(status_code=400, detail="reading_tts_format_invalid")

    tts_request = OpenAISpeechRequest(
        model=payload.model,
        input=sanitized_text,
        voice=payload.voice,
        response_format=response_format,
        stream=payload.stream,
    )
    if payload.speed is not None:
        tts_request.speed = payload.speed

    try:
        tts_service = await get_tts_service_v2()
        speech_iter = tts_service.generate_speech(tts_request, fallback=True)
    except Exception as exc:
        _raise_for_tts_error(exc)

    headers = {
        "Content-Disposition": f"attachment; filename=reading_{item_id}.{response_format}",
        "X-Reading-Item-Id": str(item_id),
    }
    if row.url or row.canonical_url:
        headers["X-Reading-Url"] = row.url or row.canonical_url or ""

    async def _stream_chunks():
        try:
            async for chunk in speech_iter:
                if chunk:
                    yield chunk
        except Exception as exc:
            _raise_for_tts_error(exc)

    if payload.stream:
        return StreamingResponse(_stream_chunks(), media_type=content_type, headers=headers)

    audio_bytes = b""
    try:
        async for chunk in speech_iter:
            if chunk:
                audio_bytes += chunk
    except Exception as exc:
        _raise_for_tts_error(exc)

    audio_bytes = audio_bytes.replace(b"--final_boundary_for_non_streamed--", b"")
    if not audio_bytes:
        raise HTTPException(status_code=500, detail="reading_tts_no_audio")
    return Response(content=audio_bytes, media_type=content_type, headers=headers)


@router.patch(
    "/items/{item_id}",
    response_model=ReadingItem,
    summary="Update reading item metadata",
    dependencies=[Depends(rbac_rate_limit("reading.update"))],
)
async def update_reading_item(
    item_id: int,
    payload: ReadingUpdateRequest = Body(
        ...,
        examples={
            "mark_read": {
                "summary": "Mark read and favorite",
                "value": {"status": "read", "favorite": True, "tags": ["ai", "priority"]},
            }
        },
    ),
    current_user: User = Depends(get_request_user),
) -> ReadingItem:
    service = _service_for_user(current_user)
    try:
        row = service.update_item(
            item_id=item_id,
            status=payload.status,
            favorite=payload.favorite,
            tags=payload.tags,
            notes=payload.notes,
            title=payload.title,
        )
        return _to_reading_item(row)
    except KeyError:
        raise HTTPException(status_code=404, detail="reading_item_not_found")
    except Exception as exc:
        logger.error(f"reading_update_failed: {exc}")
        raise HTTPException(status_code=400, detail="reading_update_failed")


@router.delete(
    "/items/{item_id}",
    response_model=ReadingDeleteResponse,
    summary="Delete a reading item",
    dependencies=[Depends(rbac_rate_limit("reading.delete"))],
)
async def delete_reading_item(
    item_id: int,
    hard: bool = Query(False),
    current_user: User = Depends(get_request_user),
) -> ReadingDeleteResponse:
    service = _service_for_user(current_user)
    try:
        if hard:
            service.delete_item(item_id)
            return ReadingDeleteResponse(status="deleted", item_id=item_id, hard=True)
        row = service.update_item(item_id, status="archived")
        return ReadingDeleteResponse(status=row.status or "archived", item_id=item_id, hard=False)
    except KeyError:
        raise HTTPException(status_code=404, detail="reading_item_not_found")
    except Exception as exc:
        logger.error(f"reading_delete_failed: {exc}")
        raise HTTPException(status_code=400, detail="reading_delete_failed")


@router.get(
    "/export",
    response_class=StreamingResponse,
    summary="Export reading list items",
    dependencies=[Depends(rbac_rate_limit("reading.export"))],
)
async def export_reading_items(
    status: Optional[List[str]] = Query(None),
    tags: Optional[List[str]] = Query(None),
    favorite: Optional[bool] = Query(None),
    q: Optional[str] = Query(None),
    domain: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(1000, ge=1, le=10000),
    format: str = Query("jsonl", description="Export format: jsonl or zip"),
    current_user: User = Depends(get_request_user),
) -> StreamingResponse:
    service = _service_for_user(current_user)
    rows, total = service.list_items(
        status=status,
        tags=tags,
        favorite=favorite,
        q=q,
        domain=domain,
        page=page,
        size=size,
    )

    def _serialize_row(row: ContentItemRow) -> dict:
        metadata = {}
        if getattr(row, "metadata_json", None):
            try:
                import json as _json

                metadata = _json.loads(row.metadata_json) if row.metadata_json else {}
            except Exception:
                metadata = {}
        return {
            "id": row.id,
            "url": row.url,
            "canonical_url": row.canonical_url,
            "domain": row.domain,
            "title": row.title,
            "summary": row.summary,
            "notes": row.notes,
            "status": row.status,
            "favorite": row.favorite,
            "tags": row.tags,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "read_at": row.read_at,
            "published_at": row.published_at,
            "origin_type": row.origin_type,
            "metadata": metadata,
        }

    export_rows = [_serialize_row(row) for row in rows]
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    if format.lower() == "zip":
        import io
        import json as _json
        import zipfile

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            payload = "".join(_json.dumps(row, ensure_ascii=False) + "\n" for row in export_rows)
            zf.writestr("reading_export.jsonl", payload)
        buffer.seek(0)
        headers = {"Content-Disposition": f"attachment; filename=reading_export_{timestamp}.zip"}
        return StreamingResponse(buffer, media_type="application/zip", headers=headers)

    if format.lower() != "jsonl":
        raise HTTPException(status_code=400, detail="reading_export_format_invalid")

    import json as _json

    def _iter_lines():
        for row in export_rows:
            yield _json.dumps(row, ensure_ascii=False) + "\n"

    headers = {"Content-Disposition": f"attachment; filename=reading_export_{timestamp}.jsonl"}
    return StreamingResponse(_iter_lines(), media_type="application/x-ndjson", headers=headers)
