from __future__ import annotations

import inspect
import json
import secrets
import threading
import uuid
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
from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Telegram.session_mapper import (
    build_telegram_session_key,
    derive_telegram_assistant_conversation_id,
)
from tldw_Server_API.app.services.mcp_hub_approval_service import (
    _scope_key_for_tool_call,
    get_mcp_hub_approval_service,
)
from tldw_Server_API.app.services.telegram_delivery_service import TelegramDeliveryService

_PROVIDER = "telegram"
_DEFAULT_BOT_USERNAME = "example_bot"
_CREDENTIAL_VERSION = 1
_TELEGRAM_APPROVAL_CALLBACK_PREFIX = "tgapp1."
_TELEGRAM_APPROVAL_CALLBACK_MAX_LENGTH = 64
_TELEGRAM_PENDING_APPROVAL_TTL_SECONDS = 300
_WEBHOOK_REPLAY_WINDOW_SECONDS = 3600
_WEBHOOK_RECEIPTS = TTLReceiptStore()
_TELEGRAM_PENDING_APPROVAL_LOCK = threading.Lock()
_TELEGRAM_PENDING_APPROVALS: dict[str, dict[str, Any]] = {}
_TELEGRAM_LINK_LOCK = threading.Lock()
_TELEGRAM_PAIRING_CODES: dict[str, dict[str, Any]] = {}
_TELEGRAM_ACTOR_LINKS: dict[tuple[str, int, int], dict[str, Any]] = {}
_TELEGRAM_PAIRING_CODE_TTL_SECONDS = 900


@dataclass(frozen=True)
class TelegramScope:
    scope_type: str
    scope_id: int


@dataclass(frozen=True)
class TelegramWebhookContext:
    scope: TelegramScope
    bot_username: str


@dataclass(frozen=True)
class TelegramCommand:
    action: str
    input: str
    target_bot_username: str | None = None


@dataclass(frozen=True)
class TelegramMessagePolicy:
    should_process: bool
    reason: str | None = None
    command: TelegramCommand | None = None


_TELEGRAM_REQUEST_NAMESPACE = uuid.UUID("f3b8b11f-6a65-4a2a-a7fd-8f9d9cf3f3d4")


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


def _coerce_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def _prune_pending_telegram_approvals_locked(now: datetime) -> None:
    stale_tokens: list[str] = []
    for approval_token, record in _TELEGRAM_PENDING_APPROVALS.items():
        expires_at = _coerce_datetime(record.get("expires_at"))
        if expires_at is None or expires_at <= now:
            stale_tokens.append(approval_token)
    for approval_token in stale_tokens:
        _TELEGRAM_PENDING_APPROVALS.pop(approval_token, None)


