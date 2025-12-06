from __future__ import annotations

from math import ceil
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    Body,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import (
    get_media_db_for_user,
    try_get_media_db_for_user,
)
from tldw_Server_API.app.api.v1.API_Deps.rate_limiting import limiter
from tldw_Server_API.app.api.v1.schemas.media_request_models import SearchRequest
from pydantic import ValidationError
from tldw_Server_API.app.api.v1.schemas.media_response_models import (
    MediaListItem,
    MediaListResponse,
)
from tldw_Server_API.app.api.v1.utils.cache import generate_etag, is_not_modified
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.DB_Manager import get_paginated_files
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import (
    DatabaseError,
    MediaDatabase,
    fetch_keywords_for_media_batch,
)
from tldw_Server_API.app.core.Utils.metadata_utils import normalize_safe_metadata


router = APIRouter(tags=["Media Management"])


try:
    HTTP_422_UNPROCESSABLE = status.HTTP_422_UNPROCESSABLE_CONTENT
except AttributeError:  # Starlette < 0.27
    HTTP_422_UNPROCESSABLE = status.HTTP_422_UNPROCESSABLE_ENTITY


def _is_test_mode() -> bool:
    try:
        from tldw_Server_API.app.core.testing import is_test_mode as _is_test_mode_impl

        return bool(_is_test_mode_impl())
    except Exception:
        return False


_SEARCH_RATE_LIMIT = "600/minute" if _is_test_mode() else "30/minute"


@router.get(
    "/",
    summary="List Media (slash)",
)
async def list_media_endpoint(
    request: Request,
    response: Response,
    current_user: User = Depends(get_request_user),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    results_per_page: int = Query(10, ge=1, description="Items per page"),
    include_keywords: bool = Query(
        False,
        description="Include associated keywords for each media item.",
    ),
    db: MediaDatabase = Depends(get_media_db_for_user),
    if_none_match: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """
    Return paginated list of active media items (basic fields only).

    Preserves existing TEST_MODE diagnostics and response shape while
    adding ETag support based on a deterministic serialization.
    """
    try:
        # TEST_MODE diagnostics (headers + log messages)
        try:
            if _is_test_mode():
                db_path = getattr(db, "db_path_str", getattr(db, "db_path", "?"))
                headers = getattr(request, "headers", {}) or {}
                logger.warning(
                    "TEST_MODE: list_media db_path={} user_id={} auth_headers="
                    "{{'X-API-KEY': {{'present': {}}}}, 'Authorization': {{'present': {}}}}}",
                    db_path,
                    getattr(current_user, "id", "?"),
                    bool(headers.get("X-API-KEY")),
                    bool(headers.get("authorization")),
                )
        except Exception:
            pass

        rows, total_pages, current_page, total_items = get_paginated_files(
            db_instance=db,
            page=page,
            results_per_page=results_per_page,
        )

        # Additional TEST_MODE summary + headers
        try:
            if _is_test_mode():
                logger.warning(
                    "TEST_MODE: list_media summary page={} rpp={} total_items={} rows_returned={}",
                    page,
                    results_per_page,
                    total_items,
                    len(rows or []),
                )
                if response is not None:
                    db_path = getattr(db, "db_path_str", getattr(db, "db_path", "?"))
                    try:
                        response.headers["X-TLDW-DB-Path"] = str(db_path)
                        response.headers["X-TLDW-List-Total"] = str(int(total_items))
                    except Exception:
                        pass
        except Exception:
            pass

        # Build base items and collect IDs for keyword lookup
        base_items: List[Dict[str, Any]] = []
        media_ids: List[int] = []
        for r in rows or []:
            rid_raw = r["id"] if isinstance(r, dict) else r[0]
            title = r["title"] if isinstance(r, dict) else r[1]
            rtype = r["type"] if isinstance(r, dict) else r[2]
            try:
                rid = int(rid_raw)
            except (TypeError, ValueError):
                # Skip rows with invalid IDs rather than failing the entire listing
                logger.error("Skipping media row with invalid id: {}", rid_raw)
                continue
            media_ids.append(rid)
            base_items.append(
                {
                    "id": rid,
                    "title": str(title),
                    "type": str(rtype),
                }
            )

        # Optionally fetch keywords for all media items on this page in a single batch
        keywords_map: Dict[int, List[str]] = {}
        if include_keywords and media_ids:
            try:
                keywords_map = fetch_keywords_for_media_batch(
                    media_ids=media_ids,
                    db_instance=db,
                )
            except Exception as exc:
                # Log and degrade gracefully if keyword lookup fails
                logger.error(
                    "Error fetching keywords for media list page={} rpp={}: {}",
                    page,
                    results_per_page,
                    exc,
                    exc_info=True,
                )
                keywords_map = {}

        # Build response items, including keywords only when requested
        items: List[Dict[str, Any]] = []
        for item in base_items:
            mid = item["id"]
            base_payload: Dict[str, Any] = {
                "id": mid,
                "title": item["title"],
                "type": item["type"],
                "url": f"/api/v1/media/{mid}",
            }
            if include_keywords:
                base_payload["keywords"] = keywords_map.get(mid, [])
            items.append(base_payload)

        payload: Dict[str, Any] = {
            "items": items,
            "pagination": {
                "page": int(current_page),
                "results_per_page": int(results_per_page),
                "total_pages": int(total_pages),
                "total_items": int(total_items),
            },
        }

        etag = generate_etag(payload)
        response.headers["ETag"] = etag
        if is_not_modified(etag, if_none_match):
            response.status_code = status.HTTP_304_NOT_MODIFIED
            return {}

        return payload
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error listing media: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list media",
        ) from exc


