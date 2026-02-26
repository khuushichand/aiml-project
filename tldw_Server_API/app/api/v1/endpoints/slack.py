from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from collections import deque
from urllib.parse import parse_qs, urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import require_roles
from tldw_Server_API.app.api.v1.API_Deps.jobs_deps import get_job_manager as _global_get_job_manager
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.AuthNZ.repos.byok_oauth_state_repo import AuthnzByokOAuthStateRepo
from tldw_Server_API.app.core.AuthNZ.repos.user_provider_secrets_repo import AuthnzUserProviderSecretsRepo
from tldw_Server_API.app.core.AuthNZ.user_provider_secrets import (
    decrypt_byok_payload,
    dumps_envelope,
    encrypt_byok_payload,
    key_hint_for_api_key,
    loads_envelope,
)
from tldw_Server_API.app.core.http_client import RetryPolicy as _RetryPolicy
from tldw_Server_API.app.core.http_client import afetch as _http_afetch
from tldw_Server_API.app.core.Metrics.metrics_logger import log_counter

router = APIRouter(prefix="/slack", tags=["slack"])


class _TTLReceiptStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._seen: dict[str, float] = {}

    def clear(self) -> None:
        with self._lock:
            self._seen.clear()

    def seen_or_store(self, key: str, ttl_seconds: int, now: float | None = None) -> bool:
        ts = now if now is not None else time.time()
        expiry = ts + max(1, ttl_seconds)
        with self._lock:
            self._cleanup_locked(ts)
            existing = self._seen.get(key)
            if existing and existing > ts:
                return True
            self._seen[key] = expiry
            return False

    def _cleanup_locked(self, now: float) -> None:
        stale_keys = [k for k, expires_at in self._seen.items() if expires_at <= now]
        for k in stale_keys:
            self._seen.pop(k, None)


class _SlidingWindowLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._windows: dict[str, deque[float]] = {}

    def clear(self) -> None:
        with self._lock:
            self._windows.clear()

    def allow(self, key: str, limit_per_minute: int, now: float | None = None) -> tuple[bool, int]:
        ts = now if now is not None else time.time()
        limit = max(1, limit_per_minute)
        cutoff = ts - 60.0

        with self._lock:
            window = self._windows.setdefault(key, deque())
            while window and window[0] <= cutoff:
                window.popleft()
            if len(window) >= limit:
                retry_after = int(max(1, 60 - (ts - window[0])))
                return False, retry_after
            window.append(ts)
            return True, 0


_EVENT_RECEIPTS = _TTLReceiptStore()
_COMMAND_RECEIPTS = _TTLReceiptStore()
_RATE_LIMITER = _SlidingWindowLimiter()
_POLICY_RATE_LIMITER = _SlidingWindowLimiter()
_SLACK_POLICY_LOCK = threading.Lock()
_SLACK_POLICIES: dict[str, dict[str, Any]] = {}
_POLICY_DEFAULT_KEY = "__default__"


def _reset_slack_state_for_tests() -> None:
    _EVENT_RECEIPTS.clear()
    _COMMAND_RECEIPTS.clear()
    _RATE_LIMITER.clear()
    _POLICY_RATE_LIMITER.clear()
    with _SLACK_POLICY_LOCK:
        _SLACK_POLICIES.clear()


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _signing_secret() -> str:
    return (os.getenv("SLACK_SIGNING_SECRET") or "").strip()


def _replay_window_seconds() -> int:
    return _env_int("SLACK_REPLAY_WINDOW_SECONDS", 300)


def _dedupe_ttl_seconds() -> int:
    return _env_int("SLACK_DEDUPE_TTL_SECONDS", 3600)


def _ingress_rate_limit_per_minute() -> int:
    return _env_int("SLACK_INGRESS_RATE_LIMIT_PER_MINUTE", 120)


def _policy_workspace_quota_per_minute() -> int:
    return _env_int("SLACK_POLICY_WORKSPACE_QUOTA_PER_MINUTE", 120)


def _policy_user_quota_per_minute() -> int:
    return _env_int("SLACK_POLICY_USER_QUOTA_PER_MINUTE", 60)


def _coerce_nonempty_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


def _oauth_client_id() -> str:
    return (os.getenv("SLACK_CLIENT_ID") or "").strip()


def _oauth_client_secret() -> str:
    return (os.getenv("SLACK_CLIENT_SECRET") or "").strip()


def _oauth_redirect_uri() -> str:
    redirect_uri = _coerce_nonempty_string(os.getenv("SLACK_OAUTH_REDIRECT_URI"))
    if not redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="SLACK_OAUTH_REDIRECT_URI is not configured",
        )
    return redirect_uri


def _oauth_auth_url() -> str:
    return _coerce_nonempty_string(os.getenv("SLACK_OAUTH_AUTH_URL")) or "https://slack.com/oauth/v2/authorize"


def _oauth_token_url() -> str:
    return _coerce_nonempty_string(os.getenv("SLACK_OAUTH_TOKEN_URL")) or "https://slack.com/api/oauth.v2.access"


def _oauth_state_ttl_seconds() -> int:
    return _env_int("SLACK_OAUTH_STATE_TTL_SECONDS", 600)


def _oauth_scopes() -> str:
    raw = _coerce_nonempty_string(os.getenv("SLACK_OAUTH_SCOPES")) or "commands,chat:write"
    scopes: list[str] = []
    for part in raw.replace(" ", ",").split(","):
        cleaned = part.strip()
        if cleaned and cleaned not in scopes:
            scopes.append(cleaned)
    return ",".join(scopes)


