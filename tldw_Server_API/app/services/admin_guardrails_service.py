from __future__ import annotations

import os
from typing import Any

from fastapi import HTTPException, status

from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal, is_single_user_principal
from tldw_Server_API.app.core.AuthNZ.password_service import PasswordService
from tldw_Server_API.app.services.auth_service import fetch_active_user_by_id


def _enterprise_admin_mode_enabled() -> bool:
    raw_value = os.getenv("ADMIN_UI_ENTERPRISE_MODE", "")
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


async def verify_privileged_action(
    principal: AuthPrincipal,
    db: Any,
    password_service: PasswordService,
    *,
    reason: str | None,
    admin_password: str | None,
) -> str:
    """
    Enforce step-up guardrails for high-risk admin actions.

    Requires a human-readable reason for every privileged action. In enterprise
    mode, or for any non-single-user principal, it also requires the acting
    admin's current password and validates it against the active user record.

    Raises:
        HTTPException: When the reason is missing, the password reauth check
            fails, or the acting principal cannot be resolved to an active admin
            account.
    """
    normalized_reason = str(reason or "").strip()
    normalized_password = str(admin_password or "").strip()

    if len(normalized_reason) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reason is required for this action",
        )

    if is_single_user_principal(principal) and not _enterprise_admin_mode_enabled():
        return normalized_reason

    if len(normalized_password) < 8:
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