@router.get(
    "/metadata-search",
    summary="Search media by safe metadata",
)
async def search_by_metadata(
    request: Request,
    response: Response,
    filters: Optional[str] = Query(
        None,
        description="JSON list of {field, op, value}",
    ),
    field: Optional[str] = Query(
        None,
        description="Single filter field",
    ),
    op: Optional[str] = Query(
        "icontains",
        description="Operator: eq|contains|icontains|startswith|endswith",
    ),
    value: Optional[str] = Query(
        None,
        description="Single filter value",
    ),
    match_mode: str = Query("all", description="all|any"),
    group_by_media: bool = Query(True),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: MediaDatabase = Depends(get_media_db_for_user),
    if_none_match: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """
    Search media items based on version safe_metadata fields and identifier indices.

    Mirrors the legacy implementation while adding basic ETag support.
    """
    try:
        flt_list: List[Dict[str, Any]] = []
        import json as _json

        if filters:
            try:
                parsed = _json.loads(filters)
                if isinstance(parsed, list):
                    for f in parsed:
                        if isinstance(f, dict) and "field" in f and "value" in f:
                            flt_list.append(
                                {
                                    "field": f["field"],
                                    "op": f.get("op", "icontains"),
                                    "value": f["value"],
                                }
                            )
            except Exception as je:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid 'filters' JSON: {je}",
                ) from je
        elif field and value is not None:
            flt_list.append(
                {
                    "field": field,
                    "op": op or "icontains",
                    "value": value,
                }
            )

        # Normalize identifier filters where applicable (doi/pmid/pmcid/arxiv_id)
        norm_fields = {
            "doi",
            "pmid",
            "pmcid",
            "arxiv_id",
            "DOI",
            "PMID",
            "PMCID",
            "arXiv",
            "ArXiv",
        }
        canonical_order = ("doi", "pmid", "pmcid", "arxiv_id", "s2_paper_id")
        normalized_filters: List[Dict[str, Any]] = []
        for f in flt_list or []:
            try:
                fld = f.get("field")
                if fld in norm_fields:
                    norm = normalize_safe_metadata({fld: f.get("value")})
                    key = next(
                        (k for k in canonical_order if k in norm),
                        (fld or "").lower(),
                    )
                    val = norm.get(key, f.get("value"))
                    normalized_filters.append(
                        {
                            "field": key,
                            "op": f.get("op", "icontains"),
                            "value": val,
                        }
                    )
                else:
                    normalized_filters.append(f)
            except ValueError as ve:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(ve),
                ) from ve

        rows, total = db.search_by_safe_metadata(
            filters=normalized_filters or None,
            match_all=(match_mode.lower() == "all"),
            page=page,
            per_page=per_page,
            group_by_media=group_by_media,
        )

        for r in rows:
            sm = r.get("safe_metadata")
            if isinstance(sm, str):
                try:
                    r["safe_metadata"] = _json.loads(sm)
                except Exception:
                    r["safe_metadata"] = None

        payload: Dict[str, Any] = {
            "results": rows,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": (total + per_page - 1) // per_page,
            },
        }

        etag = generate_etag(payload)
        response.headers["ETag"] = etag
        if is_not_modified(etag, if_none_match):
            response.status_code = status.HTTP_304_NOT_MODIFIED
            return {}

        return payload
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Metadata search error: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error performing metadata search",
        ) from exc