def _get_job_manager() -> Any:
    return _global_get_job_manager()


async def _close_http_response(response: Any) -> None:
    close_async = getattr(response, "aclose", None)
    if callable(close_async):
        await close_async()
        return
    close_sync = getattr(response, "close", None)
    if callable(close_sync):
        close_sync()


async def _get_oauth_state_repo() -> AuthnzByokOAuthStateRepo:
    pool = await get_db_pool()
    repo = AuthnzByokOAuthStateRepo(pool)
    await repo.ensure_tables()
    return repo


async def _get_user_secret_repo() -> AuthnzUserProviderSecretsRepo:
    pool = await get_db_pool()
    repo = AuthnzUserProviderSecretsRepo(pool)
    await repo.ensure_tables()
    return repo


def _encrypt_slack_payload(payload: dict[str, Any]) -> str:
    return dumps_envelope(encrypt_byok_payload(payload))


def _decrypt_slack_payload(encrypted_blob: str) -> dict[str, Any] | None:
    if not encrypted_blob:
        return None
    try:
        payload = decrypt_byok_payload(loads_envelope(encrypted_blob))
    except Exception as exc:
        logger.warning("Failed to decrypt Slack installation payload: {}", exc)
        return None
    return payload if isinstance(payload, dict) else None


def _default_installations_payload() -> dict[str, Any]:
    return {
        "provider": "slack",
        "credential_version": 1,
        "installations": {},
    }


def _normalize_installations_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    merged = _default_installations_payload()
    if isinstance(payload, dict):
        merged.update(payload)
    installations = merged.get("installations")
    if not isinstance(installations, dict):
        merged["installations"] = {}
    return merged


def _public_installation_record(installation: dict[str, Any]) -> dict[str, Any]:
    return {
        "team_id": installation.get("team_id"),
        "team_name": installation.get("team_name"),
        "enterprise_id": installation.get("enterprise_id"),
        "bot_user_id": installation.get("bot_user_id"),
        "scope": installation.get("scope"),
        "installed_at": installation.get("installed_at"),
        "installed_by": installation.get("installed_by"),
        "disabled": bool(installation.get("disabled")),
    }


async def _slack_oauth_token_exchange(*, token_url: str, form_data: dict[str, Any]) -> dict[str, Any]:
    response = await _http_afetch(
        method="POST",
        url=token_url,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data=form_data,
        timeout=30,
        retry=_RetryPolicy(attempts=1),
    )
    try:
        status_code = int(getattr(response, "status_code", 0))
        payload: dict[str, Any] | None = None
        try:
            maybe_payload = response.json()
            if isinstance(maybe_payload, dict):
                payload = dict(maybe_payload)
        except Exception:
            payload = None

        if status_code < 200 or status_code >= 300:
            detail = "Slack OAuth token exchange failed"
            if payload:
                provider_error = _coerce_nonempty_string(payload.get("error"))
                if provider_error:
                    detail = f"{detail}: {provider_error}"
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=detail,
            )
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Slack OAuth token exchange returned invalid payload",
            )
        return payload
    finally:
        await _close_http_response(response)


def _error_response(status_code: int, error: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"ok": False, "error": error, "message": message},
    )


def _metric_labels(**labels: Any) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in labels.items():
        if value is None:
            continue
        normalized[str(key)] = str(value)
    return normalized


def _emit_slack_counter(metric_name: str, **labels: Any) -> None:
    try:
        log_counter(metric_name, labels=_metric_labels(**labels))
    except Exception as exc:
        logger.debug("Failed to emit Slack metric {}: {}", metric_name, exc)


def _extract_timestamp(header_value: str | None) -> int | None:
    if not header_value:
        return None
    try:
        return int(header_value.strip())
    except (TypeError, ValueError):
        return None


def _verify_slack_signature(raw_body: bytes, timestamp_header: str | None, signature_header: str | None) -> tuple[bool, str | None]:
    secret = _signing_secret()
    if not secret:
        logger.warning("Slack signing secret is not configured")
        return False, "signing_secret_not_configured"

    timestamp = _extract_timestamp(timestamp_header)
    if timestamp is None:
        return False, "invalid_timestamp"

    now = int(time.time())
    if abs(now - timestamp) > max(1, _replay_window_seconds()):
        return False, "stale_request"

    if not signature_header or not signature_header.startswith("v0="):
        return False, "invalid_signature"

    base = f"v0:{timestamp}:".encode("utf-8") + raw_body
    expected = "v0=" + hmac.new(secret.encode("utf-8"), base, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature_header.strip()):
        return False, "invalid_signature"

    return True, None


def _rate_limit_key_for_events(payload: dict, request: Request) -> str:
    team_id = payload.get("team_id")
    if isinstance(team_id, dict):
        team_id = team_id.get("id")
    app_id = payload.get("api_app_id")
    fallback = request.client.host if request.client else "unknown"
    return f"slack:events:{app_id or 'na'}:{team_id or fallback}"


def _rate_limit_key_for_commands(form_payload: dict[str, str], request: Request) -> str:
    team_id = form_payload.get("team_id") or form_payload.get("team_domain")
    app_id = form_payload.get("api_app_id") or "na"
    fallback = request.client.host if request.client else "unknown"
    return f"slack:commands:{app_id}:{team_id or fallback}"


def _is_bot_event(payload: dict) -> bool:
    event = payload.get("event")
    if not isinstance(event, dict):
        return False
    subtype = str(event.get("subtype") or "").strip().lower()
    return bool(event.get("bot_id") or subtype == "bot_message")


