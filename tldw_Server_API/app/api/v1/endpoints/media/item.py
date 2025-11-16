from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, Request, Response, status
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.api.v1.schemas.media_response_models import MediaDetailResponse
from tldw_Server_API.app.api.v1.utils.cache import generate_etag, is_not_modified
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.DB_Manager import get_full_media_details_rich2
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import DatabaseError, MediaDatabase


router = APIRouter(tags=["Media Management"])


def _is_test_mode() -> bool:
    try:
        from tldw_Server_API.app.core.testing import is_test_mode as _is_test_mode_impl

        return bool(_is_test_mode_impl())
    except Exception:
        return False


@router.get(
    "/{media_id:int}",
    status_code=status.HTTP_200_OK,
    summary="Get Media Item Details",
)
async def get_media_item(
    request: Request,
    response: Response,
    media_id: int = Path(..., description="The ID of the media item"),
    include_content: bool = Query(
        True,
        description="Include main content text in response",
    ),
    include_versions: bool = Query(
        True,
        description="Include versions list",
    ),
    include_version_content: bool = Query(
        False,
        description="Include content for each version in versions list",
    ),
    db: MediaDatabase = Depends(get_media_db_for_user),
    current_user: User = Depends(get_request_user),
    if_none_match: str | None = Header(None),
) -> Any:
    """
    Retrieve Media Item by ID.

    Fetches the details for a specific active media item, including
    its associated keywords, latest prompt/analysis, and versions.
    """
    logger.debug(
        "Attempting to fetch rich details for media_id: {}",
        media_id,
    )

    # TEST_MODE diagnostics
    try:
        if _is_test_mode():
            db_path = getattr(db, "db_path_str", getattr(db, "db_path", "?"))
            headers = getattr(request, "headers", {}) or {}
            logger.info(
                "TEST_MODE: get_media_item id={} db_path={} user_id={} "
                "auth_headers={{'X-API-KEY': {{'present': {}}}}, 'Authorization': {{'present': {}}}}}",
                media_id,
                db_path,
                getattr(current_user, "id", "?"),
                bool(headers.get("X-API-KEY")),
                bool(headers.get("authorization")),
            )
    except Exception:
        pass

    try:
        details = get_full_media_details_rich2(
            db_instance=db,
            media_id=media_id,
            include_content=include_content,
            include_versions=include_versions,
            include_version_content=include_version_content,
        )
        if not details:
            logger.warning(
                "Media not found or not active for ID: {}",
                media_id,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Media not found or is inactive/trashed",
            )

        response_model = MediaDetailResponse(**details)
        payload = response_model.model_dump()

        etag = generate_etag(payload)
        response.headers["ETag"] = etag
        if is_not_modified(etag, if_none_match):
            response.status_code = status.HTTP_304_NOT_MODIFIED
            return {}

        return payload
    except HTTPException:
        raise
    except DatabaseError as exc:
        logger.error(
            "Database error fetching details for media {}: {}",
            media_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error retrieving media details",
        ) from exc
    except Exception as exc:
        logger.error(
            "Unexpected error fetching details for media {}: {}",
            media_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred retrieving media details",
        ) from exc


__all__ = ["router"]
