from __future__ import annotations

import json
import secrets
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from loguru import logger

from tldw_Server_API.app.api.v1.endpoints._in_memory_limits import TTLReceiptStore
from tldw_Server_API.app.api.v1.schemas.telegram_schemas import (
    TelegramBotConfigResponse,
    TelegramBotConfigUpdate,
    TELEGRAM_WEBHOOK_SECRET_MIN_LENGTH,
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
_WEBHOOK_REPLAY_WINDOW_SECONDS = 3600
_WEBHOOK_RECEIPTS = TTLReceiptStore()
_TELEGRAM_LINK_LOCK = threading.Lock()
_TELEGRAM_PAIRING_CODES: dict[str, dict[str, Any]] = {}
_TELEGRAM_ACTOR_LINKS: dict[tuple[str, int, int], dict[str, Any]] = {}
_TELEGRAM_PAIRING_CODE_TTL_SECONDS = 900


@dataclass(frozen=True)
class TelegramScope:
    scope_type: str
    scope_id: int


@dataclass(frozen=True)
class TelegramCommand:
    action: str
    input: str


@dataclass(frozen=True)
class TelegramMessagePolicy:
    should_process: bool
    reason: str | None = None
    command: TelegramCommand | None = None


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


def _collect_scope_ids(values: list[int] | None) -> list[int]:
    out: set[int] = set()
    for raw in values or []:
        try:
            out.add(int(raw))
        except (TypeError, ValueError):
            continue
    return sorted(out)


def _telegram_actor_link_key(scope: TelegramScope, telegram_user_id: int) -> tuple[str, int, int]:
    return (scope.scope_type, scope.scope_id, telegram_user_id)


def _generate_telegram_pairing_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(8))


