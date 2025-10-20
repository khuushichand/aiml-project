from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from loguru import logger

from tldw_Server_API.app.api.v1.schemas.reading_schemas import (
    ReadingItem,
    ReadingItemsListResponse,
    ReadingSaveRequest,
    ReadingUpdateRequest,
)
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.Collections.reading_service import ReadingService
from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase


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
        )
        return _to_reading_item(row)
    except KeyError:
        raise HTTPException(status_code=404, detail="reading_item_not_found")
    except Exception as exc:
        logger.error(f"reading_update_failed: {exc}")
        raise HTTPException(status_code=400, detail="reading_update_failed")