def _store_pending_telegram_approval(
    *,
    approval_policy_id: int | None,
    context_key: str,
    conversation_id: str | None,
    tool_name: str,
    tool_args: Any,
    scope: TelegramScope,
    initiating_auth_user_id: int,
    expires_at: datetime | None = None,
    ttl_seconds: int = _TELEGRAM_PENDING_APPROVAL_TTL_SECONDS,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    expiry = _coerce_datetime(expires_at)
    if expiry is None:
        expiry = now + timedelta(seconds=max(1, int(ttl_seconds)))
    initiating_user_id = _coerce_int(initiating_auth_user_id)
    if initiating_user_id is None:
        raise ValueError("initiating_auth_user_id is required")
    scope_fingerprint = _scope_key_for_tool_call(tool_name, tool_args)
    with _TELEGRAM_PENDING_APPROVAL_LOCK:
        _prune_pending_telegram_approvals_locked(now)
        while True:
            approval_token = secrets.token_urlsafe(12)
            if approval_token not in _TELEGRAM_PENDING_APPROVALS:
                break
        record = {
            "approval_token": approval_token,
            "approval_policy_id": _coerce_int(approval_policy_id),
            "context_key": str(context_key).strip(),
            "conversation_id": _coerce_nonempty_string(conversation_id),
            "tool_name": str(tool_name).strip(),
            "scope_fingerprint": scope_fingerprint,
            "scope_type": scope.scope_type,
            "scope_id": scope.scope_id,
            "initiating_auth_user_id": initiating_user_id,
            "expires_at": expiry,
            "created_at": now,
            "reserved_at": None,
        }
        _TELEGRAM_PENDING_APPROVALS[approval_token] = record
        return dict(record)


def build_telegram_approval_callback_data(
    *,
    approval_policy_id: int | None,
    context_key: str,
    conversation_id: str | None,
    tool_name: str,
    tool_args: Any,
    scope: TelegramScope,
    initiating_auth_user_id: int,
    expires_at: datetime | None = None,
    ttl_seconds: int = _TELEGRAM_PENDING_APPROVAL_TTL_SECONDS,
) -> str:
    """Build short callback data and register the approval server-side."""
    record = _store_pending_telegram_approval(
        approval_policy_id=approval_policy_id,
        context_key=context_key,
        conversation_id=conversation_id,
        tool_name=tool_name,
        tool_args=tool_args,
        scope=scope,
        initiating_auth_user_id=initiating_auth_user_id,
        expires_at=expires_at,
        ttl_seconds=ttl_seconds,
    )
    callback_data = f"{_TELEGRAM_APPROVAL_CALLBACK_PREFIX}{record['approval_token']}"
    if len(callback_data) > _TELEGRAM_APPROVAL_CALLBACK_MAX_LENGTH:
        raise ValueError("Telegram approval callback_data exceeds Telegram limits")
    return callback_data


def _parse_telegram_approval_callback_data(callback_data: Any) -> dict[str, Any] | None:
    text = _coerce_nonempty_string(callback_data)
    if not text or not text.startswith(_TELEGRAM_APPROVAL_CALLBACK_PREFIX):
        return None
    approval_token = text[len(_TELEGRAM_APPROVAL_CALLBACK_PREFIX) :]
    if not approval_token:
        return None
    return {"approval_token": approval_token}


def _peek_pending_telegram_approval(approval_token: str, *, now: datetime | None = None) -> dict[str, Any] | None:
    current = now or datetime.now(timezone.utc)
    with _TELEGRAM_PENDING_APPROVAL_LOCK:
        _prune_pending_telegram_approvals_locked(current)
        record = _TELEGRAM_PENDING_APPROVALS.get(str(approval_token).strip())
        return dict(record) if record else None


def _reserve_pending_telegram_approval(approval_token: str, *, now: datetime | None = None) -> dict[str, Any] | None:
    current = now or datetime.now(timezone.utc)
    token = str(approval_token).strip()
    with _TELEGRAM_PENDING_APPROVAL_LOCK:
        _prune_pending_telegram_approvals_locked(current)
        record = _TELEGRAM_PENDING_APPROVALS.get(token)
        if not record:
            return None
        if record.get("reserved_at") is not None:
            return None
        record["reserved_at"] = current
        return dict(record)


def _release_pending_telegram_approval(approval_token: str) -> None:
    token = str(approval_token).strip()
    with _TELEGRAM_PENDING_APPROVAL_LOCK:
        record = _TELEGRAM_PENDING_APPROVALS.get(token)
        if not record:
            return
        record["reserved_at"] = None


def _consume_pending_telegram_approval(approval_token: str) -> None:
    token = str(approval_token).strip()
    with _TELEGRAM_PENDING_APPROVAL_LOCK:
        _TELEGRAM_PENDING_APPROVALS.pop(token, None)


def _peek_pending_telegram_approval_for_tests(callback_data: Any) -> dict[str, Any] | None:
    parsed = _parse_telegram_approval_callback_data(callback_data)
    if parsed is None:
        return None
    return _peek_pending_telegram_approval(parsed["approval_token"])


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


def _normalize_telegram_bot_username(value: Any) -> str | None:
    username = _coerce_nonempty_string(value)
    if not username:
        return None
    if username.startswith("@"):
        username = username[1:]
    username = username.strip().lower()
    return username or None


def _command_targets_configured_bot(
    command: TelegramCommand | None,
    configured_bot_username: Any,
) -> bool:
    if command is None:
        return False
    if command.target_bot_username is None:
        return True
    normalized_bot_username = _normalize_telegram_bot_username(configured_bot_username)
    if normalized_bot_username is None:
        return False
    return command.target_bot_username == normalized_bot_username


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
    action_token, target_username = (command_token.split("@", 1) + [None])[:2]
    action = action_token.strip().lower()
    if not action:
        return None
    argument = _coerce_nonempty_string(parts[1]) if len(parts) > 1 else ""
    return TelegramCommand(
        action=action,
        input=argument or "",
        target_bot_username=_normalize_telegram_bot_username(target_username),
    )


def evaluate_telegram_message_policy(
    *,
    chat_type: Any,
    text: Any,
    bot_username: Any = None,
    reply_to_bot: bool = False,
) -> TelegramMessagePolicy:
    command = parse_telegram_command(text)
    if command is not None and not _command_targets_configured_bot(command, bot_username):
        return TelegramMessagePolicy(
            should_process=False,
            reason="command_not_for_configured_bot",
            command=command,
        )
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


def _extract_message_chat_id(payload: dict[str, Any]) -> int | None:
    message = payload.get("message")
    if not isinstance(message, dict):
        return None
    chat = message.get("chat")
    if not isinstance(chat, dict):
        return None
    return _coerce_int(chat.get("id"))


def _extract_message_thread_id(payload: dict[str, Any]) -> int | None:
    message = payload.get("message")
    if not isinstance(message, dict):
        return None
    return _coerce_int(message.get("message_thread_id"))


def _extract_message_id(payload: dict[str, Any]) -> int | None:
    message = payload.get("message")
    if not isinstance(message, dict):
        return None
    return _coerce_int(message.get("message_id"))


def _message_reply_to_bot(
    payload: dict[str, Any],
    *,
    configured_bot_username: Any = None,
) -> bool:
    message = payload.get("message")
    if not isinstance(message, dict):
        return False
    reply_to_message = message.get("reply_to_message")
    if not isinstance(reply_to_message, dict):
        return False
    reply_from = reply_to_message.get("from")
    if not isinstance(reply_from, dict):
        return False
    if not bool(reply_from.get("is_bot")):
        return False
    reply_username = _normalize_telegram_bot_username(reply_from.get("username"))
    configured_username = _normalize_telegram_bot_username(configured_bot_username)
    if reply_username is None or configured_username is None:
        return False
    return reply_username == configured_username


def _build_telegram_tenant_id(scope: TelegramScope) -> str:
    return f"{scope.scope_type}:{scope.scope_id}"


def _build_telegram_request_id(scope: TelegramScope, update_id: int) -> str:
    return str(uuid.uuid5(_TELEGRAM_REQUEST_NAMESPACE, f"{scope.scope_type}:{scope.scope_id}:{update_id}"))


def _build_telegram_ask_job_payload(
    *,
    scope: TelegramScope,
    update_id: int,
    message_id: int | None,
    telegram_user_id: int,
    text: str,
    chat_type: str | None,
    reply_to_bot: bool,
    configured_bot_username: str,
    command: TelegramCommand,
    linked_actor: dict[str, Any],
    telegram_chat_id: int | None,
    telegram_thread_id: int | None,
    request_id: str,
) -> dict[str, Any]:
    tenant_id = _build_telegram_tenant_id(scope)
    session_key = build_telegram_session_key(
        tenant_id=tenant_id,
        chat_type=chat_type or "private",
        telegram_user_id=telegram_user_id,
        telegram_chat_id=telegram_chat_id,
        topic_or_thread_id=telegram_thread_id,
    )
    return {
        "telegram": {
            "scope_type": scope.scope_type,
            "scope_id": scope.scope_id,
            "update_id": update_id,
            "message_id": message_id,
            "chat_type": chat_type,
            "telegram_user_id": telegram_user_id,
            "telegram_chat_id": telegram_chat_id,
            "topic_or_thread_id": telegram_thread_id,
            "text": text,
            "reply_to_bot": reply_to_bot,
            "bot_username": configured_bot_username,
            "command": {
                "action": command.action,
                "input": command.input,
                "target_bot_username": command.target_bot_username,
            },
            "linked_actor": {
                "auth_user_id": str(linked_actor["auth_user_id"]),
                "telegram_user_id": telegram_user_id,
            },
        },
        "session": {
            "tenant_id": tenant_id,
            "session_key": session_key,
            "assistant_conversation_id": derive_telegram_assistant_conversation_id(session_key),
        },
        "request_id": request_id,
    }


async def _resolve_job_manager_for_request(request: Request) -> JobManager:
    from tldw_Server_API.app.api.v1.API_Deps.jobs_deps import get_job_manager

    resolver = get_job_manager
    app = getattr(request, "app", None)
    dependency_overrides = getattr(app, "dependency_overrides", None)
    if isinstance(dependency_overrides, dict):
        override = dependency_overrides.get(get_job_manager)
        if override is not None:
            resolver = override

    resolved = resolver()
    if inspect.isawaitable(resolved):
        resolved = await resolved
    return resolved


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


def _extract_callback_query(payload: dict[str, Any]) -> dict[str, Any] | None:
    callback_query = payload.get("callback_query")
    return callback_query if isinstance(callback_query, dict) else None


def _extract_callback_query_actor_id(payload: dict[str, Any]) -> int | None:
    callback_query = _extract_callback_query(payload)
    if callback_query is None:
        return None
    from_block = callback_query.get("from")
    if not isinstance(from_block, dict):
        return None
    return _coerce_int(from_block.get("id"))


def _extract_callback_query_data(payload: dict[str, Any]) -> str | None:
    callback_query = _extract_callback_query(payload)
    if callback_query is None:
        return None
    return _coerce_nonempty_string(callback_query.get("data"))


async def _handle_telegram_approval_callback_query(
    *,
    scope: TelegramScope,
    payload: dict[str, Any],
    get_approval_service: Callable[[], Awaitable[Any]],
) -> JSONResponse:
    callback_data = _extract_callback_query_data(payload)
    parsed_callback = _parse_telegram_approval_callback_data(callback_data)
    if parsed_callback is None:
        return _telegram_webhook_error(status.HTTP_400_BAD_REQUEST, "invalid_payload")

    now = datetime.now(timezone.utc)
    pending_approval = _reserve_pending_telegram_approval(
        parsed_callback["approval_token"],
        now=now,
    )
    if pending_approval is None:
        return _telegram_webhook_error(status.HTTP_409_CONFLICT, "approval_unavailable")

    should_release = True
    telegram_user_id = _extract_callback_query_actor_id(payload)
    if telegram_user_id is None:
        return _telegram_webhook_error(status.HTTP_400_BAD_REQUEST, "invalid_payload")

    try:
        if (
            pending_approval.get("scope_type") != scope.scope_type
            or _coerce_int(pending_approval.get("scope_id")) != scope.scope_id
        ):
            return _telegram_webhook_error(status.HTTP_409_CONFLICT, "approval_unavailable")

        linked_actor = _resolve_telegram_actor_link(scope, telegram_user_id)
        if linked_actor is None:
            return _telegram_webhook_error(status.HTTP_403_FORBIDDEN, "account_link_required")

        linked_auth_user_id = _coerce_int(linked_actor.get("auth_user_id"))
        initiating_auth_user_id = _coerce_int(pending_approval.get("initiating_auth_user_id"))
        if (
            linked_auth_user_id is None
            or initiating_auth_user_id is None
            or linked_auth_user_id != initiating_auth_user_id
        ):
            return _telegram_webhook_error(status.HTTP_403_FORBIDDEN, "approval_not_authorized")

        try:
            approval_service = await get_approval_service()
        except Exception as exc:
            logger.error("Failed to resolve Telegram approval service: {}", exc)
            return _telegram_webhook_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "approval_service_unavailable",
            )

        if not hasattr(approval_service, "record_decision"):
            return _telegram_webhook_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "approval_service_unavailable",
            )

        decision = await approval_service.record_decision(
            approval_policy_id=_coerce_int(pending_approval.get("approval_policy_id")),
            context_key=str(pending_approval.get("context_key") or ""),
            conversation_id=_coerce_nonempty_string(pending_approval.get("conversation_id")),
            tool_name=str(pending_approval.get("tool_name") or ""),
            scope_key=str(pending_approval.get("scope_fingerprint") or ""),
            decision="approved",
            consume_on_match=True,
            expires_at=_coerce_datetime(pending_approval.get("expires_at")),
            actor_id=linked_auth_user_id,
        )
        should_release = False
        _consume_pending_telegram_approval(parsed_callback["approval_token"])
        return JSONResponse(
            status_code=200,
            content={
                "ok": True,
                "status": "approved",
                "approval_decision_id": decision.get("id") if isinstance(decision, dict) else None,
                "approval_policy_id": pending_approval.get("approval_policy_id"),
                "scope_key": pending_approval.get("scope_fingerprint"),
            },
        )
    except Exception as exc:
        logger.error("Failed to persist Telegram approval decision: {}", exc)
        return _telegram_webhook_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "approval_service_unavailable",
        )
    finally:
        if should_release:
            _release_pending_telegram_approval(parsed_callback["approval_token"])


