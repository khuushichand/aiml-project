# admin/__init__.py
# Description: Admin endpoints for user management, registration codes, and system administration
#
# Imports
from __future__ import annotations

import asyncio
import os

from typing import Any, Literal

#
# 3rd-party imports
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import (
    check_rate_limit,
    get_auth_principal,
    get_db_transaction,
    require_roles,
)
from . import admin_api_keys as admin_api_keys_endpoints
from . import admin_budgets as admin_budgets_endpoints
from . import admin_byok as admin_byok_endpoints
from . import admin_llm_providers as admin_llm_providers_endpoints
from . import admin_network as admin_network_endpoints
from . import admin_orgs as admin_orgs_endpoints
from . import admin_personalization as admin_personalization_endpoints
from . import admin_profiles as admin_profiles_endpoints
from . import admin_tools as admin_tools_endpoints
from . import admin_system as admin_system_endpoints
from . import admin_registration as admin_registration_endpoints
from . import admin_sessions_mfa as admin_sessions_mfa_endpoints
from . import admin_settings as admin_settings_endpoints
from . import admin_usage as admin_usage_endpoints
from . import admin_user as admin_user_endpoints
from tldw_Server_API.app.api.v1.schemas.admin_rbac_schemas import (
    EffectivePermissionsResponse,
    OverrideEffect,
    PermissionCreateRequest,
    PermissionResponse,
    RateLimitResponse,
    RateLimitUpsertRequest,
    RoleCreateRequest,
    RoleEffectivePermissionsResponse,
    RolePermissionBooleanMatrixResponse,
    RolePermissionGrant,
    RolePermissionMatrixResponse,
    RoleResponse,
    UserOverrideEntry,
    UserOverridesResponse,
    UserOverrideUpsertRequest,
    UserRoleListResponse,
)

#
# Local imports
from tldw_Server_API.app.api.v1.schemas.admin_schemas import (
    BackupCreateRequest,
    BackupCreateResponse,
    BackupItem,
    BackupListResponse,
    BackupRestoreRequest,
    BackupRestoreResponse,
    FeatureFlagItem,
    FeatureFlagsResponse,
    FeatureFlagUpsertRequest,
    IncidentCreateRequest,
    IncidentEventCreateRequest,
    IncidentItem,
    IncidentListResponse,
    IncidentUpdateRequest,
    KanbanFtsMaintenanceResponse,
    MaintenanceState,
    MaintenanceUpdateRequest,
    RetentionPoliciesResponse,
    RetentionPolicy,
    RetentionPolicyUpdateRequest,
    ToolPermissionBatchRequest,
    ToolPermissionCreateRequest,
    ToolPermissionGrantRequest,
    ToolPermissionPrefixRequest,
    ToolPermissionResponse,
)
from tldw_Server_API.app.api.v1.schemas.auth_schemas import MessageResponse
from tldw_Server_API.app.core.AuthNZ.database import is_postgres_backend
from tldw_Server_API.app.core.AuthNZ.exceptions import DuplicateRoleError
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.AuthNZ.rbac import get_effective_permissions
from tldw_Server_API.app.core.AuthNZ.repos.rbac_repo import AuthnzRbacRepo
from tldw_Server_API.app.core.Chat.chat_service import (
    invalidate_model_alias_caches,
)
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.DB_Management.Kanban_DB import InputError, KanbanDB, KanbanDBError
from tldw_Server_API.app.core.exceptions import ResourceNotFoundError
from tldw_Server_API.app.core.Usage.pricing_catalog import reset_pricing_catalog
from tldw_Server_API.app.services import admin_profiles_service, admin_scope_service
from tldw_Server_API.app.services.admin_data_ops_service import (
    create_backup_snapshot as svc_create_backup_snapshot,
)
from tldw_Server_API.app.services.admin_data_ops_service import (
    list_backup_items as svc_list_backup_items,
)
from tldw_Server_API.app.services.admin_data_ops_service import (
    list_retention_policies as svc_list_retention_policies,
)
from tldw_Server_API.app.services.admin_data_ops_service import (
    restore_backup_snapshot as svc_restore_backup_snapshot,
)
from tldw_Server_API.app.services.admin_data_ops_service import (
    update_retention_policy as svc_update_retention_policy,
)
from tldw_Server_API.app.services.admin_roles_permissions_service import (
    create_role as svc_create_role,
)
from tldw_Server_API.app.services.admin_roles_permissions_service import (
    delete_role as svc_delete_role,
)
from tldw_Server_API.app.services.admin_roles_permissions_service import (
    delete_tool_permission as svc_delete_tool_permission,
)
from tldw_Server_API.app.services.admin_roles_permissions_service import (
    grant_tool_permission_to_role as svc_grant_tool_perm,
)
from tldw_Server_API.app.services.admin_roles_permissions_service import (
    list_roles as svc_list_roles,
)
from tldw_Server_API.app.services.admin_roles_permissions_service import (
    list_role_permissions as svc_list_role_permissions,
)
from tldw_Server_API.app.services.admin_roles_permissions_service import (
    list_tool_permissions as svc_list_tool_permissions,
)
from tldw_Server_API.app.services.admin_roles_permissions_service import (
    revoke_tool_permission_from_role as svc_revoke_tool_perm,
)
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

PLATFORM_ADMIN_ROLES = {"owner", "super_admin", "admin"}

# Test shim: some tests expect a private helper `_is_postgres_backend` to monkeypatch.
# Provide an alias to the public function for backward compatibility in tests.
_is_postgres_backend = is_postgres_backend


def _get_rbac_repo() -> AuthnzRbacRepo:
    """
    Factory for AuthnzRbacRepo used by admin RBAC endpoints.

    Keeping construction behind a small helper makes it easy to monkeypatch
    in tests and provides a single place to attach request-scoped state if
    we later bind the repo to a specific backend handle.
    """
    return AuthnzRbacRepo()

# Best-effort coordination for test-time SQLite migrations
_authnz_migration_lock = asyncio.Lock()

#######################################################################################################################
#
# Router Configuration

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_roles("admin"))],  # All endpoints require admin role
    responses={403: {"description": "Not authorized"}}
)

router.include_router(admin_profiles_endpoints.router)
router.include_router(admin_sessions_mfa_endpoints.router)
router.include_router(admin_byok_endpoints.router)
router.include_router(admin_llm_providers_endpoints.router)
router.include_router(admin_orgs_endpoints.router)
router.include_router(admin_settings_endpoints.router)
router.include_router(admin_registration_endpoints.router)
router.include_router(admin_system_endpoints.router)
router.include_router(admin_usage_endpoints.router)
router.include_router(admin_budgets_endpoints.router)
router.include_router(admin_user_endpoints.router)
router.include_router(admin_api_keys_endpoints.router)
router.include_router(admin_tools_endpoints.router)
router.include_router(admin_personalization_endpoints.router)
router.include_router(admin_network_endpoints.router)

# Backend detection now standardized via core AuthNZ database helper


