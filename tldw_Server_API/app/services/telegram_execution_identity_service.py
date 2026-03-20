from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from tldw_Server_API.app.core.AuthNZ.permissions import TELEGRAM_RECEIVE, TELEGRAM_REPLY
from tldw_Server_API.app.core.AuthNZ.rbac import get_effective_permissions

PermissionResolver = Callable[[int], list[str]]


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


def _coerce_positive_ttl(value: Any, fallback_seconds: int) -> int:
    try:
        candidate = int(value)
    except (TypeError, ValueError):
        candidate = int(fallback_seconds)
    return max(1, candidate)


def _unique_strings(values: Sequence[Any] | None) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in values or []:
        cleaned = str(raw or "").strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


def _normalize_capability_scopes(
    scopes: Mapping[str, Sequence[Any]] | None,
) -> dict[str, list[str]]:
    if not isinstance(scopes, Mapping):
        return {}
    normalized: dict[str, list[str]] = {}
    for raw_key, raw_values in scopes.items():
        key = str(raw_key or "").strip()
        values = _unique_strings(list(raw_values or []))
        if key and values:
            normalized[key] = values
    return normalized


def _intersect_values(parent_values: Sequence[str], requested_values: Sequence[Any] | None) -> list[str]:
    if requested_values is None:
        return list(parent_values)
    requested_set = set(_unique_strings(list(requested_values or [])))
    if not requested_set:
        return []
    return [value for value in parent_values if value in requested_set]


def _intersect_capability_scopes(
    parent_scopes: Mapping[str, list[str]],
    requested_scopes: Mapping[str, Sequence[Any]] | None,
) -> dict[str, list[str]]:
    if requested_scopes is None:
        return {key: list(values) for key, values in parent_scopes.items()}

    normalized_requested = _normalize_capability_scopes(requested_scopes)
    out: dict[str, list[str]] = {}
    for key, requested_values in normalized_requested.items():
        parent_values = parent_scopes.get(key) or []
        intersected = _intersect_values(parent_values, requested_values)
        if intersected:
            out[key] = intersected
    return out


@dataclass(frozen=True, slots=True)
class TelegramExecutionIdentity:
    execution_id: str
    parent_execution_id: str | None
    tenant_id: str
    auth_user_id: str
    source: str
    permissions: list[str]
    capability_scopes: dict[str, list[str]]
    allowed_workspace_ids: list[str]
    allowed_workflow_ids: list[str]
    allowed_tool_ids: list[str]
    conversation_id: str | None
    persona_id: str | None
    character_id: str | None
    request_id: str | None
    telegram_user_id: int | None
    telegram_chat_id: int | None
    telegram_thread_id: int | None
    scope_type: str | None
    scope_id: int | None
    issued_at: datetime
    expires_at: datetime

    def to_payload(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "parent_execution_id": self.parent_execution_id,
            "tenant_id": self.tenant_id,
            "auth_user_id": self.auth_user_id,
            "source": self.source,
            "permissions": list(self.permissions),
            "capability_scopes": {
                key: list(values) for key, values in self.capability_scopes.items()
            },
            "allowed_workspace_ids": list(self.allowed_workspace_ids),
            "allowed_workflow_ids": list(self.allowed_workflow_ids),
            "allowed_tool_ids": list(self.allowed_tool_ids),
            "conversation_id": self.conversation_id,
            "persona_id": self.persona_id,
            "character_id": self.character_id,
            "request_id": self.request_id,
            "telegram_user_id": self.telegram_user_id,
            "telegram_chat_id": self.telegram_chat_id,
            "telegram_thread_id": self.telegram_thread_id,
            "scope_type": self.scope_type,
            "scope_id": self.scope_id,
            "issued_at": self.issued_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
        }