def _reset_telegram_webhook_state_for_tests() -> None:
    """Reset webhook dedupe receipts for deterministic tests."""
    _WEBHOOK_RECEIPTS.clear()


def _reset_telegram_approval_state_for_tests() -> None:
    """Reset Telegram approval callback state for deterministic tests."""
    with _TELEGRAM_PENDING_APPROVAL_LOCK:
        _TELEGRAM_PENDING_APPROVALS.clear()


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
) -> TelegramWebhookContext | None:
    try:
        rows = await repo.list_secrets(provider=_PROVIDER)
    except Exception as exc:
        logger.error("Failed to list Telegram bot configs for webhook resolution: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram bot configuration is unavailable",
        ) from exc

    matches: list[TelegramWebhookContext] = []
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
        matches.append(
            TelegramWebhookContext(
                scope=TelegramScope(scope_type=scope_type, scope_id=scope_id),
                bot_username=_normalize_telegram_bot_username(payload.get("bot_username"))
                or _DEFAULT_BOT_USERNAME,
            )
        )
        if len(matches) > 1:
            logger.warning("Ambiguous Telegram webhook secret matched multiple scopes; rejecting request")
            return None

    return matches[0] if matches else None


async def telegram_webhook_impl(
    *,
    request: Request,
    job_manager: JobManager | None = None,
    get_org_secret_repo: Callable[[], Awaitable[Any]] = _get_org_secret_repo,
    get_approval_service: Callable[[], Awaitable[Any]] = get_mcp_hub_approval_service,
    dedupe_receipts: TTLReceiptStore = _WEBHOOK_RECEIPTS,
    dedupe_ttl_seconds: int = _WEBHOOK_REPLAY_WINDOW_SECONDS,
) -> JSONResponse:
    webhook_secret = _coerce_valid_webhook_secret_header(request)
    if not webhook_secret:
        return _telegram_webhook_error(status.HTTP_401_UNAUTHORIZED, "invalid_secret")

    repo = await get_org_secret_repo()
    webhook_context = await _resolve_webhook_scope_from_secret(
        repo=repo,
        webhook_secret=webhook_secret,
    )
    if webhook_context is None:
        return _telegram_webhook_error(status.HTTP_401_UNAUTHORIZED, "invalid_secret")
    scope = webhook_context.scope
    configured_bot_username = webhook_context.bot_username

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

    dedupe_key = f"{scope.scope_type}:{scope.scope_id}:{update_id_int}"
    if dedupe_receipts.seen_or_store(dedupe_key, dedupe_ttl_seconds):
        return JSONResponse(status_code=200, content={"ok": True, "status": "duplicate"})

    callback_query = _extract_callback_query(payload)
    if callback_query is not None:
        return await _handle_telegram_approval_callback_query(
            scope=scope,
            payload=payload,
            get_approval_service=get_approval_service,
        )

    telegram_user_id, text = _extract_message_actor_and_text(payload)
    chat_type = _extract_message_chat_type(payload)
    telegram_chat_id = _extract_message_chat_id(payload)
    telegram_thread_id = _extract_message_thread_id(payload)
    message_id = _extract_message_id(payload)
    reply_to_bot = _message_reply_to_bot(payload, configured_bot_username=configured_bot_username)
    message_policy = evaluate_telegram_message_policy(
        chat_type=chat_type,
        text=text,
        bot_username=configured_bot_username,
        reply_to_bot=reply_to_bot,
    )
    if not message_policy.should_process:
        return JSONResponse(status_code=200, content={"ok": True, "status": "ignored"})

    linked_actor = _resolve_telegram_actor_link(scope, telegram_user_id) if telegram_user_id is not None else None

    if _is_privileged_telegram_command(message_policy.command):
        if linked_actor is None:
            return _telegram_webhook_error(status.HTTP_403_FORBIDDEN, "account_link_required")

    if message_policy.command is not None and message_policy.command.action == "ask" and linked_actor is not None:
        if job_manager is None:
            job_manager = await _resolve_job_manager_for_request(request)
        request_id = _build_telegram_request_id(scope, update_id_int)
        payload = _build_telegram_ask_job_payload(
            scope=scope,
            update_id=update_id_int,
            message_id=message_id,
            telegram_user_id=telegram_user_id,
            text=text or "",
            chat_type=chat_type,
            reply_to_bot=reply_to_bot,
            configured_bot_username=configured_bot_username,
            command=message_policy.command,
            linked_actor=linked_actor,
            telegram_chat_id=telegram_chat_id,
            telegram_thread_id=telegram_thread_id,
            request_id=request_id,
        )
        queued_job = TelegramDeliveryService(job_manager).queue_inbound_ask(
            owner_user_id=str(linked_actor["auth_user_id"]),
            request_id=request_id,
            payload=payload,
        )
        return JSONResponse(
            status_code=200,
            content={
                "ok": True,
                "status": "queued",
                "request_id": request_id,
                "job_id": queued_job.get("id"),
            },
        )

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