async def _ensure_sqlite_authnz_ready_if_test_mode() -> None:
    """Best-effort: ensure AuthNZ SQLite schema/migrations before admin ops in tests.

    In CI/pytest with SQLite, the pool can reinitialize while migrations are
    pending. This helper checks for a core table and, if missing, runs
    migrations. A module-level asyncio.Lock coordinates concurrent requests to
    avoid parallel migration attempts.
    """
    try:
        # Only act in obvious test contexts to avoid production overhead
        is_test = (
            os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes")
            or os.getenv("PYTEST_CURRENT_TEST") is not None
        )
        if not is_test:
            return

        from pathlib import Path as _Path

        from tldw_Server_API.app.core.AuthNZ.database import get_db_pool as _get_db_pool
        pool = await _get_db_pool()

        # Skip if Postgres
        if getattr(pool, "pool", None) is not None:
            return

        # Acquire coordination lock to avoid concurrent migration attempts
        async with _authnz_migration_lock:
            # Re-check existence of a core table after acquiring the lock in case
            # another coroutine completed migrations while we waited
            try:
                async with pool.acquire() as conn:
                    cur = await conn.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='organizations'"
                    )
                    row = await cur.fetchone()
                    if row:
                        return
            except Exception:
                # Proceed to ensure migrations
                pass

            from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables as _ensure
            db_path = getattr(pool, "_sqlite_fs_path", None) or getattr(pool, "db_path", None)
            if isinstance(db_path, str) and db_path:
                path_obj = _Path(db_path)
                # Best-effort: ensure parent directories exist to avoid path issues in CI
                try:
                    path_obj.parent.mkdir(parents=True, exist_ok=True)
                except Exception:
                    pass
                await asyncio.to_thread(_ensure, path_obj)
    except Exception as _e:
        # Best-effort only; do not interfere with request handling
        logger.debug(f"AuthNZ test ensure skipped/failed: {_e}")


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
    """Best-effort audit emission for admin actions."""
    try:
        actor_id_raw = getattr(request.state, "user_id", None) or principal.user_id
        try:
            actor_id = int(actor_id_raw) if actor_id_raw is not None else None
        except (TypeError, ValueError):
            actor_id = None
        if actor_id is None:
            return
        from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import (
            get_or_create_audit_service_for_user_id,
        )
        from tldw_Server_API.app.core.Audit.unified_audit_service import (
            AuditContext,
            AuditEventCategory,
            AuditEventType,
        )
        audit_service = await get_or_create_audit_service_for_user_id(actor_id)
        correlation_id = (
            request.headers.get("X-Correlation-ID")
            or getattr(request.state, "correlation_id", None)
        )
        request_id = (
            request.headers.get("X-Request-ID")
            or getattr(request.state, "request_id", None)
            or ""
        )
        ctx = AuditContext(
            user_id=str(actor_id),
            correlation_id=correlation_id,
            request_id=request_id,
            ip_address=(request.client.host if request.client else None),
            user_agent=request.headers.get("user-agent"),
            endpoint=str(request.url.path),
            method=request.method,
        )
        await audit_service.log_event(
            event_type=AuditEventType(event_type),
            category=AuditEventCategory(category),
            context=ctx,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            metadata=metadata,
        )
    except Exception as exc:
        logger.warning("Admin audit emission failed: {}", exc, exc_info=True)


# Test shim: budgets tests monkeypatch this symbol via the admin module path.
async def emit_budget_audit_event(
    request: Request,
    principal: AuthPrincipal,
    *,
    org_id: int,
    budget_updates: dict[str, Any] | None,
    audit_changes: list[dict[str, Any]] | None,
    clear_budgets: bool,
    actor_role: str | None,
) -> None:
    from tldw_Server_API.app.services.budget_audit_service import emit_budget_audit_event as svc_emit

    await svc_emit(
        request,
        principal,
        org_id=org_id,
        budget_updates=budget_updates,
        audit_changes=audit_changes,
        clear_budgets=clear_budgets,
        actor_role=actor_role,
    )


async def _enforce_admin_user_scope(
    principal: AuthPrincipal,
    target_user_id: int,
    *,
    require_hierarchy: bool,
) -> None:
    """Enforce shared org/team membership and optional role hierarchy for admin actions."""
    await admin_scope_service.enforce_admin_user_scope(
        principal,
        target_user_id,
        require_hierarchy=require_hierarchy,
    )


def _is_platform_admin(principal: AuthPrincipal) -> bool:
    return admin_scope_service.is_platform_admin(principal)


def _require_platform_admin(principal: AuthPrincipal) -> None:
    return admin_scope_service.require_platform_admin(principal)


async def _get_admin_org_ids(principal: AuthPrincipal) -> list[int] | None:
    return await admin_scope_service.get_admin_org_ids(principal)


# Compat shim: tests import this helper from the admin module.
async def _load_bulk_user_candidates(
    *,
    principal: AuthPrincipal,
    org_id: int | None,
    team_id: int | None,
    role: str | None,
    is_active: bool | None,
    search: str | None,
    user_ids: list[int] | None,
) -> list[int]:
    return await admin_profiles_service._load_bulk_user_candidates(
        principal=principal,
        org_id=org_id,
        team_id=team_id,
        role=role,
        is_active=is_active,
        search=search,
        user_ids=user_ids,
    )


def _get_kanban_db_for_user_id(user_id: int) -> KanbanDB:
    db_path = DatabasePaths.get_kanban_db_path(user_id)
    return KanbanDB(db_path=str(db_path), user_id=str(user_id))


