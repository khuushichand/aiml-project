from __future__ import annotations

from copy import deepcopy
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import check_rate_limit, get_auth_principal
from tldw_Server_API.app.api.v1.schemas.mcp_hub_schemas import (
    ACPProfileCreateRequest,
    ACPProfileResponse,
    ACPProfileUpdateRequest,
    ApprovalDecisionCreateRequest,
    ApprovalDecisionResponse,
    ApprovalPolicyCreateRequest,
    ApprovalPolicyResponse,
    ApprovalPolicyUpdateRequest,
    AssignmentCredentialBindingUpsertRequest,
    CredentialBindingResponse,
    EffectivePolicyResponse,
    EffectiveExternalAccessResponse,
    ExternalSecretSetRequest,
    ExternalSecretSetResponse,
    ExternalServerAuthTemplateResponse,
    ExternalServerAuthTemplateUpdateRequest,
    ExternalServerCredentialSlotCreateRequest,
    ExternalServerCredentialSlotResponse,
    ExternalServerCredentialSlotUpdateRequest,
    ExternalServerSlotSecretSetResponse,
    ExternalServerCreateRequest,
    ExternalServerResponse,
    ExternalServerUpdateRequest,
    MCPHubDeleteResponse,
    PermissionProfileCreateRequest,
    PermissionProfileResponse,
    PermissionProfileUpdateRequest,
    PolicyAssignmentCreateRequest,
    PolicyAssignmentResponse,
    PolicyAssignmentUpdateRequest,
    PolicyOverrideResponse,
    PolicyOverrideUpsertRequest,
    ToolRegistryEntryResponse,
    ToolRegistryModuleResponse,
    ToolRegistrySummaryResponse,
)
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.AuthNZ.permissions import SYSTEM_CONFIGURE
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.AuthNZ.repos.mcp_hub_repo import McpHubRepo
from tldw_Server_API.app.core.config import config
from tldw_Server_API.app.core.exceptions import BadRequestError, ResourceNotFoundError
from tldw_Server_API.app.services.mcp_hub_external_legacy_inventory import (
    McpHubExternalLegacyInventoryService,
)
from tldw_Server_API.app.services.mcp_hub_policy_resolver import McpHubPolicyResolver, get_mcp_hub_policy_resolver
from tldw_Server_API.app.services.mcp_hub_service import McpHubConflictError, McpHubService
from tldw_Server_API.app.services.mcp_hub_tool_registry import McpHubToolRegistryService

router = APIRouter(prefix="/mcp/hub", tags=["mcp-hub"], dependencies=[Depends(check_rate_limit)])

_MCP_HUB_ADMIN_PERMISSIONS = frozenset({SYSTEM_CONFIGURE, "*"})
_VALID_SCOPE_TYPES = frozenset({"global", "org", "team", "user"})
_CAPABILITY_GRANT_PERMISSIONS = {
    "credentials.use": "grant.credentials.use",
    "filesystem.delete": "grant.filesystem.delete",
    "filesystem.read": "grant.filesystem.read",
    "filesystem.write": "grant.filesystem.write",
    "mcp.server.connect": "grant.mcp.server.connect",
    "network.external": "grant.network.external",
    "process.execute": "grant.process.execute",
    "tool.invoke": "grant.tool.invoke",
}
_TOOL_GRANT_KEYS = ("allowed_tools", "tool_patterns", "tool_names")
_UNION_POLICY_KEYS = frozenset({"allowed_tools", "denied_tools", "tool_names", "tool_patterns", "capabilities"})
_SUPPORTED_APPROVAL_DURATIONS = frozenset({"once", "session", "conversation"})
_DEFAULT_SCOPED_APPROVAL_TTL_MINUTES = 480


async def get_mcp_hub_service() -> McpHubService:
    """Resolve MCP Hub service with storage bootstrap checks."""
    pool = await get_db_pool()
    repo = McpHubRepo(pool)
    await repo.ensure_tables()
    cfg = config
    inventory_service = McpHubExternalLegacyInventoryService(
        config_path=str(
            getattr(cfg, "external_servers_config_path", None)
            or "tldw_Server_API/Config_Files/mcp_external_servers.yaml"
        )
    )
    return McpHubService(repo, legacy_inventory_service=inventory_service)


async def get_mcp_hub_policy_resolver_dep() -> McpHubPolicyResolver:
    """Resolve MCP Hub policy resolver for effective policy previews."""
    return await get_mcp_hub_policy_resolver()


async def get_mcp_hub_tool_registry_dep() -> McpHubToolRegistryService:
    """Resolve the derived MCP Hub tool registry service."""
    return McpHubToolRegistryService()


def _load_json_object(raw: Any) -> dict[str, Any]:
    """Parse JSON-like values into a dict, returning empty dict on decode failures."""
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except (TypeError, ValueError):
            logger.debug("MCP hub payload JSON decode failed")
            return {}
    return {}


def _is_mutation_allowed(principal: AuthPrincipal) -> bool:
    """Return True when the principal is allowed to mutate MCP Hub configuration."""
    roles = {
        str(role).strip().lower()
        for role in (principal.roles or [])
        if str(role).strip()
    }
    if "admin" in roles:
        return True
    permissions = {
        str(permission).strip().lower()
        for permission in (principal.permissions or [])
        if str(permission).strip()
    }
    required = {perm.lower() for perm in _MCP_HUB_ADMIN_PERMISSIONS}
    return bool(permissions & required)


def _require_mutation_permission(principal: AuthPrincipal) -> None:
    """Require mutation permission for MCP Hub write operations."""
    if _is_mutation_allowed(principal):
        return
    raise HTTPException(status_code=403, detail=f"{SYSTEM_CONFIGURE} permission required")


def _require_grant_authority(principal: AuthPrincipal, policy_document: dict[str, Any]) -> None:
    """Require capability grant authority for the requested policy document."""
    roles = {
        str(role).strip().lower()
        for role in (principal.roles or [])
        if str(role).strip()
    }
    if "admin" in roles:
        return

    granted = {
        str(permission).strip().lower()
        for permission in (principal.permissions or [])
        if str(permission).strip()
    }
    if "*" in granted:
        return

    raw_capabilities = _as_str_list(policy_document.get("capabilities"))
    capabilities = {
        str(capability).strip().lower()
        for capability in raw_capabilities
        if str(capability).strip()
    }
    if any(
        str(entry).strip()
        for key in _TOOL_GRANT_KEYS
        for entry in _as_str_list(policy_document.get(key))
    ):
        capabilities.add("tool.invoke")
    missing = [
        required
        for capability in sorted(capabilities)
        if (required := _CAPABILITY_GRANT_PERMISSIONS.get(capability)) and required.lower() not in granted
    ]
    if missing:
        raise HTTPException(
            status_code=403,
            detail=f"Grant authority required: {', '.join(missing)}",
        )


def _as_str_list(value: Any) -> list[str]:
    """Normalize a loose scalar-or-sequence value into a cleaned string list."""
    if isinstance(value, str):
        cleaned = value.strip()
        return [cleaned] if cleaned else []
    if not isinstance(value, (list, tuple, set)):
        return []
    out: list[str] = []
    for entry in value:
        cleaned = str(entry or "").strip()
        if cleaned:
            out.append(cleaned)
    return out


