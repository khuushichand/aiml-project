from __future__ import annotations

from typing import Optional, List

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile

from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase

from tldw_Server_API.app.api.v1.endpoints import _legacy_media as legacy_media  # type: ignore

router = APIRouter()


@router.post(
    "/process-audios",
    summary="Transcribe / chunk / analyse audio and return full artefacts (no DB write)",
    tags=["Media Processing (No DB)"],
)
async def process_audios_endpoint(
    background_tasks: BackgroundTasks,
    db: MediaDatabase = Depends(get_media_db_for_user),
    form_data: legacy_media.ProcessAudiosForm = Depends(  # type: ignore[attr-defined]
        legacy_media.get_process_audios_form  # type: ignore[attr-defined]
    ),
    files: Optional[List[UploadFile]] = File(
        None,
        description="Audio file uploads",
    ),
    usage_log: legacy_media.UsageEventLogger = Depends(  # type: ignore[attr-defined]
        legacy_media.get_usage_event_logger  # type: ignore[attr-defined]
    ),
):
    """
    Thin wrapper that delegates to the legacy implementation.

    This keeps the HTTP contract and internal behavior identical while
    allowing the `/process-audios` route to live under the modular
    `media` package.
    """

    return await legacy_media.process_audios_endpoint(  # type: ignore[func-returns-value]
        background_tasks=background_tasks,
        db=db,
        form_data=form_data,
        files=files,
        usage_log=usage_log,
    )


__all__ = ["router"]