async def _validate_identifier_query(
    doi: Optional[str] = Query(None),
    pmid: Optional[str] = Query(None),
    pmcid: Optional[str] = Query(None),
    arxiv_id: Optional[str] = Query(None),
    s2_paper_id: Optional[str] = Query(None),
) -> bool:
    """
    Early validation for /by-identifier to ensure malformed IDs return 400 before auth/DB.

    Uses normalize_safe_metadata which raises ValueError for invalid DOI/PMID/PMCID.
    """
    raw: Dict[str, Any] = {}
    if doi is not None:
        raw["doi"] = doi
    if pmid is not None:
        raw["pmid"] = pmid
    if pmcid is not None:
        raw["pmcid"] = pmcid
    if arxiv_id is not None:
        raw["arxiv_id"] = arxiv_id
    if s2_paper_id is not None:
        raw["s2_paper_id"] = s2_paper_id

    try:
        if raw:
            normalize_safe_metadata(raw)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provide at least one identifier",
            )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        ) from ve
    return True


@router.get(
    "/by-identifier",
    summary="Find media by standard identifier (DOI/PMID/PMCID/arXiv/S2)",
    dependencies=[Depends(_validate_identifier_query)],
)
async def get_by_identifier(
    request: Request,
    response: Response,
    doi: Optional[str] = Query(None),
    pmid: Optional[str] = Query(None),
    pmcid: Optional[str] = Query(None),
    arxiv_id: Optional[str] = Query(None),
    s2_paper_id: Optional[str] = Query(None),
    group_by_media: bool = Query(True),
    db: Optional[MediaDatabase] = Depends(try_get_media_db_for_user),
    if_none_match: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """
    Quick lookup by canonical identifiers. Returns latest matching version per media by default.
    """
    try:
        flt_list: List[Dict[str, Any]] = []
        raw_filters: List[Dict[str, Any]] = []
        if doi:
            raw_filters.append({"field": "doi", "op": "eq", "value": doi})
        if pmid:
            raw_filters.append({"field": "pmid", "op": "eq", "value": pmid})
        if pmcid:
            raw_filters.append({"field": "pmcid", "op": "eq", "value": pmcid})
        if arxiv_id:
            raw_filters.append({"field": "arxiv_id", "op": "eq", "value": arxiv_id})
        if s2_paper_id:
            raw_filters.append(
                {"field": "s2_paper_id", "op": "eq", "value": s2_paper_id}
            )

        for f in raw_filters:
            try:
                if f["field"] != "s2_paper_id":
                    norm = normalize_safe_metadata({f["field"]: f["value"]})
                else:
                    norm = {f["field"]: f["value"]}
                canonical_order = ("doi", "pmid", "pmcid", "arxiv_id", "s2_paper_id")
                key = next(
                    (k for k in canonical_order if k in norm),
                    (f["field"] or "").lower(),
                )
                val = norm.get(key, f["value"])
                flt_list.append({"field": key, "op": f["op"], "value": val})
            except ValueError as ve:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(ve),
                ) from ve

        if not flt_list:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provide at least one identifier",
            )
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Media DB initialization failed",
            )

        rows, total = db.search_by_safe_metadata(
            filters=flt_list,
            match_all=True,
            page=1,
            per_page=50,
            group_by_media=group_by_media,
        )

        import json as _json

        for r in rows:
            sm = r.get("safe_metadata")
            if isinstance(sm, str):
                try:
                    r["safe_metadata"] = _json.loads(sm)
                except Exception:
                    r["safe_metadata"] = None

        payload: Dict[str, Any] = {"results": rows, "total": total}
        etag = generate_etag(payload)
        response.headers["ETag"] = etag
        if is_not_modified(etag, if_none_match):
            response.status_code = status.HTTP_304_NOT_MODIFIED
            return {}

        return payload
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Identifier lookup error: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error in identifier lookup",
        ) from exc


