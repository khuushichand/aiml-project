"""
org_invites.py

Public invite endpoints for preview and redemption.
These are separate from the org management endpoints in orgs.py.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
from tldw_Server_API.app.api.v1.schemas.org_team_schemas import (
    OrgInvitePreviewResponse,
    OrgInviteRedeemRequest,
    OrgInviteRedeemResponse,
)
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.services.org_invite_service import get_invite_service


router = APIRouter(
    prefix="/invites",
    tags=["invites"],
)


@router.get(
    "/preview",
    response_model=OrgInvitePreviewResponse,
    summary="Preview an invite",
    description="Get public information about an invite without authentication. "
    "Returns organization name, team (if applicable), role, and validity status.",
)
async def preview_invite(
    code: str = Query(..., min_length=8, description="The invite code to preview"),
):
    """
    Preview an invite code without authentication.

    This allows users to see what organization/team they would join before
    logging in or signing up.
    """
    invite_service = await get_invite_service()
    preview = await invite_service.preview_invite(code)

    if preview is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite code not found",
        )

    return OrgInvitePreviewResponse(
        org_name=preview.get("org_name"),
        org_slug=preview.get("org_slug"),
        team_name=preview.get("team_name"),
        role_to_grant=preview.get("role_to_grant", "member"),
        is_valid=preview.get("is_valid", False),
        status=preview.get("status", "unknown"),
        message=preview.get("message"),
        expires_at=preview.get("expires_at"),
    )


@router.post(
    "/redeem",
    response_model=OrgInviteRedeemResponse,
    summary="Redeem an invite",
    description="Redeem an invite code to join an organization (and optionally a team). "
    "Requires authentication. If already a member, returns success with was_already_member=True.",
)
async def redeem_invite(
    body: OrgInviteRedeemRequest,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
):
    """
    Redeem an invite code to join an organization.

    This is idempotent - if the user is already a member, it returns success
    with was_already_member=True.

    The user's IP address and user agent are recorded for audit purposes.
    """
    invite_service = await get_invite_service()

    # Extract client info for audit logging
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    result = await invite_service.redeem_invite(
        code=body.code,
        user_id=principal.user_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    if not result.success:
        # Determine appropriate status code based on the failure reason
        if "expired" in (result.message or "").lower():
            status_code = status.HTTP_410_GONE
        elif "exhausted" in (result.message or "").lower() or "limit" in (result.message or "").lower():
            status_code = status.HTTP_410_GONE
        elif "revoked" in (result.message or "").lower():
            status_code = status.HTTP_410_GONE
        elif "not found" in (result.message or "").lower():
            status_code = status.HTTP_404_NOT_FOUND
        else:
            status_code = status.HTTP_400_BAD_REQUEST

        raise HTTPException(
            status_code=status_code,
            detail=result.message or "Failed to redeem invite",
        )

    if result.was_already_member:
        logger.info(
            f"User {principal.user_id} attempted to redeem invite {body.code[:8]}... "
            f"but was already a member of org {result.org_id}"
        )
    else:
        logger.info(
            f"User {principal.user_id} redeemed invite {body.code[:8]}... "
            f"and joined org {result.org_id}"
            f"{f' team {result.team_id}' if result.team_id else ''} "
            f"with role {result.role}"
        )

    return OrgInviteRedeemResponse(
        success=result.success,
        org_id=result.org_id,
        org_name=result.org_name,
        team_id=result.team_id,
        team_name=result.team_name,
        role=result.role,
        was_already_member=result.was_already_member,
        message=result.message,
    )
