from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from loguru import logger

from tldw_Server_API.app.api.v1.schemas.telegram_schemas import TelegramBotConfigUpdate
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.AuthNZ.repos.user_provider_secrets_repo import (
    AuthnzUserProviderSecretsRepo,
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


def _coerce_nonempty_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


async def _get_user_secret_repo() -> AuthnzUserProviderSecretsRepo:
    pool = await get_db_pool()
    repo = AuthnzUserProviderSecretsRepo(pool)
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


def _default_bot_config_payload() -> dict[str, Any]:
    return {
        "provider": _PROVIDER,
        "credential_version": _CREDENTIAL_VERSION,
        "bot_username": _DEFAULT_BOT_USERNAME,
        "enabled": False,
    }


def _normalize_bot_config_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    merged = _default_bot_config_payload()
    if isinstance(payload, dict):
        merged.update(payload)
    merged["bot_username"] = _coerce_nonempty_string(merged.get("bot_username")) or _DEFAULT_BOT_USERNAME
    merged["enabled"] = bool(merged.get("enabled"))
    return merged


def _public_bot_config_record(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_bot_config_payload(payload)
    return {
        "ok": True,
        "provider": _PROVIDER,
        "bot_username": normalized["bot_username"],
        "enabled": normalized["enabled"],
    }


async def telegram_admin_put_bot_impl(
    *,
    user: User,
    payload: TelegramBotConfigUpdate,
    get_user_secret_repo: Callable[[], Awaitable[Any]] = _get_user_secret_repo,
    encrypt_telegram_payload: Callable[[dict[str, Any]], str] = _encrypt_telegram_payload,
) -> dict[str, Any]:
    bot_token = _coerce_nonempty_string(payload.bot_token)
    webhook_secret = _coerce_nonempty_string(payload.webhook_secret)
    if not bot_token or not webhook_secret:
        raise ValueError("bot_token and webhook_secret are required")

    config_payload = _normalize_bot_config_payload(
        {
            "bot_token": bot_token,
            "webhook_secret": webhook_secret,
            "enabled": bool(payload.enabled),
        }
    )

    repo = await get_user_secret_repo()
    now = datetime.now(timezone.utc)
    await repo.upsert_secret(
        user_id=int(user.id),
        provider=_PROVIDER,
        encrypted_blob=encrypt_telegram_payload(config_payload),
        key_hint=key_hint_for_api_key(bot_token),
        metadata={
            "bot_username": config_payload["bot_username"],
            "enabled": config_payload["enabled"],
            "credential_version": _CREDENTIAL_VERSION,
        },
        updated_at=now,
        created_by=int(user.id),
        updated_by=int(user.id),
    )
    return _public_bot_config_record(config_payload)


async def telegram_admin_get_bot_impl(
    *,
    user: User,
    get_user_secret_repo: Callable[[], Awaitable[Any]] = _get_user_secret_repo,
    decrypt_telegram_payload: Callable[[str | None], dict[str, Any] | None] = _decrypt_telegram_payload,
) -> dict[str, Any]:
    repo = await get_user_secret_repo()
    row = await repo.fetch_secret_for_user(int(user.id), _PROVIDER)
    payload = decrypt_telegram_payload(row.get("encrypted_blob")) if row else None
    return _public_bot_config_record(payload)
