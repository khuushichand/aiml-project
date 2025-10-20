from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger

from tldw_Server_API.app.api.v1.schemas.items_schemas import Item, ItemsListResponse
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.Collections_DB_Deps import get_collections_db_for_user
from tldw_Server_API.app.core.DB_Management.Collections_DB import ContentItemRow


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
    status_filter: Optional[List[str]] = Query(None, description="Filter by status (e.g., saved, read)"),
    favorite: Optional[bool] = Query(None, description="Filter by favorite flag"),
    origin: Optional[str] = Query(None, description="Filter by origin (watchlist, reading, etc.)"),
    job_id: Optional[int] = Query(None, description="Filter by job_id"),
    run_id: Optional[int] = Query(None, description="Filter by run_id"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    current_user: User = Depends(get_request_user),
    db = Depends(get_media_db_for_user),
    collections_db = Depends(get_collections_db_for_user),
):
    must_have_keywords = tags or []
    # Prepare date range
    dr = None
    date_from_iso = None
    date_to_iso = None
    try:
        start_dt = datetime.fromisoformat(date_from) if date_from else None
        end_dt = datetime.fromisoformat(date_to) if date_to else None
        if start_dt or end_dt:
            dr = {"start_date": start_dt, "end_date": end_dt}
        if start_dt:
            date_from_iso = start_dt.isoformat()
        if end_dt:
            date_to_iso = end_dt.isoformat()
    except Exception:
        raise HTTPException(status_code=422, detail="invalid_date_range")

    # Query collections layer first
    try:
        coll_rows, coll_total = collections_db.list_content_items(
            ids=ids,
            q=q,
            tags=tags,
            domain=domain,
            date_from=date_from_iso,
            date_to=date_to_iso,
            status=status_filter,
            favorite=favorite,
            job_id=job_id,
            run_id=run_id,
            origin=origin,
            page=page,
            size=size,
        )
    except Exception as e:
        logger.error(f"collections items query failed: {e}")
        raise HTTPException(status_code=500, detail="items_query_failed")

    if coll_total > 0:
        return ItemsListResponse(
            items=[_content_item_to_schema(r) for r in coll_rows],
            total=coll_total,
            page=page,
            size=size,
        )

    if origin or (status_filter and len(status_filter) > 0) or favorite is not None:
        return ItemsListResponse(items=[], total=0, page=page, size=size)

    # Legacy fallback to Media DB when collections layer has no data
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


def _content_item_to_schema(row: ContentItemRow) -> Item:
    domain = row.domain or _domain_from_url(row.url)
    summary = row.summary
    if not summary:
        metadata = {}
        if row.metadata_json:
            try:
                import json as _json
                metadata = _json.loads(row.metadata_json)
            except Exception:
                metadata = {}
        summary = metadata.get("summary")
    item_id = row.media_id if row.media_id is not None else row.id
    return Item(
        id=int(item_id),
        title=row.title or "Untitled",
        url=row.url,
        domain=domain or "",
        summary=summary,
        published_at=row.published_at,
        tags=row.tags,
        type=row.origin,
    )