def _command_fingerprint(raw_body: bytes) -> str:
    return hashlib.sha256(raw_body).hexdigest()


_SUPPORTED_SLACK_ACTIONS = ("help", "ask", "rag", "summarize", "status")


def _slack_usage_text() -> str:
    return "Supported commands: help | ask <query> | rag <query> | summarize <text> | status"


def _normalize_string_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    values: list[str] = []
    for item in raw:
        cleaned = _coerce_nonempty_string(item)
        if cleaned and cleaned not in values:
            values.append(cleaned)
    return values


def _default_slack_policy() -> dict[str, Any]:
    return {
        "allowed_commands": list(_SUPPORTED_SLACK_ACTIONS),
        "channel_allowlist": [],
        "channel_denylist": [],
        "default_response_mode": "ephemeral",
        "strict_user_mapping": False,
        "service_user_id": None,
        "user_mappings": {},
        "workspace_quota_per_minute": _policy_workspace_quota_per_minute(),
        "user_quota_per_minute": _policy_user_quota_per_minute(),
        "status_scope": "workspace",
    }


def _normalize_slack_policy_payload(
    payload: dict[str, Any] | None,
    *,
    base: dict[str, Any] | None = None,
) -> dict[str, Any]:
    merged = dict(base or _default_slack_policy())
    data = payload if isinstance(payload, dict) else {}

    if "allowed_commands" in data:
        allowed: list[str] = []
        for candidate in _normalize_string_list(data.get("allowed_commands")):
            lowered = candidate.lower()
            if lowered in _SUPPORTED_SLACK_ACTIONS and lowered not in allowed:
                allowed.append(lowered)
        merged["allowed_commands"] = allowed or list(_SUPPORTED_SLACK_ACTIONS)

    if "channel_allowlist" in data:
        merged["channel_allowlist"] = _normalize_string_list(data.get("channel_allowlist"))
    if "channel_denylist" in data:
        merged["channel_denylist"] = _normalize_string_list(data.get("channel_denylist"))

    if "default_response_mode" in data:
        mode = _coerce_nonempty_string(data.get("default_response_mode"))
        if mode and mode.lower() in {"ephemeral", "thread", "channel"}:
            merged["default_response_mode"] = mode.lower()

    if "strict_user_mapping" in data:
        merged["strict_user_mapping"] = bool(data.get("strict_user_mapping"))
    if "service_user_id" in data:
        merged["service_user_id"] = _coerce_nonempty_string(data.get("service_user_id"))

    if "user_mappings" in data and isinstance(data.get("user_mappings"), dict):
        normalized_mappings: dict[str, str] = {}
        for raw_key, raw_value in dict(data.get("user_mappings") or {}).items():
            key = _coerce_nonempty_string(raw_key)
            value = _coerce_nonempty_string(raw_value)
            if key and value:
                normalized_mappings[key] = value
        merged["user_mappings"] = normalized_mappings

    if "workspace_quota_per_minute" in data:
        value = _safe_int(data.get("workspace_quota_per_minute"))
        if value is not None and value > 0:
            merged["workspace_quota_per_minute"] = value
    if "user_quota_per_minute" in data:
        value = _safe_int(data.get("user_quota_per_minute"))
        if value is not None and value > 0:
            merged["user_quota_per_minute"] = value

    if "status_scope" in data:
        scope = _coerce_nonempty_string(data.get("status_scope"))
        if scope and scope.lower() in {"workspace", "workspace_and_user"}:
            merged["status_scope"] = scope.lower()

    return merged


def _policy_key(workspace_id: str | None) -> str:
    return _coerce_nonempty_string(workspace_id) or _POLICY_DEFAULT_KEY


def _slack_policy_for_workspace(workspace_id: str | None) -> dict[str, Any]:
    key = _policy_key(workspace_id)
    with _SLACK_POLICY_LOCK:
        default_raw = _SLACK_POLICIES.get(_POLICY_DEFAULT_KEY)
        default_policy = _normalize_slack_policy_payload(default_raw if isinstance(default_raw, dict) else None)
        if key == _POLICY_DEFAULT_KEY:
            return default_policy
        selected = _SLACK_POLICIES.get(key)
        if isinstance(selected, dict):
            return _normalize_slack_policy_payload(selected, base=default_policy)
        return default_policy


def _set_slack_policy(workspace_id: str | None, payload: dict[str, Any] | None) -> tuple[str | None, dict[str, Any]]:
    key = _policy_key(workspace_id)
    cleaned_workspace = _coerce_nonempty_string(workspace_id)
    with _SLACK_POLICY_LOCK:
        default_raw = _SLACK_POLICIES.get(_POLICY_DEFAULT_KEY)
        default_policy = _normalize_slack_policy_payload(default_raw if isinstance(default_raw, dict) else None)
        base = default_policy if key != _POLICY_DEFAULT_KEY else _default_slack_policy()
        normalized = _normalize_slack_policy_payload(payload, base=base)
        _SLACK_POLICIES[key] = dict(normalized)
    return cleaned_workspace, normalized


