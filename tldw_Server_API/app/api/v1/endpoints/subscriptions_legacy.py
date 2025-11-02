from __future__ import annotations

"""
Deprecated legacy endpoints for `/api/v1/subscriptions/*`.

All routes under this prefix return 410 Gone with a Link header pointing to the
replacement Watchlists endpoints.
"""

from typing import Optional
from fastapi import APIRouter, Request, Response, status


router = APIRouter(prefix="/subscriptions", tags=["subscriptions-deprecated"])


def _map_subscriptions_to_watchlists(path: str) -> str:
    # Basic mapping: replace the first "subscriptions" segment with "watchlists"
    if not path:
        return "/watchlists"
    parts = path.split("/")
    out: list[str] = []
    replaced = False
    for p in parts:
        if not p:
            continue
        if not replaced and p == "subscriptions":
            out.append("watchlists")
            replaced = True
            continue
        out.append(p)
    mapped = "/" + "/".join(out) if out else "/watchlists"
    # Specific heuristics for common legacy nouns
    mapped = mapped.replace("/checks", "/runs")  # SubscriptionChecks → Scrape Runs
    return mapped


def _deprecated_payload(request: Request, mapped: str) -> dict[str, object]:
    return {
        "detail": "subscriptions_api_deprecated",
        "message": "The /api/v1/subscriptions/* API is deprecated. Use /api/v1/watchlists/* instead.",
        "method": request.method,
        "path": request.url.path,
        "replacement": mapped,
        "status": 410,
    }


@router.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"], include_in_schema=False)
async def subscriptions_deprecated(request: Request, full_path: Optional[str] = None) -> Response:
    mapped = _map_subscriptions_to_watchlists(request.url.path)
    payload = _deprecated_payload(request, mapped)
    headers = {
        "Deprecation": "true",
        "Link": f"<{mapped}>; rel=\"replacement\"",
        "Sunset": "true",
        "X-Deprecated-Endpoint": "subscriptions",
    }
    from fastapi.responses import JSONResponse

    return JSONResponse(content=payload, status_code=status.HTTP_410_GONE, headers=headers)
