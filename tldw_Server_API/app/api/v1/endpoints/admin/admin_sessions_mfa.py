from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import (
    get_auth_principal,
    get_session_manager_dep,
)
from tldw_Server_API.app.api.v1.schemas.auth_schemas import MessageResponse, SessionResponse
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.services import admin_sessions_mfa_service

router = APIRouter()


@router.get("/users/{user_id}/sessions", response_model=list[SessionResponse])
async def admin_list_user_sessions(
    user_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
    session_manager=Depends(get_session_manager_dep),
) -> list[SessionResponse]:
    """List active sessions for a user (admin scope)."""
    return await admin_sessions_mfa_service.list_user_sessions(
        principal,
        user_id,
        session_manager,
    )


@router.delete("/users/{user_id}/sessions/{session_id}", response_model=MessageResponse)
async def admin_revoke_user_session(
    user_id: int,
    session_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
    session_manager=Depends(get_session_manager_dep),
) -> MessageResponse:
    """Revoke a specific session for a user (admin scope)."""
    return await admin_sessions_mfa_service.revoke_user_session(
        principal,
        user_id,
        session_id,
        session_manager,
    )


@router.post("/users/{user_id}/sessions/revoke-all", response_model=MessageResponse)
async def admin_revoke_all_user_sessions(
    user_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
    session_manager=Depends(get_session_manager_dep),
) -> MessageResponse:
    """Revoke all sessions for a user (admin scope)."""
    return await admin_sessions_mfa_service.revoke_all_user_sessions(
        principal,
        user_id,
        session_manager,
    )


@router.get("/users/{user_id}/mfa", response_model=dict[str, Any])
async def admin_get_user_mfa_status(
    user_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> dict[str, Any]:
    """Fetch MFA status for a user (admin scope)."""
    return await admin_sessions_mfa_service.get_user_mfa_status(
        principal,
        user_id,
    )


@router.post("/users/{user_id}/mfa/disable", response_model=MessageResponse)
async def admin_disable_user_mfa(
    user_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> MessageResponse:
    """Disable MFA for a user (admin scope)."""
    return await admin_sessions_mfa_service.disable_user_mfa(
        principal,
        user_id,
    )