def _resolve_slack_actor_id(policy: dict[str, Any], slack_user_id: str | None) -> tuple[str | None, dict[str, Any] | None]:
    requested_user_id = _coerce_nonempty_string(slack_user_id)
    user_mappings = policy.get("user_mappings") if isinstance(policy.get("user_mappings"), dict) else {}
    mapped_user = user_mappings.get(requested_user_id) if requested_user_id else None
    if mapped_user:
        return _coerce_nonempty_string(mapped_user), None

    service_user_id = _coerce_nonempty_string(policy.get("service_user_id"))
    strict_mapping = bool(policy.get("strict_user_mapping"))
    if strict_mapping and not service_user_id:
        return None, {
            "status_code": status.HTTP_403_FORBIDDEN,
            "error": "unknown_user_mapping",
            "message": "Slack user is not mapped to a local user and strict mapping is enabled",
        }
    return requested_user_id or service_user_id, None


def _evaluate_slack_policy(
    *,
    policy: dict[str, Any],
    team_id: str | None,
    channel_id: str | None,
    actor_user_id: str | None,
    action: str,
) -> dict[str, Any] | None:
    allowed_commands = policy.get("allowed_commands")
    if isinstance(allowed_commands, list) and allowed_commands:
        if action not in {str(item).lower() for item in allowed_commands}:
            return {
                "status_code": status.HTTP_403_FORBIDDEN,
                "error": "command_blocked_by_policy",
                "message": f"Command '{action}' is not allowed for this workspace",
            }

    deny_channels = {item for item in _normalize_string_list(policy.get("channel_denylist"))}
    allow_channels = {item for item in _normalize_string_list(policy.get("channel_allowlist"))}
    if channel_id and channel_id in deny_channels:
        return {
            "status_code": status.HTTP_403_FORBIDDEN,
            "error": "channel_blocked_by_policy",
            "message": f"Channel '{channel_id}' is blocked by policy",
        }
    if allow_channels and channel_id and channel_id not in allow_channels:
        return {
            "status_code": status.HTTP_403_FORBIDDEN,
            "error": "channel_not_allowed_by_policy",
            "message": f"Channel '{channel_id}' is not in the allowlist",
        }

    workspace_limit = _safe_int(policy.get("workspace_quota_per_minute")) or _policy_workspace_quota_per_minute()
    workspace_key = _coerce_nonempty_string(team_id) or "unknown"
    allowed_workspace, retry_after_workspace = _POLICY_RATE_LIMITER.allow(
        f"slack:workspace:{workspace_key}",
        max(1, workspace_limit),
    )
    if not allowed_workspace:
        return {
            "status_code": status.HTTP_429_TOO_MANY_REQUESTS,
            "error": "workspace_quota_exceeded",
            "message": "Workspace command quota exceeded",
            "retry_after_seconds": retry_after_workspace,
        }

    if actor_user_id:
        user_limit = _safe_int(policy.get("user_quota_per_minute")) or _policy_user_quota_per_minute()
        allowed_user, retry_after_user = _POLICY_RATE_LIMITER.allow(
            f"slack:user:{workspace_key}:{actor_user_id}",
            max(1, user_limit),
        )
        if not allowed_user:
            return {
                "status_code": status.HTTP_429_TOO_MANY_REQUESTS,
                "error": "user_quota_exceeded",
                "message": "User command quota exceeded",
                "retry_after_seconds": retry_after_user,
            }

    return None


def _slack_policy_error_response(policy_error: dict[str, Any], *, team_id: str | None, action: str | None) -> JSONResponse:
    status_code = int(policy_error.get("status_code") or status.HTTP_403_FORBIDDEN)
    response_payload = {k: v for k, v in policy_error.items() if k != "status_code"}
    headers: dict[str, str] = {}
    retry_after = _safe_int(policy_error.get("retry_after_seconds"))
    if retry_after is not None and retry_after > 0:
        headers["Retry-After"] = str(retry_after)
        _emit_slack_counter(
            "slack_policy_quota_rejections_total",
            team_id=team_id or "na",
            action=action or "na",
            error=response_payload.get("error"),
        )
    else:
        _emit_slack_counter(
            "slack_policy_denied_total",
            team_id=team_id or "na",
            action=action or "na",
            error=response_payload.get("error"),
        )
    logger.warning(
        "Slack policy denied request: team_id={} action={} error={}",
        team_id or "na",
        action or "na",
        response_payload.get("error"),
    )
    return JSONResponse(status_code=status_code, headers=headers, content={"ok": False, **response_payload})

def _slack_action_route(action: str) -> str:
    routes = {
        "help": "slack.help",
        "ask": "chat.ask",
        "rag": "rag.search",
        "summarize": "summarize.run",
        "status": "jobs.status",
    }
    return routes.get(action, "chat.ask")


def _parse_slack_text_command(text: str | None) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    raw = (text or "").strip()
    if not raw:
        action = "help"
        return {
            "action": action,
            "route": _slack_action_route(action),
            "input": "",
        }, None

    parts = raw.split(maxsplit=1)
    command = parts[0].strip().lower()
    remainder = parts[1].strip() if len(parts) > 1 else ""
    if command not in _SUPPORTED_SLACK_ACTIONS:
        return None, {
            "error": "unknown_command",
            "message": f"Unknown command '{command}'. {_slack_usage_text()}",
            "usage": _slack_usage_text(),
        }
    return {
        "action": command,
        "route": _slack_action_route(command),
        "input": remainder,
    }, None


