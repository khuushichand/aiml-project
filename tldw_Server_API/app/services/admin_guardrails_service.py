from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status

from tldw_Server_API.app.api.v1.schemas.admin_schemas import unwrap_optional_secret
from tldw_Server_API.app.core.AuthNZ.jwt_service import get_jwt_service
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal, is_single_user_principal
from tldw_Server_API.app.core.AuthNZ.password_service import PasswordService
from tldw_Server_API.app.core.AuthNZ.token_blacklist import get_token_blacklist
from tldw_Server_API.app.services.auth_service import fetch_active_user_by_id


def _enterprise_admin_mode_enabled() -> bool:
    raw_value = os.getenv("ADMIN_UI_ENTERPRISE_MODE", "")
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_actor_email(actor: Any) -> str:
    raw_email = ""
    if isinstance(actor, dict):
        raw_email = str(actor.get("email") or "")
    else:
        raw_email = str(getattr(actor, "email", "") or "")
    return raw_email.strip().lower()


def _matches_actor_identity(payload: dict[str, Any], actor: Any) -> bool:
    actor_id = int(actor["id"]) if isinstance(actor, dict) and actor.get("id") is not None else None
    if actor_id is None:
        return False

    for candidate in (payload.get("user_id"), payload.get("sub")):
        if isinstance(candidate, int) and candidate == actor_id:
            return True
        if isinstance(candidate, str) and candidate.isdigit() and int(candidate) == actor_id:
            return True

    actor_email = _normalize_actor_email(actor)
    payload_email = str(payload.get("email") or "").strip().lower()
    return bool(actor_email and payload_email and actor_email == payload_email)


async def _verify_admin_reauth_token(
    *,
    actor: Any,
    admin_reauth_token: str,
) -> bool:
    jwt_service = get_jwt_service()
    payload = await jwt_service.verify_token_async(admin_reauth_token, token_type="admin_reauth")
    purpose = str(payload.get("purpose") or "").strip().lower()
    if purpose != "admin_reauth":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin reauthentication failed",
        )
    if not _matches_actor_identity(payload, actor):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin reauthentication failed",
        )

    jti = str(payload.get("jti") or "").strip()
    raw_exp = payload.get("exp")
    exp_dt: datetime | None = None
    if isinstance(raw_exp, (int, float)):
        exp_dt = datetime.fromtimestamp(raw_exp, tz=timezone.utc)
    elif isinstance(raw_exp, datetime):
        exp_dt = raw_exp if raw_exp.tzinfo is not None else raw_exp.replace(tzinfo=timezone.utc)

    if not jti or exp_dt is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin reauthentication failed",
        )

    blacklist = get_token_blacklist()
    actor_id = int(actor["id"]) if isinstance(actor, dict) else None
    await blacklist.revoke_token(
        jti=jti,
        expires_at=exp_dt,
        user_id=actor_id,
        token_type="admin_reauth",
        reason="admin_reauth_used",
        revoked_by=actor_id,
        ip_address=None,
    )
    return True


async def verify_privileged_action(
    principal: AuthPrincipal,
    db: Any,
    password_service: PasswordService,
    *,
    reason: str | None,
    admin_password: Any | None,
    admin_reauth_token: Any | None = None,
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
    normalized_password = unwrap_optional_secret(admin_password) or ""
    normalized_reauth_token = unwrap_optional_secret(admin_reauth_token) or ""

    if len(normalized_reason) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reason is required for this action",
        )

    if is_single_user_principal(principal) and not _enterprise_admin_mode_enabled():
        return normalized_reason

    if principal.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Privileged action reauthentication requires an authenticated admin user",
        )

    actor = await fetch_active_user_by_id(db, int(principal.user_id))
    if not actor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin reauthentication failed",
        )
    password_hash = actor.get("password_hash") if actor else None

    if len(normalized_password) >= 8 and isinstance(password_hash, str) and password_hash:
        verified, _needs_rehash = password_service.verify_password(normalized_password, password_hash)
        if not verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin reauthentication failed",
            )
        return normalized_reason

    if normalized_reauth_token:
        try:
            await _verify_admin_reauth_token(
                actor=actor,
                admin_reauth_token=normalized_reauth_token,
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin reauthentication failed",
            ) from exc
        return normalized_reason

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Reason and current password or admin reauthentication token are required for this action",
    )
