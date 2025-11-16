from __future__ import annotations

from fastapi import APIRouter, Depends

from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.core.AuthNZ.permissions import MEDIA_CREATE, PermissionChecker
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import rbac_rate_limit
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase

from tldw_Server_API.app.api.v1.endpoints import _legacy_media as legacy_media  # type: ignore

router = APIRouter()


@router.post(
    "/process-web-scraping",
    dependencies=[
        Depends(PermissionChecker(MEDIA_CREATE)),
        Depends(rbac_rate_limit("media.create")),
    ],
)
async def process_web_scraping_endpoint(
    payload: legacy_media.WebScrapingRequest,  # type: ignore[attr-defined]
    db: MediaDatabase = Depends(get_media_db_for_user),
    usage_log: legacy_media.UsageEventLogger = Depends(  # type: ignore[attr-defined]
        legacy_media.get_usage_event_logger  # type: ignore[attr-defined]
    ),
):
    """
    Thin wrapper that delegates to the legacy implementation.

    This keeps the HTTP contract, rate limiting, and usage logging behavior
    identical while allowing the `/process-web-scraping` route to live under
    the modular `media` package.
    """

    return await legacy_media.process_web_scraping_endpoint(  # type: ignore[func-returns-value]
        payload=payload,
        db=db,
        usage_log=usage_log,
    )


__all__ = ["router"]

