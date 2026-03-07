from __future__ import annotations

from fastapi import HTTPException, status

from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.services.auth_service import fetch_active_user_by_id


async def verify_privileged_action(
    principal: AuthPrincipal,
    db,
    password_service,
    *,
    reason: str | None,
    admin_password: str | None,
) -> str:
    normalized_reason = str(reason or "").strip()
    normalized_password = str(admin_password or "").strip()

    if len(normalized_reason) < 8 or len(normalized_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reason and current password are required for this action",
        )

    if principal.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Privileged action reauthentication requires an authenticated admin user",
        )

    actor = await fetch_active_user_by_id(db, int(principal.user_id))
    password_hash = actor.get("password_hash") if actor else None
    if not actor or not isinstance(password_hash, str) or not password_hash:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin reauthentication failed",
        )

    verified, _needs_rehash = password_service.verify_password(normalized_password, password_hash)
    if not verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin reauthentication failed",
        )

    return normalized_reason
