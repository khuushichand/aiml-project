from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import (
    check_rate_limit,
    get_auth_principal,
)
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.services import admin_personalization_service

router = APIRouter()


@router.post(
    "/personalization/consolidate",
    response_model=dict,
    dependencies=[Depends(check_rate_limit)],
)
async def trigger_personalization_consolidation(
    user_id: str | None = Query(None, description="User ID to consolidate; defaults to single-user id"),
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> dict:
    """
    Trigger personalization consolidation (admin scope).

    Args:
        user_id: User ID to consolidate; defaults to the single-user id.
        principal: Authenticated principal used for admin authorization.

    Returns:
        Consolidation trigger result payload.
    """
    if not (principal.is_admin or ("admin" in (principal.roles or []))):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return await admin_personalization_service.trigger_consolidation(user_id=user_id)


@router.get("/personalization/status", response_model=dict)
async def get_personalization_status() -> dict:
    return await admin_personalization_service.get_status()
