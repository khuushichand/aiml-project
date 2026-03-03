from __future__ import annotations

import inspect
import json
from typing import Any

from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import (
    get_or_create_audit_service_for_user_id_optional,
)
from tldw_Server_API.app.core.Audit.unified_audit_service import (
    AuditContext,
    AuditEventCategory,
    AuditEventType,
)
from tldw_Server_API.app.core.AuthNZ.repos.mcp_hub_repo import McpHubRepo
from tldw_Server_API.app.core.AuthNZ.user_provider_secrets import (
    build_secret_payload,
    dumps_envelope,
    encrypt_byok_payload,
    key_hint_for_api_key,
)


async def _await_if_needed(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def emit_mcp_hub_audit(
    *,
    action: str,
    actor_id: int | None,
    resource_type: str,
    resource_id: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Best-effort audit emitter for MCP Hub mutations."""
    try:
        svc = await get_or_create_audit_service_for_user_id_optional(actor_id)
        ctx = AuditContext(
            user_id=str(actor_id) if actor_id is not None else None,
            endpoint="/api/v1/mcp/hub",
            method="INTERNAL",
        )
        await svc.log_event(
            event_type=AuditEventType.CONFIG_CHANGED,
            category=AuditEventCategory.SYSTEM,
            context=ctx,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            metadata={
                "actor_id": actor_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "action": action,
                **(metadata or {}),
            },
        )
        await svc.flush(raise_on_failure=False)
    except Exception as exc:
        logger.warning("MCP hub audit emission failed for action={}: {}", action, exc)


class McpHubService:
    """Business logic for MCP Hub profile and external server management."""

    def __init__(self, repo: McpHubRepo):
        self.repo = repo

    async def create_acp_profile(
        self,
        *,
        name: str,
        owner_scope_type: str,
        owner_scope_id: int | None,
        profile: dict[str, Any],
        actor_id: int | None,
        description: str | None = None,
        is_active: bool = True,
    ) -> dict[str, Any]:
        row = await self.repo.create_acp_profile(
            name=name,
            owner_scope_type=owner_scope_type,
            owner_scope_id=owner_scope_id,
            profile_json=json.dumps(profile or {}),
            actor_id=actor_id,
            description=description,
            is_active=is_active,
        )
        await _await_if_needed(
            emit_mcp_hub_audit(
                action="mcp_hub.acp_profile.create",
                actor_id=actor_id,
                resource_type="mcp_acp_profile",
                resource_id=str(row.get("id") or ""),
                metadata={"name": row.get("name"), "owner_scope_type": row.get("owner_scope_type")},
            )
        )
        return row

    async def list_acp_profiles(
        self,
        *,
        owner_scope_type: str | None = None,
        owner_scope_id: int | None = None,
    ) -> list[dict[str, Any]]:
        return await self.repo.list_acp_profiles(
            owner_scope_type=owner_scope_type,
            owner_scope_id=owner_scope_id,
        )

    async def update_acp_profile(
        self,
        profile_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
        owner_scope_type: str | None = None,
        owner_scope_id: int | None = None,
        profile: dict[str, Any] | None = None,
        is_active: bool | None = None,
        actor_id: int | None = None,
    ) -> dict[str, Any] | None:
        row = await self.repo.update_acp_profile(
            profile_id,
            name=name,
            description=description,
            owner_scope_type=owner_scope_type,
            owner_scope_id=owner_scope_id,
            profile_json=json.dumps(profile) if profile is not None else None,
            is_active=is_active,
            actor_id=actor_id,
        )
        if row:
            await _await_if_needed(
                emit_mcp_hub_audit(
                    action="mcp_hub.acp_profile.update",
                    actor_id=actor_id,
                    resource_type="mcp_acp_profile",
                    resource_id=str(row.get("id") or profile_id),
                    metadata={"name": row.get("name"), "owner_scope_type": row.get("owner_scope_type")},
                )
            )
        return row

    async def delete_acp_profile(self, profile_id: int, *, actor_id: int | None) -> bool:
        deleted = await self.repo.delete_acp_profile(profile_id)
        if deleted:
            await _await_if_needed(
                emit_mcp_hub_audit(
                    action="mcp_hub.acp_profile.delete",
                    actor_id=actor_id,
                    resource_type="mcp_acp_profile",
                    resource_id=str(profile_id),
                    metadata=None,
                )
            )
        return deleted

    async def create_external_server(
        self,
        *,
        server_id: str,
        name: str,
        transport: str,
        config: dict[str, Any],
        owner_scope_type: str,
        owner_scope_id: int | None,
        enabled: bool,
        actor_id: int | None,
    ) -> dict[str, Any]:
        previous = await self.repo.get_external_server(server_id)
        row = await self.repo.upsert_external_server(
            server_id=server_id,
            name=name,
            transport=transport,
            config_json=json.dumps(config or {}),
            owner_scope_type=owner_scope_type,
            owner_scope_id=owner_scope_id,
            enabled=enabled,
            actor_id=actor_id,
        )
        action = (
            "mcp_hub.external_server.create"
            if previous is None
            else "mcp_hub.external_server.update"
        )
        await _await_if_needed(
            emit_mcp_hub_audit(
                action=action,
                actor_id=actor_id,
                resource_type="mcp_external_server",
                resource_id=server_id,
                metadata={
                    "name": row.get("name"),
                    "transport": row.get("transport"),
                    "enabled": row.get("enabled"),
                },
            )
        )
        return row

    async def list_external_servers(
        self,
        *,
        owner_scope_type: str | None = None,
        owner_scope_id: int | None = None,
    ) -> list[dict[str, Any]]:
        return await self.repo.list_external_servers(
            owner_scope_type=owner_scope_type,
            owner_scope_id=owner_scope_id,
        )

    async def delete_external_server(self, server_id: str, *, actor_id: int | None) -> bool:
        deleted = await self.repo.delete_external_server(server_id)
        if deleted:
            await _await_if_needed(
                emit_mcp_hub_audit(
                    action="mcp_hub.external_server.delete",
                    actor_id=actor_id,
                    resource_type="mcp_external_server",
                    resource_id=server_id,
                    metadata=None,
                )
            )
        return deleted

    async def set_external_server_secret(
        self,
        *,
        server_id: str,
        secret_value: str,
        actor_id: int | None,
    ) -> dict[str, Any]:
        server = await self.repo.get_external_server(server_id)
        if not server:
            raise ValueError("External server not found")

        secret = (secret_value or "").strip()
        if not secret:
            raise ValueError("Secret value is required")

        secret_payload = build_secret_payload(secret)
        envelope = encrypt_byok_payload(secret_payload)
        stored = await self.repo.upsert_external_secret(
            server_id=server_id,
            encrypted_blob=dumps_envelope(envelope),
            key_hint=key_hint_for_api_key(secret),
            actor_id=actor_id,
        )
        await _await_if_needed(
            emit_mcp_hub_audit(
                action="mcp_hub.external_secret.update",
                actor_id=actor_id,
                resource_type="mcp_external_server",
                resource_id=server_id,
                metadata={"key_hint": stored.get("key_hint")},
            )
        )
        return {
            "server_id": server_id,
            "secret_configured": True,
            "key_hint": stored.get("key_hint"),
            "updated_at": stored.get("updated_at"),
        }

    async def clear_external_server_secret(
        self,
        *,
        server_id: str,
        actor_id: int | None,
    ) -> bool:
        cleared = await self.repo.clear_external_secret(server_id)
        if cleared:
            await _await_if_needed(
                emit_mcp_hub_audit(
                    action="mcp_hub.external_secret.clear",
                    actor_id=actor_id,
                    resource_type="mcp_external_server",
                    resource_id=server_id,
                    metadata=None,
                )
            )
        return cleared