def _parse_slack_command(form_payload: dict[str, str]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    text = form_payload.get("text")
    return _parse_slack_text_command(text)


def _parse_slack_mention(payload: dict[str, Any]) -> dict[str, Any] | None:
    event = payload.get("event")
    if not isinstance(event, dict):
        return None
    event_type = str(event.get("type") or "").strip().lower()
    if event_type != "app_mention":
        return None

    text = str(event.get("text") or "").strip()
    if not text:
        action = "help"
        return {"action": action, "route": _slack_action_route(action), "input": ""}

    normalized = " ".join(part for part in text.split() if not part.startswith("<@")).strip()
    parsed, _error = _parse_slack_text_command(normalized)
    if parsed:
        return parsed

    # Mention defaults to ask when input does not start with a supported command.
    return {
        "action": "ask",
        "route": _slack_action_route("ask"),
        "input": normalized,
    }


def _slack_response_mode(form_payload: dict[str, str], policy: dict[str, Any] | None = None) -> str:
    raw = str(form_payload.get("response_mode") or "").strip().lower()
    if not raw and isinstance(policy, dict):
        raw = str(policy.get("default_response_mode") or "").strip().lower()
    if raw in {"ephemeral", "thread", "channel"}:
        return raw
    return "ephemeral"


def _safe_int(raw_value: Any) -> int | None:
    try:
        return int(str(raw_value).strip())
    except (TypeError, ValueError):
        return None


def _enqueue_slack_job(
    *,
    form_payload: dict[str, str],
    parsed_command: dict[str, Any],
    owner_user_id: str | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    jm = _get_job_manager()
    request_id = _coerce_nonempty_string(form_payload.get("trigger_id")) or secrets.token_urlsafe(12)
    owner = _coerce_nonempty_string(owner_user_id) or _coerce_nonempty_string(form_payload.get("user_id")) or None
    action = str(parsed_command.get("action") or "ask")
    response_mode = _slack_response_mode(form_payload, policy)
    job = jm.create_job(
        domain="slack",
        queue="default",
        job_type=f"slack_{action}",
        payload={
            "request_id": request_id,
            "team_id": _coerce_nonempty_string(form_payload.get("team_id")),
            "channel_id": _coerce_nonempty_string(form_payload.get("channel_id")),
            "thread_ts": _coerce_nonempty_string(form_payload.get("thread_ts")),
            "command": parsed_command,
            "response_mode": response_mode,
        },
        owner_user_id=owner,
        request_id=request_id,
    )
    job_id = _safe_int(job.get("id"))
    return {
        "job_id": job_id,
        "request_id": request_id,
        "response_mode": response_mode,
        "job_status": str(job.get("status") or "queued"),
    }


@router.post("/events")
async def slack_events(request: Request) -> JSONResponse:
    raw_body = await request.body()
    ok, error = _verify_slack_signature(
        raw_body,
        request.headers.get("x-slack-request-timestamp"),
        request.headers.get("x-slack-signature"),
    )
    if not ok:
        status = 503 if error == "signing_secret_not_configured" else 401
        _emit_slack_counter(
            "slack_signature_failures_total",
            endpoint="events",
            reason=error or "unknown",
        )
        return _error_response(status, str(error or "invalid_request"), "Slack request verification failed")

    try:
        payload = json.loads(raw_body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _error_response(400, "invalid_json", "Invalid JSON payload")

    if not isinstance(payload, dict):
        return _error_response(400, "invalid_payload", "Payload must be a JSON object")

    allowed, retry_after = _RATE_LIMITER.allow(
        _rate_limit_key_for_events(payload, request),
        _ingress_rate_limit_per_minute(),
    )
    if not allowed:
        _emit_slack_counter("slack_requests_total", endpoint="events", outcome="rate_limited")
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": str(retry_after)},
            content={"ok": False, "error": "rate_limited", "retry_after_seconds": retry_after},
        )

    event_type = str(payload.get("type") or "").strip()
    if event_type == "url_verification":
        challenge = payload.get("challenge")
        if not isinstance(challenge, str) or not challenge:
            return _error_response(400, "missing_challenge", "Missing challenge")
        return JSONResponse(status_code=200, content={"challenge": challenge})

    if event_type == "event_callback":
        event_id = str(payload.get("event_id") or "").strip()
        dedupe_key = event_id or hashlib.sha256(raw_body).hexdigest()
        is_duplicate = _EVENT_RECEIPTS.seen_or_store(dedupe_key, _dedupe_ttl_seconds())
        if is_duplicate:
            _emit_slack_counter("slack_requests_total", endpoint="events", outcome="duplicate")
            return JSONResponse(status_code=200, content={"ok": True, "status": "duplicate"})

        if _is_bot_event(payload):
            _emit_slack_counter("slack_requests_total", endpoint="events", outcome="ignored_bot_event")
            return JSONResponse(status_code=200, content={"ok": True, "status": "ignored_bot_event"})

        mention_parsed = _parse_slack_mention(payload)
        if mention_parsed:
            event = payload.get("event") if isinstance(payload.get("event"), dict) else {}
            team_id = _coerce_nonempty_string(payload.get("team_id"))
            channel_id = _coerce_nonempty_string(event.get("channel")) if isinstance(event, dict) else None
            slack_user_id = _coerce_nonempty_string(event.get("user")) if isinstance(event, dict) else None
            policy = _slack_policy_for_workspace(team_id)
            actor_user_id, mapping_error = _resolve_slack_actor_id(policy, slack_user_id)
            if mapping_error:
                return _slack_policy_error_response(
                    mapping_error,
                    team_id=team_id,
                    action=str(mention_parsed.get("action") or ""),
                )
            policy_error = _evaluate_slack_policy(
                policy=policy,
                team_id=team_id,
                channel_id=channel_id,
                actor_user_id=actor_user_id,
                action=str(mention_parsed.get("action") or ""),
            )
            if policy_error:
                return _slack_policy_error_response(
                    policy_error,
                    team_id=team_id,
                    action=str(mention_parsed.get("action") or ""),
                )
            _emit_slack_counter(
                "slack_requests_total",
                endpoint="events",
                outcome="accepted",
                action=str(mention_parsed.get("action") or "na"),
            )
            return JSONResponse(
                status_code=200,
                content={"ok": True, "status": "accepted", "parsed": mention_parsed},
            )
        _emit_slack_counter("slack_requests_total", endpoint="events", outcome="accepted")
        return JSONResponse(status_code=200, content={"ok": True, "status": "accepted"})

    _emit_slack_counter("slack_requests_total", endpoint="events", outcome="accepted")
    return JSONResponse(status_code=200, content={"ok": True, "status": "accepted"})


@router.post("/commands")
async def slack_commands(request: Request) -> JSONResponse:
    raw_body = await request.body()
    ok, error = _verify_slack_signature(
        raw_body,
        request.headers.get("x-slack-request-timestamp"),
        request.headers.get("x-slack-signature"),
    )
    if not ok:
        status = 503 if error == "signing_secret_not_configured" else 401
        _emit_slack_counter(
            "slack_signature_failures_total",
            endpoint="commands",
            reason=error or "unknown",
        )
        return _error_response(status, str(error or "invalid_request"), "Slack request verification failed")

    try:
        parsed = parse_qs(raw_body.decode("utf-8"), keep_blank_values=True)
    except UnicodeDecodeError:
        return _error_response(400, "invalid_form", "Unable to parse form body")

    form_payload = {k: (v[0] if v else "") for k, v in parsed.items()}
    allowed, retry_after = _RATE_LIMITER.allow(
        _rate_limit_key_for_commands(form_payload, request),
        _ingress_rate_limit_per_minute(),
    )
    if not allowed:
        _emit_slack_counter("slack_requests_total", endpoint="commands", outcome="rate_limited")
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": str(retry_after)},
            content={"ok": False, "error": "rate_limited", "retry_after_seconds": retry_after},
        )

    dedupe_key = _command_fingerprint(raw_body)
    is_duplicate = _COMMAND_RECEIPTS.seen_or_store(dedupe_key, _dedupe_ttl_seconds())
    if is_duplicate:
        _emit_slack_counter("slack_requests_total", endpoint="commands", outcome="duplicate")
        return JSONResponse(status_code=200, content={"ok": True, "status": "duplicate"})

    parsed_command, parse_error = _parse_slack_command(form_payload)
    if parse_error:
        _emit_slack_counter("slack_requests_total", endpoint="commands", outcome="invalid_command")
        return JSONResponse(
            status_code=400,
            content={"ok": False, **parse_error},
        )
    action = str(parsed_command.get("action") or "")
    team_id = _coerce_nonempty_string(form_payload.get("team_id")) or _coerce_nonempty_string(form_payload.get("team_domain"))
    channel_id = _coerce_nonempty_string(form_payload.get("channel_id"))
    slack_user_id = _coerce_nonempty_string(form_payload.get("user_id"))
    policy = _slack_policy_for_workspace(team_id)
    actor_user_id, mapping_error = _resolve_slack_actor_id(policy, slack_user_id)
    if mapping_error:
        return _slack_policy_error_response(mapping_error, team_id=team_id, action=action)

    policy_error = _evaluate_slack_policy(
        policy=policy,
        team_id=team_id,
        channel_id=channel_id,
        actor_user_id=actor_user_id,
        action=action,
    )
    if policy_error:
        return _slack_policy_error_response(policy_error, team_id=team_id, action=action)

    logger.bind(
        integration="slack",
        workspace_id=team_id or "na",
        channel_id=channel_id or "na",
        command=action or "na",
        request_id=_coerce_nonempty_string(form_payload.get("trigger_id")) or "na",
        actor_user_id=actor_user_id or "na",
    ).info("Slack command accepted")

    if action in {"ask", "rag", "summarize"}:
        enqueued = _enqueue_slack_job(
            form_payload=form_payload,
            parsed_command=parsed_command,
            owner_user_id=actor_user_id,
            policy=policy,
        )
        _emit_slack_counter("slack_jobs_enqueued_total", action=action, team_id=team_id or "na")
        _emit_slack_counter("slack_requests_total", endpoint="commands", outcome="queued", action=action)
        return JSONResponse(
            status_code=200,
            content={
                "ok": True,
                "status": "queued",
                "parsed": parsed_command,
                **enqueued,
            },
        )

    if action == "status":
        jm = _get_job_manager()
        requested_job_id = _safe_int(parsed_command.get("input"))
        if requested_job_id is None:
            _emit_slack_counter("slack_requests_total", endpoint="commands", outcome="invalid_status_query")
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": "invalid_status_query",
                    "message": "Status command requires a numeric job id. Example: status 42",
                },
            )
        job = jm.get_job(requested_job_id)
        job_payload = job.get("payload") if isinstance(job, dict) and isinstance(job.get("payload"), dict) else {}
        job_team_id = _coerce_nonempty_string(job_payload.get("team_id"))
        owner_user_id = _coerce_nonempty_string(job.get("owner_user_id")) if isinstance(job, dict) else None
        status_scope = str(policy.get("status_scope") or "workspace").strip().lower()
        wrong_workspace = bool(job_team_id and team_id and job_team_id != team_id)
        wrong_user_scope = bool(
            status_scope == "workspace_and_user"
            and actor_user_id
            and owner_user_id
            and actor_user_id != owner_user_id
        )
        if not job or wrong_workspace or wrong_user_scope:
            _emit_slack_counter("slack_requests_total", endpoint="commands", outcome="status_denied")
            return JSONResponse(
                status_code=404,
                content={"ok": False, "error": "job_not_found", "job_id": requested_job_id},
            )
        _emit_slack_counter("slack_requests_total", endpoint="commands", outcome="accepted", action=action)
        return JSONResponse(
            status_code=200,
            content={
                "ok": True,
                "status": "accepted",
                "parsed": parsed_command,
                "job": {
                    "id": requested_job_id,
                    "status": job.get("status"),
                    "domain": job.get("domain"),
                    "queue": job.get("queue"),
                    "job_type": job.get("job_type"),
                },
            },
        )

    _emit_slack_counter("slack_requests_total", endpoint="commands", outcome="accepted", action=action or "na")
    return JSONResponse(
        status_code=200,
        content={"ok": True, "status": "accepted", "parsed": parsed_command},
    )


