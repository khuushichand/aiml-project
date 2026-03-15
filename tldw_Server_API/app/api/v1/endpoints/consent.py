"""
consent.py

GDPR consent management endpoints.
Allows users to view, grant, and withdraw consent for data processing purposes.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
from tldw_Server_API.app.core.AuthNZ.consent_manager import ConsentManager
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal

router = APIRouter(
    prefix="/consent",
    tags=["consent"],
    responses={
        401: {"description": "Not authenticated"},
    },
)

_CONSENT_NONCRITICAL_EXCEPTIONS = (
    AttributeError,
    KeyError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)


def _get_consent_db_path() -> str:
    """Resolve the consent database path from env or default."""
    env_path = os.environ.get("CONSENT_DB_PATH")
    if env_path:
        return env_path
    try:
        from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
        base = DatabasePaths.get_shared_audit_db_path().parent
        return str(base / "consent.db")
    except _CONSENT_NONCRITICAL_EXCEPTIONS:
        db_dir = Path("./Databases")
        db_dir.mkdir(parents=True, exist_ok=True)
        return str(db_dir / "consent.db")


def _get_consent_manager() -> ConsentManager:
    """Get or create a ConsentManager instance."""
    db_path = _get_consent_db_path()
    return ConsentManager(db_path)


def _resolve_user_id(principal: AuthPrincipal) -> int:
    """Extract integer user_id from the auth principal."""
    if principal.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User identification required for consent management.",
        )
    return principal.user_id


@router.get("/preferences")
async def get_consent_preferences(
    principal: AuthPrincipal = Depends(get_auth_principal),
):
    """Get current user's consent preferences."""
    user_id = _resolve_user_id(principal)
    try:
        mgr = _get_consent_manager()
        records = mgr.get_user_consents(user_id)
        return {
            "user_id": user_id,
            "consents": records,
        }
    except _CONSENT_NONCRITICAL_EXCEPTIONS as exc:
        logger.error("Failed to get consent preferences for user {}: {}", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve consent preferences.",
        ) from exc


@router.post("/preferences/{purpose}")
async def grant_consent(
    purpose: str,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
):
    """Grant consent for a specific purpose."""
    user_id = _resolve_user_id(principal)
    ip_address = None
    user_agent = None
    try:
        ip_address = request.client.host if request.client else None
    except _CONSENT_NONCRITICAL_EXCEPTIONS:
        pass
    try:
        user_agent = request.headers.get("user-agent")
    except _CONSENT_NONCRITICAL_EXCEPTIONS:
        pass

    try:
        mgr = _get_consent_manager()
        result = mgr.grant_consent(
            user_id,
            purpose,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return result
    except _CONSENT_NONCRITICAL_EXCEPTIONS as exc:
        logger.error("Failed to grant consent for user {} purpose {}: {}", user_id, purpose, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record consent.",
        ) from exc


@router.delete("/preferences/{purpose}")
async def withdraw_consent(
    purpose: str,
    principal: AuthPrincipal = Depends(get_auth_principal),
):
    """Withdraw consent for a specific purpose."""
    user_id = _resolve_user_id(principal)
    try:
        mgr = _get_consent_manager()
        result = mgr.withdraw_consent(user_id, purpose)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No active consent found for purpose '{purpose}'.",
            )
        return result
    except HTTPException:
        raise
    except _CONSENT_NONCRITICAL_EXCEPTIONS as exc:
        logger.error("Failed to withdraw consent for user {} purpose {}: {}", user_id, purpose, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to withdraw consent.",
        ) from exc