def _store_telegram_pairing_code(
    *,
    scope: TelegramScope,
    auth_user_id: int | None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    with _TELEGRAM_LINK_LOCK:
        while True:
            code = _generate_telegram_pairing_code()
            if code in _TELEGRAM_PAIRING_CODES:
                continue
            record = {
                "pairing_code": code,
                "scope_type": scope.scope_type,
                "scope_id": scope.scope_id,
                "auth_user_id": auth_user_id,
                "created_at": now,
                "expires_at": now + timedelta(seconds=_TELEGRAM_PAIRING_CODE_TTL_SECONDS),
            }
            _TELEGRAM_PAIRING_CODES[code] = record
            return record


def _register_telegram_actor_link_for_tests(
    *,
    scope_type: str,
    scope_id: int,
    telegram_user_id: int,
    auth_user_id: int,
    telegram_username: str | None = None,
) -> None:
    """Install a deterministic in-memory actor link for tests."""
    record = {
        "scope_type": scope_type,
        "scope_id": scope_id,
        "telegram_user_id": telegram_user_id,
        "auth_user_id": auth_user_id,
        "telegram_username": telegram_username,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    with _TELEGRAM_LINK_LOCK:
        _TELEGRAM_ACTOR_LINKS[(scope_type, scope_id, telegram_user_id)] = record


def _resolve_telegram_actor_link(scope: TelegramScope, telegram_user_id: int) -> dict[str, Any] | None:
    with _TELEGRAM_LINK_LOCK:
        link = _TELEGRAM_ACTOR_LINKS.get(_telegram_actor_link_key(scope, telegram_user_id))
        return dict(link) if link else None


def parse_telegram_command(text: Any) -> TelegramCommand | None:
    normalized = _coerce_nonempty_string(text)
    if not normalized:
        return None
    if not normalized.startswith("/"):
        return None

    parts = normalized.split(maxsplit=1)
    command_token = parts[0][1:]
    if not command_token:
        return None
    action = command_token.split("@", 1)[0].strip().lower()
    if not action:
        return None
    argument = _coerce_nonempty_string(parts[1]) if len(parts) > 1 else ""
    return TelegramCommand(action=action, input=argument or "")


def evaluate_telegram_message_policy(
    *,
    chat_type: Any,
    text: Any,
    reply_to_bot: bool = False,
) -> TelegramMessagePolicy:
    command = parse_telegram_command(text)
    if command is not None:
        return TelegramMessagePolicy(should_process=True, command=command)

    normalized_chat_type = _coerce_nonempty_string(chat_type)
    if normalized_chat_type in {"group", "supergroup"} and not reply_to_bot:
        return TelegramMessagePolicy(
            should_process=False,
            reason="group_freeform_requires_command_or_reply",
        )

    return TelegramMessagePolicy(should_process=True)


def _is_privileged_telegram_command(command: TelegramCommand | None) -> bool:
    if command is None:
        return False
    if command.action not in {"persona", "character"}:
        return False
    tokens = command.input.lower().split()
    if not tokens:
        return False
    return tokens[0] == "set"


def _extract_message_actor_and_text(payload: dict[str, Any]) -> tuple[int | None, str | None]:
    message = payload.get("message")
    if not isinstance(message, dict):
        return None, None
    from_block = message.get("from")
    telegram_user_id = _coerce_int(from_block.get("id")) if isinstance(from_block, dict) else None
    text = _coerce_nonempty_string(message.get("text"))
    return telegram_user_id, text


def _extract_message_chat_type(payload: dict[str, Any]) -> str | None:
    message = payload.get("message")
    if not isinstance(message, dict):
        return None
    chat = message.get("chat")
    if not isinstance(chat, dict):
        return None
    return _coerce_nonempty_string(chat.get("type"))


def _message_reply_to_bot(payload: dict[str, Any]) -> bool:
    message = payload.get("message")
    if not isinstance(message, dict):
        return False
    reply_to_message = message.get("reply_to_message")
    if not isinstance(reply_to_message, dict):
        return False
    reply_from = reply_to_message.get("from")
    if not isinstance(reply_from, dict):
        return False
    return bool(reply_from.get("is_bot"))


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

    team_ids = _collect_scope_ids(principal.team_ids)
    org_ids = _collect_scope_ids(principal.org_ids)

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


def _reset_telegram_webhook_state_for_tests() -> None:
    """Reset webhook dedupe receipts for deterministic tests."""
    _WEBHOOK_RECEIPTS.clear()


def _reset_telegram_link_state_for_tests() -> None:
    """Reset Telegram pairing/link state for deterministic tests."""
    with _TELEGRAM_LINK_LOCK:
        _TELEGRAM_PAIRING_CODES.clear()
        _TELEGRAM_ACTOR_LINKS.clear()


def _telegram_webhook_error(
    status_code: int,
    error: str,
    *,
    detail: str | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "ok": False,
            "error": error,
            **({"detail": detail} if detail else {}),
        },
    )


def _coerce_valid_webhook_secret_header(request: Request) -> str | None:
    webhook_secret = _coerce_nonempty_string(
        request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    )
    if not webhook_secret:
        return None
    if len(webhook_secret) < TELEGRAM_WEBHOOK_SECRET_MIN_LENGTH:
        return None
    return webhook_secret


async def _resolve_webhook_scope_from_secret(
    *,
    repo: AuthnzOrgProviderSecretsRepo,
    webhook_secret: str,
) -> TelegramScope | None:
    try:
        rows = await repo.list_secrets(provider=_PROVIDER)
    except Exception as exc:
        logger.error("Failed to list Telegram bot configs for webhook resolution: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram bot configuration is unavailable",
        ) from exc

    matches: list[TelegramScope] = []
    for row in rows:
        scope_type = str(row.get("scope_type") or "").strip().lower()
        scope_id = _coerce_int(row.get("scope_id"))
        if scope_type not in {"org", "team"} or scope_id is None:
            continue
        try:
            secret_row = await repo.fetch_secret(scope_type, scope_id, _PROVIDER)
        except Exception as exc:
            logger.error(
                "Failed to load Telegram bot config for webhook resolution at {}:{}: {}",
                scope_type,
                scope_id,
                exc,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Telegram bot configuration is unavailable",
            ) from exc
        if not secret_row:
            continue
        payload = _decrypt_telegram_payload(secret_row.get("encrypted_blob"))
        if not isinstance(payload, dict):
            continue
        stored_secret = _coerce_nonempty_string(payload.get("webhook_secret"))
        if not stored_secret or not secrets.compare_digest(stored_secret, webhook_secret):
            continue
        if not bool(payload.get("enabled")):
            continue
        matches.append(TelegramScope(scope_type=scope_type, scope_id=scope_id))
        if len(matches) > 1:
            logger.warning("Ambiguous Telegram webhook secret matched multiple scopes; rejecting request")
            return None

    return matches[0] if matches else None


async def telegram_webhook_impl(
    *,
    request: Request,
    get_org_secret_repo: Callable[[], Awaitable[Any]] = _get_org_secret_repo,
    dedupe_receipts: TTLReceiptStore = _WEBHOOK_RECEIPTS,
    dedupe_ttl_seconds: int = _WEBHOOK_REPLAY_WINDOW_SECONDS,
) -> JSONResponse:
    webhook_secret = _coerce_valid_webhook_secret_header(request)
    if not webhook_secret:
        return _telegram_webhook_error(status.HTTP_401_UNAUTHORIZED, "invalid_secret")

    repo = await get_org_secret_repo()
    scope = await _resolve_webhook_scope_from_secret(
        repo=repo,
        webhook_secret=webhook_secret,
    )
    if scope is None:
        return _telegram_webhook_error(status.HTTP_401_UNAUTHORIZED, "invalid_secret")

    raw_body = await request.body()
    try:
        payload = json.loads(raw_body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _telegram_webhook_error(status.HTTP_400_BAD_REQUEST, "invalid_json")

    if not isinstance(payload, dict):
        return _telegram_webhook_error(status.HTTP_400_BAD_REQUEST, "invalid_payload")

    update_id = payload.get("update_id")
    if not isinstance(update_id, int) or isinstance(update_id, bool):
        return _telegram_webhook_error(
            status.HTTP_400_BAD_REQUEST,
            "invalid_payload",
            detail="update_id is required",
        )
    update_id_int = update_id

    telegram_user_id, text = _extract_message_actor_and_text(payload)
    chat_type = _extract_message_chat_type(payload)
    reply_to_bot = _message_reply_to_bot(payload)
    message_policy = evaluate_telegram_message_policy(
        chat_type=chat_type,
        text=text,
        reply_to_bot=reply_to_bot,
    )
    if not message_policy.should_process:
        return JSONResponse(status_code=200, content={"ok": True, "status": "ignored"})

    dedupe_key = f"{scope.scope_type}:{scope.scope_id}:{update_id_int}"
    if dedupe_receipts.seen_or_store(dedupe_key, dedupe_ttl_seconds):
        return JSONResponse(status_code=200, content={"ok": True, "status": "duplicate"})

    if _is_privileged_telegram_command(message_policy.command):
        if telegram_user_id is None or _resolve_telegram_actor_link(scope, telegram_user_id) is None:
            return _telegram_webhook_error(status.HTTP_403_FORBIDDEN, "account_link_required")

    return JSONResponse(status_code=200, content={"ok": True, "status": "accepted"})


async def telegram_admin_start_link_impl(
    *,
    principal: AuthPrincipal,
    request: Request | None = None,
) -> dict[str, Any]:
    scope = _resolve_shared_scope(principal=principal, request=request)
    record = _store_telegram_pairing_code(
        scope=scope,
        auth_user_id=int(principal.user_id) if principal.user_id is not None else None,
    )
    return {
        "ok": True,
        "pairing_code": record["pairing_code"],
        "scope_type": record["scope_type"],
        "scope_id": record["scope_id"],
        "expires_at": record["expires_at"].isoformat(),
    }


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
