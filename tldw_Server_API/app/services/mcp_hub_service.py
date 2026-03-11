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
from tldw_Server_API.app.core.exceptions import (
    BadRequestError,
    ResourceNotFoundError,
)
from tldw_Server_API.app.core.AuthNZ.repos.mcp_hub_repo import McpHubRepo
from tldw_Server_API.app.core.AuthNZ.user_provider_secrets import (
    build_secret_payload,
    dumps_envelope,
    encrypt_byok_payload,
    key_hint_for_api_key,
)
from tldw_Server_API.app.services.mcp_hub_external_legacy_inventory import (
    McpHubExternalLegacyInventoryService,
)
from tldw_Server_API.app.services.mcp_hub_external_access_resolver import (
    McpHubExternalAccessResolver,
)
from tldw_Server_API.app.services.mcp_hub_external_auth_service import (
    ManagedExternalAuthBridge,
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


class McpHubConflictError(BadRequestError):
    """Raised when creating an MCP Hub resource would overwrite an existing one."""


_SCOPE_RANK = {"global": 0, "org": 1, "team": 2, "user": 3}


class McpHubService:
    """Business logic for MCP Hub profile and external server management."""

    def __init__(
        self,
        repo: McpHubRepo,
        *,
        legacy_inventory_service: McpHubExternalLegacyInventoryService | None = None,
    ):
        self.repo = repo
        self.legacy_inventory_service = legacy_inventory_service

    async def _list_legacy_inventory(self) -> list[dict[str, Any]]:
        if self.legacy_inventory_service is not None:
            return await self.legacy_inventory_service.list_inventory()
        return list(getattr(self, "_legacy_external_inventory", []) or [])

    async def _get_legacy_inventory_item(self, server_id: str) -> dict[str, Any] | None:
        if self.legacy_inventory_service is not None:
            return await self.legacy_inventory_service.get_inventory_item(server_id)
        inventory = await self._list_legacy_inventory()
        target = str(server_id or "").strip()
        return next((item for item in inventory if str(item.get("id") or "") == target), None)

    @staticmethod
    def _supported_auth_template_target_for_transport(transport: str) -> str | None:
        normalized = str(transport or "").strip().lower()
        if normalized == "websocket":
            return "header"
        if normalized == "stdio":
            return "env"
        return None

    async def _validate_managed_external_auth_template_config(
        self,
        *,
        server_id: str,
        transport: str,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        out = dict(config or {})
        auth = dict(out.get("auth") or {})
        mode = str(auth.get("mode") or "").strip().lower()
        raw_mappings = auth.get("mappings")

        if raw_mappings is None:
            return out
        if mode not in {"template"}:
            raise BadRequestError("Managed auth templates require auth.mode='template'")
        if not isinstance(raw_mappings, list) or not raw_mappings:
            raise BadRequestError("Managed auth template requires at least one mapping")

        expected_target = self._supported_auth_template_target_for_transport(transport)
        if expected_target is None:
            raise BadRequestError("Managed auth templates are supported only for websocket and stdio transports")

        slot_rows = await self.repo.list_external_server_credential_slots(server_id=server_id)
        valid_slots = {
            str(row.get("slot_name") or "").strip().lower()
            for row in slot_rows
            if str(row.get("slot_name") or "").strip()
        }
        seen_targets: set[tuple[str, str]] = set()
        normalized_mappings: list[dict[str, Any]] = []

        for raw_mapping in raw_mappings:
            if not isinstance(raw_mapping, dict):
                raise BadRequestError("Managed auth template mappings must be objects")

            slot_name = str(raw_mapping.get("slot_name") or "").strip().lower()
            if not slot_name:
                raise BadRequestError("Managed auth template mapping requires slot_name")
            if slot_name not in valid_slots:
                raise BadRequestError(f"Managed auth template references unknown slot: {slot_name}")

            target_type = str(raw_mapping.get("target_type") or "").strip().lower()
            if target_type not in {"header", "env"}:
                raise BadRequestError(f"Unsupported auth template target_type: {target_type or 'missing'}")
            if target_type != expected_target:
                raise BadRequestError("Managed auth template target_type is invalid for the server transport")

            target_name = str(raw_mapping.get("target_name") or "").strip()
            if not target_name:
                raise BadRequestError("Managed auth template mapping requires target_name")
            target_key = (target_type, target_name.lower())
            if target_key in seen_targets:
                raise BadRequestError("Managed auth template contains duplicate target mappings")
            seen_targets.add(target_key)

            normalized_mappings.append(
                {
                    "slot_name": slot_name,
                    "target_type": target_type,
                    "target_name": target_name,
                    "prefix": str(raw_mapping.get("prefix") or ""),
                    "suffix": str(raw_mapping.get("suffix") or ""),
                    "required": bool(raw_mapping.get("required", True)),
                }
            )

        auth["mode"] = "template"
        auth["mappings"] = normalized_mappings
        auth.pop("required_slots", None)
        auth.pop("slot_bindings", None)
        out["auth"] = auth
        return out

    async def _build_auth_template_status(
        self,
        *,
        row: dict[str, Any],
        slots: list[dict[str, Any]],
    ) -> dict[str, Any]:
        result = {
            "auth_template_present": False,
            "auth_template_valid": False,
            "auth_template_blocked_reason": "no_auth_template",
        }
        if str(row.get("server_source") or "managed") != "managed":
            return result

        config = dict(row.get("config") or {})
        auth = dict(config.get("auth") or {})
        template_mappings = ManagedExternalAuthBridge._extract_template_mappings(auth)
        if not template_mappings:
            return result

        result["auth_template_present"] = True

        expected_target = self._supported_auth_template_target_for_transport(str(row.get("transport") or ""))
        if expected_target is None:
            result["auth_template_blocked_reason"] = "unsupported_template_transport_target"
            return result

        slot_lookup = {
            str(slot.get("slot_name") or "").strip().lower(): dict(slot)
            for slot in slots
            if str(slot.get("slot_name") or "").strip()
        }
        seen_targets: set[tuple[str, str]] = set()

        for raw_mapping in template_mappings:
            slot_name = str(raw_mapping.get("slot_name") or "").strip().lower()
            target_type = str(raw_mapping.get("target_type") or "").strip().lower()
            target_name = str(raw_mapping.get("target_name") or "").strip()
            if not slot_name or slot_name not in slot_lookup or not target_name:
                result["auth_template_blocked_reason"] = "auth_template_invalid"
                return result
            if target_type not in {"header", "env"}:
                result["auth_template_blocked_reason"] = "auth_template_invalid"
                return result
            if target_type != expected_target:
                result["auth_template_blocked_reason"] = "unsupported_template_transport_target"
                return result
            target_key = (target_type, target_name.lower())
            if target_key in seen_targets:
                result["auth_template_blocked_reason"] = "auth_template_invalid"
                return result
            seen_targets.add(target_key)

            if bool(raw_mapping.get("required", True)) and not bool(slot_lookup[slot_name].get("secret_configured")):
                result["auth_template_blocked_reason"] = "required_slot_secret_missing"
                return result

        result["auth_template_valid"] = True
        result["auth_template_blocked_reason"] = None
        return result

    async def _resolve_binding_target(
        self,
        *,
        binding_target_type: str,
        binding_target_id: int,
    ) -> dict[str, Any]:
        if binding_target_type == "profile":
            row = await self.repo.get_permission_profile(int(binding_target_id))
            if not row:
                raise ResourceNotFoundError("mcp_permission_profile", identifier=str(binding_target_id))
            return row
        if binding_target_type == "assignment":
            row = await self.repo.get_policy_assignment(int(binding_target_id))
            if not row:
                raise ResourceNotFoundError("mcp_policy_assignment", identifier=str(binding_target_id))
            return row
        raise BadRequestError("Invalid credential binding target")

    @staticmethod
    def _validate_binding_scope(
        *,
        server_row: dict[str, Any],
        target_row: dict[str, Any],
    ) -> None:
        server_scope_type = str(server_row.get("owner_scope_type") or "global")
        target_scope_type = str(target_row.get("owner_scope_type") or "global")
        server_rank = _SCOPE_RANK.get(server_scope_type, -1)
        target_rank = _SCOPE_RANK.get(target_scope_type, -1)
        if server_rank < 0 or target_rank < 0:
            raise BadRequestError("Invalid MCP Hub owner scope")
        if server_rank > target_rank:
            raise BadRequestError("Cannot bind a narrower-scope external server to a broader target")
        if server_rank == target_rank and server_scope_type != "global":
            if server_row.get("owner_scope_id") != target_row.get("owner_scope_id"):
                raise BadRequestError("Cannot bind an external server from a different owner scope")

    @staticmethod
    def _normalize_imported_external_config(config: dict[str, Any]) -> dict[str, Any]:
        out = dict(config or {})
        auth = dict(out.get("auth") or {})
        mode = str(auth.get("mode") or "").strip().lower()
        if mode == "bearer_env":
            auth = {"mode": "bearer_token"}
        elif mode == "api_key_env":
            auth = {
                "mode": "api_key_header",
                "api_key_header": str(auth.get("api_key_header") or "X-API-KEY"),
            }
        if auth:
            out["auth"] = auth
        return out

    async def _attach_slot_summary(self, row: dict[str, Any]) -> dict[str, Any]:
        out = dict(row)
        if str(out.get("server_source") or "managed") == "managed":
            out["credential_slots"] = await self.repo.list_external_server_credential_slots(
                server_id=str(out.get("id") or "")
            )
        else:
            out["credential_slots"] = []
        out.update(
            await self._build_auth_template_status(
                row=out,
                slots=list(out.get("credential_slots") or []),
            )
        )
        return out

    async def create_permission_profile(
        self,
        *,
        name: str,
        owner_scope_type: str,
        owner_scope_id: int | None,
        mode: str,
        policy_document: dict[str, Any],
        actor_id: int | None,
        description: str | None = None,
        is_active: bool = True,
    ) -> dict[str, Any]:
        row = await self.repo.create_permission_profile(
            name=name,
            owner_scope_type=owner_scope_type,
            owner_scope_id=owner_scope_id,
            mode=mode,
            policy_document=policy_document,
            actor_id=actor_id,
            description=description,
            is_active=is_active,
        )
        await _await_if_needed(
            emit_mcp_hub_audit(
                action="mcp_hub.permission_profile.create",
                actor_id=actor_id,
                resource_type="mcp_permission_profile",
                resource_id=str(row.get("id") or ""),
                metadata={"name": row.get("name"), "owner_scope_type": row.get("owner_scope_type")},
            )
        )
        return row

    async def list_permission_profiles(
        self,
        *,
        owner_scope_type: str | None = None,
        owner_scope_id: int | None = None,
    ) -> list[dict[str, Any]]:
        return await self.repo.list_permission_profiles(
            owner_scope_type=owner_scope_type,
            owner_scope_id=owner_scope_id,
        )

    async def get_permission_profile(self, profile_id: int) -> dict[str, Any] | None:
        """Fetch a single permission profile by id."""
        return await self.repo.get_permission_profile(profile_id)

    async def update_permission_profile(
        self,
        profile_id: int,
        *,
        actor_id: int | None = None,
        **update_fields: Any,
    ) -> dict[str, Any] | None:
        row = await self.repo.update_permission_profile(
            profile_id,
            actor_id=actor_id,
            **update_fields,
        )
        if row:
            await _await_if_needed(
                emit_mcp_hub_audit(
                    action="mcp_hub.permission_profile.update",
                    actor_id=actor_id,
                    resource_type="mcp_permission_profile",
                    resource_id=str(row.get("id") or profile_id),
                    metadata={"name": row.get("name"), "owner_scope_type": row.get("owner_scope_type")},
                )
            )
        return row

    async def delete_permission_profile(self, profile_id: int, *, actor_id: int | None) -> bool:
        deleted = await self.repo.delete_permission_profile(profile_id)
        if deleted:
            await _await_if_needed(
                emit_mcp_hub_audit(
                    action="mcp_hub.permission_profile.delete",
                    actor_id=actor_id,
                    resource_type="mcp_permission_profile",
                    resource_id=str(profile_id),
                    metadata=None,
                )
            )
        return deleted

    async def create_policy_assignment(
        self,
        *,
        target_type: str,
        target_id: str | None,
        owner_scope_type: str,
        owner_scope_id: int | None,
        profile_id: int | None,
        inline_policy_document: dict[str, Any],
        approval_policy_id: int | None,
        actor_id: int | None,
        is_active: bool = True,
    ) -> dict[str, Any]:
        row = await self.repo.create_policy_assignment(
            target_type=target_type,
            target_id=target_id,
            owner_scope_type=owner_scope_type,
            owner_scope_id=owner_scope_id,
            profile_id=profile_id,
            inline_policy_document=inline_policy_document,
            approval_policy_id=approval_policy_id,
            actor_id=actor_id,
            is_active=is_active,
        )
        await _await_if_needed(
            emit_mcp_hub_audit(
                action="mcp_hub.policy_assignment.create",
                actor_id=actor_id,
                resource_type="mcp_policy_assignment",
                resource_id=str(row.get("id") or ""),
                metadata={"target_type": row.get("target_type"), "target_id": row.get("target_id")},
            )
        )
        return row

    async def list_policy_assignments(
        self,
        *,
        owner_scope_type: str | None = None,
        owner_scope_id: int | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
    ) -> list[dict[str, Any]]:
        return await self.repo.list_policy_assignments(
            owner_scope_type=owner_scope_type,
            owner_scope_id=owner_scope_id,
            target_type=target_type,
            target_id=target_id,
        )

    async def get_policy_assignment(self, assignment_id: int) -> dict[str, Any] | None:
        """Fetch a single policy assignment by id."""
        return await self.repo.get_policy_assignment(assignment_id)

    async def update_policy_assignment(
        self,
        assignment_id: int,
        *,
        actor_id: int | None = None,
        **update_fields: Any,
    ) -> dict[str, Any] | None:
        row = await self.repo.update_policy_assignment(
            assignment_id,
            actor_id=actor_id,
            **update_fields,
        )
        if row:
            await _await_if_needed(
                emit_mcp_hub_audit(
                    action="mcp_hub.policy_assignment.update",
                    actor_id=actor_id,
                    resource_type="mcp_policy_assignment",
                    resource_id=str(row.get("id") or assignment_id),
                    metadata={"target_type": row.get("target_type"), "target_id": row.get("target_id")},
                )
            )
        return row

    async def delete_policy_assignment(self, assignment_id: int, *, actor_id: int | None) -> bool:
        existing_override = await self.repo.get_policy_override_by_assignment(assignment_id)
        if existing_override:
            await self.repo.delete_policy_override_by_assignment(assignment_id)
            await _await_if_needed(
                emit_mcp_hub_audit(
                    action="mcp_hub.policy_override.delete",
                    actor_id=actor_id,
                    resource_type="mcp_policy_override",
                    resource_id=str(existing_override.get("id") or ""),
                    metadata={"assignment_id": assignment_id},
                )
            )
        deleted = await self.repo.delete_policy_assignment(assignment_id)
        if deleted:
            await _await_if_needed(
                emit_mcp_hub_audit(
                    action="mcp_hub.policy_assignment.delete",
                    actor_id=actor_id,
                    resource_type="mcp_policy_assignment",
                    resource_id=str(assignment_id),
                    metadata=None,
                )
            )
        return deleted

    async def get_policy_override(self, assignment_id: int) -> dict[str, Any] | None:
        """Fetch a single assignment-bound override by assignment id."""
        return await self.repo.get_policy_override_by_assignment(assignment_id)

    async def upsert_policy_override(
        self,
        assignment_id: int,
        *,
        override_policy_document: dict[str, Any],
        is_active: bool,
        broadens_access: bool,
        grant_authority_snapshot: dict[str, Any],
        actor_id: int | None,
    ) -> dict[str, Any] | None:
        row = await self.repo.upsert_policy_override(
            assignment_id,
            override_policy_document=override_policy_document,
            is_active=is_active,
            broadens_access=broadens_access,
            grant_authority_snapshot=grant_authority_snapshot,
            actor_id=actor_id,
        )
        if row:
            await _await_if_needed(
                emit_mcp_hub_audit(
                    action="mcp_hub.policy_override.upsert",
                    actor_id=actor_id,
                    resource_type="mcp_policy_override",
                    resource_id=str(row.get("id") or ""),
                    metadata={
                        "assignment_id": assignment_id,
                        "broadens_access": bool(row.get("broadens_access")),
                        "is_active": bool(row.get("is_active")),
                    },
                )
            )
        return row

    async def delete_policy_override(self, assignment_id: int, *, actor_id: int | None) -> bool:
        existing = await self.repo.get_policy_override_by_assignment(assignment_id)
        deleted = await self.repo.delete_policy_override_by_assignment(assignment_id)
        if deleted:
            await _await_if_needed(
                emit_mcp_hub_audit(
                    action="mcp_hub.policy_override.delete",
                    actor_id=actor_id,
                    resource_type="mcp_policy_override",
                    resource_id=str((existing or {}).get("id") or ""),
                    metadata={"assignment_id": assignment_id},
                )
            )
        return deleted

    async def create_approval_policy(
        self,
        *,
        name: str,
        owner_scope_type: str,
        owner_scope_id: int | None,
        mode: str,
        rules: dict[str, Any],
        actor_id: int | None,
        description: str | None = None,
        is_active: bool = True,
    ) -> dict[str, Any]:
        row = await self.repo.create_approval_policy(
            name=name,
            owner_scope_type=owner_scope_type,
            owner_scope_id=owner_scope_id,
            mode=mode,
            rules=rules,
            actor_id=actor_id,
            description=description,
            is_active=is_active,
        )
        await _await_if_needed(
            emit_mcp_hub_audit(
                action="mcp_hub.approval_policy.create",
                actor_id=actor_id,
                resource_type="mcp_approval_policy",
                resource_id=str(row.get("id") or ""),
                metadata={"name": row.get("name"), "mode": row.get("mode")},
            )
        )
        return row

    async def list_approval_policies(
        self,
        *,
        owner_scope_type: str | None = None,
        owner_scope_id: int | None = None,
    ) -> list[dict[str, Any]]:
        return await self.repo.list_approval_policies(
            owner_scope_type=owner_scope_type,
            owner_scope_id=owner_scope_id,
        )

    async def get_approval_policy(self, approval_policy_id: int) -> dict[str, Any] | None:
        """Fetch a single approval policy by id."""
        return await self.repo.get_approval_policy(approval_policy_id)

    async def update_approval_policy(
        self,
        approval_policy_id: int,
        *,
        actor_id: int | None = None,
        **update_fields: Any,
    ) -> dict[str, Any] | None:
        row = await self.repo.update_approval_policy(
            approval_policy_id,
            actor_id=actor_id,
            **update_fields,
        )
        if row:
            await _await_if_needed(
                emit_mcp_hub_audit(
                    action="mcp_hub.approval_policy.update",
                    actor_id=actor_id,
                    resource_type="mcp_approval_policy",
                    resource_id=str(row.get("id") or approval_policy_id),
                    metadata={"name": row.get("name"), "mode": row.get("mode")},
                )
            )
        return row

    async def delete_approval_policy(self, approval_policy_id: int, *, actor_id: int | None) -> bool:
        deleted = await self.repo.delete_approval_policy(approval_policy_id)
        if deleted:
            await _await_if_needed(
                emit_mcp_hub_audit(
                    action="mcp_hub.approval_policy.delete",
                    actor_id=actor_id,
                    resource_type="mcp_approval_policy",
                    resource_id=str(approval_policy_id),
                    metadata=None,
                )
            )
        return deleted

    async def record_approval_decision(
        self,
        *,
        approval_policy_id: int | None,
        context_key: str,
        conversation_id: str | None,
        tool_name: str,
        scope_key: str,
        decision: str,
        consume_on_match: bool = False,
        expires_at: Any = None,
        actor_id: int | None = None,
    ) -> dict[str, Any]:
        row = await self.repo.create_approval_decision(
            approval_policy_id=approval_policy_id,
            context_key=context_key,
            conversation_id=conversation_id,
            tool_name=tool_name,
            scope_key=scope_key,
            decision=decision,
            consume_on_match=consume_on_match,
            expires_at=expires_at,
            actor_id=actor_id,
        )
        await _await_if_needed(
            emit_mcp_hub_audit(
                action="mcp_hub.approval_decision.create",
                actor_id=actor_id,
                resource_type="mcp_approval_decision",
                resource_id=str(row.get("id") or ""),
                metadata={
                    "approval_policy_id": approval_policy_id,
                    "tool_name": tool_name,
                    "decision": decision,
                },
            )
        )
        return row

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
        allow_existing: bool = False,
    ) -> dict[str, Any]:
        """Create an external server definition, optionally allowing idempotent update behavior."""
        previous = await self.repo.get_external_server(server_id)
        if previous is not None and not allow_existing:
            raise McpHubConflictError(f"External server already exists: {server_id}")
        normalized_config = await self._validate_managed_external_auth_template_config(
            server_id=server_id,
            transport=transport,
            config=dict(config or {}),
        )
        row = await self.repo.upsert_external_server(
            server_id=server_id,
            name=name,
            transport=transport,
            config_json=json.dumps(normalized_config),
            owner_scope_type=owner_scope_type,
            owner_scope_id=owner_scope_id,
            enabled=enabled,
            server_source="managed",
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

    async def update_external_server(
        self,
        server_id: str,
        *,
        name: str | None = None,
        transport: str | None = None,
        config: dict[str, Any] | None = None,
        owner_scope_type: str | None = None,
        owner_scope_id: int | None = None,
        enabled: bool | None = None,
        actor_id: int | None,
    ) -> dict[str, Any]:
        """Update an existing external server definition."""
        existing = await self.repo.get_external_server(server_id)
        if not existing:
            raise ResourceNotFoundError("mcp_external_server", identifier=server_id)
        existing_config: dict[str, Any] = {}
        raw_config = existing.get("config_json")
        if isinstance(raw_config, dict):
            existing_config = dict(raw_config)
        elif isinstance(raw_config, str) and raw_config.strip():
            try:
                parsed = json.loads(raw_config)
                if isinstance(parsed, dict):
                    existing_config = parsed
            except (TypeError, ValueError):
                existing_config = {}
        next_transport = transport if transport is not None else str(existing.get("transport") or "")
        next_config = await self._validate_managed_external_auth_template_config(
            server_id=server_id,
            transport=next_transport,
            config=dict(config if config is not None else existing_config),
        )
        row = await self.repo.update_external_server(
            server_id,
            name=name if name is not None else str(existing.get("name") or ""),
            transport=next_transport,
            config_json=json.dumps(next_config),
            owner_scope_type=(
                owner_scope_type
                if owner_scope_type is not None
                else str(existing.get("owner_scope_type") or "global")
            ),
            owner_scope_id=owner_scope_id if owner_scope_id is not None else existing.get("owner_scope_id"),
            enabled=enabled if enabled is not None else bool(existing.get("enabled")),
            server_source=str(existing.get("server_source") or "managed"),
            legacy_source_ref=existing.get("legacy_source_ref"),
            superseded_by_server_id=existing.get("superseded_by_server_id"),
            actor_id=actor_id,
        )
        if not row:
            raise ResourceNotFoundError("mcp_external_server", identifier=server_id)
        await _await_if_needed(
            emit_mcp_hub_audit(
                action="mcp_hub.external_server.update",
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
        rows = await self.repo.list_external_servers(
            owner_scope_type=owner_scope_type,
            owner_scope_id=owner_scope_id,
        )
        managed_ids = {str(row.get("id") or "") for row in rows}
        legacy_rows = [
            {
                "id": str(item.get("id") or ""),
                "name": str(item.get("name") or ""),
                "enabled": bool(item.get("enabled", True)),
                "owner_scope_type": str(item.get("owner_scope_type") or owner_scope_type or "global"),
                "owner_scope_id": item.get("owner_scope_id", owner_scope_id),
                "transport": str(item.get("transport") or ""),
                "config_json": json.dumps(item.get("config") or {}),
                "config": dict(item.get("config") or {}),
                "secret_configured": bool(),
                "key_hint": None,
                "server_source": "legacy",
                "legacy_source_ref": item.get("legacy_source_ref"),
                "superseded_by_server_id": item.get("superseded_by_server_id"),
                "binding_count": 0,
                "runtime_executable": False,
                "auth_template_present": False,
                "auth_template_valid": False,
                "auth_template_blocked_reason": "no_auth_template",
                "credential_slots": [],
                "created_by": None,
                "updated_by": None,
                "created_at": None,
                "updated_at": None,
            }
            for item in await self._list_legacy_inventory()
            if str(item.get("id") or "") not in managed_ids
        ]
        managed_rows = [await self._attach_slot_summary(row) for row in rows]
        return [*managed_rows, *legacy_rows]

    async def list_external_server_credential_slots(
        self,
        *,
        server_id: str,
    ) -> list[dict[str, Any]]:
        server = await self.repo.get_external_server(server_id)
        if not server:
            raise ResourceNotFoundError("mcp_external_server", identifier=server_id)
        return await self.repo.list_external_server_credential_slots(server_id=server_id)

    async def create_external_server_credential_slot(
        self,
        *,
        server_id: str,
        slot_name: str,
        display_name: str,
        secret_kind: str,
        privilege_class: str,
        is_required: bool,
        actor_id: int | None,
    ) -> dict[str, Any]:
        server = await self.repo.get_external_server(server_id)
        if not server:
            raise ResourceNotFoundError("mcp_external_server", identifier=server_id)
        row = await self.repo.create_external_server_credential_slot(
            server_id=server_id,
            slot_name=slot_name,
            display_name=display_name,
            secret_kind=secret_kind,
            privilege_class=privilege_class,
            is_required=is_required,
            actor_id=actor_id,
        )
        await _await_if_needed(
            emit_mcp_hub_audit(
                action="mcp_hub.external_server_slot.create",
                actor_id=actor_id,
                resource_type="mcp_external_server",
                resource_id=server_id,
                metadata={"slot_name": row.get("slot_name")},
            )
        )
        return row

    async def update_external_server_credential_slot(
        self,
        *,
        server_id: str,
        slot_name: str,
        display_name: str | None = None,
        secret_kind: str | None = None,
        privilege_class: str | None = None,
        is_required: bool | None = None,
        actor_id: int | None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "server_id": server_id,
            "slot_name": slot_name,
            "actor_id": actor_id,
        }
        if display_name is not None:
            kwargs["display_name"] = display_name
        if secret_kind is not None:
            kwargs["secret_kind"] = secret_kind
        if privilege_class is not None:
            kwargs["privilege_class"] = privilege_class
        if is_required is not None:
            kwargs["is_required"] = is_required
        row = await self.repo.update_external_server_credential_slot(**kwargs)
        if not row:
            raise ResourceNotFoundError("mcp_external_server_slot", identifier=f"{server_id}/{slot_name}")
        await _await_if_needed(
            emit_mcp_hub_audit(
                action="mcp_hub.external_server_slot.update",
                actor_id=actor_id,
                resource_type="mcp_external_server",
                resource_id=server_id,
                metadata={"slot_name": row.get("slot_name")},
            )
        )
        return row

    async def delete_external_server_credential_slot(
        self,
        *,
        server_id: str,
        slot_name: str,
        actor_id: int | None,
    ) -> bool:
        deleted = await self.repo.delete_external_server_credential_slot(
            server_id=server_id,
            slot_name=slot_name,
        )
        if deleted:
            await _await_if_needed(
                emit_mcp_hub_audit(
                    action="mcp_hub.external_server_slot.delete",
                    actor_id=actor_id,
                    resource_type="mcp_external_server",
                    resource_id=server_id,
                    metadata={"slot_name": slot_name},
                )
            )
        return deleted

    async def set_external_server_slot_secret(
        self,
        *,
        server_id: str,
        slot_name: str,
        secret_value: str,
        actor_id: int | None,
    ) -> dict[str, Any]:
        slot = await self.repo.get_external_server_credential_slot(server_id=server_id, slot_name=slot_name)
        if not slot:
            raise ResourceNotFoundError("mcp_external_server_slot", identifier=f"{server_id}/{slot_name}")
        secret = (secret_value or "").strip()
        if not secret:
            raise BadRequestError("Secret value is required")
        secret_payload = build_secret_payload(secret)
        envelope = encrypt_byok_payload(secret_payload)
        stored = await self.repo.upsert_external_server_slot_secret(
            server_id=server_id,
            slot_name=slot_name,
            encrypted_blob=dumps_envelope(envelope),
            key_hint=key_hint_for_api_key(secret),
            actor_id=actor_id,
        )
        await _await_if_needed(
            emit_mcp_hub_audit(
                action="mcp_hub.external_server_slot_secret.update",
                actor_id=actor_id,
                resource_type="mcp_external_server",
                resource_id=server_id,
                metadata={"slot_name": slot_name, "key_hint": stored.get("key_hint")},
            )
        )
        return {
            "server_id": server_id,
            "slot_name": slot_name,
            "secret_configured": bool(stored),
            "key_hint": stored.get("key_hint"),
            "updated_at": stored.get("updated_at"),
        }

    async def clear_external_server_slot_secret(
        self,
        *,
        server_id: str,
        slot_name: str,
        actor_id: int | None,
    ) -> bool:
        cleared = await self.repo.clear_external_server_slot_secret(server_id=server_id, slot_name=slot_name)
        if cleared:
            await _await_if_needed(
                emit_mcp_hub_audit(
                    action="mcp_hub.external_server_slot_secret.clear",
                    actor_id=actor_id,
                    resource_type="mcp_external_server",
                    resource_id=server_id,
                    metadata={"slot_name": slot_name},
                )
            )
        return cleared

    async def get_external_server_auth_template(
        self,
        *,
        server_id: str,
    ) -> dict[str, Any]:
        server = await self.repo.get_external_server(server_id)
        if not server:
            raise ResourceNotFoundError("mcp_external_server", identifier=server_id)
        config = dict(server.get("config") or {})
        auth = dict(config.get("auth") or {})
        try:
            mappings = ManagedExternalAuthBridge._extract_template_mappings(auth) or []
        except ValueError as exc:
            raise BadRequestError(str(exc)) from exc
        return {
            "mode": "template",
            "mappings": mappings,
        }

    async def update_external_server_auth_template(
        self,
        *,
        server_id: str,
        auth_template: dict[str, Any],
        actor_id: int | None,
    ) -> dict[str, Any]:
        server = await self.repo.get_external_server(server_id)
        if not server:
            raise ResourceNotFoundError("mcp_external_server", identifier=server_id)
        existing_config: dict[str, Any] = dict(server.get("config") or {})
        next_config = dict(existing_config)
        next_config["auth"] = {
            "mode": "template",
            "mappings": list(auth_template.get("mappings") or []),
        }
        await self.update_external_server(
            server_id,
            config=next_config,
            actor_id=actor_id,
        )
        return await self.get_external_server_auth_template(server_id=server_id)

    async def import_legacy_external_server(
        self,
        *,
        server_id: str,
        actor_id: int | None,
    ) -> dict[str, Any]:
        legacy = await self._get_legacy_inventory_item(server_id)
        if legacy is None:
            raise ResourceNotFoundError("mcp_external_server_legacy", identifier=server_id)

        row = await self.create_external_server(
            server_id=server_id,
            name=str(legacy.get("name") or server_id),
            transport=str(legacy.get("transport") or "websocket"),
            config=self._normalize_imported_external_config(dict(legacy.get("config") or {})),
            owner_scope_type=str(legacy.get("owner_scope_type") or "global"),
            owner_scope_id=legacy.get("owner_scope_id"),
            enabled=bool(legacy.get("enabled", True)),
            actor_id=actor_id,
            allow_existing=True,
        )
        updated = await self.repo.update_external_server(
            server_id,
            name=str(row.get("name") or server_id),
            transport=str(row.get("transport") or legacy.get("transport") or "websocket"),
            config_json=json.dumps(dict(row.get("config") or {})),
            owner_scope_type=str(row.get("owner_scope_type") or "global"),
            owner_scope_id=row.get("owner_scope_id"),
            enabled=bool(row.get("enabled")),
            server_source="managed",
            legacy_source_ref=legacy.get("legacy_source_ref"),
            superseded_by_server_id=None,
            actor_id=actor_id,
        )
        return updated or row

    async def list_profile_credential_bindings(
        self,
        *,
        profile_id: int,
    ) -> list[dict[str, Any]]:
        await self._resolve_binding_target(binding_target_type="profile", binding_target_id=profile_id)
        return await self.repo.list_credential_bindings(
            binding_target_type="profile",
            binding_target_id=str(profile_id),
        )

    async def upsert_profile_credential_binding(
        self,
        *,
        profile_id: int,
        external_server_id: str,
        slot_name: str | None = None,
        actor_id: int | None,
    ) -> dict[str, Any]:
        target_row = await self._resolve_binding_target(binding_target_type="profile", binding_target_id=profile_id)
        server_row = await self.repo.get_external_server(external_server_id)
        if not server_row:
            raise ResourceNotFoundError("mcp_external_server", identifier=external_server_id)
        self._validate_binding_scope(server_row=server_row, target_row=target_row)
        row = await self.repo.upsert_credential_binding(
            binding_target_type="profile",
            binding_target_id=str(profile_id),
            external_server_id=external_server_id,
            slot_name=slot_name,
            credential_ref="slot" if slot_name else "server",
            binding_mode="grant",
            usage_rules={},
            actor_id=actor_id,
        )
        await _await_if_needed(
            emit_mcp_hub_audit(
                action="mcp_hub.profile_credential_binding.upsert",
                actor_id=actor_id,
                resource_type="mcp_permission_profile",
                resource_id=str(profile_id),
                metadata={"external_server_id": external_server_id, "slot_name": slot_name, "binding_mode": "grant"},
            )
        )
        return row

    async def delete_profile_credential_binding(
        self,
        *,
        profile_id: int,
        external_server_id: str,
        slot_name: str | None = None,
        actor_id: int | None,
    ) -> bool:
        await self._resolve_binding_target(binding_target_type="profile", binding_target_id=profile_id)
        deleted = await self.repo.delete_credential_binding(
            binding_target_type="profile",
            binding_target_id=str(profile_id),
            external_server_id=external_server_id,
            slot_name=slot_name,
        )
        if deleted:
            await _await_if_needed(
                emit_mcp_hub_audit(
                action="mcp_hub.profile_credential_binding.delete",
                actor_id=actor_id,
                resource_type="mcp_permission_profile",
                resource_id=str(profile_id),
                metadata={"external_server_id": external_server_id, "slot_name": slot_name},
            )
        )
        return deleted

    async def list_assignment_credential_bindings(
        self,
        *,
        assignment_id: int,
    ) -> list[dict[str, Any]]:
        await self._resolve_binding_target(binding_target_type="assignment", binding_target_id=assignment_id)
        return await self.repo.list_credential_bindings(
            binding_target_type="assignment",
            binding_target_id=str(assignment_id),
        )

    async def upsert_assignment_credential_binding(
        self,
        *,
        assignment_id: int,
        external_server_id: str,
        slot_name: str | None = None,
        binding_mode: str,
        actor_id: int | None,
    ) -> dict[str, Any]:
        target_row = await self._resolve_binding_target(binding_target_type="assignment", binding_target_id=assignment_id)
        server_row = await self.repo.get_external_server(external_server_id)
        if not server_row:
            raise ResourceNotFoundError("mcp_external_server", identifier=external_server_id)
        self._validate_binding_scope(server_row=server_row, target_row=target_row)
        row = await self.repo.upsert_credential_binding(
            binding_target_type="assignment",
            binding_target_id=str(assignment_id),
            external_server_id=external_server_id,
            slot_name=slot_name,
            credential_ref="slot" if slot_name else "server",
            binding_mode=binding_mode,
            usage_rules={},
            actor_id=actor_id,
        )
        await _await_if_needed(
            emit_mcp_hub_audit(
                action="mcp_hub.assignment_credential_binding.upsert",
                actor_id=actor_id,
                resource_type="mcp_policy_assignment",
                resource_id=str(assignment_id),
                metadata={"external_server_id": external_server_id, "slot_name": slot_name, "binding_mode": binding_mode},
            )
        )
        return row

    async def delete_assignment_credential_binding(
        self,
        *,
        assignment_id: int,
        external_server_id: str,
        slot_name: str | None = None,
        actor_id: int | None,
    ) -> bool:
        await self._resolve_binding_target(binding_target_type="assignment", binding_target_id=assignment_id)
        deleted = await self.repo.delete_credential_binding(
            binding_target_type="assignment",
            binding_target_id=str(assignment_id),
            external_server_id=external_server_id,
            slot_name=slot_name,
        )
        if deleted:
            await _await_if_needed(
                emit_mcp_hub_audit(
                action="mcp_hub.assignment_credential_binding.delete",
                actor_id=actor_id,
                resource_type="mcp_policy_assignment",
                resource_id=str(assignment_id),
                metadata={"external_server_id": external_server_id, "slot_name": slot_name},
            )
        )
        return deleted

    async def resolve_effective_external_access(
        self,
        *,
        assignment_id: int,
        actor_id: int | None,
    ) -> dict[str, Any]:
        resolver = McpHubExternalAccessResolver(repo=self.repo)
        assignment = await self.repo.get_policy_assignment(int(assignment_id))
        policy_document: dict[str, Any] = {}
        if assignment:
            profile_id = assignment.get("profile_id")
            if profile_id is not None:
                profile = await self.repo.get_permission_profile(int(profile_id))
                if profile and bool(profile.get("is_active", True)):
                    policy_document = dict(profile.get("policy_document") or {})
            inline_policy = dict((assignment or {}).get("inline_policy_document") or {})
            policy_document.update(inline_policy)
            override_row = await self.repo.get_policy_override_by_assignment(int(assignment_id))
            if override_row and bool(override_row.get("is_active", True)):
                policy_document.update(dict(override_row.get("override_policy_document") or {}))
        effective_policy = {"capabilities": list(policy_document.get("capabilities") or [])}
        summary = await resolver.resolve(
            assignment_id=int(assignment_id),
            effective_policy=effective_policy,
        )
        await _await_if_needed(
            emit_mcp_hub_audit(
                action="mcp_hub.external_access.resolve",
                actor_id=actor_id,
                resource_type="mcp_policy_assignment",
                resource_id=str(assignment_id),
                metadata={"server_count": len(summary.get("servers") or [])},
            )
        )
        return summary

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
            raise ResourceNotFoundError("mcp_external_server", identifier=server_id)

        secret = (secret_value or "").strip()
        if not secret:
            raise BadRequestError("Secret value is required")

        slots = await self.repo.list_external_server_credential_slots(server_id=server_id)
        if slots:
            default_slot = await self.repo.get_external_server_default_slot(server_id=server_id)
            if default_slot is None:
                raise BadRequestError("Server-level secret alias is only valid for default-slot servers")
            slot_row = await self.set_external_server_slot_secret(
                server_id=server_id,
                slot_name=str(default_slot.get("slot_name") or ""),
                secret_value=secret,
                actor_id=actor_id,
            )
            stored = await self.repo.upsert_external_secret(
                server_id=server_id,
                encrypted_blob=dumps_envelope(encrypt_byok_payload(build_secret_payload(secret))),
                key_hint=key_hint_for_api_key(secret),
                actor_id=actor_id,
            )
            return {
                "server_id": server_id,
                "slot_name": slot_row.get("slot_name"),
                "secret_configured": bool(stored),
                "key_hint": stored.get("key_hint"),
                "updated_at": stored.get("updated_at"),
            }

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
        secret_configured = bool(stored)
        return {
            "server_id": server_id,
            "secret_configured": secret_configured,
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