@router.get("/jobs/{job_id}")
async def slack_job_status(
    job_id: int,
):
    jm = _get_job_manager()
    job = jm.get_job(int(job_id))
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job_not_found")
    if str(job.get("domain") or "").strip().lower() != "slack":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job_not_found")
    return {
        "ok": True,
        "job": {
            "id": int(job.get("id") or job_id),
            "status": job.get("status"),
            "domain": job.get("domain"),
            "queue": job.get("queue"),
            "job_type": job.get("job_type"),
        },
    }


@router.post("/oauth/start")
async def slack_oauth_start(
    user: User = Depends(get_request_user),
):
    client_id = _oauth_client_id()
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="SLACK_CLIENT_ID is not configured",
        )
    redirect_uri = _oauth_redirect_uri()
    state = secrets.token_urlsafe(32)
    auth_session_id = secrets.token_urlsafe(24)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=max(1, _oauth_state_ttl_seconds()))

    state_repo = await _get_oauth_state_repo()
    state_secret = _encrypt_slack_payload({"nonce": secrets.token_urlsafe(24)})
    await state_repo.create_state(
        state=state,
        user_id=int(user.id),
        provider="slack",
        auth_session_id=auth_session_id,
        redirect_uri=redirect_uri,
        pkce_verifier_encrypted=state_secret,
        expires_at=expires_at,
        created_at=now,
    )

    query = {
        "client_id": client_id,
        "scope": _oauth_scopes(),
        "redirect_uri": redirect_uri,
        "state": state,
    }
    auth_url = f"{_oauth_auth_url()}?{urlencode(query)}"
    return {
        "ok": True,
        "status": "ready",
        "auth_url": auth_url,
        "auth_session_id": auth_session_id,
        "expires_at": expires_at.isoformat(),
    }


