from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.api.v1.schemas.media_response_models import (
    VersionDetailResponse,
)
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import (
    DatabaseError,
    MediaDatabase,
    check_media_exists,
    get_document_version,
)


router = APIRouter(tags=["Media Versioning"])


def _is_test_mode() -> bool:
    try:
        from tldw_Server_API.app.core.testing import is_test_mode as _is_test_mode_impl

        return bool(_is_test_mode_impl())
    except Exception:
        return False


@router.get(
    "/{media_id:int}/versions",
    summary="List Media Versions",
    response_model=List[VersionDetailResponse],
    response_model_exclude_none=True,
)
async def list_versions(
    media_id: int = Path(..., description="The ID of the media item"),
    include_content: bool = Query(
        False,
        description="Include full content in response",
    ),
    limit: int = Query(
        10,
        ge=1,
        le=100,
        description="Results per page",
    ),
    page: int = Query(
        1,
        ge=1,
        description="Page number",
    ),
    db: MediaDatabase = Depends(get_media_db_for_user),
) -> List[VersionDetailResponse]:
    """
    List active versions for an active media item.
    """
    logger.debug(
        "Listing versions for media_id: {} (Page: {}, Limit: {}, Content: {})",
        media_id,
        page,
        limit,
        include_content,
    )

    offset = (page - 1) * limit

    try:
        media_exists = check_media_exists(db_instance=db, media_id=media_id)
        if not media_exists:
            logger.warning(
                "Cannot list versions: Media ID {} not found or deleted.",
                media_id,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Media item not found or deleted",
            )

        select_cols_list = [
            "dv.id",
            "dv.uuid",
            "dv.media_id",
            "dv.version_number",
            "dv.created_at",
            "dv.prompt",
            "dv.analysis_content",
            "dv.safe_metadata",
            "dv.last_modified",
            "dv.version",
        ]
        if include_content:
            select_cols_list.append("dv.content")
        select_cols = ", ".join(select_cols_list)

        query = f"""
            SELECT {select_cols}
            FROM DocumentVersions dv
            WHERE dv.media_id = ? AND dv.deleted = 0
            ORDER BY dv.version_number DESC
            LIMIT ? OFFSET ?
        """
        params = (media_id, limit, offset)
        cursor = db.execute_query(query, params)
        raw_rows = [dict(row) for row in cursor.fetchall()]

        versions: List[VersionDetailResponse] = []
        for rv in raw_rows:
            created_at_dt: Optional[datetime] = rv.get("created_at")
            if isinstance(created_at_dt, str):
                try:
                    created_at_dt = datetime.fromisoformat(
                        created_at_dt.replace("Z", "+00:00")
                    )
                except Exception:
                    pass
            safe_md = rv.get("safe_metadata")
            if isinstance(safe_md, str):
                import json as _json

                try:
                    safe_md = _json.loads(safe_md)
                except Exception:
                    safe_md = None
            versions.append(
                VersionDetailResponse(
                    uuid=rv.get("uuid"),
                    media_id=rv.get("media_id"),
                    version_number=rv.get("version_number"),
                    created_at=created_at_dt,
                    prompt=rv.get("prompt"),
                    analysis_content=rv.get("analysis_content"),
                    safe_metadata=safe_md,
                    content=rv.get("content") if include_content else None,
                )
            )

        return versions
    except DatabaseError as exc:
        logger.error(
            "Database error listing versions for media {}: {}",
            media_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Unexpected error listing versions for media {}: {}",
            media_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error listing versions",
        ) from exc


@router.get(
    "/{media_id:int}/versions/{version_number:int}",
    summary="Get Specific Media Version",
    response_model=VersionDetailResponse,
    response_model_exclude_none=True,
)
async def get_version(
    media_id: int = Path(..., description="The ID of the media item"),
    version_number: int = Path(..., description="The version number"),
    include_content: bool = Query(
        True,
        description="Include full content in response",
    ),
    db: MediaDatabase = Depends(get_media_db_for_user),
) -> VersionDetailResponse:
    """
    Get details of a specific active version for an active media item.
    """
    logger.debug(
        "Getting version {} for media_id: {} (Content: {})",
        version_number,
        media_id,
        include_content,
    )
    try:
        version_dict = get_document_version(
            db_instance=db,
            media_id=media_id,
            version_number=version_number,
            include_content=include_content,
        )

        if version_dict is None:
            logger.warning(
                "Active version {} not found for active media {}",
                version_number,
                media_id,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Version not found or media/version is inactive",
            )

        created_at_dt = version_dict.get("created_at")
        if isinstance(created_at_dt, str):
            try:
                created_at_dt = datetime.fromisoformat(
                    created_at_dt.replace("Z", "+00:00")
                )
            except Exception:
                pass
        safe_md = version_dict.get("safe_metadata")
        if isinstance(safe_md, str):
            import json as _json

            try:
                safe_md = _json.loads(safe_md)
            except Exception:
                safe_md = None

        return VersionDetailResponse(
            uuid=version_dict.get("uuid"),
            media_id=version_dict.get("media_id"),
            version_number=version_dict.get("version_number"),
            created_at=created_at_dt,
            prompt=version_dict.get("prompt"),
            analysis_content=version_dict.get("analysis_content"),
            safe_metadata=safe_md,
            content=version_dict.get("content") if include_content else None,
        )
    except ValueError as exc:
        logger.warning(
            "Invalid input for get_document_version: {}",
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid request parameters",
        ) from exc
    except DatabaseError as exc:
        logger.error(
            "Database error getting version {} for media {}: {}",
            version_number,
            media_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Unexpected error getting version {} for media {}: {}",
            version_number,
            media_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error getting version",
        ) from exc


__all__ = ["router"]
