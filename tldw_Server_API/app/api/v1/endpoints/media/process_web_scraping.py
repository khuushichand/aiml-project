from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import rbac_rate_limit
from tldw_Server_API.app.core.AuthNZ.permissions import MEDIA_CREATE, PermissionChecker
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.services.web_scraping_service import (
    process_web_scraping_task,
)
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
    Ingest / scrape data from websites or sitemaps, optionally summarize,
    then either store ephemeral or persist in DB.

    This is the modular implementation of `/process-web-scraping`, mirroring
    the legacy behavior while routing through the `media` package and using
    the `media` shim so tests can continue to patch `process_web_scraping_task`.
    """
    try:
        # Usage logging is best-effort; never fail the request.
        try:
            usage_log.log_event(
                "webscrape.process",
                tags=[str(payload.scrape_method or "")],
                metadata={
                    "mode": payload.mode,
                    "max_pages": payload.max_pages,
                    "max_depth": payload.max_depth,
                },
            )
        except Exception:
            pass

        # Resolve the scraping task via the media shim so tests that
        # monkeypatch `media.process_web_scraping_task` continue to work.
        try:
            from tldw_Server_API.app.api.v1.endpoints import media as media_mod

            task = getattr(
                media_mod,
                "process_web_scraping_task",
                process_web_scraping_task,
            )
        except Exception:  # pragma: no cover - defensive fallback
            task = process_web_scraping_task

        result = await task(
            scrape_method=payload.scrape_method,
            url_input=payload.url_input,
            url_level=payload.url_level,
            max_pages=payload.max_pages,
            max_depth=payload.max_depth,
            summarize_checkbox=payload.summarize_checkbox,
            custom_prompt=payload.custom_prompt,
            api_name=payload.api_name,
            api_key=None,  # API key retrieved from server config
            keywords=payload.keywords or "",
            custom_titles=payload.custom_titles,
            system_prompt=payload.system_prompt,
            temperature=payload.temperature,
            custom_cookies=payload.custom_cookies,
            mode=payload.mode,
            user_id=(
                getattr(getattr(db, "user", None), "id", None)
                if db is not None
                else None
            ),
            user_agent=payload.user_agent,
            custom_headers=payload.custom_headers,
            crawl_strategy=payload.crawl_strategy,
            include_external=payload.include_external,
            score_threshold=payload.score_threshold,
        )
        return result
    except Exception as exc:  # pragma: no cover - defensive path
        import traceback

        error_detail = f"Web scraping failed: {str(exc)}"
        logger.error("Web scraping endpoint error: {}", error_detail)
        try:
            logger.error("Traceback: {}", traceback.format_exc())
            logger.error(
                "Request details - scrape_method: {}, url_input: {}",
                payload.scrape_method,
                (payload.url_input[:100] if payload.url_input else "None"),
            )
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=error_detail)


__all__ = ["router"]
