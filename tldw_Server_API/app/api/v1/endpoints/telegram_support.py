from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from fastapi import HTTPException, Request, status
from loguru import logger

from tldw_Server_API.app.api.v1.schemas.telegram_schemas import (
    TelegramBotConfigResponse,
    TelegramBotConfigUpdate,
)
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.AuthNZ.repos.org_provider_secrets_repo import (
    AuthnzOrgProviderSecretsRepo,
)
from tldw_Server_API.app.core.AuthNZ.user_provider_secrets import (
    decrypt_byok_payload,
    dumps_envelope,
    encrypt_byok_payload,
    key_hint_for_api_key,
    loads_envelope,
)

_PROVIDER = "telegram"
_DEFAULT_BOT_USERNAME = "example_bot"
_CREDENTIAL_VERSION = 1


@dataclass(frozen=True)
class TelegramScope:
    scope_type: str
    scope_id: int


def _coerce_nonempty_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _collect_scope_ids(values: list[int] | None, active_id: int | None) -> list[int]:
    out: set[int] = set()
    for raw in values or []:
        try:
            out.add(int(raw))
        except (TypeError, ValueError):
            continue
    if active_id is not None:
        try:
            out.add(int(active_id))
        except (TypeError, ValueError):
            pass
    return sorted(out)


def _normalize_bot_config_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    merged: dict[str, Any] = {
        "provider": _PROVIDER,
        "credential_version": _CREDENTIAL_VERSION,
        "bot_username": _DEFAULT_BOT_USERNAME,
        "enabled": False,
    }
    if isinstance(payload, dict):
        merged.update(payload)
    merged["bot_username"] = _coerce_nonempty_string(merged.get("bot_username")) or _DEFAULT_BOT_USERNAME
    merged["enabled"] = bool(merged.get("enabled"))
    return merged


def _public_bot_config_record(
    payload: dict[str, Any] | None,
    *,
    scope: TelegramScope,
) -> TelegramBotConfigResponse:
    normalized = _normalize_bot_config_payload(payload)
    return TelegramBotConfigResponse(
        scope_type=scope.scope_type,
        scope_id=scope.scope_id,
        bot_username=normalized["bot_username"],
        enabled=normalized["enabled"],
    )


async def _get_org_secret_repo() -> AuthnzOrgProviderSecretsRepo:
    pool = await get_db_pool()
    repo = AuthnzOrgProviderSecretsRepo(pool)
    await repo.ensure_tables()
    return repo


def _encrypt_telegram_payload(payload: dict[str, Any]) -> str:
    return dumps_envelope(encrypt_byok_payload(payload))


def _decrypt_telegram_payload(encrypted_blob: str | None) -> dict[str, Any] | None:
    if not encrypted_blob:
        return None
    try:
        payload = decrypt_byok_payload(loads_envelope(encrypted_blob))
    except Exception as exc:
        logger.warning("Failed to decrypt Telegram bot config payload: {}", exc)
        return None
    return payload if isinstance(payload, dict) else None


def _resolve_shared_scope(
    *,
    principal: AuthPrincipal,
    request: Request | None = None,
) -> TelegramScope:
    request_active_team_id = _coerce_int(getattr(request.state, "active_team_id", None)) if request else None
    request_active_org_id = _coerce_int(getattr(request.state, "active_org_id", None)) if request else None

    active_team_id = _coerce_int(principal.active_team_id)
    if active_team_id is None:
        active_team_id = request_active_team_id
    active_org_id = _coerce_int(principal.active_org_id)
    if active_org_id is None:
        active_org_id = request_active_org_id

    team_ids = _collect_scope_ids(principal.team_ids, active_team_id)
    org_ids = _collect_scope_ids(principal.org_ids, active_org_id)

    if active_team_id is not None:
        if active_team_id not in team_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An active org/team scope is required",
            )
        return TelegramScope(scope_type="team", scope_id=active_team_id)

    if active_org_id is not None:
        if active_org_id not in org_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An active org/team scope is required",
            )
        return TelegramScope(scope_type="org", scope_id=active_org_id)

    visible_scopes: list[TelegramScope] = [TelegramScope("team", team_id) for team_id in team_ids]
    visible_scopes.extend(TelegramScope("org", org_id) for org_id in org_ids)
    if len(visible_scopes) == 1:
        return visible_scopes[0]

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="An active org/team scope is required",
    )


async def telegram_admin_put_bot_impl(
    *,
    principal: AuthPrincipal,
    payload: TelegramBotConfigUpdate,
    request: Request | None = None,
    get_org_secret_repo: Callable[[], Awaitable[Any]] = _get_org_secret_repo,
    encrypt_telegram_payload: Callable[[dict[str, Any]], str] = _encrypt_telegram_payload,
) -> TelegramBotConfigResponse:
    bot_token = _coerce_nonempty_string(payload.bot_token)
    webhook_secret = _coerce_nonempty_string(payload.webhook_secret)
    if not bot_token or not webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="bot_token and webhook_secret are required",
        )

    scope = _resolve_shared_scope(principal=principal, request=request)
    config_payload = _normalize_bot_config_payload(
        {
            "bot_token": bot_token,
            "webhook_secret": webhook_secret,
            "enabled": bool(payload.enabled),
        }
    )

    repo = await get_org_secret_repo()
    now = datetime.now(timezone.utc)
    await repo.upsert_secret(
        scope_type=scope.scope_type,
        scope_id=scope.scope_id,
        provider=_PROVIDER,
        encrypted_blob=encrypt_telegram_payload(config_payload),
        key_hint=key_hint_for_api_key(bot_token),
        metadata={
            "bot_username": config_payload["bot_username"],
            "enabled": config_payload["enabled"],
            "credential_version": _CREDENTIAL_VERSION,
        },
        updated_at=now,
        created_by=int(principal.user_id) if principal.user_id is not None else None,
        updated_by=int(principal.user_id) if principal.user_id is not None else None,
    )
    return _public_bot_config_record(config_payload, scope=scope)


async def telegram_admin_get_bot_impl(
    *,
    principal: AuthPrincipal,
    request: Request | None = None,
    get_org_secret_repo: Callable[[], Awaitable[Any]] = _get_org_secret_repo,
    decrypt_telegram_payload: Callable[[str | None], dict[str, Any] | None] = _decrypt_telegram_payload,
) -> TelegramBotConfigResponse:
    scope = _resolve_shared_scope(principal=principal, request=request)
    repo = await get_org_secret_repo()
    row = await repo.fetch_secret(scope.scope_type, scope.scope_id, _PROVIDER)
    payload = decrypt_telegram_payload(row.get("encrypted_blob")) if row else None
    return _public_bot_config_record(payload, scope=scope)
