from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
from tldw_Server_API.app.api.v1.schemas.admin_schemas import (
    FeatureFlagItem,
    FeatureFlagsResponse,
    FeatureFlagUpsertRequest,
    IncidentCreateRequest,
    IncidentEventCreateRequest,
    IncidentItem,
    IncidentListResponse,
    IncidentUpdateRequest,
    MaintenanceState,
    MaintenanceUpdateRequest,
)
from tldw_Server_API.app.api.v1.schemas.auth_schemas import MessageResponse
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.AuthNZ.repos.rbac_repo import AuthnzRbacRepo
from tldw_Server_API.app.core.AuthNZ.repos.users_repo import AuthnzUsersRepo
from tldw_Server_API.app.core.Chat.chat_service import (
    invalidate_model_alias_caches,
)
from tldw_Server_API.app.core.Usage.pricing_catalog import reset_pricing_catalog
from tldw_Server_API.app.services.admin_system_ops_service import (
    add_incident_event as svc_add_incident_event,
)
from tldw_Server_API.app.services.admin_system_ops_service import (
    create_incident as svc_create_incident,
)
from tldw_Server_API.app.services.admin_system_ops_service import (
    delete_feature_flag as svc_delete_feature_flag,
)
from tldw_Server_API.app.services.admin_system_ops_service import (
    delete_incident as svc_delete_incident,
)
from tldw_Server_API.app.services.admin_system_ops_service import (
    get_maintenance_state as svc_get_maintenance_state,
)
from tldw_Server_API.app.services.admin_system_ops_service import (
    list_feature_flags as svc_list_feature_flags,
)
from tldw_Server_API.app.services.admin_system_ops_service import (
    list_incidents as svc_list_incidents,
)
from tldw_Server_API.app.services.admin_system_ops_service import (
    update_incident as svc_update_incident,
)
from tldw_Server_API.app.services.admin_system_ops_service import (
    update_maintenance_state as svc_update_maintenance_state,
)
from tldw_Server_API.app.services.admin_system_ops_service import (
    upsert_feature_flag as svc_upsert_feature_flag,
)

router = APIRouter()

_INCIDENT_ASSIGNABLE_ROLES = frozenset({"admin", "owner", "super_admin"})

_OPS_NONCRITICAL_EXCEPTIONS = (
    asyncio.CancelledError,
    asyncio.TimeoutError,
    AssertionError,
    AttributeError,
    ConnectionError,
    FileNotFoundError,
    IndexError,
    KeyError,
    LookupError,
    OSError,
    PermissionError,
    RuntimeError,
    TimeoutError,
    TypeError,
    ValueError,
    UnicodeDecodeError,
    HTTPException,
)


def _require_platform_admin(principal: AuthPrincipal) -> None:
    from tldw_Server_API.app.api.v1.endpoints import admin as admin_mod

    return admin_mod._require_platform_admin(principal)


def _user_has_incident_admin_role(user: dict[str, Any], role_rows: list[dict[str, Any]]) -> bool:
    """Return whether the user is eligible for incident assignment."""

    role_names = {
        str(role.get("name") or "").strip().lower() for role in role_rows if str(role.get("name") or "").strip()
    }
    legacy_role = str(user.get("role") or "").strip().lower()
    if legacy_role:
        role_names.add(legacy_role)
    return bool(role_names & _INCIDENT_ASSIGNABLE_ROLES) or bool(user.get("is_superuser"))


async def _resolve_incident_assignee(user_id: int) -> dict[str, Any]:
    """Resolve persisted assignee fields for an incident update.

    Raises:
        ValueError: ``assignee_not_found`` when the user does not exist.
        ValueError: ``incident_assignee_must_be_admin`` when the user is not admin-capable.
    """

    repo = await AuthnzUsersRepo.from_pool()
    user = await repo.get_user_by_id(int(user_id))
    if not user:
        raise ValueError("assignee_not_found")

    rbac_repo = AuthnzRbacRepo()
    role_rows = await asyncio.to_thread(rbac_repo.get_user_roles, int(user_id))
    if not _user_has_incident_admin_role(user, role_rows):
        raise ValueError("incident_assignee_must_be_admin")

    label = str(user.get("email") or "").strip() or str(user.get("username") or "").strip() or str(user["id"])
    return {
        "assigned_to_user_id": int(user["id"]),
        "assigned_to_label": label,
    }