def _unique(items: list[str]) -> list[str]:
    """Preserve order while removing duplicate string values."""
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _merge_policy_documents(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Merge overlay policy fields into a base document using union semantics for allowlists."""
    merged = deepcopy(base)
    for key, value in overlay.items():
        if key in _UNION_POLICY_KEYS:
            merged[key] = _unique(_as_str_list(merged.get(key)) + _as_str_list(value))
            continue
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = _merge_policy_documents(
                dict(merged.get(key) or {}),
                dict(value or {}),
            )
            continue
        merged[key] = deepcopy(value)
    return merged


def _tool_grant_entries(policy_document: dict[str, Any]) -> set[str]:
    """Collect every tool-grant entry across the supported allowlist keys."""
    entries: set[str] = set()
    for key in _TOOL_GRANT_KEYS:
        entries.update(_as_str_list(policy_document.get(key)))
    return entries


def _grant_authority_delta(base_policy_document: dict[str, Any], merged_policy_document: dict[str, Any]) -> dict[str, Any]:
    """Extract the broadened-access delta that requires explicit grant authority."""
    base_capabilities = {entry.lower() for entry in _as_str_list(base_policy_document.get("capabilities"))}
    merged_capabilities = {entry.lower() for entry in _as_str_list(merged_policy_document.get("capabilities"))}
    next_document: dict[str, Any] = {}

    extra_capabilities = sorted(merged_capabilities - base_capabilities)
    if extra_capabilities:
        next_document["capabilities"] = extra_capabilities

    base_tools = _tool_grant_entries(base_policy_document)
    merged_tools = _tool_grant_entries(merged_policy_document)
    extra_tools = sorted(merged_tools - base_tools)
    if extra_tools:
        next_document["allowed_tools"] = extra_tools

    return next_document


def _grant_authority_snapshot(principal: AuthPrincipal, delta_document: dict[str, Any]) -> dict[str, Any]:
    """Capture granted and required permissions for an override broadening audit record."""
    granted_permissions = sorted(
        {
            str(permission).strip().lower()
            for permission in (principal.permissions or [])
            if str(permission).strip()
        }
    )
    required_permissions = sorted(
        {
            required
            for capability in {
                str(capability).strip().lower()
                for capability in _as_str_list(delta_document.get("capabilities"))
            }
            if (required := _CAPABILITY_GRANT_PERMISSIONS.get(capability))
        }
    )
    if _tool_grant_entries(delta_document):
        required_permissions.append(_CAPABILITY_GRANT_PERMISSIONS["tool.invoke"])
    return {
        "required_permissions": _unique(required_permissions),
        "granted_permissions": granted_permissions,
    }


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


def _resolve_visible_scope_filters(
    *,
    principal: AuthPrincipal,
    owner_scope_type: str | None,
    owner_scope_id: int | None,
) -> list[tuple[str | None, int | None]]:
    """
    Resolve list query filters constrained to scopes visible to the authenticated principal.

    Returns one or more `(scope_type, scope_id)` filters. A `scope_type` of `None` means
    unrestricted query (admin-like contexts only).
    """
    scope_type = owner_scope_type.strip().lower() if owner_scope_type else None
    if scope_type is not None and scope_type not in _VALID_SCOPE_TYPES:
        raise HTTPException(status_code=422, detail="Invalid owner_scope_type")

    if _is_mutation_allowed(principal):
        if scope_type is None:
            if owner_scope_id is not None:
                raise HTTPException(status_code=422, detail="owner_scope_id requires owner_scope_type")
            return [(None, None)]
        if scope_type == "global":
            if owner_scope_id is not None:
                raise HTTPException(status_code=422, detail="global scope cannot include owner_scope_id")
            return [("global", None)]
        if owner_scope_id is None:
            raise HTTPException(status_code=422, detail=f"{scope_type} scope requires owner_scope_id")
        return [(scope_type, int(owner_scope_id))]

    user_id = int(principal.user_id) if principal.user_id is not None else None
    org_ids = _collect_scope_ids(principal.org_ids, principal.active_org_id)
    team_ids = _collect_scope_ids(principal.team_ids, principal.active_team_id)

    if scope_type is None:
        if owner_scope_id is not None:
            raise HTTPException(status_code=422, detail="owner_scope_id requires owner_scope_type")
        filters: list[tuple[str | None, int | None]] = [("global", None)]
        if user_id is not None:
            filters.append(("user", user_id))
        filters.extend(("org", org_id) for org_id in org_ids)
        filters.extend(("team", team_id) for team_id in team_ids)
        return filters

    if scope_type == "global":
        if owner_scope_id is not None:
            raise HTTPException(status_code=422, detail="global scope cannot include owner_scope_id")
        return [("global", None)]

    if scope_type == "user":
        target_user_id = int(owner_scope_id) if owner_scope_id is not None else user_id
        if target_user_id is None or user_id is None or target_user_id != user_id:
            raise HTTPException(status_code=403, detail="Forbidden scope filter")
        return [("user", user_id)]

    if scope_type == "org":
        if owner_scope_id is None:
            return [("org", org_id) for org_id in org_ids]
        if int(owner_scope_id) not in set(org_ids):
            raise HTTPException(status_code=403, detail="Forbidden scope filter")
        return [("org", int(owner_scope_id))]

    if scope_type == "team":
        if owner_scope_id is None:
            return [("team", team_id) for team_id in team_ids]
        if int(owner_scope_id) not in set(team_ids):
            raise HTTPException(status_code=403, detail="Forbidden scope filter")
        return [("team", int(owner_scope_id))]

    raise HTTPException(status_code=422, detail="Invalid owner_scope_type")


def _dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate row dictionaries by `id` while preserving final-write wins semantics."""
    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        row_id = str(row.get("id") or "")
        if not row_id:
            continue
        deduped[row_id] = row
    return list(deduped.values())


def _profile_row_to_response(row: dict[str, Any]) -> ACPProfileResponse:
    return ACPProfileResponse(
        id=int(row.get("id")),
        name=str(row.get("name") or ""),
        description=row.get("description"),
        owner_scope_type=str(row.get("owner_scope_type") or "global"),
        owner_scope_id=row.get("owner_scope_id"),
        profile=_load_json_object(row.get("profile_json")),
        is_active=bool(row.get("is_active")),
        created_by=row.get("created_by"),
        updated_by=row.get("updated_by"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def _external_row_to_response(row: dict[str, Any]) -> ExternalServerResponse:
    slots = [
        ExternalServerCredentialSlotResponse.model_validate(slot)
        for slot in (row.get("credential_slots") or [])
        if isinstance(slot, dict)
    ]
    return ExternalServerResponse(
        id=str(row.get("id") or ""),
        name=str(row.get("name") or ""),
        enabled=bool(row.get("enabled")),
        owner_scope_type=str(row.get("owner_scope_type") or "global"),
        owner_scope_id=row.get("owner_scope_id"),
        transport=str(row.get("transport") or ""),
        config=_load_json_object(row.get("config_json") if row.get("config_json") is not None else row.get("config")),
        secret_configured=bool(row.get("secret_configured")),
        key_hint=row.get("key_hint"),
        server_source=str(row.get("server_source") or "managed"),
        legacy_source_ref=row.get("legacy_source_ref"),
        superseded_by_server_id=row.get("superseded_by_server_id"),
        binding_count=int(row.get("binding_count") or 0),
        runtime_executable=bool(
            row.get("runtime_executable")
            if row.get("runtime_executable") is not None
            else True
        ),
        auth_template_present=bool(row.get("auth_template_present")),
        auth_template_valid=bool(row.get("auth_template_valid")),
        auth_template_blocked_reason=row.get("auth_template_blocked_reason"),
        credential_slots=slots,
        created_by=row.get("created_by"),
        updated_by=row.get("updated_by"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def _permission_profile_row_to_response(row: dict[str, Any]) -> PermissionProfileResponse:
    return PermissionProfileResponse(
        id=int(row.get("id")),
        name=str(row.get("name") or ""),
        description=row.get("description"),
        owner_scope_type=str(row.get("owner_scope_type") or "global"),
        owner_scope_id=row.get("owner_scope_id"),
        mode=str(row.get("mode") or "custom"),
        policy_document=_load_json_object(row.get("policy_document")),
        is_active=bool(row.get("is_active")),
        created_by=row.get("created_by"),
        updated_by=row.get("updated_by"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def _policy_assignment_row_to_response(row: dict[str, Any]) -> PolicyAssignmentResponse:
    return PolicyAssignmentResponse(
        id=int(row.get("id")),
        target_type=str(row.get("target_type") or "default"),
        target_id=row.get("target_id"),
        owner_scope_type=str(row.get("owner_scope_type") or "global"),
        owner_scope_id=row.get("owner_scope_id"),
        profile_id=row.get("profile_id"),
        inline_policy_document=_load_json_object(row.get("inline_policy_document")),
        approval_policy_id=row.get("approval_policy_id"),
        is_active=bool(row.get("is_active")),
        has_override=bool(row.get("has_override")),
        override_id=row.get("override_id"),
        override_active=bool(row.get("override_active")),
        override_updated_at=row.get("override_updated_at"),
        created_by=row.get("created_by"),
        updated_by=row.get("updated_by"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def _policy_override_row_to_response(row: dict[str, Any]) -> PolicyOverrideResponse:
    return PolicyOverrideResponse(
        id=int(row.get("id")),
        assignment_id=int(row.get("assignment_id")),
        override_policy_document=_load_json_object(row.get("override_policy_document")),
        is_active=bool(row.get("is_active")),
        created_by=row.get("created_by"),
        updated_by=row.get("updated_by"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def _approval_policy_row_to_response(row: dict[str, Any]) -> ApprovalPolicyResponse:
    return ApprovalPolicyResponse(
        id=int(row.get("id")),
        name=str(row.get("name") or ""),
        description=row.get("description"),
        owner_scope_type=str(row.get("owner_scope_type") or "global"),
        owner_scope_id=row.get("owner_scope_id"),
        mode=str(row.get("mode") or "allow_silently"),
        rules=_load_json_object(row.get("rules")),
        is_active=bool(row.get("is_active")),
        created_by=row.get("created_by"),
        updated_by=row.get("updated_by"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def _approval_decision_row_to_response(row: dict[str, Any]) -> ApprovalDecisionResponse:
    return ApprovalDecisionResponse(
        id=int(row.get("id")),
        approval_policy_id=row.get("approval_policy_id"),
        context_key=str(row.get("context_key") or ""),
        conversation_id=row.get("conversation_id"),
        tool_name=str(row.get("tool_name") or ""),
        scope_key=str(row.get("scope_key") or ""),
        decision=str(row.get("decision") or "denied"),
        consume_on_match=bool(row.get("consume_on_match")),
        expires_at=row.get("expires_at"),
        consumed_at=row.get("consumed_at"),
        created_by=row.get("created_by"),
        created_at=row.get("created_at"),
    )


def _extract_context_key_user_id(context_key: str) -> int | None:
    match = re.search(r"(?:^|\|)user:(\d+)(?:\||$)", str(context_key))
    if not match:
        return None
    try:
        return int(match.group(1))
    except (TypeError, ValueError):
        return None


def _validated_duration_options(rules: dict[str, Any] | None) -> list[str]:
    """Return supported approval durations from policy rules or raise for unsupported entries."""
    raw = (rules or {}).get("duration_options")
    if raw is None:
        return ["once", "session"]
    if not isinstance(raw, list):
        raise HTTPException(status_code=422, detail="rules.duration_options must be a list")
    out: list[str] = []
    seen: set[str] = set()
    for entry in raw:
        value = str(entry or "").strip().lower()
        if not value:
            continue
        if value not in _SUPPORTED_APPROVAL_DURATIONS:
            raise HTTPException(
                status_code=422,
                detail=f"rules.duration_options contains unsupported duration '{value}'",
            )
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out or ["once", "session"]


def _normalized_approval_rules(rules: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize approval policy rules to the server-supported shape."""
    normalized = dict(rules or {})
    normalized["duration_options"] = _validated_duration_options(normalized)
    return normalized


def _approval_ttl_minutes(rules: dict[str, Any], duration: str) -> int:
    """Resolve a bounded TTL for scoped approvals."""
    duration_key = str(duration or "").strip().lower()
    raw = rules.get(f"{duration_key}_ttl_minutes")
    if raw is None:
        raw = rules.get("scoped_ttl_minutes")
    try:
        value = int(raw) if raw is not None else _DEFAULT_SCOPED_APPROVAL_TTL_MINUTES
    except (TypeError, ValueError):
        value = _DEFAULT_SCOPED_APPROVAL_TTL_MINUTES
    return max(1, min(value, 24 * 60))


def _approval_decision_lifetime(
    *,
    decision: str,
    duration: str,
    conversation_id: str | None,
    rules: dict[str, Any],
) -> tuple[bool, datetime | None]:
    """Compute server-side approval persistence from a validated duration selection."""
    normalized_decision = str(decision or "").strip().lower()
    normalized_duration = str(duration or "").strip().lower()
    if normalized_decision != "approved":
        return False, datetime.now(timezone.utc)
    if normalized_duration == "once":
        return True, None
    if normalized_duration in {"session", "conversation"}:
        if not str(conversation_id or "").strip():
            raise HTTPException(status_code=422, detail="conversation_id is required for scoped approvals")
        ttl_minutes = _approval_ttl_minutes(rules, normalized_duration)
        return False, datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
    raise HTTPException(status_code=422, detail=f"Unsupported approval duration '{normalized_duration}'")


async def _get_visible_policy_assignment_or_404(
    *,
    assignment_id: int,
    principal: AuthPrincipal,
    svc: McpHubService,
) -> dict[str, Any]:
    """Fetch a policy assignment and ensure the principal can access its owner scope."""
    assignment = await svc.get_policy_assignment(assignment_id)
    if assignment is None:
        raise ResourceNotFoundError("mcp_policy_assignment", identifier=str(assignment_id))
    _resolve_visible_scope_filters(
        principal=principal,
        owner_scope_type=str(assignment.get("owner_scope_type") or "global"),
        owner_scope_id=assignment.get("owner_scope_id"),
    )
    return assignment


async def _get_visible_permission_profile_or_404(
    *,
    profile_id: int,
    principal: AuthPrincipal,
    svc: McpHubService,
) -> dict[str, Any]:
    """Fetch a permission profile and ensure the principal can access its owner scope."""
    profile = await svc.get_permission_profile(profile_id)
    if profile is None:
        raise ResourceNotFoundError("mcp_permission_profile", identifier=str(profile_id))
    _resolve_visible_scope_filters(
        principal=principal,
        owner_scope_type=str(profile.get("owner_scope_type") or "global"),
        owner_scope_id=profile.get("owner_scope_id"),
    )
    return profile


async def _assignment_base_policy_document(
    *,
    svc: McpHubService,
    assignment: dict[str, Any],
) -> tuple[int | None, dict[str, Any]]:
    """Resolve the merged profile-plus-inline base policy for an assignment."""
    base_document: dict[str, Any] = {}
    profile_id = assignment.get("profile_id")
    if profile_id is not None:
        profile_row = await svc.get_permission_profile(int(profile_id))
        if profile_row and bool(profile_row.get("is_active", True)):
            base_document = _merge_policy_documents(
                base_document,
                _load_json_object(profile_row.get("policy_document")),
            )
    base_document = _merge_policy_documents(
        base_document,
        _load_json_object(assignment.get("inline_policy_document")),
    )
    return (int(profile_id) if profile_id is not None else None, base_document)


def _binding_row_to_response(row: dict[str, Any]) -> CredentialBindingResponse:
    return CredentialBindingResponse(
        id=int(row.get("id")),
        binding_target_type=str(row.get("binding_target_type") or ""),
        binding_target_id=str(row.get("binding_target_id") or ""),
        external_server_id=str(row.get("external_server_id") or ""),
        slot_name=(
            str(row.get("slot_name") or "").strip()
            if str(row.get("slot_name") or "").strip()
            else None
        ),
        credential_ref=str(row.get("credential_ref") or "server"),
        binding_mode=str(row.get("binding_mode") or "grant"),
        usage_rules=_load_json_object(row.get("usage_rules")),
        created_by=row.get("created_by"),
        updated_by=row.get("updated_by"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


@router.get("/tool-registry", response_model=list[ToolRegistryEntryResponse])
async def list_tool_registry(
    _principal: AuthPrincipal = Depends(get_auth_principal),
    registry: McpHubToolRegistryService = Depends(get_mcp_hub_tool_registry_dep),
) -> list[ToolRegistryEntryResponse]:
    """List normalized MCP tool metadata derived from the live module registry."""
    return [ToolRegistryEntryResponse.model_validate(row) for row in await registry.list_entries()]


@router.get("/tool-registry/modules", response_model=list[ToolRegistryModuleResponse])
async def list_tool_registry_modules(
    _principal: AuthPrincipal = Depends(get_auth_principal),
    registry: McpHubToolRegistryService = Depends(get_mcp_hub_tool_registry_dep),
) -> list[ToolRegistryModuleResponse]:
    """List grouped MCP tool metadata summaries by module."""
    return [ToolRegistryModuleResponse.model_validate(row) for row in await registry.list_modules()]


@router.get("/tool-registry/summary", response_model=ToolRegistrySummaryResponse)
async def get_tool_registry_summary(
    _principal: AuthPrincipal = Depends(get_auth_principal),
    registry: McpHubToolRegistryService = Depends(get_mcp_hub_tool_registry_dep),
) -> ToolRegistrySummaryResponse:
    """Return tool entries and module summaries from a single registry enumeration."""
    summary = await registry.get_summary()
    return ToolRegistrySummaryResponse(
        entries=[ToolRegistryEntryResponse.model_validate(row) for row in summary.get("entries", [])],
        modules=[ToolRegistryModuleResponse.model_validate(row) for row in summary.get("modules", [])],
    )


@router.post("/permission-profiles", response_model=PermissionProfileResponse, status_code=201)
async def create_permission_profile(
    payload: PermissionProfileCreateRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> PermissionProfileResponse:
    """Create a new permission profile within the provided owner scope."""
    _require_mutation_permission(principal)
    _require_grant_authority(principal, payload.policy_document)
    row = await svc.create_permission_profile(
        name=payload.name,
        description=payload.description,
        owner_scope_type=payload.owner_scope_type,
        owner_scope_id=payload.owner_scope_id,
        mode=payload.mode,
        policy_document=payload.policy_document,
        is_active=payload.is_active,
        actor_id=principal.user_id,
    )
    return _permission_profile_row_to_response(row)


@router.get("/permission-profiles", response_model=list[PermissionProfileResponse])
async def list_permission_profiles(
    owner_scope_type: str | None = None,
    owner_scope_id: int | None = None,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> list[PermissionProfileResponse]:
    """List permission profiles visible to the current principal with scope-constrained filtering."""
    filters = _resolve_visible_scope_filters(
        principal=principal,
        owner_scope_type=owner_scope_type,
        owner_scope_id=owner_scope_id,
    )
    rows: list[dict[str, Any]] = []
    for scope_type, scope_id in filters:
        rows.extend(
            await svc.list_permission_profiles(
                owner_scope_type=scope_type,
                owner_scope_id=scope_id,
            )
        )
    rows = _dedupe_rows(rows)
    return [_permission_profile_row_to_response(row) for row in rows]


@router.put("/permission-profiles/{profile_id}", response_model=PermissionProfileResponse)
async def update_permission_profile(
    profile_id: int,
    payload: PermissionProfileUpdateRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> PermissionProfileResponse:
    """Update an existing permission profile by id."""
    _require_mutation_permission(principal)
    update_fields = payload.model_dump(exclude_unset=True)
    if "policy_document" in update_fields:
        _require_grant_authority(principal, update_fields.get("policy_document") or {})
    try:
        row = await svc.update_permission_profile(
            profile_id,
            actor_id=principal.user_id,
            **update_fields,
        )
        if not row:
            raise ResourceNotFoundError("mcp_permission_profile", identifier=str(profile_id))
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _permission_profile_row_to_response(row)


@router.delete("/permission-profiles/{profile_id}", response_model=MCPHubDeleteResponse)
async def delete_permission_profile(
    profile_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> MCPHubDeleteResponse:
    """Delete a permission profile by id."""
    _require_mutation_permission(principal)
    try:
        deleted = await svc.delete_permission_profile(profile_id, actor_id=principal.user_id)
        if not deleted:
            raise ResourceNotFoundError("mcp_permission_profile", identifier=str(profile_id))
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return MCPHubDeleteResponse(ok=True)


@router.post("/policy-assignments", response_model=PolicyAssignmentResponse, status_code=201)
async def create_policy_assignment(
    payload: PolicyAssignmentCreateRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> PolicyAssignmentResponse:
    """Create a new policy assignment for a default, group, or persona target."""
    _require_mutation_permission(principal)
    _require_grant_authority(principal, payload.inline_policy_document)
    row = await svc.create_policy_assignment(
        target_type=payload.target_type,
        target_id=payload.target_id,
        owner_scope_type=payload.owner_scope_type,
        owner_scope_id=payload.owner_scope_id,
        profile_id=payload.profile_id,
        inline_policy_document=payload.inline_policy_document,
        approval_policy_id=payload.approval_policy_id,
        is_active=payload.is_active,
        actor_id=principal.user_id,
    )
    return _policy_assignment_row_to_response(row)


@router.get("/policy-assignments", response_model=list[PolicyAssignmentResponse])
async def list_policy_assignments(
    owner_scope_type: str | None = None,
    owner_scope_id: int | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> list[PolicyAssignmentResponse]:
    """List policy assignments visible to the current principal with scope-constrained filtering."""
    filters = _resolve_visible_scope_filters(
        principal=principal,
        owner_scope_type=owner_scope_type,
        owner_scope_id=owner_scope_id,
    )
    rows: list[dict[str, Any]] = []
    for scope_type, scope_id in filters:
        rows.extend(
            await svc.list_policy_assignments(
                owner_scope_type=scope_type,
                owner_scope_id=scope_id,
                target_type=target_type,
                target_id=target_id,
            )
        )
    rows = _dedupe_rows(rows)
    return [_policy_assignment_row_to_response(row) for row in rows]


@router.put("/policy-assignments/{assignment_id}", response_model=PolicyAssignmentResponse)
async def update_policy_assignment(
    assignment_id: int,
    payload: PolicyAssignmentUpdateRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> PolicyAssignmentResponse:
    """Update an existing policy assignment by id."""
    _require_mutation_permission(principal)
    update_fields = payload.model_dump(exclude_unset=True)
    if "inline_policy_document" in update_fields:
        _require_grant_authority(principal, update_fields.get("inline_policy_document") or {})
    try:
        row = await svc.update_policy_assignment(
            assignment_id,
            actor_id=principal.user_id,
            **update_fields,
        )
        if not row:
            raise ResourceNotFoundError("mcp_policy_assignment", identifier=str(assignment_id))
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _policy_assignment_row_to_response(row)


@router.delete("/policy-assignments/{assignment_id}", response_model=MCPHubDeleteResponse)
async def delete_policy_assignment(
    assignment_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> MCPHubDeleteResponse:
    """Delete a policy assignment by id."""
    _require_mutation_permission(principal)
    try:
        deleted = await svc.delete_policy_assignment(assignment_id, actor_id=principal.user_id)
        if not deleted:
            raise ResourceNotFoundError("mcp_policy_assignment", identifier=str(assignment_id))
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return MCPHubDeleteResponse(ok=True)


@router.get(
    "/policy-assignments/{assignment_id}/override",
    response_model=PolicyOverrideResponse,
)
async def get_policy_assignment_override(
    assignment_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> PolicyOverrideResponse:
    """Fetch the single override attached to a policy assignment."""
    try:
        await _get_visible_policy_assignment_or_404(
            assignment_id=assignment_id,
            principal=principal,
            svc=svc,
        )
        row = await svc.get_policy_override(assignment_id)
        if not row:
            raise ResourceNotFoundError("mcp_policy_override", identifier=str(assignment_id))
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _policy_override_row_to_response(row)


@router.put(
    "/policy-assignments/{assignment_id}/override",
    response_model=PolicyOverrideResponse,
)
async def upsert_policy_assignment_override(
    assignment_id: int,
    payload: PolicyOverrideUpsertRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> PolicyOverrideResponse:
    """Create or replace the single override attached to a policy assignment."""
    _require_mutation_permission(principal)
    try:
        assignment = await _get_visible_policy_assignment_or_404(
            assignment_id=assignment_id,
            principal=principal,
            svc=svc,
        )
        profile_id, base_document = await _assignment_base_policy_document(
            svc=svc,
            assignment=assignment,
        )
        merged_document = _merge_policy_documents(base_document, payload.override_policy_document)
        delta_document = _grant_authority_delta(base_document, merged_document)
        if delta_document:
            _require_grant_authority(principal, delta_document)
        row = await svc.upsert_policy_override(
            assignment_id,
            override_policy_document=payload.override_policy_document,
            is_active=payload.is_active,
            broadens_access=bool(delta_document),
            grant_authority_snapshot={
                **_grant_authority_snapshot(principal, delta_document),
                "assignment_id": assignment_id,
                "profile_id": profile_id,
            },
            actor_id=principal.user_id,
        )
        if not row:
            raise ResourceNotFoundError("mcp_policy_assignment", identifier=str(assignment_id))
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _policy_override_row_to_response(row)


@router.delete(
    "/policy-assignments/{assignment_id}/override",
    response_model=MCPHubDeleteResponse,
)
async def delete_policy_assignment_override(
    assignment_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> MCPHubDeleteResponse:
    """Delete the override attached to a policy assignment."""
    _require_mutation_permission(principal)
    try:
        await _get_visible_policy_assignment_or_404(
            assignment_id=assignment_id,
            principal=principal,
            svc=svc,
        )
        deleted = await svc.delete_policy_override(assignment_id, actor_id=principal.user_id)
        if not deleted:
            raise ResourceNotFoundError("mcp_policy_override", identifier=str(assignment_id))
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return MCPHubDeleteResponse(ok=True)


@router.post("/approval-policies", response_model=ApprovalPolicyResponse, status_code=201)
async def create_approval_policy(
    payload: ApprovalPolicyCreateRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> ApprovalPolicyResponse:
    """Create a new runtime approval policy within the provided owner scope."""
    _require_mutation_permission(principal)
    normalized_rules = _normalized_approval_rules(payload.rules)
    row = await svc.create_approval_policy(
        name=payload.name,
        description=payload.description,
        owner_scope_type=payload.owner_scope_type,
        owner_scope_id=payload.owner_scope_id,
        mode=payload.mode,
        rules=normalized_rules,
        is_active=payload.is_active,
        actor_id=principal.user_id,
    )
    return _approval_policy_row_to_response(row)


@router.get("/approval-policies", response_model=list[ApprovalPolicyResponse])
async def list_approval_policies(
    owner_scope_type: str | None = None,
    owner_scope_id: int | None = None,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> list[ApprovalPolicyResponse]:
    """List approval policies visible to the current principal with scope-constrained filtering."""
    filters = _resolve_visible_scope_filters(
        principal=principal,
        owner_scope_type=owner_scope_type,
        owner_scope_id=owner_scope_id,
    )
    rows: list[dict[str, Any]] = []
    for scope_type, scope_id in filters:
        rows.extend(
            await svc.list_approval_policies(
                owner_scope_type=scope_type,
                owner_scope_id=scope_id,
            )
        )
    rows = _dedupe_rows(rows)
    return [_approval_policy_row_to_response(row) for row in rows]


@router.put("/approval-policies/{approval_policy_id}", response_model=ApprovalPolicyResponse)
async def update_approval_policy(
    approval_policy_id: int,
    payload: ApprovalPolicyUpdateRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> ApprovalPolicyResponse:
    """Update an approval policy by id."""
    _require_mutation_permission(principal)
    update_fields = payload.model_dump(exclude_unset=True)
    if "rules" in update_fields:
        update_fields["rules"] = _normalized_approval_rules(update_fields.get("rules"))
    try:
        row = await svc.update_approval_policy(
            approval_policy_id,
            actor_id=principal.user_id,
            **update_fields,
        )
        if not row:
            raise ResourceNotFoundError("mcp_approval_policy", identifier=str(approval_policy_id))
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _approval_policy_row_to_response(row)


@router.delete("/approval-policies/{approval_policy_id}", response_model=MCPHubDeleteResponse)
async def delete_approval_policy(
    approval_policy_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> MCPHubDeleteResponse:
    """Delete an approval policy by id."""
    _require_mutation_permission(principal)
    try:
        deleted = await svc.delete_approval_policy(approval_policy_id, actor_id=principal.user_id)
        if not deleted:
            raise ResourceNotFoundError("mcp_approval_policy", identifier=str(approval_policy_id))
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return MCPHubDeleteResponse(ok=True)


@router.post("/approval-decisions", response_model=ApprovalDecisionResponse, status_code=201)
async def create_approval_decision(
    payload: ApprovalDecisionCreateRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> ApprovalDecisionResponse:
    """Persist a user approval or denial decision for a pending MCP Hub runtime approval."""
    actor_id = int(principal.user_id) if principal.user_id is not None else None
    context_user_id = _extract_context_key_user_id(payload.context_key)
    if actor_id is None:
        raise HTTPException(status_code=403, detail="Authenticated user required")
    if context_user_id is None:
        raise HTTPException(status_code=422, detail="context_key must include a numeric user id")
    if context_user_id != actor_id and not _is_mutation_allowed(principal):
        raise HTTPException(status_code=403, detail="Forbidden approval context")

    approval_rules: dict[str, Any] = {"duration_options": ["once", "session"]}
    if payload.approval_policy_id is not None:
        policy_row = await svc.get_approval_policy(int(payload.approval_policy_id))
        if policy_row is None:
            raise HTTPException(status_code=404, detail="Approval policy not found")
        approval_rules = _normalized_approval_rules(policy_row.get("rules") if isinstance(policy_row, dict) else {})

    if payload.duration not in _validated_duration_options(approval_rules):
        raise HTTPException(
            status_code=422,
            detail=f"duration '{payload.duration}' is not allowed by the approval policy",
        )

    consume_on_match, expires_at = _approval_decision_lifetime(
        decision=payload.decision,
        duration=payload.duration,
        conversation_id=payload.conversation_id,
        rules=approval_rules,
    )

    row = await svc.record_approval_decision(
        approval_policy_id=payload.approval_policy_id,
        context_key=payload.context_key,
        conversation_id=payload.conversation_id,
        tool_name=payload.tool_name,
        scope_key=payload.scope_key,
        decision=payload.decision,
        consume_on_match=consume_on_match,
        expires_at=expires_at,
        actor_id=actor_id,
    )
    return _approval_decision_row_to_response(row)


@router.get("/effective-policy", response_model=EffectivePolicyResponse)
async def get_effective_policy(
    persona_id: str | None = None,
    group_id: str | None = None,
    org_id: int | None = None,
    team_id: int | None = None,
    principal: AuthPrincipal = Depends(get_auth_principal),
    resolver: McpHubPolicyResolver = Depends(get_mcp_hub_policy_resolver_dep),
) -> EffectivePolicyResponse:
    """Resolve the effective MCP Hub policy for the authenticated user and optional target context."""
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="Authenticated user required")

    metadata: dict[str, Any] = {"mcp_policy_context_enabled": True}
    if persona_id:
        metadata["persona_id"] = persona_id
    if group_id:
        metadata["group_id"] = group_id
    if org_id is not None:
        metadata["org_id"] = org_id
    if team_id is not None:
        metadata["team_id"] = team_id

    return await resolver.resolve_for_context(
        user_id=principal.user_id,
        metadata=metadata,
    )


@router.get("/acp-profiles", response_model=list[ACPProfileResponse])
async def list_acp_profiles(
    owner_scope_type: str | None = None,
    owner_scope_id: int | None = None,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> list[ACPProfileResponse]:
    """List ACP profiles visible to the current principal with scope-constrained filtering."""
    filters = _resolve_visible_scope_filters(
        principal=principal,
        owner_scope_type=owner_scope_type,
        owner_scope_id=owner_scope_id,
    )
    rows: list[dict[str, Any]] = []
    for scope_type, scope_id in filters:
        rows.extend(
            await svc.list_acp_profiles(
                owner_scope_type=scope_type,
                owner_scope_id=scope_id,
            )
        )
    rows = _dedupe_rows(rows)
    return [_profile_row_to_response(row) for row in rows]


@router.post("/acp-profiles", response_model=ACPProfileResponse, status_code=201)
async def create_acp_profile(
    payload: ACPProfileCreateRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> ACPProfileResponse:
    """Create a new ACP profile within the provided owner scope."""
    _require_mutation_permission(principal)
    row = await svc.create_acp_profile(
        name=payload.name,
        description=payload.description,
        owner_scope_type=payload.owner_scope_type,
        owner_scope_id=payload.owner_scope_id,
        profile=payload.profile,
        is_active=payload.is_active,
        actor_id=principal.user_id,
    )
    return _profile_row_to_response(row)


@router.put("/acp-profiles/{profile_id}", response_model=ACPProfileResponse)
async def update_acp_profile(
    profile_id: int,
    payload: ACPProfileUpdateRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> ACPProfileResponse:
    """Update an existing ACP profile by id."""
    _require_mutation_permission(principal)
    row = await svc.update_acp_profile(
        profile_id,
        name=payload.name,
        description=payload.description,
        owner_scope_type=payload.owner_scope_type,
        owner_scope_id=payload.owner_scope_id,
        profile=payload.profile,
        is_active=payload.is_active,
        actor_id=principal.user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="ACP profile not found")
    return _profile_row_to_response(row)


@router.delete("/acp-profiles/{profile_id}", response_model=MCPHubDeleteResponse)
async def delete_acp_profile(
    profile_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> MCPHubDeleteResponse:
    """Delete an ACP profile by id."""
    _require_mutation_permission(principal)
    deleted = await svc.delete_acp_profile(profile_id, actor_id=principal.user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="ACP profile not found")
    return MCPHubDeleteResponse(ok=True)


@router.get("/external-servers", response_model=list[ExternalServerResponse])
async def list_external_servers(
    owner_scope_type: str | None = None,
    owner_scope_id: int | None = None,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> list[ExternalServerResponse]:
    """List external MCP servers visible to the current principal with scope-constrained filtering."""
    filters = _resolve_visible_scope_filters(
        principal=principal,
        owner_scope_type=owner_scope_type,
        owner_scope_id=owner_scope_id,
    )
    rows: list[dict[str, Any]] = []
    for scope_type, scope_id in filters:
        rows.extend(
            await svc.list_external_servers(
                owner_scope_type=scope_type,
                owner_scope_id=scope_id,
            )
        )
    rows = _dedupe_rows(rows)
    return [_external_row_to_response(row) for row in rows]


@router.post("/external-servers", response_model=ExternalServerResponse, status_code=201)
async def create_external_server(
    payload: ExternalServerCreateRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> ExternalServerResponse:
    """Create a new external MCP server definition."""
    _require_mutation_permission(principal)
    try:
        row = await svc.create_external_server(
            server_id=payload.server_id,
            name=payload.name,
            transport=payload.transport,
            config=payload.config,
            owner_scope_type=payload.owner_scope_type,
            owner_scope_id=payload.owner_scope_id,
            enabled=payload.enabled,
            actor_id=principal.user_id,
            allow_existing=False,
        )
    except McpHubConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _external_row_to_response(row)


@router.post("/external-servers/{server_id}/import", response_model=ExternalServerResponse, status_code=201)
async def import_external_server(
    server_id: str,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> ExternalServerResponse:
    """Import a legacy external server definition into MCP Hub managed storage."""
    _require_mutation_permission(principal)
    try:
        row = await svc.import_legacy_external_server(
            server_id=server_id,
            actor_id=principal.user_id,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except McpHubConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _external_row_to_response(row)


@router.get(
    "/external-servers/{server_id}/auth-template",
    response_model=ExternalServerAuthTemplateResponse,
)
async def get_external_server_auth_template(
    server_id: str,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> ExternalServerAuthTemplateResponse:
    """Fetch the managed auth template for an external server."""
    _ = principal
    try:
        row = await svc.get_external_server_auth_template(server_id=server_id)
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BadRequestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ExternalServerAuthTemplateResponse.model_validate(row)


@router.put(
    "/external-servers/{server_id}/auth-template",
    response_model=ExternalServerAuthTemplateResponse,
)
async def update_external_server_auth_template(
    server_id: str,
    payload: ExternalServerAuthTemplateUpdateRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> ExternalServerAuthTemplateResponse:
    """Create or update the managed auth template for an external server."""
    _require_mutation_permission(principal)
    try:
        row = await svc.update_external_server_auth_template(
            server_id=server_id,
            auth_template=payload.model_dump(),
            actor_id=principal.user_id,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BadRequestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ExternalServerAuthTemplateResponse.model_validate(row)


@router.get(
    "/external-servers/{server_id}/credential-slots",
    response_model=list[ExternalServerCredentialSlotResponse],
)
async def list_external_server_credential_slots(
    server_id: str,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> list[ExternalServerCredentialSlotResponse]:
    """List credential slots configured on a managed external server."""
    _ = principal
    try:
        rows = await svc.list_external_server_credential_slots(server_id=server_id)
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [ExternalServerCredentialSlotResponse.model_validate(row) for row in rows]


@router.post(
    "/external-servers/{server_id}/credential-slots",
    response_model=ExternalServerCredentialSlotResponse,
    status_code=201,
)
async def create_external_server_credential_slot(
    server_id: str,
    payload: ExternalServerCredentialSlotCreateRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> ExternalServerCredentialSlotResponse:
    """Create a credential slot on a managed external server."""
    _require_mutation_permission(principal)
    try:
        row = await svc.create_external_server_credential_slot(
            server_id=server_id,
            slot_name=payload.slot_name,
            display_name=payload.display_name,
            secret_kind=payload.secret_kind,
            privilege_class=payload.privilege_class,
            is_required=payload.is_required,
            actor_id=principal.user_id,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BadRequestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ExternalServerCredentialSlotResponse.model_validate(row)


@router.put(
    "/external-servers/{server_id}/credential-slots/{slot_name}",
    response_model=ExternalServerCredentialSlotResponse,
)
async def update_external_server_credential_slot(
    server_id: str,
    slot_name: str,
    payload: ExternalServerCredentialSlotUpdateRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> ExternalServerCredentialSlotResponse:
    """Update credential slot metadata on a managed external server."""
    _require_mutation_permission(principal)
    try:
        row = await svc.update_external_server_credential_slot(
            server_id=server_id,
            slot_name=slot_name,
            display_name=payload.display_name,
            secret_kind=payload.secret_kind,
            privilege_class=payload.privilege_class,
            is_required=payload.is_required,
            actor_id=principal.user_id,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BadRequestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ExternalServerCredentialSlotResponse.model_validate(row)


@router.delete(
    "/external-servers/{server_id}/credential-slots/{slot_name}",
    response_model=MCPHubDeleteResponse,
)
async def delete_external_server_credential_slot(
    server_id: str,
    slot_name: str,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> MCPHubDeleteResponse:
    """Delete a credential slot from a managed external server."""
    _require_mutation_permission(principal)
    deleted = await svc.delete_external_server_credential_slot(
        server_id=server_id,
        slot_name=slot_name,
        actor_id=principal.user_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Credential slot not found")
    return MCPHubDeleteResponse(ok=True)


@router.post(
    "/external-servers/{server_id}/credential-slots/{slot_name}/secret",
    response_model=ExternalServerSlotSecretSetResponse,
)
async def set_external_server_slot_secret(
    server_id: str,
    slot_name: str,
    payload: ExternalSecretSetRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> ExternalServerSlotSecretSetResponse:
    """Set or rotate the secret value for an external server credential slot."""
    _require_mutation_permission(principal)
    try:
        out = await svc.set_external_server_slot_secret(
            server_id=server_id,
            slot_name=slot_name,
            secret_value=payload.secret,
            actor_id=principal.user_id,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BadRequestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ExternalServerSlotSecretSetResponse(**out)


@router.delete(
    "/external-servers/{server_id}/credential-slots/{slot_name}/secret",
    response_model=MCPHubDeleteResponse,
)
async def clear_external_server_slot_secret(
    server_id: str,
    slot_name: str,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> MCPHubDeleteResponse:
    """Clear the stored secret for an external server credential slot."""
    _require_mutation_permission(principal)
    deleted = await svc.clear_external_server_slot_secret(
        server_id=server_id,
        slot_name=slot_name,
        actor_id=principal.user_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Credential slot secret not found")
    return MCPHubDeleteResponse(ok=True)


@router.get("/permission-profiles/{profile_id}/credential-bindings", response_model=list[CredentialBindingResponse])
async def list_profile_credential_bindings(
    profile_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> list[CredentialBindingResponse]:
    """List external server bindings attached to a permission profile."""
    await _get_visible_permission_profile_or_404(profile_id=profile_id, principal=principal, svc=svc)
    rows = await svc.list_profile_credential_bindings(profile_id=profile_id)
    return [_binding_row_to_response(row) for row in rows]


@router.put(
    "/permission-profiles/{profile_id}/credential-bindings/{server_id}",
    response_model=CredentialBindingResponse,
)
async def upsert_profile_credential_binding(
    profile_id: int,
    server_id: str,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> CredentialBindingResponse:
    """Grant a managed external server to a permission profile."""
    _require_mutation_permission(principal)
    await _get_visible_permission_profile_or_404(profile_id=profile_id, principal=principal, svc=svc)
    try:
        row = await svc.upsert_profile_credential_binding(
            profile_id=profile_id,
            external_server_id=server_id,
            actor_id=principal.user_id,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BadRequestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _binding_row_to_response(row)


@router.put(
    "/permission-profiles/{profile_id}/credential-bindings/{server_id}/{slot_name}",
    response_model=CredentialBindingResponse,
)
async def upsert_profile_slot_credential_binding(
    profile_id: int,
    server_id: str,
    slot_name: str,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> CredentialBindingResponse:
    """Grant a managed external server slot to a permission profile."""
    _require_mutation_permission(principal)
    await _get_visible_permission_profile_or_404(profile_id=profile_id, principal=principal, svc=svc)
    try:
        row = await svc.upsert_profile_credential_binding(
            profile_id=profile_id,
            external_server_id=server_id,
            slot_name=slot_name,
            actor_id=principal.user_id,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BadRequestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _binding_row_to_response(row)


@router.delete(
    "/permission-profiles/{profile_id}/credential-bindings/{server_id}",
    response_model=MCPHubDeleteResponse,
)
async def delete_profile_credential_binding(
    profile_id: int,
    server_id: str,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> MCPHubDeleteResponse:
    """Delete an external server binding from a permission profile."""
    _require_mutation_permission(principal)
    await _get_visible_permission_profile_or_404(profile_id=profile_id, principal=principal, svc=svc)
    deleted = await svc.delete_profile_credential_binding(
        profile_id=profile_id,
        external_server_id=server_id,
        actor_id=principal.user_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Credential binding not found")
    return MCPHubDeleteResponse(ok=True)


@router.delete(
    "/permission-profiles/{profile_id}/credential-bindings/{server_id}/{slot_name}",
    response_model=MCPHubDeleteResponse,
)
async def delete_profile_slot_credential_binding(
    profile_id: int,
    server_id: str,
    slot_name: str,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> MCPHubDeleteResponse:
    """Delete an external server slot binding from a permission profile."""
    _require_mutation_permission(principal)
    await _get_visible_permission_profile_or_404(profile_id=profile_id, principal=principal, svc=svc)
    deleted = await svc.delete_profile_credential_binding(
        profile_id=profile_id,
        external_server_id=server_id,
        slot_name=slot_name,
        actor_id=principal.user_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Credential binding not found")
    return MCPHubDeleteResponse(ok=True)


@router.get("/policy-assignments/{assignment_id}/credential-bindings", response_model=list[CredentialBindingResponse])
async def list_assignment_credential_bindings(
    assignment_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> list[CredentialBindingResponse]:
    """List external server bindings attached to a policy assignment."""
    await _get_visible_policy_assignment_or_404(assignment_id=assignment_id, principal=principal, svc=svc)
    rows = await svc.list_assignment_credential_bindings(assignment_id=assignment_id)
    return [_binding_row_to_response(row) for row in rows]


@router.put(
    "/policy-assignments/{assignment_id}/credential-bindings/{server_id}",
    response_model=CredentialBindingResponse,
)
async def upsert_assignment_credential_binding(
    assignment_id: int,
    server_id: str,
    payload: AssignmentCredentialBindingUpsertRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> CredentialBindingResponse:
    """Create or update an external server binding on a policy assignment."""
    _require_mutation_permission(principal)
    await _get_visible_policy_assignment_or_404(assignment_id=assignment_id, principal=principal, svc=svc)
    try:
        row = await svc.upsert_assignment_credential_binding(
            assignment_id=assignment_id,
            external_server_id=server_id,
            binding_mode=payload.binding_mode,
            actor_id=principal.user_id,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BadRequestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _binding_row_to_response(row)


@router.put(
    "/policy-assignments/{assignment_id}/credential-bindings/{server_id}/{slot_name}",
    response_model=CredentialBindingResponse,
)
async def upsert_assignment_slot_credential_binding(
    assignment_id: int,
    server_id: str,
    slot_name: str,
    payload: AssignmentCredentialBindingUpsertRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> CredentialBindingResponse:
    """Create or update an external server slot binding on a policy assignment."""
    _require_mutation_permission(principal)
    await _get_visible_policy_assignment_or_404(assignment_id=assignment_id, principal=principal, svc=svc)
    try:
        row = await svc.upsert_assignment_credential_binding(
            assignment_id=assignment_id,
            external_server_id=server_id,
            slot_name=slot_name,
            binding_mode=payload.binding_mode,
            actor_id=principal.user_id,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BadRequestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _binding_row_to_response(row)


@router.delete(
    "/policy-assignments/{assignment_id}/credential-bindings/{server_id}",
    response_model=MCPHubDeleteResponse,
)
async def delete_assignment_credential_binding(
    assignment_id: int,
    server_id: str,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> MCPHubDeleteResponse:
    """Delete an external server binding from a policy assignment."""
    _require_mutation_permission(principal)
    await _get_visible_policy_assignment_or_404(assignment_id=assignment_id, principal=principal, svc=svc)
    deleted = await svc.delete_assignment_credential_binding(
        assignment_id=assignment_id,
        external_server_id=server_id,
        actor_id=principal.user_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Credential binding not found")
    return MCPHubDeleteResponse(ok=True)


@router.delete(
    "/policy-assignments/{assignment_id}/credential-bindings/{server_id}/{slot_name}",
    response_model=MCPHubDeleteResponse,
)
async def delete_assignment_slot_credential_binding(
    assignment_id: int,
    server_id: str,
    slot_name: str,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> MCPHubDeleteResponse:
    """Delete an external server slot binding from a policy assignment."""
    _require_mutation_permission(principal)
    await _get_visible_policy_assignment_or_404(assignment_id=assignment_id, principal=principal, svc=svc)
    deleted = await svc.delete_assignment_credential_binding(
        assignment_id=assignment_id,
        external_server_id=server_id,
        slot_name=slot_name,
        actor_id=principal.user_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Credential binding not found")
    return MCPHubDeleteResponse(ok=True)


@router.get("/policy-assignments/{assignment_id}/external-access", response_model=EffectiveExternalAccessResponse)
async def get_assignment_external_access(
    assignment_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> EffectiveExternalAccessResponse:
    """Preview effective external server access for a policy assignment."""
    await _get_visible_policy_assignment_or_404(assignment_id=assignment_id, principal=principal, svc=svc)
    summary = await svc.resolve_effective_external_access(
        assignment_id=assignment_id,
        actor_id=principal.user_id,
    )
    return EffectiveExternalAccessResponse.model_validate(summary)


@router.put("/external-servers/{server_id}", response_model=ExternalServerResponse)
async def update_external_server(
    server_id: str,
    payload: ExternalServerUpdateRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> ExternalServerResponse:
    """Update an existing external MCP server definition."""
    _require_mutation_permission(principal)
    try:
        row = await svc.update_external_server(
            server_id,
            name=payload.name,
            transport=payload.transport,
            config=payload.config,
            owner_scope_type=payload.owner_scope_type,
            owner_scope_id=payload.owner_scope_id,
            enabled=payload.enabled,
            actor_id=principal.user_id,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _external_row_to_response(row)


@router.delete("/external-servers/{server_id}", response_model=MCPHubDeleteResponse)
async def delete_external_server(
    server_id: str,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> MCPHubDeleteResponse:
    """Delete an external MCP server definition by id."""
    _require_mutation_permission(principal)
    deleted = await svc.delete_external_server(server_id, actor_id=principal.user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="External server not found")
    return MCPHubDeleteResponse(ok=True)


@router.post("/external-servers/{server_id}/secret", response_model=ExternalSecretSetResponse)
async def set_external_secret(
    server_id: str,
    payload: ExternalSecretSetRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> ExternalSecretSetResponse:
    """Set or rotate an external MCP server secret using encrypted-at-rest storage."""
    _require_mutation_permission(principal)
    try:
        out = await svc.set_external_server_secret(
            server_id=server_id,
            secret_value=payload.secret,
            actor_id=principal.user_id,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BadRequestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ExternalSecretSetResponse(**out)