@router.post(
    "/kanban/fts/{action}",
    response_model=KanbanFtsMaintenanceResponse,
    dependencies=[Depends(check_rate_limit)],
)
async def admin_kanban_fts_maintenance(
    action: Literal["optimize", "rebuild"],
    user_id: int = Query(..., ge=1),
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> KanbanFtsMaintenanceResponse:
    try:
        await _enforce_admin_user_scope(principal, user_id, require_hierarchy=True)
        db = _get_kanban_db_for_user_id(user_id)
        if action == "rebuild":
            db.rebuild_fts()
        else:
            db.optimize_fts()
    except InputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KanbanDBError as exc:
        logger.error(f"Kanban FTS {action} failed for user {user_id}: {exc}")
        raise HTTPException(status_code=500, detail="Kanban FTS maintenance failed") from exc
    except Exception as exc:
        logger.error(f"Kanban FTS {action} failed for user {user_id}: {exc}")
        raise HTTPException(status_code=500, detail="Kanban FTS maintenance failed") from exc
    return KanbanFtsMaintenanceResponse(user_id=user_id, action=action, status="ok")


#######################################################################################################################
#
# RBAC: Roles, Permissions, Assignments, Overrides

@router.get("/roles", response_model=list[RoleResponse])
async def list_roles(db=Depends(get_db_transaction)) -> list[RoleResponse]:
    try:
        rows = await svc_list_roles(db)
        return [RoleResponse(**row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to list roles: {e}")
        raise HTTPException(status_code=500, detail="Failed to list roles")


@router.post("/roles", response_model=RoleResponse)
async def create_role(payload: RoleCreateRequest, db=Depends(get_db_transaction)) -> RoleResponse:
    try:
        row = await svc_create_role(db, payload.name, payload.description, False)
        return RoleResponse(**row)
    except DuplicateRoleError as dup:
        raise HTTPException(status_code=409, detail=f"Role '{dup.name}' already exists")
    except Exception as e:
        logger.error(f"Failed to create role: {e}")
        raise HTTPException(status_code=500, detail="Failed to create role")


@router.delete("/roles/{role_id}")
async def delete_role(role_id: int, db=Depends(get_db_transaction)) -> dict:
    try:
        await svc_delete_role(db, role_id)
        return {"message": "Role deleted"}
    except Exception as e:
        logger.error(f"Failed to delete role {role_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete role")


@router.get("/roles/{role_id}/permissions", response_model=list[PermissionResponse])
async def list_role_permissions(role_id: int, db=Depends(get_db_transaction)) -> list[PermissionResponse]:
    """List permissions granted to a specific role (read-only matrix row)."""
    try:
        rows = await svc_list_role_permissions(db, role_id)
        return [PermissionResponse(**r) for r in rows]
    except Exception as e:
        logger.error(f"Failed to list permissions for role {role_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list role permissions")


@router.get("/permissions/tools", response_model=list[ToolPermissionResponse])
async def list_tool_permissions(db=Depends(get_db_transaction)) -> list[ToolPermissionResponse]:
    """List tool execution permissions (name starts with 'tools.execute:')."""
    try:
        rows = await svc_list_tool_permissions(db)
        return [ToolPermissionResponse(**r) for r in rows]
    except Exception as e:
        logger.error(f"Failed to list tool permissions: {e}")
        raise HTTPException(status_code=500, detail="Failed to list tool permissions")


@router.post("/permissions/tools", response_model=ToolPermissionResponse)
async def create_tool_permission(payload: ToolPermissionCreateRequest, db=Depends(get_db_transaction)) -> ToolPermissionResponse:
    """Create a tool execution permission.

    - tool_name='*' → creates tools.execute:*
    - tool_name='<name>' → creates tools.execute:<name>
    """
    try:
        tool = payload.tool_name.strip()
        name = f"tools.execute:{'*' if tool == '*' else tool}"
        desc = payload.description or ("Wildcard tool execution" if tool == '*' else f"Execute tool {tool}")

        is_pg = await is_postgres_backend()
        if is_pg:
            await db.execute(
                "INSERT INTO permissions (name, description, category) VALUES ($1, $2, $3) ON CONFLICT (name) DO NOTHING",
                name, desc, 'tools',
            )
            row = await db.fetchrow(
                "SELECT name, description, category FROM permissions WHERE name = $1",
                name,
            )
            return ToolPermissionResponse(**dict(row))
        else:
            # SQLite doesn't support upsert on all versions; emulate
            cur = await db.execute("SELECT name, description, category FROM permissions WHERE name = ?", (name,))
            r = await cur.fetchone()
            if not r:
                await db.execute(
                    "INSERT INTO permissions (name, description, category) VALUES (?, ?, ?)",
                    (name, desc, 'tools'),
                )
                await db.commit()
                cur = await db.execute("SELECT name, description, category FROM permissions WHERE name = ?", (name,))
                r = await cur.fetchone()
            return ToolPermissionResponse(name=r[0], description=r[1], category=r[2])
    except Exception as e:
        logger.error(f"Failed to create tool permission: {e}")
        raise HTTPException(status_code=500, detail="Failed to create tool permission")


@router.delete("/permissions/tools/{perm_name}")
async def delete_tool_permission(perm_name: str, db=Depends(get_db_transaction)) -> dict:
    """Delete a tool execution permission by full name (e.g., tools.execute:my_tool)."""
    try:
        if not perm_name.startswith('tools.execute:'):
            raise HTTPException(status_code=400, detail="Invalid tool permission name")
        await svc_delete_tool_permission(db, perm_name)
        return {"message": "Tool permission deleted", "name": perm_name}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete tool permission {perm_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete tool permission")


@router.post("/roles/{role_id}/permissions/tools", response_model=ToolPermissionResponse)
async def grant_tool_permission_to_role(role_id: int, payload: ToolPermissionGrantRequest, db=Depends(get_db_transaction)) -> ToolPermissionResponse:
    """Grant a tool execution permission to a role.

    - tool_name='*' → grants tools.execute:*
    - tool_name='<name>' → grants tools.execute:<name>
    Creates the permission in catalog if missing.
    """
    tool = payload.tool_name.strip()
    name = f"tools.execute:{'*' if tool == '*' else tool}"
    desc = f"Wildcard tool execution" if tool == '*' else f"Execute tool {tool}"
    try:
        perm = await svc_grant_tool_perm(db, role_id, name, desc)
        return ToolPermissionResponse(name=perm['name'], description=perm.get('description'), category=perm.get('category'))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to grant tool permission to role {role_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to grant tool permission")


@router.delete("/roles/{role_id}/permissions/tools/{tool_name}")
async def revoke_tool_permission_from_role(role_id: int, tool_name: str, db=Depends(get_db_transaction)) -> dict:
    """Revoke a tool execution permission from a role.

    tool_name '*' refers to tools.execute:*
    """
    name = f"tools.execute:{'*' if tool_name.strip() == '*' else tool_name.strip()}"
    try:
        ok = await svc_revoke_tool_perm(db, role_id, name)
        if not ok:
            return {"message": "Permission not found; nothing to revoke", "name": name}
        return {"message": "Tool permission revoked", "name": name}
    except Exception as e:
        logger.error(f"Failed to revoke tool permission from role {role_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to revoke tool permission")


@router.get("/roles/{role_id}/permissions/tools", response_model=list[ToolPermissionResponse])
async def list_role_tool_permissions(role_id: int, db=Depends(get_db_transaction)) -> list[ToolPermissionResponse]:
    """List tool execution permissions assigned to a role."""
    try:
        is_pg = await is_postgres_backend()
        if is_pg:
            rows = await db.fetch(
                """
                SELECT p.name, p.description, p.category
                FROM permissions p
                JOIN role_permissions rp ON rp.permission_id = p.id
                WHERE rp.role_id = $1 AND p.name LIKE 'tools.execute:%'
                ORDER BY p.name
                """,
                role_id,
            )
            return [ToolPermissionResponse(**dict(r)) for r in rows]
        else:
            cur = await db.execute(
                """
                SELECT p.name, p.description, p.category
                FROM permissions p
                JOIN role_permissions rp ON rp.permission_id = p.id
                WHERE rp.role_id = ? AND p.name LIKE 'tools.execute:%'
                ORDER BY p.name
                """,
                (role_id,),
            )
            rows = await cur.fetchall()
            return [ToolPermissionResponse(name=r[0], description=r[1], category=r[2]) for r in rows]
    except Exception as e:
        logger.error(f"Failed to list role tool permissions for role {role_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list role tool permissions")


@router.post("/roles/{role_id}/permissions/tools/batch", response_model=list[ToolPermissionResponse])
async def grant_tool_permissions_batch(role_id: int, payload: ToolPermissionBatchRequest, db=Depends(get_db_transaction)) -> list[ToolPermissionResponse]:
    """Grant multiple tool execution permissions to a role in one call."""
    try:
        is_pg = await is_postgres_backend()
        results: list[ToolPermissionResponse] = []
        # Reuse single-grant logic inline
        for tool in payload.tool_names:
            tool = tool.strip()
            if not tool:
                continue
            name = f"tools.execute:{'*' if tool == '*' else tool}"
            desc = "Wildcard tool execution" if tool == '*' else f"Execute tool {tool}"

            if is_pg:
                await db.execute(
                    "INSERT INTO permissions (name, description, category) VALUES ($1, $2, $3) ON CONFLICT (name) DO NOTHING",
                    name, desc, 'tools',
                )
                row = await db.fetchrow("SELECT id, name, description, category FROM permissions WHERE name = $1", name)
                if not row:
                    continue
                await db.execute(
                    "INSERT INTO role_permissions (role_id, permission_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                    role_id, row['id'],
                )
                results.append(ToolPermissionResponse(name=row['name'], description=row['description'], category=row['category']))
            else:
                cur = await db.execute("SELECT id, name, description, category FROM permissions WHERE name = ?", (name,))
                r = await cur.fetchone()
                if not r:
                    await db.execute("INSERT INTO permissions (name, description, category) VALUES (?, ?, ?)", (name, desc, 'tools'))
                    await db.commit()
                    cur = await db.execute("SELECT id, name, description, category FROM permissions WHERE name = ?", (name,))
                    r = await cur.fetchone()
                await db.execute("INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)", (role_id, r[0]))
                await db.commit()
                results.append(ToolPermissionResponse(name=r[1], description=r[2], category=r[3]))
        return results
    except Exception as e:
        logger.error(f"Failed to batch grant tool permissions to role {role_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to grant tool permissions")


@router.post("/roles/{role_id}/permissions/tools/batch/revoke")
async def revoke_tool_permissions_batch(role_id: int, payload: ToolPermissionBatchRequest, db=Depends(get_db_transaction)) -> dict:
    """Revoke multiple tool execution permissions from a role."""
    try:
        is_pg = await is_postgres_backend()
        revoked: list[str] = []
        for tool in payload.tool_names:
            tool = tool.strip()
            if not tool:
                continue
            name = f"tools.execute:{'*' if tool == '*' else tool}"
            if is_pg:
                row = await db.fetchrow("SELECT id FROM permissions WHERE name = $1", name)
                if row:
                    await db.execute("DELETE FROM role_permissions WHERE role_id = $1 AND permission_id = $2", role_id, row['id'])
                    revoked.append(name)
            else:
                cur = await db.execute("SELECT id FROM permissions WHERE name = ?", (name,))
                r = await cur.fetchone()
                if r:
                    await db.execute("DELETE FROM role_permissions WHERE role_id = ? AND permission_id = ?", (role_id, r[0]))
                    await db.commit()
                    revoked.append(name)
        return {"revoked": revoked, "count": len(revoked)}
    except Exception as e:
        logger.error(f"Failed to batch revoke tool permissions from role {role_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to revoke tool permissions")


def _normalize_tool_prefix(raw_prefix: str) -> str:
    px = raw_prefix.strip()
    if not px:
        return "tools.execute:"
    if not px.startswith('tools.execute:'):
        px = 'tools.execute:' + px
    return px


@router.post("/roles/{role_id}/permissions/tools/prefix/grant", response_model=list[ToolPermissionResponse])
async def grant_tool_permissions_by_prefix(role_id: int, payload: ToolPermissionPrefixRequest, db=Depends(get_db_transaction)) -> list[ToolPermissionResponse]:
    """Grant all existing tool permissions with names starting with the prefix."""
    try:
        is_pg = await is_postgres_backend()
        prefix = _normalize_tool_prefix(payload.prefix)
        results: list[ToolPermissionResponse] = []
        if is_pg:
            rows = await db.fetch("SELECT id, name, description, category FROM permissions WHERE name LIKE $1", prefix + '%')
            for r in rows:
                await db.execute("INSERT INTO role_permissions (role_id, permission_id) VALUES ($1, $2) ON CONFLICT DO NOTHING", role_id, r['id'])
                results.append(ToolPermissionResponse(name=r['name'], description=r['description'], category=r['category']))
        else:
            cur = await db.execute("SELECT id, name, description, category FROM permissions WHERE name LIKE ?", (prefix + '%',))
            rows = await cur.fetchall()
            for r in rows:
                await db.execute("INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)", (role_id, r[0]))
                await db.commit()
                results.append(ToolPermissionResponse(name=r[1], description=r[2], category=r[3]))
        return results
    except Exception as e:
        logger.error(f"Failed to grant tool permissions by prefix to role {role_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to grant permissions by prefix")


@router.post("/roles/{role_id}/permissions/tools/prefix/revoke")
async def revoke_tool_permissions_by_prefix(role_id: int, payload: ToolPermissionPrefixRequest, db=Depends(get_db_transaction)) -> dict:
    """Revoke all tool permissions with names starting with the prefix from a role."""
    try:
        is_pg = await is_postgres_backend()
        prefix = _normalize_tool_prefix(payload.prefix)
        names: list[str] = []
        if is_pg:
            rows = await db.fetch("SELECT id, name FROM permissions WHERE name LIKE $1", prefix + '%')
            for r in rows:
                await db.execute("DELETE FROM role_permissions WHERE role_id = $1 AND permission_id = $2", role_id, r['id'])
                names.append(r['name'])
        else:
            cur = await db.execute("SELECT id, name FROM permissions WHERE name LIKE ?", (prefix + '%',))
            rows = await cur.fetchall()
            for r in rows:
                await db.execute("DELETE FROM role_permissions WHERE role_id = ? AND permission_id = ?", (role_id, r[0]))
                await db.commit()
                names.append(r[1])
        return {"revoked": names, "count": len(names)}
    except Exception as e:
        logger.error(f"Failed to revoke tool permissions by prefix from role {role_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to revoke permissions by prefix")


@router.get("/roles/matrix", response_model=RolePermissionMatrixResponse)
async def get_roles_matrix(
    category: str | None = Query(None),
    search: str | None = Query(None),
    role_search: str | None = Query(None),
    role_names: list[str] | None = Query(None),
    roles_limit: int | None = Query(100, ge=1, le=10000),
    roles_offset: int | None = Query(0, ge=0),
    db=Depends(get_db_transaction),
) -> RolePermissionMatrixResponse:
    """Return roles, filtered permissions, and grants (matrix view).

    Optional filters:
    - category: permission category exact match
    - search: substring match on name/description (case-insensitive)
    """
    try:
        is_pg = await is_postgres_backend()
        # Role filters + pagination
        role_clauses = []
        role_params: list[Any] = []
        total_roles = 0
        if is_pg:
            # Postgres
            if role_search:
                role_clauses.append(f"name ILIKE ${len(role_params)+1}")
                role_params.append(f"%{role_search}%")
            if role_names:
                role_clauses.append(f"name = ANY(${len(role_params)+1})")
                role_params.append(role_names)
            role_where = (" WHERE " + " AND ".join(role_clauses)) if role_clauses else ""
            # total count
            total_roles = await db.fetchval(f"SELECT COUNT(*) FROM roles{role_where}", *role_params)
            # fetch with limit/offset
            role_rows = await db.fetch(
                f"SELECT id, name, description, COALESCE(is_system,0) as is_system FROM roles{role_where} ORDER BY name LIMIT ${len(role_params)+1} OFFSET ${len(role_params)+2}",
                *role_params, roles_limit, roles_offset,
            )
            roles = [RoleResponse(**dict(r)) for r in role_rows]
        else:
            # SQLite
            if role_search:
                role_clauses.append("name LIKE ?")
                role_params.append(f"%{role_search}%")
            if role_names:
                placeholders = ",".join(["?"] * len(role_names))
                role_clauses.append(f"name IN ({placeholders})")
                role_params.extend(role_names)
            role_where = (" WHERE " + " AND ".join(role_clauses)) if role_clauses else ""
            # total count
            cur = await db.execute(f"SELECT COUNT(*) FROM roles{role_where}", role_params)
            row = await cur.fetchone()
            total_roles = int(row[0]) if row else 0
            # fetch with limit/offset
            cur = await db.execute(
                f"SELECT id, name, description, COALESCE(is_system,0) FROM roles{role_where} ORDER BY name LIMIT ? OFFSET ?",
                [*role_params, roles_limit, roles_offset],
            )
            role_rows = await cur.fetchall()
            roles = [RoleResponse(id=row[0], name=row[1], description=row[2], is_system=bool(row[3])) for row in role_rows]

        # Build WHERE for permissions
        clauses = []
        params: list[Any] = []
        if is_pg:
            # Postgres
            if category:
                clauses.append(f"category = ${len(params)+1}")
                params.append(category)
            if search:
                idx = len(params) + 1
                clauses.append(f"(name ILIKE ${idx} OR description ILIKE ${idx})")
                params.append(f"%{search}%")
            where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            perm_rows = await db.fetch(
                f"SELECT id, name, description, category FROM permissions{where} ORDER BY name", *params
            )
            permissions = [PermissionResponse(**dict(r)) for r in perm_rows]

            # Grants limited to filtered permissions via join
            grant_rows = await db.fetch(
                f"""
                SELECT rp.role_id, rp.permission_id
                FROM role_permissions rp
                JOIN permissions p ON p.id = rp.permission_id
                {where}
                """,
                *params,
            )
            grants = [RolePermissionGrant(role_id=r['role_id'], permission_id=r['permission_id']) for r in grant_rows]
        else:
            # SQLite
            if category:
                clauses.append("category = ?")
                params.append(category)
            if search:
                clauses.append("(name LIKE ? OR description LIKE ?)")
                params.extend([f"%{search}%", f"%{search}%"])
            where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            cur = await db.execute(
                f"SELECT id, name, description, category FROM permissions{where} ORDER BY name",
                params,
            )
            perm_rows = await cur.fetchall()
            permissions = [PermissionResponse(id=row[0], name=row[1], description=row[2], category=row[3]) for row in perm_rows]

            cur = await db.execute(
                f"""
                SELECT rp.role_id, rp.permission_id
                FROM role_permissions rp
                JOIN permissions p ON p.id = rp.permission_id
                {where}
                """,
                params,
            )
            grant_rows = await cur.fetchall()
            grants = [RolePermissionGrant(role_id=row[0], permission_id=row[1]) for row in grant_rows]

        return RolePermissionMatrixResponse(roles=roles, permissions=permissions, grants=grants, total_roles=total_roles)
    except Exception as e:
        logger.error(f"Failed to build roles/permissions matrix: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch role-permission matrix")


@router.get("/roles/matrix-boolean", response_model=RolePermissionBooleanMatrixResponse)
async def get_roles_matrix_boolean(
    category: str | None = Query(None),
    search: str | None = Query(None),
    role_search: str | None = Query(None),
    role_names: list[str] | None = Query(None),
    roles_limit: int | None = Query(100, ge=1, le=10000),
    roles_offset: int | None = Query(0, ge=0),
    db=Depends(get_db_transaction),
) -> RolePermissionBooleanMatrixResponse:
    """Return a compact boolean matrix: roles x permission_names, with optional filters."""
    try:
        is_pg = await is_postgres_backend()
        # Roles with filters + pagination
        role_clauses = []
        role_params: list[Any] = []
        total_roles = 0
        if is_pg:
            if role_search:
                role_clauses.append(f"name ILIKE ${len(role_params)+1}")
                role_params.append(f"%{role_search}%")
            if role_names:
                role_clauses.append(f"name = ANY(${len(role_params)+1})")
                role_params.append(role_names)
            role_where = (" WHERE " + " AND ".join(role_clauses)) if role_clauses else ""
            total_roles = await db.fetchval(f"SELECT COUNT(*) FROM roles{role_where}", *role_params)
            role_rows = await db.fetch(
                f"SELECT id, name, description, COALESCE(is_system,0) as is_system FROM roles{role_where} ORDER BY name LIMIT ${len(role_params)+1} OFFSET ${len(role_params)+2}",
                *role_params, roles_limit, roles_offset,
            )
            roles = [RoleResponse(**dict(r)) for r in role_rows]
        else:
            if role_search:
                role_clauses.append("name LIKE ?")
                role_params.append(f"%{role_search}%")
            if role_names:
                placeholders = ",".join(["?"] * len(role_names))
                role_clauses.append(f"name IN ({placeholders})")
                role_params.extend(role_names)
            role_where = (" WHERE " + " AND ".join(role_clauses)) if role_clauses else ""
            cur = await db.execute(f"SELECT COUNT(*) FROM roles{role_where}", role_params)
            row = await cur.fetchone()
            total_roles = int(row[0]) if row else 0
            cur = await db.execute(
                f"SELECT id, name, description, COALESCE(is_system,0) FROM roles{role_where} ORDER BY name LIMIT ? OFFSET ?",
                [*role_params, roles_limit, roles_offset],
            )
            role_rows = await cur.fetchall()
            roles = [RoleResponse(id=row[0], name=row[1], description=row[2], is_system=bool(row[3])) for row in role_rows]

        # Build WHERE for permissions
        clauses = []
        params: list[Any] = []
        if is_pg:
            if category:
                clauses.append(f"category = ${len(params)+1}")
                params.append(category)
            if search:
                idx = len(params) + 1
                clauses.append(f"(name ILIKE ${idx} OR description ILIKE ${idx})")
                params.append(f"%{search}%")
            where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            perm_rows = await db.fetch(f"SELECT id, name FROM permissions{where} ORDER BY name", *params)
            perm_ids = [r['id'] for r in perm_rows]
            perm_names = [r['name'] for r in perm_rows]
        else:
            if category:
                clauses.append("category = ?")
                params.append(category)
            if search:
                clauses.append("(name LIKE ? OR description LIKE ?)")
                params.extend([f"%{search}%", f"%{search}%"])
            where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            cur = await db.execute(f"SELECT id, name FROM permissions{where} ORDER BY name", params)
            perm_rows = await cur.fetchall()
            perm_ids = [row[0] for row in perm_rows]
            perm_names = [row[1] for row in perm_rows]

        # Grants set (also restrict to selected roles if any)
        if is_pg:
            role_ids = [r.id for r in roles]
            grant_sql = (
                f"""
                SELECT rp.role_id, rp.permission_id
                FROM role_permissions rp
                JOIN permissions p ON p.id = rp.permission_id
                {where}
                """
            )
            grant_params = list(params)
            if role_ids:
                grant_sql += f" AND rp.role_id = ANY(${len(grant_params)+1})"
                grant_params.append(role_ids)
            grant_rows = await db.fetch(grant_sql, *grant_params)
            grants_set = {(r['role_id'], r['permission_id']) for r in grant_rows}
        else:
            role_ids = [r.id for r in roles]
            grant_sql = (
                f"""
                SELECT rp.role_id, rp.permission_id
                FROM role_permissions rp
                JOIN permissions p ON p.id = rp.permission_id
                {where}
                """
            )
            grant_params = list(params)
            if role_ids:
                placeholders = ",".join(["?"] * len(role_ids))
                grant_sql += f" AND rp.role_id IN ({placeholders})"
                grant_params.extend(role_ids)
            cur = await db.execute(grant_sql, grant_params)
            grant_rows = await cur.fetchall()
            grants_set = {(row[0], row[1]) for row in grant_rows}

        # Build matrix: rows per role, cols per permission (same order as perm_names)
        role_ids = [r.id for r in roles]
        matrix: list[list[bool]] = []
        for rid in role_ids:
            row = [ (rid, pid) in grants_set for pid in perm_ids ]
            matrix.append(row)

        return RolePermissionBooleanMatrixResponse(
            roles=roles,
            permission_names=perm_names,
            matrix=matrix,
            total_roles=total_roles,
        )
    except Exception as e:
        logger.error(f"Failed to build boolean matrix: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch boolean matrix")



@router.get("/permissions/categories", response_model=list[str])
async def list_permission_categories(db=Depends(get_db_transaction)) -> list[str]:
    """List distinct permission categories (for UI filters)."""
    try:
        is_pg = await is_postgres_backend()
        if is_pg:
            rows = await db.fetch("SELECT DISTINCT category FROM permissions WHERE category IS NOT NULL ORDER BY category")
            return [r['category'] for r in rows]
        else:
            cur = await db.execute("SELECT DISTINCT category FROM permissions WHERE category IS NOT NULL ORDER BY category")
            rows = await cur.fetchall()
            return [row[0] for row in rows]
    except Exception as e:
        logger.error(f"Failed to list permission categories: {e}")
        return []


@router.get("/permissions", response_model=list[PermissionResponse])
async def list_permissions(category: str | None = None, search: str | None = None, db=Depends(get_db_transaction)) -> list[PermissionResponse]:
    try:
        is_pg = await is_postgres_backend()
        clauses = []
        params = []
        if category:
            clauses.append("category = $1" if is_pg else "category = ?")
            params.append(category)
        if search:
            if is_pg:
                clauses.append("(name ILIKE $%d OR description ILIKE $%d)" % (len(params)+1, len(params)+1))
                params.append(f"%{search}%")
            else:
                clauses.append("(name LIKE ? OR description LIKE ?)")
                params.append(f"%{search}%")
                params.append(f"%{search}%")
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        if is_pg:
            rows = await db.fetch(f"SELECT id, name, description, category FROM permissions{where} ORDER BY name", *params)
            return [PermissionResponse(**dict(r)) for r in rows]
        else:
            cur = await db.execute(f"SELECT id, name, description, category FROM permissions{where} ORDER BY name", params)
            rows = await cur.fetchall()
            return [PermissionResponse(id=row[0], name=row[1], description=row[2], category=row[3]) for row in rows]
    except Exception as e:
        logger.error(f"Failed to list permissions: {e}")
        raise HTTPException(status_code=500, detail="Failed to list permissions")


@router.post("/permissions", response_model=PermissionResponse)
async def create_permission(payload: PermissionCreateRequest, db=Depends(get_db_transaction)) -> PermissionResponse:
    try:
        is_pg = await is_postgres_backend()
        if is_pg:
            # Pre-check (case-insensitive)
            exists = await db.fetchrow("SELECT 1 FROM permissions WHERE LOWER(name) = LOWER($1)", payload.name)
            if exists:
                raise HTTPException(status_code=409, detail=f"Permission '{payload.name}' already exists")
            row = await db.fetchrow(
                "INSERT INTO permissions (name, description, category) VALUES ($1, $2, $3) RETURNING id, name, description, category",
                payload.name, payload.description, payload.category,
            )
            return PermissionResponse(**dict(row))
        else:
            # SQLite: explicit pre-check, return 409 if exists (case-insensitive)
            curx = await db.execute(
                "SELECT 1 FROM permissions WHERE LOWER(name) = LOWER(?)",
                (payload.name,),
            )
            if await curx.fetchone():
                raise HTTPException(status_code=409, detail=f"Permission '{payload.name}' already exists")
            await db.execute(
                "INSERT INTO permissions (name, description, category) VALUES (?, ?, ?)",
                (payload.name, payload.description, payload.category),
            )
            # Fetch the row via adapter
            cur = await db.execute(
                "SELECT id, name, description, category FROM permissions WHERE name = ?",
                (payload.name,),
            )
            row = await cur.fetchone()
            try:
                if isinstance(row, dict):
                    return PermissionResponse(**row)
            except Exception:
                pass
            return PermissionResponse(id=row[0], name=row[1], description=row[2], category=row[3])
    except HTTPException:
        # Preserve explicit status codes like 409 Conflict
        raise
    except Exception as e:
        logger.error(f"Failed to create permission: {e}")
        # In tests, include error details for quicker diagnosis
        import os as _os
        if _os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes"):
            raise HTTPException(status_code=500, detail=f"Failed to create permission: {e}")
        raise HTTPException(status_code=500, detail="Failed to create permission")


@router.post("/roles/{role_id}/permissions/{permission_id}")
async def grant_permission_to_role(role_id: int, permission_id: int, db=Depends(get_db_transaction)) -> dict:
    try:
        is_pg = await is_postgres_backend()
        if is_pg:
            await db.execute("INSERT INTO role_permissions (role_id, permission_id) VALUES ($1, $2) ON CONFLICT DO NOTHING", role_id, permission_id)
        else:
            await db.execute("INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)", (role_id, permission_id))
            await db.commit()
        return {"message": "Permission granted to role"}
    except Exception as e:
        logger.error(f"Failed to grant permission {permission_id} to role {role_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to grant permission to role")


@router.delete("/roles/{role_id}/permissions/{permission_id}")
async def revoke_permission_from_role(role_id: int, permission_id: int, db=Depends(get_db_transaction)) -> dict:
    try:
        is_pg = await is_postgres_backend()
        if is_pg:
            await db.execute("DELETE FROM role_permissions WHERE role_id = $1 AND permission_id = $2", role_id, permission_id)
        else:
            await db.execute("DELETE FROM role_permissions WHERE role_id = ? AND permission_id = ?", (role_id, permission_id))
            await db.commit()
        return {"message": "Permission revoked from role"}
    except Exception as e:
        logger.error(f"Failed to revoke permission {permission_id} from role {role_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to revoke permission from role")


@router.get("/users/{user_id}/roles", response_model=UserRoleListResponse)
async def get_user_roles_admin(
    user_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> UserRoleListResponse:
    try:
        await _enforce_admin_user_scope(principal, user_id, require_hierarchy=False)
        repo = _get_rbac_repo()
        loop = asyncio.get_event_loop()
        rows = await loop.run_in_executor(None, repo.get_user_roles, int(user_id))
        roles = [
            RoleResponse(
                id=int(r.get("id")),
                name=str(r.get("name")),
                description=str(r.get("description") or ""),
                is_system=bool(r.get("is_system")),
            )
            for r in rows
        ]
        return UserRoleListResponse(user_id=user_id, roles=roles)
    except Exception as e:
        logger.error(f"Failed to get user roles for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user roles")


@router.post("/users/{user_id}/roles/{role_id}")
async def add_role_to_user(
    user_id: int,
    role_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> dict:
    try:
        await _enforce_admin_user_scope(principal, user_id, require_hierarchy=True)
        is_pg = await is_postgres_backend()
        if is_pg:
            await db.execute(
                "INSERT INTO user_roles (user_id, role_id) VALUES ($1, $2) ON CONFLICT (user_id, role_id) DO NOTHING",
                user_id, role_id,
            )
        else:
            await db.execute(
                "INSERT OR IGNORE INTO user_roles (user_id, role_id) VALUES (?, ?)",
                (user_id, role_id),
            )
            await db.commit()
        return {"message": "Role added to user"}
    except Exception as e:
        logger.error(f"Failed to add role {role_id} to user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to add role to user")


@router.delete("/users/{user_id}/roles/{role_id}")
async def remove_role_from_user(
    user_id: int,
    role_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> dict:
    try:
        await _enforce_admin_user_scope(principal, user_id, require_hierarchy=True)
        is_pg = await is_postgres_backend()
        if is_pg:
            await db.execute("DELETE FROM user_roles WHERE user_id = $1 AND role_id = $2", user_id, role_id)
        else:
            await db.execute("DELETE FROM user_roles WHERE user_id = ? AND role_id = ?", (user_id, role_id))
            await db.commit()
        return {"message": "Role removed from user"}
    except Exception as e:
        logger.error(f"Failed to remove role {role_id} from user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove role from user")


@router.get("/users/{user_id}/overrides", response_model=UserOverridesResponse)
async def list_user_overrides(
    user_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> UserOverridesResponse:
    try:
        await _enforce_admin_user_scope(principal, user_id, require_hierarchy=False)
        repo = _get_rbac_repo()
        rows = repo.get_user_overrides(user_id=int(user_id))
        entries = [
            UserOverrideEntry(
                permission_id=int(r.get("permission_id")),
                permission_name=str(r.get("permission_name")),
                granted=bool(r.get("granted")),
                expires_at=str(r.get("expires_at")) if r.get("expires_at") else None,
            )
            for r in rows
        ]
        return UserOverridesResponse(user_id=user_id, overrides=entries)
    except Exception as e:
        logger.error(f"Failed to list overrides for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list user overrides")


@router.post("/users/{user_id}/overrides")
async def upsert_user_override(
    user_id: int,
    payload: UserOverrideUpsertRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> dict:
    try:
        await _enforce_admin_user_scope(principal, user_id, require_hierarchy=True)
        from tldw_Server_API.app.core.AuthNZ.settings import get_settings as _get_settings
        _settings = _get_settings()
        _is_pg = await is_postgres_backend()
        # In single-user mode, ensure the fixed user row exists before applying overrides (SQLite/PG FK safety)
        from tldw_Server_API.app.core.AuthNZ.settings import is_single_user_mode as _is_single
        if _is_single() and int(user_id) == int(getattr(_settings, 'SINGLE_USER_FIXED_ID', 1)):
            if _is_pg:
                await db.execute(
                    """
                    INSERT INTO users (id, username, email, password_hash, is_active, is_verified, role)
                    VALUES ($1, $2, $3, $4, TRUE, TRUE, COALESCE((SELECT role FROM users WHERE id=$1),'user'))
                    ON CONFLICT (id) DO NOTHING
                    """,
                    user_id, 'single_user', 'single_user@example.local', '',
                )
            else:
                # SQLite path: insert a stub single_user row with default role 'user'
                cur = await db.execute(
                    """
                    INSERT OR IGNORE INTO users (id, username, email, password_hash, is_active, is_verified, role)
                    VALUES (?, ?, ?, ?, 1, 1, 'user')
                    """,
                    user_id, 'single_user', 'single_user@example.local', '',
                )
                if not _is_pg:
                    await db.commit()
        # Resolve permission_id if only name provided
        perm_id = payload.permission_id
        if not perm_id and payload.permission_name:
            if _is_pg:
                perm_id = await db.fetchval("SELECT id FROM permissions WHERE name = $1", payload.permission_name)
            else:
                cur = await db.execute("SELECT id FROM permissions WHERE name = ?", (payload.permission_name,))
                row = await cur.fetchone()
                perm_id = row[0] if row else None
        if not perm_id:
            raise HTTPException(status_code=400, detail="permission_id or permission_name required")

        granted = payload.effect == OverrideEffect.allow
        if _is_pg:
            await db.execute(
                """
                INSERT INTO user_permissions (user_id, permission_id, granted, expires_at)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (user_id, permission_id)
                DO UPDATE SET granted = EXCLUDED.granted, expires_at = EXCLUDED.expires_at
                """,
                user_id, perm_id, granted, payload.expires_at,
            )
        else:
            cur = await db.execute(
                """
                INSERT OR REPLACE INTO user_permissions (user_id, permission_id, granted, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                user_id, perm_id, granted, payload.expires_at,
            )
            # Commit on SQLite acquire()-based connection
            if not _is_pg:
                await db.commit()
        return {"message": "Override upserted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to upsert override for user {user_id}: {e}")
        from tldw_Server_API.app.core.AuthNZ.settings import get_settings as _get_settings
        _settings = _get_settings()
        # In tests or single-user dev, surface error details to aid debugging
        if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes") or str(_settings.AUTH_MODE) == "single_user":
            raise HTTPException(status_code=500, detail=f"Failed to upsert user override: {e}")
        raise HTTPException(status_code=500, detail="Failed to upsert user override")


@router.delete("/users/{user_id}/overrides/{permission_id}")
async def delete_user_override(
    user_id: int,
    permission_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> dict:
    try:
        await _enforce_admin_user_scope(principal, user_id, require_hierarchy=True)
        _is_pg = await is_postgres_backend()
        if _is_pg:
            await db.execute("DELETE FROM user_permissions WHERE user_id = $1 AND permission_id = $2", user_id, permission_id)
        else:
            await db.execute("DELETE FROM user_permissions WHERE user_id = ? AND permission_id = ?", (user_id, permission_id))
            if not _is_pg:
                await db.commit()
        return {"message": "Override deleted"}
    except Exception as e:
        logger.exception(f"Failed to delete override for user {user_id}: {e}")
        if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes"):
            raise HTTPException(status_code=500, detail=f"Failed to delete user override: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete user override")


@router.get("/users/{user_id}/effective-permissions", response_model=EffectivePermissionsResponse)
async def get_effective_permissions_admin(
    user_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> EffectivePermissionsResponse:
    """Compute effective permissions for a user.

    Delegates to the central RBAC helper, which in turn uses the AuthNZ
    repository layer (`AuthnzRbacRepo` / `UserDatabase_v2`) so that both
    SQLite and Postgres backends share the same logic.
    """
    try:
        await _enforce_admin_user_scope(principal, user_id, require_hierarchy=False)
        loop = asyncio.get_event_loop()
        perms = await loop.run_in_executor(None, get_effective_permissions, user_id)
        return EffectivePermissionsResponse(user_id=user_id, permissions=sorted(perms))
    except Exception as e:
        logger.error(f"Failed to compute effective permissions for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to compute effective permissions")


@router.get("/roles/{role_id}/permissions/effective", response_model=RoleEffectivePermissionsResponse)
async def get_role_effective_permissions(role_id: int) -> RoleEffectivePermissionsResponse:
    """Return a convenience view combining a role's granted permissions and tool permissions.

    - permissions: non-tool permission names (e.g., media.read)
    - tool_permissions: tool execution permission names (tools.execute:...)
    - all_permissions: union of both, sorted
    """
    try:
        repo = _get_rbac_repo()
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, repo.get_role_effective_permissions, int(role_id))
        return RoleEffectivePermissionsResponse(
            role_id=role_id,
            role_name=data.get("role_name", ""),
            permissions=data.get("permissions", []),
            tool_permissions=data.get("tool_permissions", []),
            all_permissions=data.get("all_permissions", []),
        )
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Role not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to compute effective permissions for role {role_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to compute role effective permissions")


@router.post("/roles/{role_id}/rate-limits", response_model=RateLimitResponse)
async def upsert_role_rate_limit(role_id: int, payload: RateLimitUpsertRequest, db=Depends(get_db_transaction)) -> RateLimitResponse:
    try:
        is_pg = await is_postgres_backend()
        if is_pg:
            await db.execute(
                """
                INSERT INTO rbac_role_rate_limits (role_id, resource, limit_per_min, burst)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (role_id, resource) DO UPDATE SET
                    limit_per_min = EXCLUDED.limit_per_min,
                    burst = EXCLUDED.burst
                """,
                role_id, payload.resource, payload.limit_per_min, payload.burst,
            )
        else:
            await db.execute(
                """
                INSERT OR REPLACE INTO rbac_role_rate_limits (role_id, resource, limit_per_min, burst)
                VALUES (?, ?, ?, ?)
                """,
                (role_id, payload.resource, payload.limit_per_min, payload.burst),
            )
            await db.commit()
        return RateLimitResponse(scope="role", id=role_id, resource=payload.resource, limit_per_min=payload.limit_per_min, burst=payload.burst)
    except Exception as e:
        logger.error(f"Failed to upsert role rate limit: {e}")
        raise HTTPException(status_code=500, detail="Failed to upsert role rate limit")


@router.delete("/roles/{role_id}/rate-limits", response_model=MessageResponse)
async def clear_role_rate_limits(role_id: int, db=Depends(get_db_transaction)) -> MessageResponse:
    try:
        is_pg = await is_postgres_backend()
        if is_pg:
            await db.execute("DELETE FROM rbac_role_rate_limits WHERE role_id = $1", role_id)
        else:
            await db.execute("DELETE FROM rbac_role_rate_limits WHERE role_id = ?", (role_id,))
            await db.commit()
        return MessageResponse(message="Role rate limits cleared", details={"role_id": role_id})
    except Exception as e:
        logger.error(f"Failed to clear role rate limits: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear role rate limits")


@router.post("/users/{user_id}/rate-limits", response_model=RateLimitResponse)
async def upsert_user_rate_limit(
    user_id: int,
    payload: RateLimitUpsertRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> RateLimitResponse:
    try:
        await _enforce_admin_user_scope(principal, user_id, require_hierarchy=True)
        is_pg = await is_postgres_backend()
        if is_pg:
            await db.execute(
                """
                INSERT INTO rbac_user_rate_limits (user_id, resource, limit_per_min, burst)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (user_id, resource) DO UPDATE SET
                    limit_per_min = EXCLUDED.limit_per_min,
                    burst = EXCLUDED.burst
                """,
                user_id, payload.resource, payload.limit_per_min, payload.burst,
            )
        else:
            await db.execute(
                """
                INSERT OR REPLACE INTO rbac_user_rate_limits (user_id, resource, limit_per_min, burst)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, payload.resource, payload.limit_per_min, payload.burst),
            )
            await db.commit()
        return RateLimitResponse(scope="user", id=user_id, resource=payload.resource, limit_per_min=payload.limit_per_min, burst=payload.burst)
    except Exception as e:
        logger.error(f"Failed to upsert user rate limit: {e}")
        raise HTTPException(status_code=500, detail="Failed to upsert user rate limit")


#######################################################################################################################
#
# Data Ops Endpoints (Backups, Retention, Exports)

_BACKUP_DATASETS = {"media", "chacha", "prompts", "evaluations", "audit", "authnz"}
_PER_USER_BACKUP_DATASETS = _BACKUP_DATASETS - {"authnz"}


def _require_user_id_for_dataset(dataset: str, user_id: int | None) -> None:
    if dataset in _PER_USER_BACKUP_DATASETS and user_id is None:
        raise HTTPException(status_code=400, detail="user_id_required")


@router.get("/backups", response_model=BackupListResponse)
async def list_backups(
    dataset: str | None = Query(None, description="Dataset key to filter"),
    user_id: int | None = Query(None, description="User ID for per-user datasets"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> BackupListResponse:
    try:
        normalized_dataset = None
        if dataset:
            normalized_dataset = dataset.strip().lower()
            if normalized_dataset not in _BACKUP_DATASETS:
                raise HTTPException(status_code=400, detail="unknown_dataset")
            _require_user_id_for_dataset(normalized_dataset, user_id)
        if user_id is not None:
            await _enforce_admin_user_scope(principal, user_id, require_hierarchy=False)
        items, total = svc_list_backup_items(
            dataset=normalized_dataset,
            user_id=user_id,
            limit=limit,
            offset=offset,
        )
        payload = [
            BackupItem(
                id=item.filename,
                dataset=item.dataset,
                user_id=item.user_id,
                status="ready",
                size_bytes=item.size_bytes,
                created_at=item.created_at,
            )
            for item in items
        ]
        return BackupListResponse(items=payload, total=total, limit=limit, offset=offset)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to list backups: {exc}")
        raise HTTPException(status_code=500, detail="Failed to list backups")


@router.post("/backups", response_model=BackupCreateResponse)
async def create_backup(
    payload: BackupCreateRequest,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> BackupCreateResponse:
    try:
        dataset = payload.dataset.strip().lower()
        if dataset not in _BACKUP_DATASETS:
            raise HTTPException(status_code=400, detail="unknown_dataset")
        _require_user_id_for_dataset(dataset, payload.user_id)
        if payload.user_id is not None:
            await _enforce_admin_user_scope(principal, payload.user_id, require_hierarchy=False)
        item = svc_create_backup_snapshot(
            dataset=dataset,
            user_id=payload.user_id,
            backup_type=payload.backup_type or "full",
            max_backups=payload.max_backups,
        )
        await _emit_admin_audit_event(
            request,
            principal,
            event_type="data.write",
            category="system",
            resource_type="backup",
            resource_id=item.filename,
            action="backup.create",
            metadata={
                "dataset": dataset,
                "user_id": item.user_id,
                "size_bytes": item.size_bytes,
            },
        )
        return BackupCreateResponse(
            item=BackupItem(
                id=item.filename,
                dataset=item.dataset,
                user_id=item.user_id,
                status="ready",
                size_bytes=item.size_bytes,
                created_at=item.created_at,
            )
        )
    except ValueError as exc:
        if str(exc) == "unknown_dataset":
            raise HTTPException(status_code=400, detail="unknown_dataset") from exc
        raise HTTPException(status_code=400, detail="invalid_backup_request") from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to create backup: {exc}")
        raise HTTPException(status_code=500, detail="Failed to create backup")


@router.post("/backups/{backup_id}/restore", response_model=BackupRestoreResponse)
async def restore_backup(
    backup_id: str,
    payload: BackupRestoreRequest,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> BackupRestoreResponse:
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="confirm_required")
    try:
        dataset = payload.dataset.strip().lower()
        if dataset not in _BACKUP_DATASETS:
            raise HTTPException(status_code=400, detail="unknown_dataset")
        _require_user_id_for_dataset(dataset, payload.user_id)
        if payload.user_id is not None:
            await _enforce_admin_user_scope(principal, payload.user_id, require_hierarchy=False)
        result = svc_restore_backup_snapshot(
            dataset=dataset,
            user_id=payload.user_id,
            backup_id=backup_id,
        )
        await _emit_admin_audit_event(
            request,
            principal,
            event_type="data.import",
            category="system",
            resource_type="backup",
            resource_id=backup_id,
            action="backup.restore",
            metadata={
                "dataset": dataset,
                "user_id": payload.user_id,
            },
        )
        return BackupRestoreResponse(status="restored", message=result)
    except ValueError as exc:
        if str(exc) == "unknown_dataset":
            raise HTTPException(status_code=400, detail="unknown_dataset") from exc
        raise HTTPException(status_code=400, detail="invalid_restore_request") from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to restore backup: {exc}")
        raise HTTPException(status_code=500, detail="Failed to restore backup")


@router.get("/retention-policies", response_model=RetentionPoliciesResponse)
async def list_retention_policies(
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> RetentionPoliciesResponse:
    try:
        del principal
        policies = [RetentionPolicy(**item) for item in await svc_list_retention_policies()]
        return RetentionPoliciesResponse(policies=policies)
    except Exception as exc:
        logger.error(f"Failed to list retention policies: {exc}")
        raise HTTPException(status_code=500, detail="Failed to list retention policies")


@router.put("/retention-policies/{policy_key}", response_model=RetentionPolicy)
async def update_retention_policy(
    policy_key: str,
    payload: RetentionPolicyUpdateRequest,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> RetentionPolicy:
    try:
        updated = await svc_update_retention_policy(policy_key, payload.days)
        await _emit_admin_audit_event(
            request,
            principal,
            event_type="config.changed",
            category="system",
            resource_type="retention_policy",
            resource_id=policy_key,
            action="retention.update",
            metadata={"days": payload.days},
        )
        return RetentionPolicy(**updated)
    except ValueError as exc:
        detail = str(exc)
        if detail == "unknown_policy":
            raise HTTPException(status_code=404, detail="unknown_policy") from exc
        if detail == "invalid_range":
            raise HTTPException(status_code=400, detail="invalid_range") from exc
        raise HTTPException(status_code=400, detail="invalid_retention_update") from exc
    except Exception as exc:
        logger.error(f"Failed to update retention policy: {exc}")
        raise HTTPException(status_code=500, detail="Failed to update retention policy")


# System Ops Endpoints (Logs, Maintenance, Feature Flags, Incidents)

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
            actor=actor,
            note=payload.note,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail in {"invalid_scope", "missing_org_id", "missing_user_id", "invalid_key"}:
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
        metadata={"scope": payload.scope, "enabled": payload.enabled},
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
    try:
        incident = svc_update_incident(
            incident_id=incident_id,
            title=payload.title,
            status=payload.status,
            severity=payload.severity,
            summary=payload.summary,
            tags=payload.tags,
            update_message=payload.update_message,
            actor=actor,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail == "not_found":
            raise HTTPException(status_code=404, detail="incident_not_found") from exc
        if detail in {"invalid_status", "invalid_severity"}:
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
    except Exception as e:
        logger.error(f"Failed to reload pricing catalog: {e}")
        raise HTTPException(status_code=500, detail="Failed to reload pricing catalog")


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
    except Exception as e:
        logger.error(f"Failed to reload chat model alias caches: {e}")
        raise HTTPException(status_code=500, detail="Failed to reload chat model alias caches")