async def _get_admin_org_ids(principal: AuthPrincipal) -> list[int] | None:
    from tldw_Server_API.app.api.v1.endpoints import admin as admin_mod

    return await admin_mod._get_admin_org_ids(principal)


async def _emit_admin_audit_event(
    request: Request,
    principal: AuthPrincipal,
    *,
    event_type: str,
    category: str,
    resource_type: str,
    resource_id: str | None,
    action: str,
    metadata: dict[str, Any],
) -> None:
    from tldw_Server_API.app.api.v1.endpoints import admin as admin_mod

    await admin_mod._emit_admin_audit_event(
        request,
        principal,
        event_type=event_type,
        category=category,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        metadata=metadata,
    )


@router.get("/maintenance", response_model=MaintenanceState)
async def get_maintenance_mode(
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> MaintenanceState:
    del principal
    state = svc_get_maintenance_state()
    return MaintenanceState(**state)


@router.put("/maintenance", response_model=MaintenanceState)
async def update_maintenance_mode(
    payload: MaintenanceUpdateRequest,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> MaintenanceState:
    _require_platform_admin(principal)
    actor = principal.email or principal.username or (str(principal.user_id) if principal.user_id is not None else None)
    state = svc_update_maintenance_state(
        enabled=payload.enabled,
        message=payload.message,
        allowlist_user_ids=payload.allowlist_user_ids,
        allowlist_emails=payload.allowlist_emails,
        actor=actor,
    )
    await _emit_admin_audit_event(
        request,
        principal,
        event_type="config.changed",
        category="system",
        resource_type="maintenance",
        resource_id="maintenance_mode",
        action="maintenance.update",
        metadata={"enabled": payload.enabled},
    )
    return MaintenanceState(**state)


@router.get("/feature-flags", response_model=FeatureFlagsResponse)
async def list_feature_flags(
    scope: str | None = Query(None, description="global|org|user"),
    org_id: int | None = Query(None, description="Organization ID for org-scoped flags"),
    user_id: int | None = Query(None, description="User ID for user-scoped flags"),
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> FeatureFlagsResponse:
    org_ids = await _get_admin_org_ids(principal)
    if org_id is not None and org_ids is not None:
        org_ids = [org_id] if org_id in org_ids else []
    if org_ids is not None and len(org_ids) == 0:
        return FeatureFlagsResponse(items=[], total=0)
    try:
        items = svc_list_feature_flags(
            scope=scope,
            org_id=org_id if org_ids is None else None,
            user_id=user_id,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail in {"invalid_scope", "missing_org_id", "missing_user_id"}:
            raise HTTPException(status_code=400, detail=detail) from exc
        raise HTTPException(status_code=400, detail="invalid_feature_flag") from exc
    if org_ids is not None:
        items = [item for item in items if item.get("org_id") in org_ids]
    return FeatureFlagsResponse(items=[FeatureFlagItem(**item) for item in items], total=len(items))


@router.put("/feature-flags/{flag_key}", response_model=FeatureFlagItem)
async def upsert_feature_flag(
    flag_key: str,
    payload: FeatureFlagUpsertRequest,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> FeatureFlagItem:
    _require_platform_admin(principal)
    actor = principal.email or principal.username or (str(principal.user_id) if principal.user_id is not None else None)
    try:
        flag = svc_upsert_feature_flag(
            key=flag_key,
            scope=payload.scope,
            enabled=payload.enabled,
            description=payload.description,
            org_id=payload.org_id,
            user_id=payload.user_id,
            target_user_ids=payload.target_user_ids,
            rollout_percent=payload.rollout_percent,
            variant_value=payload.variant_value,
            actor=actor,
            note=payload.note,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail in {
            "invalid_scope",
            "missing_org_id",
            "missing_user_id",
            "invalid_key",
            "invalid_rollout_percent",
        }:
            raise HTTPException(status_code=400, detail=detail) from exc
        raise HTTPException(status_code=400, detail="invalid_feature_flag") from exc
    await _emit_admin_audit_event(
        request,
        principal,
        event_type="config.changed",
        category="system",
        resource_type="feature_flag",
        resource_id=flag_key,
        action="feature_flag.upsert",
        metadata={
            "scope": payload.scope,
            "enabled": payload.enabled,
            "rollout_percent": payload.rollout_percent,
            "target_user_count": len(payload.target_user_ids or []),
            "variant_value": payload.variant_value,
        },
    )
    return FeatureFlagItem(**flag)


@router.delete("/feature-flags/{flag_key}", response_model=MessageResponse)
async def delete_feature_flag(
    flag_key: str,
    request: Request,
    scope: str = Query(..., description="global|org|user"),
    org_id: int | None = Query(None),
    user_id: int | None = Query(None),
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> MessageResponse:
    _require_platform_admin(principal)
    try:
        svc_delete_feature_flag(key=flag_key, scope=scope, org_id=org_id, user_id=user_id)
    except ValueError as exc:
        detail = str(exc)
        if detail in {"invalid_scope", "missing_org_id", "missing_user_id"}:
            raise HTTPException(status_code=400, detail=detail) from exc
        if detail == "not_found":
            raise HTTPException(status_code=404, detail="feature_flag_not_found") from exc
        raise HTTPException(status_code=400, detail="invalid_feature_flag") from exc
    if request is not None:
        await _emit_admin_audit_event(
            request,
            principal,
            event_type="config.changed",
            category="system",
            resource_type="feature_flag",
            resource_id=flag_key,
            action="feature_flag.delete",
            metadata={"scope": scope, "org_id": org_id, "user_id": user_id},
        )
    return MessageResponse(message="feature_flag_deleted")


@router.get("/incidents", response_model=IncidentListResponse)
async def list_incidents(
    status: str | None = Query(None, description="Incident status"),
    severity: str | None = Query(None, description="Incident severity"),
    tag: str | None = Query(None, description="Filter by tag"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> IncidentListResponse:
    del principal
    items, total = svc_list_incidents(
        status=status,
        severity=severity,
        tag=tag,
        limit=limit,
        offset=offset,
    )
    return IncidentListResponse(
        items=[IncidentItem(**item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/incidents", response_model=IncidentItem)
async def create_incident(
    payload: IncidentCreateRequest,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> IncidentItem:
    _require_platform_admin(principal)
    actor = principal.email or principal.username or (str(principal.user_id) if principal.user_id is not None else None)
    try:
        incident = svc_create_incident(
            title=payload.title,
            status=payload.status,
            severity=payload.severity,
            summary=payload.summary,
            tags=payload.tags,
            actor=actor,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail in {"invalid_title", "invalid_status", "invalid_severity"}:
            raise HTTPException(status_code=400, detail=detail) from exc
        raise HTTPException(status_code=400, detail="invalid_incident") from exc
    await _emit_admin_audit_event(
        request,
        principal,
        event_type="ops.incident",
        category="system",
        resource_type="incident",
        resource_id=incident.get("id"),
        action="incident.create",
        metadata={"status": incident.get("status"), "severity": incident.get("severity")},
    )
    return IncidentItem(**incident)


@router.patch("/incidents/{incident_id}", response_model=IncidentItem)
async def update_incident(
    incident_id: str,
    payload: IncidentUpdateRequest,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> IncidentItem:
    _require_platform_admin(principal)
    actor = principal.email or principal.username or (str(principal.user_id) if principal.user_id is not None else None)
    update_fields = payload.model_dump(exclude_unset=True)
    workflow_fields: dict[str, Any] = {}
    for field_name in ("root_cause", "impact", "action_items"):
        if field_name in payload.model_fields_set:
            workflow_fields[field_name] = update_fields[field_name]
    try:
        assignee_fields: dict[str, Any] = {}
        if "assigned_to_user_id" in payload.model_fields_set:
            assignee_user_id = payload.assigned_to_user_id
            if assignee_user_id is None:
                assignee_fields = {
                    "assigned_to_user_id": None,
                    "assigned_to_label": None,
                }
            else:
                assignee_fields = await _resolve_incident_assignee(int(assignee_user_id))

        incident = svc_update_incident(
            incident_id=incident_id,
            title=payload.title,
            status=payload.status,
            severity=payload.severity,
            summary=payload.summary,
            tags=payload.tags,
            **assignee_fields,
            **workflow_fields,
            update_message=payload.update_message,
            actor=actor,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail == "not_found":
            raise HTTPException(status_code=404, detail="incident_not_found") from exc
        if detail == "assignee_not_found":
            raise HTTPException(status_code=404, detail=detail) from exc
        if detail in {"invalid_status", "invalid_severity", "incident_assignee_must_be_admin"}:
            raise HTTPException(status_code=400, detail=detail) from exc
        raise HTTPException(status_code=400, detail="invalid_incident") from exc
    await _emit_admin_audit_event(
        request,
        principal,
        event_type="ops.incident",
        category="system",
        resource_type="incident",
        resource_id=incident_id,
        action="incident.update",
        metadata={"status": incident.get("status"), "severity": incident.get("severity")},
    )
    return IncidentItem(**incident)


@router.post("/incidents/{incident_id}/events", response_model=IncidentItem)
async def add_incident_event(
    incident_id: str,
    payload: IncidentEventCreateRequest,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> IncidentItem:
    _require_platform_admin(principal)
    actor = principal.email or principal.username or (str(principal.user_id) if principal.user_id is not None else None)
    try:
        incident = svc_add_incident_event(
            incident_id=incident_id,
            message=payload.message,
            actor=actor,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail == "invalid_message":
            raise HTTPException(status_code=400, detail=detail) from exc
        if detail == "not_found":
            raise HTTPException(status_code=404, detail="incident_not_found") from exc
        raise HTTPException(status_code=400, detail="invalid_incident") from exc
    await _emit_admin_audit_event(
        request,
        principal,
        event_type="ops.incident",
        category="system",
        resource_type="incident",
        resource_id=incident_id,
        action="incident.event",
        metadata={"message": payload.message},
    )
    return IncidentItem(**incident)


@router.delete("/incidents/{incident_id}", response_model=MessageResponse)
async def delete_incident(
    incident_id: str,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> MessageResponse:
    _require_platform_admin(principal)
    try:
        svc_delete_incident(incident_id=incident_id)
    except ValueError as exc:
        detail = str(exc)
        if detail == "not_found":
            raise HTTPException(status_code=404, detail="incident_not_found") from exc
        raise HTTPException(status_code=400, detail="invalid_incident") from exc
    await _emit_admin_audit_event(
        request,
        principal,
        event_type="ops.incident",
        category="system",
        resource_type="incident",
        resource_id=incident_id,
        action="incident.delete",
        metadata={},
    )
    return MessageResponse(message="incident_deleted")


# ---------------------------------------------------------------------------------------------------------------------
# Pricing Catalog Management
# ---------------------------------------------


@router.post("/llm-usage/pricing/reload", response_model=dict)
async def reload_llm_pricing_catalog() -> dict:
    """Reload the LLM pricing catalog from environment and config file (admin-only).

    Picks up changes in PRICING_OVERRIDES and Config_Files/model_pricing.json
    without restarting the server.
    """
    try:
        reset_pricing_catalog()
        return {"status": "ok"}
    except _OPS_NONCRITICAL_EXCEPTIONS as e:
        logger.error(f"Failed to reload pricing catalog: {e}")
        raise HTTPException(status_code=500, detail="Failed to reload pricing catalog") from e


# ---------------------------------------------
# Chat Model Alias Cache Management
# ---------------------------------------------


@router.post("/chat/model-aliases/reload", response_model=dict)
async def reload_chat_model_alias_caches() -> dict:
    """Invalidate cached chat model lists and alias overrides (admin-only).

    Clears module-scope lru_caches used by chat model alias resolution so
    updates to Config_Files/model_pricing.json or env vars take effect
    without restarting the server.
    """
    try:
        invalidate_model_alias_caches()
        return {"status": "ok"}
    except _OPS_NONCRITICAL_EXCEPTIONS as e:
        logger.error(f"Failed to reload chat model alias caches: {e}")
        raise HTTPException(status_code=500, detail="Failed to reload chat model alias caches") from e
