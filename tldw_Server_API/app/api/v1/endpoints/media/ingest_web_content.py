from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header

from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import require_token_scope
from tldw_Server_API.app.api.v1.API_Deps.backpressure import (
    guard_backpressure_and_quota,
)
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase

from tldw_Server_API.app.api.v1.endpoints import _legacy_media as legacy_media  # type: ignore  # noqa: E501

router = APIRouter()


@router.post(
    "/ingest-web-content",
    dependencies=[
        Depends(guard_backpressure_and_quota),
        Depends(
            require_token_scope(
                "any",
                require_if_present=False,
                endpoint_id="media.ingest",
                count_as="call",
            )
        ),
    ],
)
async def ingest_web_content(
    request: legacy_media.IngestWebContentRequest,  # type: ignore[attr-defined]
    background_tasks: BackgroundTasks,
    token: str = Header(..., description="Authentication token"),
    db: MediaDatabase = Depends(get_media_db_for_user),
    usage_log: legacy_media.UsageEventLogger = Depends(  # type: ignore[attr-defined]
        legacy_media.get_usage_event_logger  # type: ignore[attr-defined]
    ),
):
    """
    Thin wrapper for `/media/ingest-web-content`.

    This keeps the HTTP contract, backpressure/quota enforcement,
    token-scope behavior, and usage logging identical to the legacy
    implementation while routing through the modular `media` package.
    """

    return await legacy_media.ingest_web_content(  # type: ignore[func-returns-value]
        request=request,
        background_tasks=background_tasks,
        token=token,
        db=db,
        usage_log=usage_log,
    )


__all__ = ["router"]