@router.get("/oauth/callback")
async def slack_oauth_callback(
    code: str,
    state: str,
):
    code_value = _coerce_nonempty_string(code)
    state_value = _coerce_nonempty_string(state)
    if not code_value or not state_value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing OAuth callback parameters",
        )

    state_repo = await _get_oauth_state_repo()
    state_record = await state_repo.consume_state(
        state=state_value,
        provider="slack",
    )
    if not state_record:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or expired OAuth state",
        )

    redirect_uri = _coerce_nonempty_string(state_record.get("redirect_uri"))
    if not redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth state is missing redirect metadata",
        )

    user_id_raw = state_record.get("user_id")
    try:
        user_id = int(user_id_raw)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth state user context is invalid",
        ) from exc

    client_id = _oauth_client_id()
    client_secret = _oauth_client_secret()
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Slack OAuth client credentials are not configured",
        )

    token_payload = await _slack_oauth_token_exchange(
        token_url=_oauth_token_url(),
        form_data={
            "code": code_value,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        },
    )
    if not bool(token_payload.get("ok")):
        provider_error = _coerce_nonempty_string(token_payload.get("error")) or "token_exchange_failed"
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Slack OAuth token exchange failed: {provider_error}",
        )

    access_token = _coerce_nonempty_string(token_payload.get("access_token"))
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Slack OAuth response missing access_token",
        )

    team_data = token_payload.get("team")
    team_id = _coerce_nonempty_string(team_data.get("id")) if isinstance(team_data, dict) else None
    team_name = _coerce_nonempty_string(team_data.get("name")) if isinstance(team_data, dict) else None
    if not team_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Slack OAuth response missing team.id",
        )

    user_repo = await _get_user_secret_repo()
    existing_row = await user_repo.fetch_secret_for_user(user_id, "slack")
    existing_payload = _decrypt_slack_payload(existing_row.get("encrypted_blob")) if existing_row else None
    merged_payload = _normalize_installations_payload(existing_payload)
    installations = merged_payload.get("installations")
    if not isinstance(installations, dict):
        installations = {}
        merged_payload["installations"] = installations

    now = datetime.now(timezone.utc)
    authed_user = token_payload.get("authed_user")
    authed_user_id = _coerce_nonempty_string(authed_user.get("id")) if isinstance(authed_user, dict) else None
    installations[team_id] = {
        "team_id": team_id,
        "team_name": team_name,
        "enterprise_id": _coerce_nonempty_string(token_payload.get("enterprise_id")),
        "bot_user_id": _coerce_nonempty_string(token_payload.get("bot_user_id")),
        "scope": _coerce_nonempty_string(token_payload.get("scope")),
        "authed_user_id": authed_user_id,
        "access_token": access_token,
        "installed_at": now.isoformat(),
        "installed_by": user_id,
        "disabled": False,
    }

    encrypted_blob = _encrypt_slack_payload(merged_payload)
    await user_repo.upsert_secret(
        user_id=user_id,
        provider="slack",
        encrypted_blob=encrypted_blob,
        key_hint=key_hint_for_api_key(access_token),
        metadata={"installation_count": len(installations)},
        updated_at=now,
        created_by=user_id,
        updated_by=user_id,
    )

    return {
        "ok": True,
        "status": "installed",
        "team_id": team_id,
        "team_name": team_name,
    }


