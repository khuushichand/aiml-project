# tldw_Server_API/app/api/v1/endpoints/reading_highlights.py
"""
Reading Highlights API (create/list/update/delete)

Stub endpoints to anchor the unified Content Collections PRD.

Endpoints mirror PRD shape:
- POST /reading/items/{item_id}/highlight
- GET  /reading/items/{item_id}/highlights
- PATCH/DELETE by highlight id

DB access must be implemented via app.core.DB_Management (no raw SQL here).
"""

from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, Path, Body
from loguru import logger

from tldw_Server_API.app.api.v1.schemas.reading_highlights_schemas import (
    HighlightCreateRequest,
    HighlightUpdateRequest,
    Highlight,
)
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.api.v1.API_Deps.Collections_DB_Deps import get_collections_db_for_user


router = APIRouter(tags=["reading-highlights"])  # no prefix; use absolute paths below


pass


@router.post("/reading/items/{item_id}/highlight", response_model=Highlight, summary="Create highlight for an item")
async def create_highlight(
    item_id: int = Path(..., ge=1),
    payload: HighlightCreateRequest = Body(...),
    current_user: User = Depends(get_request_user),
    db = Depends(get_collections_db_for_user),
) -> Highlight:
    try:
        row = db.create_highlight(
            item_id=item_id,
            quote=payload.quote,
            start_offset=payload.start_offset,
            end_offset=payload.end_offset,
            color=payload.color,
            note=payload.note,
            anchor_strategy=payload.anchor_strategy,
        )
    except Exception as e:
        logger.error(f"create_highlight failed: {e}")
        raise HTTPException(status_code=500, detail="highlight_create_failed")
    return Highlight(
        id=row.id,
        item_id=row.item_id,
        quote=row.quote,
        start_offset=row.start_offset,
        end_offset=row.end_offset,
        color=row.color,
        note=row.note,
        created_at=__import__("datetime").datetime.fromisoformat(row.created_at),
        anchor_strategy=row.anchor_strategy,
        content_hash_ref=row.content_hash_ref,
        context_before=row.context_before,
        context_after=row.context_after,
        state=row.state,
    )


@router.get("/reading/items/{item_id}/highlights", response_model=List[Highlight], summary="List highlights for an item")
async def list_highlights_for_item(
    item_id: int = Path(..., ge=1),
    current_user: User = Depends(get_request_user),
    db = Depends(get_collections_db_for_user),
) -> List[Highlight]:
    rows = db.list_highlights_by_item(item_id=item_id)
    return [
        Highlight(
            id=r.id,
            item_id=r.item_id,
            quote=r.quote,
            start_offset=r.start_offset,
            end_offset=r.end_offset,
            color=r.color,
            note=r.note,
            created_at=__import__("datetime").datetime.fromisoformat(r.created_at),
            anchor_strategy=r.anchor_strategy,
            content_hash_ref=r.content_hash_ref,
            context_before=r.context_before,
            context_after=r.context_after,
            state=r.state,
        )
        for r in rows
    ]


@router.patch("/reading/highlights/{highlight_id}", response_model=Highlight, summary="Update a highlight")
async def update_highlight(
    highlight_id: int = Path(..., ge=1),
    payload: HighlightUpdateRequest = Body(...),
    current_user: User = Depends(get_request_user),
    db = Depends(get_collections_db_for_user),
) -> Highlight:
    patch = payload.dict(exclude_unset=True)
    try:
        row = db.update_highlight(highlight_id=highlight_id, patch=patch)
    except KeyError:
        raise HTTPException(status_code=404, detail="highlight_not_found")
    return Highlight(
        id=row.id,
        item_id=row.item_id,
        quote=row.quote,
        start_offset=row.start_offset,
        end_offset=row.end_offset,
        color=row.color,
        note=row.note,
        created_at=__import__("datetime").datetime.fromisoformat(row.created_at),
        anchor_strategy=row.anchor_strategy,
        content_hash_ref=row.content_hash_ref,
        context_before=row.context_before,
        context_after=row.context_after,
        state=row.state,
    )


@router.delete("/reading/highlights/{highlight_id}", summary="Delete a highlight")
async def delete_highlight(
    highlight_id: int = Path(..., ge=1),
    current_user: User = Depends(get_request_user),
    db = Depends(get_collections_db_for_user),
) -> dict[str, Any]:
    ok = db.delete_highlight(highlight_id=highlight_id)
    if not ok:
        raise HTTPException(status_code=404, detail="highlight_not_found")
    return {"success": True}
