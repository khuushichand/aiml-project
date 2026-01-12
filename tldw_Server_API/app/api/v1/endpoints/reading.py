from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from loguru import logger

from tldw_Server_API.app.api.v1.schemas.reading_schemas import (
    ReadingItem,
    ReadingImportResponse,
    ReadingItemsListResponse,
    ReadingSaveRequest,
    ReadingUpdateRequest,
)
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.Collections.reading_service import ReadingService
from tldw_Server_API.app.core.Collections.reading_importers import (
    detect_import_source,
    parse_reading_import,
)
from tldw_Server_API.app.core.DB_Management.Collections_DB import ContentItemRow


MAX_READING_IMPORT_BYTES = 10 * 1024 * 1024

router = APIRouter(prefix="/reading", tags=["reading"])


def _service_for_user(user: User) -> ReadingService:
    if not user or user.id is None:
        raise HTTPException(status_code=500, detail="user_missing")
    return ReadingService(user.id)


def _to_reading_item(row) -> ReadingItem:
    return ReadingItem(
        id=int(row.id),
        media_id=row.media_id,
        title=row.title or "Untitled",
        url=row.url or row.canonical_url,
        domain=row.domain,
        summary=row.summary,
        notes=row.notes,
        published_at=row.published_at,
        status=row.status,
        favorite=bool(row.favorite),
        tags=row.tags,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.post("/save", response_model=ReadingItem, summary="Save a URL into the reading list")
async def save_reading_item(
    payload: ReadingSaveRequest = Body(...),
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


@router.get("/items", response_model=ReadingItemsListResponse, summary="List reading items")
async def list_reading_items(
    status: Optional[List[str]] = Query(None),
    tags: Optional[List[str]] = Query(None),
    favorite: Optional[bool] = Query(None),
    q: Optional[str] = Query(None),
    domain: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    current_user: User = Depends(get_request_user),
) -> ReadingItemsListResponse:
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
    return ReadingItemsListResponse(
        items=[_to_reading_item(row) for row in rows],
        total=total,
        page=page,
        size=size,
    )


@router.post("/import", response_model=ReadingImportResponse, summary="Import Pocket/Instapaper export into reading list")
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


@router.patch("/items/{item_id}", response_model=ReadingItem, summary="Update reading item metadata")
async def update_reading_item(
    item_id: int,
    payload: ReadingUpdateRequest = Body(...),
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
        )
        return _to_reading_item(row)
    except KeyError:
        raise HTTPException(status_code=404, detail="reading_item_not_found")
    except Exception as exc:
        logger.error(f"reading_update_failed: {exc}")
        raise HTTPException(status_code=400, detail="reading_update_failed")


@router.get("/export", response_class=StreamingResponse, summary="Export reading list items")
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