@router.get(
    "/admin/policy",
    dependencies=[Depends(require_roles("admin"))],
)
async def slack_admin_get_policy(
    team_id: str | None = Query(default=None),
):
    cleaned_team_id = _coerce_nonempty_string(team_id)
    policy = _slack_policy_for_workspace(cleaned_team_id)
    return {
        "ok": True,
        "team_id": cleaned_team_id,
        "policy": policy,
    }


@router.put(
    "/admin/policy",
    dependencies=[Depends(require_roles("admin"))],
)
async def slack_admin_set_policy(
    payload: dict[str, Any] | None = None,
):
    body = dict(payload or {})
    cleaned_team_id = _coerce_nonempty_string(body.pop("team_id", None))
    scope = "workspace" if cleaned_team_id else "default"
    team_id, policy = _set_slack_policy(cleaned_team_id, body)
    _emit_slack_counter("slack_policy_updates_total", scope=scope)
    return {
        "ok": True,
        "status": "updated",
        "team_id": team_id,
        "policy": policy,
    }


@router.get("/admin/installations")
async def slack_admin_list_installations(
    user: User = Depends(get_request_user),
):
    user_repo = await _get_user_secret_repo()
    row = await user_repo.fetch_secret_for_user(int(user.id), "slack")
    payload = _decrypt_slack_payload(row.get("encrypted_blob")) if row else None
    merged_payload = _normalize_installations_payload(payload)
    installations = merged_payload.get("installations")
    if not isinstance(installations, dict):
        installations = {}
    results = []
    for team_id, installation in installations.items():
        if not isinstance(installation, dict):
            continue
        record = _public_installation_record(installation)
        record["team_id"] = record.get("team_id") or team_id
        results.append(record)
    results.sort(key=lambda item: str(item.get("team_id") or ""))
    return {"ok": True, "installations": results}


@router.delete("/admin/installations/{team_id}")
async def slack_admin_delete_installation(
    team_id: str,
    user: User = Depends(get_request_user),
):
    cleaned_team_id = _coerce_nonempty_string(team_id)
    if not cleaned_team_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="team_id is required")
    user_id = int(user.id)
    user_repo = await _get_user_secret_repo()
    row = await user_repo.fetch_secret_for_user(user_id, "slack")
    payload = _decrypt_slack_payload(row.get("encrypted_blob")) if row else None
    merged_payload = _normalize_installations_payload(payload)
    installations = merged_payload.get("installations")
    if not isinstance(installations, dict) or cleaned_team_id not in installations:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="installation_not_found")

    installations.pop(cleaned_team_id, None)
    now = datetime.now(timezone.utc)
    if not installations:
        await user_repo.delete_secret(
            user_id=user_id,
            provider="slack",
            revoked_by=user_id,
            revoked_at=now,
        )
    else:
        replacement_token: str | None = None
        for remaining in installations.values():
            if isinstance(remaining, dict):
                replacement_token = _coerce_nonempty_string(remaining.get("access_token"))
                if replacement_token:
                    break
        await user_repo.upsert_secret(
            user_id=user_id,
            provider="slack",
            encrypted_blob=_encrypt_slack_payload(merged_payload),
            key_hint=key_hint_for_api_key(replacement_token) if replacement_token else None,
            metadata={"installation_count": len(installations)},
            updated_at=now,
            created_by=user_id,
            updated_by=user_id,
        )
    return {"ok": True, "status": "deleted", "team_id": cleaned_team_id}


@router.put("/admin/installations/{team_id}")
async def slack_admin_set_installation_state(
    team_id: str,
    payload: dict[str, Any] | None = None,
    user: User = Depends(get_request_user),
):
    cleaned_team_id = _coerce_nonempty_string(team_id)
    if not cleaned_team_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="team_id is required")

    disabled = bool((payload or {}).get("disabled"))
    user_id = int(user.id)
    user_repo = await _get_user_secret_repo()
    row = await user_repo.fetch_secret_for_user(user_id, "slack")
    stored_payload = _decrypt_slack_payload(row.get("encrypted_blob")) if row else None
    merged_payload = _normalize_installations_payload(stored_payload)
    installations = merged_payload.get("installations")
    if not isinstance(installations, dict):
        installations = {}
        merged_payload["installations"] = installations
    installation = installations.get(cleaned_team_id)
    if not isinstance(installation, dict):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="installation_not_found")

    installation["disabled"] = disabled
    now = datetime.now(timezone.utc)
    key_hint_token = _coerce_nonempty_string(installation.get("access_token")) or ""
    await user_repo.upsert_secret(
        user_id=user_id,
        provider="slack",
        encrypted_blob=_encrypt_slack_payload(merged_payload),
        key_hint=key_hint_for_api_key(key_hint_token) if key_hint_token else None,
        metadata={"installation_count": len(installations)},
        updated_at=now,
        created_by=user_id,
        updated_by=user_id,
    )
    return {
        "ok": True,
        "status": "updated",
        "team_id": cleaned_team_id,
        "disabled": disabled,
    }