@dataclass(slots=True)
class TelegramExecutionIdentityService:
    permission_resolver: PermissionResolver = get_effective_permissions
    default_ttl_seconds: int = 900

    def mint_telegram_identity(
        self,
        *,
        tenant_id: str,
        auth_user_id: str | int,
        permissions: Sequence[Any] | None = None,
        capability_scopes: Mapping[str, Sequence[Any]] | None = None,
        allowed_workspace_ids: Sequence[Any] | None = None,
        allowed_workflow_ids: Sequence[Any] | None = None,
        allowed_tool_ids: Sequence[Any] | None = None,
        conversation_id: str | None = None,
        persona_id: str | None = None,
        character_id: str | None = None,
        request_id: str | None = None,
        telegram_user_id: int | None = None,
        telegram_chat_id: int | None = None,
        telegram_thread_id: int | None = None,
        scope_type: str | None = None,
        scope_id: int | None = None,
        now: datetime | None = None,
        ttl_seconds: int | None = None,
    ) -> TelegramExecutionIdentity:
        issued_at = now.astimezone(timezone.utc) if isinstance(now, datetime) else datetime.now(timezone.utc)
        resolved_auth_user_id = str(auth_user_id).strip()
        if not resolved_auth_user_id:
            raise ValueError("auth_user_id is required")

        resolved_permissions = _unique_strings(list(permissions or []))
        if permissions is None:
            auth_user_id_int = _coerce_int(resolved_auth_user_id)
            if auth_user_id_int is None:
                raise ValueError("auth_user_id must be an integer when permissions are unresolved")
            resolved_permissions = _unique_strings(self.permission_resolver(auth_user_id_int))

        effective_permissions = _unique_strings(
            [TELEGRAM_RECEIVE, TELEGRAM_REPLY] + resolved_permissions
        )
        ttl = _coerce_positive_ttl(ttl_seconds, self.default_ttl_seconds)
        expires_at = issued_at + timedelta(seconds=ttl)

        return TelegramExecutionIdentity(
            execution_id=str(uuid.uuid4()),
            parent_execution_id=None,
            tenant_id=str(tenant_id).strip(),
            auth_user_id=resolved_auth_user_id,
            source="telegram",
            permissions=effective_permissions,
            capability_scopes=_normalize_capability_scopes(capability_scopes),
            allowed_workspace_ids=_unique_strings(list(allowed_workspace_ids or [])),
            allowed_workflow_ids=_unique_strings(list(allowed_workflow_ids or [])),
            allowed_tool_ids=_unique_strings(list(allowed_tool_ids or [])),
            conversation_id=_coerce_nonempty_string(conversation_id),
            persona_id=_coerce_nonempty_string(persona_id),
            character_id=_coerce_nonempty_string(character_id),
            request_id=_coerce_nonempty_string(request_id),
            telegram_user_id=_coerce_int(telegram_user_id),
            telegram_chat_id=_coerce_int(telegram_chat_id),
            telegram_thread_id=_coerce_int(telegram_thread_id),
            scope_type=_coerce_nonempty_string(scope_type),
            scope_id=_coerce_int(scope_id),
            issued_at=issued_at,
            expires_at=expires_at,
        )

    def mint_child_identity(
        self,
        parent: TelegramExecutionIdentity,
        *,
        permissions: Sequence[Any] | None = None,
        capability_scopes: Mapping[str, Sequence[Any]] | None = None,
        allowed_workspace_ids: Sequence[Any] | None = None,
        allowed_workflow_ids: Sequence[Any] | None = None,
        allowed_tool_ids: Sequence[Any] | None = None,
        conversation_id: str | None = None,
        persona_id: str | None = None,
        character_id: str | None = None,
        request_id: str | None = None,
        now: datetime | None = None,
        ttl_seconds: int | None = None,
    ) -> TelegramExecutionIdentity:
        issued_at = now.astimezone(timezone.utc) if isinstance(now, datetime) else datetime.now(timezone.utc)
        ttl = _coerce_positive_ttl(ttl_seconds, self.default_ttl_seconds)
        requested_expires_at = issued_at + timedelta(seconds=ttl)
        expires_at = min(parent.expires_at, requested_expires_at)

        child_permissions = _intersect_values(parent.permissions, permissions)
        child_capability_scopes = _intersect_capability_scopes(parent.capability_scopes, capability_scopes)
        child_workspace_ids = _intersect_values(parent.allowed_workspace_ids, allowed_workspace_ids)
        child_workflow_ids = _intersect_values(parent.allowed_workflow_ids, allowed_workflow_ids)
        child_tool_ids = _intersect_values(parent.allowed_tool_ids, allowed_tool_ids)

        return TelegramExecutionIdentity(
            execution_id=str(uuid.uuid4()),
            parent_execution_id=parent.execution_id,
            tenant_id=parent.tenant_id,
            auth_user_id=parent.auth_user_id,
            source=parent.source,
            permissions=child_permissions,
            capability_scopes=child_capability_scopes,
            allowed_workspace_ids=child_workspace_ids,
            allowed_workflow_ids=child_workflow_ids,
            allowed_tool_ids=child_tool_ids,
            conversation_id=_coerce_nonempty_string(conversation_id) or parent.conversation_id,
            persona_id=_coerce_nonempty_string(persona_id) or parent.persona_id,
            character_id=_coerce_nonempty_string(character_id) or parent.character_id,
            request_id=_coerce_nonempty_string(request_id) or parent.request_id,
            telegram_user_id=parent.telegram_user_id,
            telegram_chat_id=parent.telegram_chat_id,
            telegram_thread_id=parent.telegram_thread_id,
            scope_type=parent.scope_type,
            scope_id=parent.scope_id,
            issued_at=issued_at,
            expires_at=expires_at,
        )


async def get_telegram_execution_identity_service() -> TelegramExecutionIdentityService:
    return TelegramExecutionIdentityService(permission_resolver=get_effective_permissions)
