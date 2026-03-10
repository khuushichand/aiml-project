from __future__ import annotations

import json
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
from tldw_Server_API.app.api.v1.schemas.mcp_hub_schemas import (
    ACPProfileCreateRequest,
    ACPProfileResponse,
    ACPProfileUpdateRequest,
    ApprovalDecisionCreateRequest,
    ApprovalDecisionResponse,
    ApprovalPolicyCreateRequest,
    ApprovalPolicyResponse,
    ApprovalPolicyUpdateRequest,
    EffectivePolicyResponse,
    ExternalSecretSetRequest,
    ExternalSecretSetResponse,
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
)
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.AuthNZ.permissions import SYSTEM_CONFIGURE
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.AuthNZ.repos.mcp_hub_repo import McpHubRepo
from tldw_Server_API.app.core.exceptions import BadRequestError, ResourceNotFoundError
from tldw_Server_API.app.services.mcp_hub_policy_resolver import McpHubPolicyResolver, get_mcp_hub_policy_resolver
from tldw_Server_API.app.services.mcp_hub_service import McpHubConflictError, McpHubService

router = APIRouter(prefix="/mcp/hub", tags=["mcp-hub"])

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


async def get_mcp_hub_service() -> McpHubService:
    """Resolve MCP Hub service with storage bootstrap checks."""
    pool = await get_db_pool()
    repo = McpHubRepo(pool)
    await repo.ensure_tables()
    return McpHubService(repo)


async def get_mcp_hub_policy_resolver_dep() -> McpHubPolicyResolver:
    """Resolve MCP Hub policy resolver for effective policy previews."""
    return await get_mcp_hub_policy_resolver()


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

    raw_capabilities = policy_document.get("capabilities") or []
    capabilities = {
        str(capability).strip().lower()
        for capability in raw_capabilities
        if str(capability).strip()
    }
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
    return ExternalServerResponse(
        id=str(row.get("id") or ""),
        name=str(row.get("name") or ""),
        enabled=bool(row.get("enabled")),
        owner_scope_type=str(row.get("owner_scope_type") or "global"),
        owner_scope_id=row.get("owner_scope_id"),
        transport=str(row.get("transport") or ""),
        config=_load_json_object(row.get("config_json")),
        secret_configured=bool(row.get("secret_configured")),
        key_hint=row.get("key_hint"),
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
    row = await svc.update_permission_profile(
        profile_id,
        actor_id=principal.user_id,
        **update_fields,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Permission profile not found")
    return _permission_profile_row_to_response(row)


@router.delete("/permission-profiles/{profile_id}", response_model=MCPHubDeleteResponse)
async def delete_permission_profile(
    profile_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> MCPHubDeleteResponse:
    """Delete a permission profile by id."""
    _require_mutation_permission(principal)
    deleted = await svc.delete_permission_profile(profile_id, actor_id=principal.user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Permission profile not found")
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
    row = await svc.update_policy_assignment(
        assignment_id,
        actor_id=principal.user_id,
        **update_fields,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Policy assignment not found")
    return _policy_assignment_row_to_response(row)


@router.delete("/policy-assignments/{assignment_id}", response_model=MCPHubDeleteResponse)
async def delete_policy_assignment(
    assignment_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> MCPHubDeleteResponse:
    """Delete a policy assignment by id."""
    _require_mutation_permission(principal)
    deleted = await svc.delete_policy_assignment(assignment_id, actor_id=principal.user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Policy assignment not found")
    return MCPHubDeleteResponse(ok=True)


@router.post("/approval-policies", response_model=ApprovalPolicyResponse, status_code=201)
async def create_approval_policy(
    payload: ApprovalPolicyCreateRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> ApprovalPolicyResponse:
    """Create a new runtime approval policy within the provided owner scope."""
    _require_mutation_permission(principal)
    row = await svc.create_approval_policy(
        name=payload.name,
        description=payload.description,
        owner_scope_type=payload.owner_scope_type,
        owner_scope_id=payload.owner_scope_id,
        mode=payload.mode,
        rules=payload.rules,
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
    row = await svc.update_approval_policy(
        approval_policy_id,
        actor_id=principal.user_id,
        **payload.model_dump(exclude_unset=True),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Approval policy not found")
    return _approval_policy_row_to_response(row)


@router.delete("/approval-policies/{approval_policy_id}", response_model=MCPHubDeleteResponse)
async def delete_approval_policy(
    approval_policy_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> MCPHubDeleteResponse:
    """Delete an approval policy by id."""
    _require_mutation_permission(principal)
    deleted = await svc.delete_approval_policy(approval_policy_id, actor_id=principal.user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Approval policy not found")
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

    row = await svc.record_approval_decision(
        approval_policy_id=payload.approval_policy_id,
        context_key=payload.context_key,
        conversation_id=payload.conversation_id,
        tool_name=payload.tool_name,
        scope_key=payload.scope_key,
        decision=payload.decision,
        consume_on_match=payload.consume_on_match,
        expires_at=payload.expires_at,
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