@router.post(
    "/search",
    status_code=status.HTTP_200_OK,
    summary="Search Media Items",
    response_model=MediaListResponse,
)
@limiter.limit(_SEARCH_RATE_LIMIT)
async def search_media_items(
    request: Request,
    payload: Dict[str, Any] = Body(...),
    page: int = Query(1, ge=1, description="Page number"),
    results_per_page: int = Query(
        10,
        ge=1,
        le=100,
        description="Results per page",
    ),
    db: MediaDatabase = Depends(get_media_db_for_user),
    if_none_match: Optional[str] = Header(None),
) -> Response:
    """
    Search across media items based on various criteria.

    Preserves the legacy response envelope while using centralized
    ETag helpers for conditional responses.
    """
    try:
        try:
            search_params = SearchRequest(**payload)
        except ValidationError as ve:
            raise HTTPException(
                status_code=HTTP_422_UNPROCESSABLE,
                detail=ve.errors(),
            ) from ve
        query_text_for_match: Optional[str] = None
        if search_params.exact_phrase:
            query_text_for_match = f'"{search_params.exact_phrase.strip()}"'
        elif search_params.query:
            query_text_for_match = search_params.query.strip()

        items_data, total_items = db.search_media_db(
            search_query=query_text_for_match,
            search_fields=search_params.fields,
            media_types=search_params.media_types,
            date_range=search_params.date_range,
            must_have_keywords=search_params.must_have,
            must_not_have_keywords=search_params.must_not_have,
            sort_by=search_params.sort_by,
            page=page,
            results_per_page=results_per_page,
            include_trash=False,
            include_deleted=False,
        )

        formatted_items = [
            MediaListItem(
                id=item["id"],
                title=item["title"],
                type=item["type"],
                url=f"/api/v1/media/{item['id']}",
            )
            for item in items_data
        ]

        total_pages = (
            ceil(total_items / results_per_page)
            if results_per_page > 0 and total_items > 0
            else 0
        )

        from tldw_Server_API.app.api.v1.schemas.media_response_models import (
            PaginationInfo,
        )

        pagination_info = PaginationInfo(
            page=page,
            results_per_page=results_per_page,
            total_pages=total_pages,
            total_items=total_items,
        )

        try:
            response_obj = MediaListResponse(
                items=formatted_items,
                pagination=pagination_info,
            )

            payload_dict = response_obj.model_dump()
            payload_dict["results"] = payload_dict.get("items", [])

            etag = generate_etag(payload_dict)
            if is_not_modified(etag, if_none_match):
                return Response(
                    status_code=status.HTTP_304_NOT_MODIFIED,
                    headers={"ETag": etag},
                )

            import json

            response_json = json.dumps(payload_dict)
            return Response(
                content=response_json,
                media_type="application/json",
                headers={"ETag": etag},
            )
        except Exception as ve:
            logger.debug(
                "Data causing validation error in search: items_count={}, "
                "pagination={}",
                len(formatted_items),
                pagination_info.model_dump_json(indent=2)
                if pagination_info
                else "None",
            )
            logger.error(
                f"Pydantic validation error creating MediaListResponse for search: {ve}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error: Response creation failed.",
            ) from ve
    except ValueError as ve:
        logger.warning(
            f"Invalid parameters for media search: {ve}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=HTTP_422_UNPROCESSABLE,
            detail=str(ve),
        ) from ve
    except DatabaseError as exc:
        logger.error(f"Database error during media search: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred during the search.",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            f"Unexpected error in search_media_items endpoint: {exc}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected internal server error occurred.",
        ) from exc


__all__ = ["router"]
