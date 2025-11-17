from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile

from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import rbac_rate_limit
from tldw_Server_API.app.core.AuthNZ.permissions import MEDIA_CREATE, PermissionChecker
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.Ingestion_Media_Processing.persistence import (
    add_media_persist,
)

from tldw_Server_API.app.api.v1.endpoints import _legacy_media as legacy_media  # type: ignore

router = APIRouter()


@router.post(
    "/add",
    # Status code is determined dynamically based on per-item results.
    dependencies=[
        Depends(get_media_db_for_user),
        Depends(PermissionChecker(MEDIA_CREATE)),
        Depends(rbac_rate_limit("media.create")),
    ],
    summary="Add media (URLs/files) with processing and persistence",
    tags=["Media Ingestion & Persistence"],
)
async def add_media(
    background_tasks: BackgroundTasks,
    form_data: legacy_media.AddMediaForm = Depends(  # type: ignore[attr-defined]
        legacy_media.get_add_media_form  # type: ignore[attr-defined]
    ),
    files: Optional[List[UploadFile]] = File(
        None,
        description="List of files to upload",
    ),
    db: MediaDatabase = Depends(get_media_db_for_user),
    current_user: legacy_media.User = Depends(  # type: ignore[attr-defined]
        legacy_media.get_request_user  # type: ignore[attr-defined]
    ),
    usage_log: legacy_media.UsageEventLogger = Depends(  # type: ignore[attr-defined]
        legacy_media.get_usage_event_logger  # type: ignore[attr-defined]
    ),
):
    """
    Thin wrapper for the `/media/add` endpoint.

    This keeps the HTTP contract, auth/RBAC behavior, and side effects
    identical to the legacy implementation while routing through the
    modular `media` package. Processing and persistence logic is
    implemented in the core `persistence.add_media_orchestrate`
    helper, with `_legacy_media.add_media` retained only as a
    compatibility shim for any historical imports.
    """

    return await add_media_persist(
        background_tasks=background_tasks,
        form_data=form_data,
        files=files,
        db=db,
        current_user=current_user,
        usage_log=usage_log,
        response=None,
    )


__all__ = ["router"]
