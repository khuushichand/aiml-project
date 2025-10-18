from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger

from tldw_Server_API.app.api.v1.schemas.items_schemas import Item, ItemsListResponse
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user


router = APIRouter(prefix="/items", tags=["items"])


def _domain_from_url(url: str | None) -> str:
    if not url:
        return ""
    try:
        from urllib.parse import urlparse
        return urlparse(url).hostname or ""
    except Exception:
        return ""


@router.get("", response_model=ItemsListResponse, summary="Unified items list across origins")
async def list_items(
    ids: Optional[List[int]] = Query(None, description="Filter by item IDs"),
    q: Optional[str] = Query(None, description="Search query (title/content)"),
    tags: Optional[List[str]] = Query(None, description="Require these tags (names)"),
    domain: Optional[str] = Query(None, description="Filter by domain (hostname)"),
    date_from: Optional[str] = Query(None, description="ISO start date inclusive"),
    date_to: Optional[str] = Query(None, description="ISO end date inclusive"),
    job_id: Optional[int] = Query(None, description="Filter by job_id (placeholder; no-op until jobs tables exist)"),
    run_id: Optional[int] = Query(None, description="Filter by run_id (placeholder; no-op until runs tables exist)"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    current_user: User = Depends(get_request_user),
    db = Depends(get_media_db_for_user),
):
    must_have_keywords = tags or []
    # Prepare date range
    dr = None
    try:
        start_dt = datetime.fromisoformat(date_from) if date_from else None
        end_dt = datetime.fromisoformat(date_to) if date_to else None
        if start_dt or end_dt:
            dr = {"start_date": start_dt, "end_date": end_dt}
    except Exception:
        raise HTTPException(status_code=422, detail="invalid_date_range")

    # Query media DB
    try:
        rows, total = db.search_media_db(
            search_query=q,
            search_fields=["title", "content"],
            media_types=None,
            date_range=dr,
            must_have_keywords=must_have_keywords,
            must_not_have_keywords=None,
            sort_by="last_modified_desc",
            media_ids_filter=ids,
            page=page,
            results_per_page=size,
            include_trash=False,
            include_deleted=False,
        )
    except Exception as e:
        logger.error(f"items list failed: {e}")
        raise HTTPException(status_code=500, detail="items_query_failed")

    # Build items and apply optional domain filter in-process
    items: List[Item] = []
    for r in rows:
        url = r.get("url")
        dom = _domain_from_url(url)
        if domain and dom and dom != domain:
            continue
        # Fetch tags per item
        try:
            from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import fetch_keywords_for_media, get_document_version
            tag_list = fetch_keywords_for_media(media_id=int(r.get("id")), db_instance=db)
        except Exception:
            tag_list = []

        # Derive summary/published_at best-effort
        summary = None
        published_at = None
        try:
            latest = get_document_version(db, media_id=int(r.get("id")), version_number=None, include_content=False)  # type: ignore[name-defined]
            if isinstance(latest, dict):
                summary = latest.get("analysis_content") or None
                sm = latest.get("safe_metadata")
                if isinstance(sm, str):
                    import json as _json
                    try:
                        sm = _json.loads(sm)
                    except Exception:
                        sm = None
                if isinstance(sm, dict):
                    published_at = sm.get("published_at") or sm.get("date")
        except Exception:
            pass
        if not summary:
            content = r.get("content") or ""
            if isinstance(content, str) and content:
                summary = (content[:500] + "...") if len(content) > 500 else content

        items.append(
            Item(
                id=int(r.get("id")),
                title=r.get("title") or "Untitled",
                url=url,
                domain=dom,
                summary=summary or None,
                published_at=published_at,
                tags=tag_list,
                type=r.get("type") or None,
            )
        )

    return ItemsListResponse(items=items, total=total, page=page, size=size)
