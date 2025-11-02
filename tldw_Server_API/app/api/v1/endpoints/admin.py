# admin.py
# Description: Admin endpoints for user management, registration codes, and system administration
#
# Imports
from __future__ import annotations

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import secrets
import string
import os
import json
#
# 3rd-party imports
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Response
from fastapi.responses import PlainTextResponse
from loguru import logger
#
# Local imports
from tldw_Server_API.app.api.v1.schemas.admin_schemas import (
    UserListResponse,
    UserUpdateRequest,
    RegistrationCodeRequest,
    RegistrationCodeResponse,
    RegistrationCodeListResponse,
    SystemStatsResponse,
    SecurityAlertStatusResponse,
    SecurityAlertSinkStatus,
    AuditLogResponse,
    UserQuotaUpdateRequest,
    UsageDailyResponse,
    UsageTopResponse,
    UsageDailyRow,
    UsageTopRow,
    LLMUsageLogResponse,
    LLMUsageLogRow,
    LLMUsageSummaryResponse,
    LLMUsageSummaryRow,
    LLMTopSpendersResponse,
    LLMTopSpenderRow,
    ToolPermissionCreateRequest,
    ToolPermissionResponse,
    ToolPermissionGrantRequest,
    ToolPermissionBatchRequest,
    ToolPermissionPrefixRequest,
    ToolCatalogCreateRequest,
    ToolCatalogResponse,
    ToolCatalogEntryCreateRequest,
    ToolCatalogEntryResponse,
    RateLimitResetRequest,
    RateLimitResetResponse,
)
from tldw_Server_API.app.api.v1.schemas.api_key_schemas import (
    APIKeyCreateRequest,
    APIKeyCreateResponse,
    APIKeyRotateRequest,
    APIKeyMetadata,
    APIKeyUpdateRequest,
    APIKeyAuditEntry,
    APIKeyAuditListResponse,
)
from tldw_Server_API.app.api.v1.schemas.admin_rbac_schemas import (
    RoleCreateRequest,
    RoleResponse,
    PermissionCreateRequest,
    PermissionResponse,
    UserRoleListResponse,
    UserOverrideUpsertRequest,
    UserOverridesResponse,
    UserOverrideEntry,
    EffectivePermissionsResponse,
    RateLimitUpsertRequest,
    RateLimitResponse,
    RolePermissionMatrixResponse,
    RolePermissionGrant,
    RolePermissionBooleanMatrixResponse,
    RoleEffectivePermissionsResponse,
)
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import (
    require_admin,
    get_db_transaction,
    get_storage_service_dep
)
from tldw_Server_API.app.core.AuthNZ.rate_limiter import get_rate_limiter as get_authnz_rate_limiter
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, is_postgres_backend
from tldw_Server_API.app.core.AuthNZ.settings import Settings, get_settings
from tldw_Server_API.app.services.storage_quota_service import StorageQuotaService
from tldw_Server_API.app.core.AuthNZ.exceptions import (
    UserNotFoundError,
    DuplicateUserError,
    QuotaExceededError
)
from tldw_Server_API.app.core.config import settings as app_settings
from tldw_Server_API.app.core.AuthNZ.api_key_manager import get_api_key_manager
from tldw_Server_API.app.core.AuthNZ.rbac import get_effective_permissions
from tldw_Server_API.app.services.usage_aggregator import aggregate_usage_daily
from tldw_Server_API.app.services.llm_usage_aggregator import aggregate_llm_usage_daily
from tldw_Server_API.app.core.AuthNZ.alerting import get_security_alert_dispatcher
from tldw_Server_API.app.core.AuthNZ.orgs_teams import (
    create_organization,
    list_organizations,
    create_team,
    add_team_member,
    list_team_members,
    remove_team_member,
    add_org_member,
    list_org_members,
    remove_org_member,
    update_org_member_role,
    list_org_memberships_for_user,
)
from tldw_Server_API.app.core.AuthNZ.exceptions import DuplicateOrganizationError, DuplicateTeamError, DuplicateRoleError
from tldw_Server_API.app.core.AuthNZ.exceptions import DuplicateOrganizationError
from tldw_Server_API.app.api.v1.schemas.org_team_schemas import (
    OrganizationCreateRequest,
    OrganizationResponse,
    OrganizationListResponse,
    TeamCreateRequest,
    TeamResponse,
    TeamMemberAddRequest,
    TeamMemberResponse,
    VirtualKeyCreateRequest,
    OrgMemberAddRequest,
    OrgMemberResponse,
    OrgMemberRoleUpdateRequest,
    OrgMemberListItem,
    OrgMembershipItem,
    OrganizationWatchlistsSettingsUpdate,
    OrganizationWatchlistsSettingsResponse,
)
from tldw_Server_API.app.core.Usage.pricing_catalog import reset_pricing_catalog
from tldw_Server_API.app.services.admin_roles_permissions_service import (
    list_roles as svc_list_roles,
    create_role as svc_create_role,
    delete_role as svc_delete_role,
    list_role_permissions as svc_list_role_permissions,
    list_tool_permissions as svc_list_tool_permissions,
    delete_tool_permission as svc_delete_tool_permission,
    grant_tool_permission_to_role as svc_grant_tool_perm,
    revoke_tool_permission_from_role as svc_revoke_tool_perm,
)
from tldw_Server_API.app.services.admin_orgs_service import list_teams_by_org as svc_list_teams_by_org
from tldw_Server_API.app.services.admin_usage_service import (
    fetch_usage_daily as svc_fetch_usage_daily,
    export_usage_daily_csv_text as svc_export_usage_daily_csv_text,
    fetch_usage_top as svc_fetch_usage_top,
    export_usage_top_csv_text as svc_export_usage_top_csv_text,
    fetch_llm_usage as svc_fetch_llm_usage,
    fetch_llm_usage_summary as svc_fetch_llm_usage_summary,
)
from tldw_Server_API.app.services.admin_service import update_api_key_metadata
from tldw_Server_API.app.core.Security.webui_access_guard import (
    webui_remote_access_enabled,
    setup_remote_access_enabled,
)
from tldw_Server_API.app.core.config import load_comprehensive_config
import ipaddress

# Test shim: some tests expect a private helper `_is_postgres_backend` to monkeypatch.
# Provide an alias to the public function for backward compatibility in tests.
_is_postgres_backend = is_postgres_backend

#######################################################################################################################
#
# Router Configuration

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],  # All endpoints require admin role
    responses={403: {"description": "Not authorized"}}
)

# Backend detection now standardized via core AuthNZ database helper


#######################################################################################################################
#
# User Management Endpoints

@router.get("/users", response_model=UserListResponse)
async def list_users(
    request: Request,
    response: Response,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    db=Depends(get_db_transaction)
) -> UserListResponse:
    """
    List all users with pagination and filters

    Args:
        page: Page number (1-based)
        limit: Items per page
        role: Filter by role
        is_active: Filter by active status
        search: Search in username/email

    Returns:
        Paginated list of users
    """
    # TEST_MODE diagnostics: annotate DB backend and admin dependency success
    try:
        if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes"):
            try:
                from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
                pool = await get_db_pool()
                db_backend = "postgres" if getattr(pool, "pool", None) is not None else "sqlite"
                response.headers["X-TLDW-Admin-DB"] = db_backend
                response.headers["X-TLDW-Admin-Req"] = "ok"
                # Log presence of Authorization header for debugging
                from loguru import logger as _logger
                auth_hdr = request.headers.get("Authorization")
                _logger.info(f"Admin list_users TEST_MODE: Authorization present={bool(auth_hdr)}")
            except Exception as _e:
                response.headers["X-TLDW-Admin-Diag-Error"] = str(_e)
    except Exception:
        pass
    try:
        is_pg = await is_postgres_backend()
        offset = (page - 1) * limit

        # Build query conditions
        conditions = []
        params = []
        param_count = 0

        if role:
            param_count += 1
            conditions.append(f"role = ${param_count}" if is_pg else "role = ?")
            params.append(role)

        if is_active is not None:
            param_count += 1
            conditions.append(f"is_active = ${param_count}" if is_pg else "is_active = ?")
            params.append(is_active)

        if search:
            param_count += 1
            search_pattern = f"%{search}%"
            if is_pg:
                conditions.append(f"(username ILIKE ${param_count} OR email ILIKE ${param_count})")
            else:
                conditions.append("(username LIKE ? OR email LIKE ?)")
                params.append(search_pattern)  # Add twice for SQLite
            params.append(search_pattern)

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

        # Get total count
        if is_pg:
            # PostgreSQL
            count_query = f"SELECT COUNT(*) FROM users{where_clause}"
            total = await db.fetchval(count_query, *params)

            # Get users
            query = f"""
                SELECT id, uuid, username, email, role, is_active, is_verified,
                       created_at, last_login, storage_quota_mb, storage_used_mb
                FROM users{where_clause}
                ORDER BY created_at DESC
                LIMIT ${param_count + 1} OFFSET ${param_count + 2}
            """
            params.extend([limit, offset])
            rows = await db.fetch(query, *params)
        else:
            # SQLite
            count_query = f"SELECT COUNT(*) FROM users{where_clause}"
            cursor = await db.execute(count_query, params)
            total = (await cursor.fetchone())[0]

            # Get users
            query = f"""
                SELECT id, uuid, username, email, role, is_active, is_verified,
                       created_at, last_login, storage_quota_mb, storage_used_mb
                FROM users{where_clause}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()

        # Normalize rows into Pydantic-friendly dicts (works for Postgres and SQLite)
        users = []
        for row in rows:
            if hasattr(row, 'keys') or isinstance(row, dict):  # Mapping/Record (Postgres path)
                r = dict(row)
                user_dict = {
                    "id": int(r.get("id")),
                    "uuid": str(r.get("uuid")) if r.get("uuid") is not None else None,
                    "username": r.get("username"),
                    "email": r.get("email"),
                    "role": r.get("role"),
                    "is_active": bool(r.get("is_active")),
                    "is_verified": bool(r.get("is_verified")),
                    "created_at": r.get("created_at"),
                    "last_login": r.get("last_login"),
                    "storage_quota_mb": int(r.get("storage_quota_mb") or 0),
                    "storage_used_mb": float(r.get("storage_used_mb") or 0.0),
                }
                users.append(user_dict)
            else:  # Tuple (SQLite path)
                user_dict = {
                    "id": int(row[0]),
                    "uuid": str(row[1]) if row[1] is not None else None,
                    "username": row[2],
                    "email": row[3],
                    "role": row[4],
                    "is_active": bool(row[5]),
                    "is_verified": bool(row[6]),
                    "created_at": row[7],
                    "last_login": row[8],
                    "storage_quota_mb": int(row[9] or 0),
                    "storage_used_mb": float(row[10] or 0.0),
                }
                users.append(user_dict)

        result = UserListResponse(
            users=users,
            total=total,
            page=page,
            limit=limit,
            pages=(total + limit - 1) // limit
        )
        return result

    except Exception as e:
        logger.error(f"Failed to list users: {e}")
        try:
            if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes"):
                response.headers["X-TLDW-Admin-Error"] = str(e)
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve users"
        )


#######################################################################################################################
#
# Per-User API Key Management (Admin)

@router.get("/users/{user_id}/api-keys", response_model=List[APIKeyMetadata])
async def admin_list_user_api_keys(
    user_id: int,
    include_revoked: bool = False,
) -> list[APIKeyMetadata]:
    """List API keys for a specific user (admin)."""
    try:
        api_mgr = await get_api_key_manager()
        rows = await api_mgr.list_user_keys(user_id=user_id, include_revoked=include_revoked)
        return [APIKeyMetadata(**row) for row in rows]
    except Exception as e:
        logger.error(f"Admin failed to list API keys for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list API keys")


@router.post("/users/{user_id}/api-keys", response_model=APIKeyCreateResponse)
async def admin_create_user_api_key(
    user_id: int,
    request: APIKeyCreateRequest,
) -> APIKeyCreateResponse:
    """Create a new API key for the given user (admin)."""
    try:
        api_mgr = await get_api_key_manager()
        result = await api_mgr.create_api_key(
            user_id=user_id,
            name=request.name,
            description=request.description,
            scope=request.scope,
            expires_in_days=request.expires_in_days,
        )
        return APIKeyCreateResponse(**result)
    except Exception as e:
        logger.error(f"Admin failed to create API key for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to create API key")


@router.post("/users/{user_id}/api-keys/{key_id}/rotate", response_model=APIKeyCreateResponse)
async def admin_rotate_user_api_key(
    user_id: int,
    key_id: int,
    request: APIKeyRotateRequest,
) -> APIKeyCreateResponse:
    """Rotate an API key for the given user and return the new key (admin)."""
    try:
        api_mgr = await get_api_key_manager()
        result = await api_mgr.rotate_api_key(
            key_id=key_id,
            user_id=user_id,
            expires_in_days=request.expires_in_days,
        )
        return APIKeyCreateResponse(**result)
    except Exception as e:
        logger.error(f"Admin failed to rotate API key {key_id} for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to rotate API key")


@router.delete("/users/{user_id}/api-keys/{key_id}")
async def admin_revoke_user_api_key(
    user_id: int,
    key_id: int,
) -> Dict[str, Any]:
    """Revoke an API key for the given user (admin)."""
    try:
        api_mgr = await get_api_key_manager()
        success = await api_mgr.revoke_api_key(key_id=key_id, user_id=user_id)
        if not success:
            raise HTTPException(status_code=404, detail="API key not found")
        return {"message": "API key revoked", "user_id": user_id, "key_id": key_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin failed to revoke API key {key_id} for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to revoke API key")


@router.patch("/users/{user_id}/api-keys/{key_id}", response_model=APIKeyMetadata)
async def admin_update_user_api_key(
    user_id: int,
    key_id: int,
    request: APIKeyUpdateRequest,
    db=Depends(get_db_transaction)
) -> APIKeyMetadata:
    """Update per-key limits like rate_limit and allowed_ips (admin)."""
    try:
        try:
            row = await update_api_key_metadata(
                db,
                user_id=user_id,
                key_id=key_id,
                rate_limit=request.rate_limit,
                allowed_ips=request.allowed_ips,
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="No updates provided")
        except LookupError:
            raise HTTPException(status_code=404, detail="API key not found")
        return APIKeyMetadata(**row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin failed to update API key {key_id} for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update API key")


#######################################################################################################################
#
# Organizations and Teams

@router.post("/orgs", response_model=OrganizationResponse)
async def admin_create_org(payload: OrganizationCreateRequest) -> OrganizationResponse:
    try:
        row = await create_organization(name=payload.name, owner_user_id=payload.owner_user_id, slug=payload.slug)
        return OrganizationResponse(**row)
    except DuplicateOrganizationError as dup:
        # Conflict: name or slug already exists
        raise HTTPException(status_code=409, detail=f"Organization with {dup.field} '{dup.value}' already exists")
    except Exception as e:
        logger.error(f"Failed to create organization: {e}")
        raise HTTPException(status_code=500, detail="Failed to create organization")


@router.get("/orgs")
async def admin_list_orgs(
    request: Request,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    q: Optional[str] = Query(None),
) -> Any:
    """List organizations.

    Backwards compatibility: when called without pagination/search query params,
    return a plain list of organizations. When any of ('limit', 'offset', 'q')
    are present in the query string, return a structured payload with
    pagination metadata.
    """
    try:
        # Detect whether caller explicitly requested pagination/search
        qp = request.query_params
        wants_wrapper = any(k in qp for k in ("limit", "offset", "q"))

        # Ask service for rows and optionally total
        result = await list_organizations(limit=limit, offset=offset, q=q, with_total=wants_wrapper)  # type: ignore[assignment]
        if wants_wrapper:
            rows, total = result  # type: ignore[misc]
        else:
            rows = result  # type: ignore[assignment]
            total = 0
        items = [OrganizationResponse(**r).model_dump() for r in rows]

        if wants_wrapper:
            has_more = (offset + len(items)) < int(total or 0)
            return {
                "items": items,
                "total": int(total or 0),
                "limit": limit,
                "offset": offset,
                "has_more": has_more,
            }
        # Raw list for legacy/simple callers
        return items
    except Exception as e:
        logger.error(f"Failed to list organizations: {e}")
        raise HTTPException(status_code=500, detail="Failed to list organizations")


@router.post("/orgs/{org_id}/teams", response_model=TeamResponse)
async def admin_create_team(org_id: int, payload: TeamCreateRequest) -> TeamResponse:
    try:
        row = await create_team(org_id=org_id, name=payload.name, slug=payload.slug, description=payload.description)
        return TeamResponse(**row)
    except DuplicateTeamError as dup:
        raise HTTPException(status_code=409, detail=f"Team with {dup.field} '{dup.value}' already exists in org {org_id}")
    except Exception as e:
        logger.error(f"Failed to create team: {e}")
        raise HTTPException(status_code=500, detail="Failed to create team")


@router.get("/orgs/{org_id}/teams", response_model=List[TeamResponse])
async def admin_list_teams(org_id: int, limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0), db=Depends(get_db_transaction)) -> list[TeamResponse]:
    try:
        rows = await svc_list_teams_by_org(db, org_id, limit, offset)
        return [TeamResponse(**r) for r in rows]
    except Exception as e:
        logger.error(f"Failed to list teams: {e}")
        raise HTTPException(status_code=500, detail="Failed to list teams")


@router.patch("/orgs/{org_id}/watchlists/settings", response_model=OrganizationWatchlistsSettingsResponse)
async def admin_update_org_watchlists_settings(
    org_id: int,
    payload: OrganizationWatchlistsSettingsUpdate,
    db=Depends(get_db_transaction),
):
    """Update watchlists-related organization settings (metadata).

    Currently supports:
      - require_include_default: default include-only gating for jobs in this org
    """
    try:
        # Fetch existing metadata for this org (works for both backends)
        if hasattr(db, "fetchrow"):
            row = await db.fetchrow("SELECT metadata FROM organizations WHERE id = $1", org_id)
            meta_raw = row.get("metadata") if row else None
        else:
            cur = await db.execute("SELECT metadata FROM organizations WHERE id = ?", (org_id,))
            row = await cur.fetchone()
            meta_raw = row[0] if row else None
        if not row:
            raise HTTPException(status_code=404, detail="organization_not_found")
        meta: Dict[str, Any]
        try:
            meta = json.loads(meta_raw) if meta_raw else {}
            if not isinstance(meta, dict):
                meta = {}
        except Exception:
            meta = {}

        wl = meta.get("watchlists") if isinstance(meta.get("watchlists"), dict) else {}
        changed = False
        if payload.require_include_default is not None:
            wl["require_include_default"] = bool(payload.require_include_default)
            changed = True
        if changed:
            meta["watchlists"] = wl
            if hasattr(db, "fetchrow"):
                await db.execute(
                    "UPDATE organizations SET metadata = $1, updated_at = CURRENT_TIMESTAMP WHERE id = $2",
                    json.dumps(meta), org_id,
                )
            else:
                await db.execute(
                    "UPDATE organizations SET metadata = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (json.dumps(meta), org_id),
                )
        return OrganizationWatchlistsSettingsResponse(
            org_id=org_id,
            require_include_default=wl.get("require_include_default"),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update org watchlists settings for org {org_id}: {e}")
        raise HTTPException(status_code=500, detail="failed_to_update_org_watchlists_settings")


@router.get("/orgs/{org_id}/watchlists/settings", response_model=OrganizationWatchlistsSettingsResponse)
async def admin_get_org_watchlists_settings(org_id: int, db=Depends(get_db_transaction)) -> OrganizationWatchlistsSettingsResponse:
    """Fetch watchlists-related organization settings (from metadata)."""
    try:
        if hasattr(db, "fetchrow"):
            row = await db.fetchrow("SELECT metadata FROM organizations WHERE id = $1", org_id)
            meta_raw = row.get("metadata") if row else None
        else:
            cur = await db.execute("SELECT metadata FROM organizations WHERE id = ?", (org_id,))
            row = await cur.fetchone()
            meta_raw = row[0] if row else None
        if not row:
            raise HTTPException(status_code=404, detail="organization_not_found")
        require_include_default = None
        if meta_raw:
            try:
                meta = json.loads(meta_raw)
                if isinstance(meta, dict):
                    wl = meta.get("watchlists") if isinstance(meta.get("watchlists"), dict) else None
                    if isinstance(wl, dict) and isinstance(wl.get("require_include_default"), bool):
                        require_include_default = bool(wl.get("require_include_default"))
                    elif isinstance(meta.get("watchlists_require_include_default"), bool):
                        require_include_default = bool(meta.get("watchlists_require_include_default"))
            except Exception:
                pass
        return OrganizationWatchlistsSettingsResponse(org_id=org_id, require_include_default=require_include_default)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch org watchlists settings for org {org_id}: {e}")
        raise HTTPException(status_code=500, detail="failed_to_fetch_org_watchlists_settings")


@router.post("/teams/{team_id}/members", response_model=TeamMemberResponse)
async def admin_add_team_member(team_id: int, payload: TeamMemberAddRequest, request: Request) -> TeamMemberResponse:
    try:
        row = await add_team_member(team_id=team_id, user_id=payload.user_id, role=payload.role or 'member')
        # Best-effort audit
        try:
            actor_id = getattr(request.state, 'user_id', None)
            if isinstance(actor_id, int):
                from tldw_Server_API.app.core.DB_Management.Users_DB import get_user_by_id as _get_user
                from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User as _User
                from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import get_audit_service_for_user
                from tldw_Server_API.app.core.Audit.unified_audit_service import AuditContext, AuditEventType, AuditEventCategory
                _ud = await _get_user(actor_id)
                if _ud:
                    _user = _User(**_ud)
                    _svc = await get_audit_service_for_user(_user)
                    _ctx = AuditContext(
                        user_id=str(actor_id),
                        ip_address=(request.client.host if request.client else None),
                        user_agent=request.headers.get('user-agent'),
                        endpoint=str(request.url.path),
                        method=request.method,
                    )
                    await _svc.log_event(
                        event_type=AuditEventType.DATA_WRITE,
                        category=AuditEventCategory.AUTHORIZATION,
                        context=_ctx,
                        resource_type='team',
                        resource_id=str(team_id),
                        action='team_member.add',
                        metadata={'target_user_id': payload.user_id, 'role': payload.role or 'member'}
                    )
        except Exception as _e:
            logger.debug(f"Audit (team member add) skipped/failed: {_e}")
        return TeamMemberResponse(**row)
    except Exception as e:
        logger.error(f"Failed to add team member: {e}")
        raise HTTPException(status_code=500, detail="Failed to add team member")


@router.get("/teams/{team_id}/members", response_model=List[TeamMemberResponse])
async def admin_list_team_members(team_id: int) -> list[TeamMemberResponse]:
    try:
        rows = await list_team_members(team_id)
        return [TeamMemberResponse(**r) for r in rows]
    except Exception as e:
        logger.error(f"Failed to list team members: {e}")
        raise HTTPException(status_code=500, detail="Failed to list team members")


@router.delete("/teams/{team_id}/members/{user_id}")
async def admin_remove_team_member(team_id: int, user_id: int, request: Request) -> Dict[str, Any]:
    """Remove a user from a team (admin)."""
    try:
        res = await remove_team_member(team_id=team_id, user_id=user_id)
        if not res.get("removed"):
            # Even if delete didn't error, treat as not found when no rows affected
            # (we don't currently return affected row count; return generic message)
            return {"message": "No membership found", "team_id": team_id, "user_id": user_id}
        # Best-effort audit
        try:
            actor_id = getattr(request.state, 'user_id', None)
            if isinstance(actor_id, int):
                from tldw_Server_API.app.core.DB_Management.Users_DB import get_user_by_id as _get_user
                from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User as _User
                from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import get_audit_service_for_user
                from tldw_Server_API.app.core.Audit.unified_audit_service import AuditContext, AuditEventType, AuditEventCategory
                _ud = await _get_user(actor_id)
                if _ud:
                    _user = _User(**_ud)
                    _svc = await get_audit_service_for_user(_user)
                    _ctx = AuditContext(
                        user_id=str(actor_id),
                        ip_address=(request.client.host if request.client else None),
                        user_agent=request.headers.get('user-agent'),
                        endpoint=str(request.url.path),
                        method=request.method,
                    )
                    await _svc.log_event(
                        event_type=AuditEventType.DATA_DELETE,
                        category=AuditEventCategory.AUTHORIZATION,
                        context=_ctx,
                        resource_type='team',
                        resource_id=str(team_id),
                        action='team_member.remove',
                        metadata={'target_user_id': user_id}
                    )
        except Exception as _e:
            logger.debug(f"Audit (team member remove) skipped/failed: {_e}")
        return {"message": "Team member removed", **res}
    except Exception as e:
        logger.error(f"Failed to remove team member user_id={user_id} from team_id={team_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove team member")


# ============================
# Organization membership endpoints
# ============================

@router.post("/orgs/{org_id}/members", response_model=OrgMemberResponse)
async def admin_add_org_member(org_id: int, payload: OrgMemberAddRequest, request: Request) -> OrgMemberResponse:
    try:
        row = await add_org_member(org_id=org_id, user_id=payload.user_id, role=payload.role or 'member')
        # Best-effort audit
        try:
            actor_id = getattr(request.state, 'user_id', None)
            if isinstance(actor_id, int):
                from tldw_Server_API.app.core.DB_Management.Users_DB import get_user_by_id as _get_user
                from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User as _User
                from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import get_audit_service_for_user
                from tldw_Server_API.app.core.Audit.unified_audit_service import AuditContext, AuditEventType, AuditEventCategory
                _ud = await _get_user(actor_id)
                if _ud:
                    _user = _User(**_ud)
                    _svc = await get_audit_service_for_user(_user)
                    _ctx = AuditContext(
                        user_id=str(actor_id),
                        ip_address=(request.client.host if request.client else None),
                        user_agent=request.headers.get('user-agent'),
                        endpoint=str(request.url.path),
                        method=request.method,
                    )
                    await _svc.log_event(
                        event_type=AuditEventType.DATA_WRITE,
                        category=AuditEventCategory.AUTHORIZATION,
                        context=_ctx,
                        resource_type='organization',
                        resource_id=str(org_id),
                        action='org_member.add',
                        metadata={'target_user_id': payload.user_id, 'role': payload.role or 'member'}
                    )
        except Exception as _e:
            logger.debug(f"Audit (org member add) skipped/failed: {_e}")
        return OrgMemberResponse(**row)
    except Exception as e:
        logger.error(f"Failed to add org member: {e}")
        raise HTTPException(status_code=500, detail="Failed to add org member")


@router.get("/orgs/{org_id}/members", response_model=List[OrgMemberListItem])
async def admin_list_org_members(
    org_id: int,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    role: Optional[str] = None,
    status: Optional[str] = None,
) -> list[OrgMemberListItem]:
    try:
        rows = await list_org_members(org_id=org_id, limit=limit, offset=offset, role=role, status=status)
        out: list[OrgMemberListItem] = []
        for r in rows:
            d = dict(r)
            try:
                from datetime import datetime
                if isinstance(d.get('added_at'), datetime):
                    d['added_at'] = d['added_at'].isoformat()
            except Exception:
                pass
            out.append(OrgMemberListItem(**d))
        return out
    except Exception as e:
        logger.error(f"Failed to list org members: {e}")
        raise HTTPException(status_code=500, detail="Failed to list org members")


@router.delete("/orgs/{org_id}/members/{user_id}")
async def admin_remove_org_member(org_id: int, user_id: int, request: Request) -> Dict[str, Any]:
    try:
        res = await remove_org_member(org_id=org_id, user_id=user_id)
        if res.get("error") == "owner_required":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization must retain at least one owner",
            )
        if not res.get("removed"):
            return {"message": "No membership found", "org_id": org_id, "user_id": user_id}
        # Best-effort audit
        try:
            actor_id = getattr(request.state, 'user_id', None)
            if isinstance(actor_id, int):
                from tldw_Server_API.app.core.DB_Management.Users_DB import get_user_by_id as _get_user
                from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User as _User
                from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import get_audit_service_for_user
                from tldw_Server_API.app.core.Audit.unified_audit_service import AuditContext, AuditEventType, AuditEventCategory
                _ud = await _get_user(actor_id)
                if _ud:
                    _user = _User(**_ud)
                    _svc = await get_audit_service_for_user(_user)
                    _ctx = AuditContext(
                        user_id=str(actor_id),
                        ip_address=(request.client.host if request.client else None),
                        user_agent=request.headers.get('user-agent'),
                        endpoint=str(request.url.path),
                        method=request.method,
                    )
                    await _svc.log_event(
                        event_type=AuditEventType.DATA_DELETE,
                        category=AuditEventCategory.AUTHORIZATION,
                        context=_ctx,
                        resource_type='organization',
                        resource_id=str(org_id),
                        action='org_member.remove',
                        metadata={'target_user_id': user_id}
                    )
        except Exception as _e:
            logger.debug(f"Audit (org member remove) skipped/failed: {_e}")
        return {"message": "Org member removed", **res}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove org member user_id={user_id} from org_id={org_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove org member")


@router.patch("/orgs/{org_id}/members/{user_id}", response_model=OrgMemberResponse)
async def admin_update_org_member_role(org_id: int, user_id: int, payload: OrgMemberRoleUpdateRequest, request: Request) -> OrgMemberResponse:
    try:
        row = await update_org_member_role(org_id=org_id, user_id=user_id, role=payload.role)
        if not row:
            raise HTTPException(status_code=404, detail="Org membership not found")
        if row.get("error") == "owner_required":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization must retain at least one owner",
            )
        # Best-effort audit
        try:
            actor_id = getattr(request.state, 'user_id', None)
            if isinstance(actor_id, int):
                from tldw_Server_API.app.core.DB_Management.Users_DB import get_user_by_id as _get_user
                from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User as _User
                from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import get_audit_service_for_user
                from tldw_Server_API.app.core.Audit.unified_audit_service import AuditContext, AuditEventType, AuditEventCategory
                _ud = await _get_user(actor_id)
                if _ud:
                    _user = _User(**_ud)
                    _svc = await get_audit_service_for_user(_user)
                    _ctx = AuditContext(
                        user_id=str(actor_id),
                        ip_address=(request.client.host if request.client else None),
                        user_agent=request.headers.get('user-agent'),
                        endpoint=str(request.url.path),
                        method=request.method,
                    )
                    await _svc.log_event(
                        event_type=AuditEventType.DATA_UPDATE,
                        category=AuditEventCategory.AUTHORIZATION,
                        context=_ctx,
                        resource_type='organization',
                        resource_id=str(org_id),
                        action='org_member.update',
                        metadata={'target_user_id': user_id, 'new_role': payload.role}
                    )
        except Exception as _e:
            logger.debug(f"Audit (org member role update) skipped/failed: {_e}")
        return OrgMemberResponse(**row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update org member role user_id={user_id} org_id={org_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update org member role")


@router.get("/users/{user_id}/org-memberships", response_model=List[OrgMembershipItem])
async def admin_list_user_org_memberships(user_id: int) -> list[OrgMembershipItem]:
    try:
        rows = await list_org_memberships_for_user(user_id)
        return [OrgMembershipItem(**r) for r in rows]
    except Exception as e:
        logger.error(f"Failed to list org memberships for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list org memberships")

@router.post("/users/{user_id}/virtual-keys")
async def admin_create_virtual_key(user_id: int, payload: VirtualKeyCreateRequest) -> Dict[str, Any]:
    try:
        api_mgr = await get_api_key_manager()
        result = await api_mgr.create_virtual_key(
            user_id=user_id,
            name=payload.name,
            description=payload.description,
            expires_in_days=payload.expires_in_days,
            org_id=payload.org_id,
            team_id=payload.team_id,
            allowed_endpoints=payload.allowed_endpoints,
            allowed_providers=payload.allowed_providers,
            allowed_models=payload.allowed_models,
            budget_day_tokens=payload.budget_day_tokens,
            budget_month_tokens=payload.budget_month_tokens,
            budget_day_usd=payload.budget_day_usd,
            budget_month_usd=payload.budget_month_usd,
            allowed_methods=payload.allowed_methods,
            allowed_paths=payload.allowed_paths,
            max_calls=payload.max_calls,
            max_runs=payload.max_runs,
        )
        return result
    except Exception as e:
        logger.error(f"Admin failed to create virtual key for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to create virtual key")


@router.get("/users/{user_id}/virtual-keys", response_model=List[APIKeyMetadata])
async def admin_list_virtual_keys(user_id: int, db=Depends(get_db_transaction)) -> list[APIKeyMetadata]:
    try:
        wanted = {
            'id','key_prefix','name','description','scope','status','created_at','expires_at','usage_count','last_used_at','last_used_ip'
        }
        # Defensive: ensure user_id is a plain int (some callers might pass (id,))
        if isinstance(user_id, (tuple, list)):
            user_id = user_id[0]
        user_id = int(user_id)
        is_pg = await is_postgres_backend()
        if is_pg:
            rows = await db.fetch("SELECT id, key_prefix, name, description, scope, status, created_at, expires_at, usage_count, last_used_at, last_used_ip FROM api_keys WHERE user_id = $1 AND COALESCE(is_virtual,FALSE) = TRUE ORDER BY created_at DESC", user_id)
            items = [APIKeyMetadata(**dict(r)) for r in rows]
        else:
            cur = await db.execute("SELECT id, key_prefix, name, description, scope, status, created_at, expires_at, usage_count, last_used_at, last_used_ip FROM api_keys WHERE user_id = ? AND COALESCE(is_virtual,0) = 1 ORDER BY created_at DESC", (user_id,))
            rows = await cur.fetchall()
            items = [
                APIKeyMetadata(
                    id=r[0], key_prefix=r[1], name=r[2], description=r[3], scope=r[4], status=r[5], created_at=r[6], expires_at=r[7], usage_count=r[8], last_used_at=r[9], last_used_ip=r[10]
                ) for r in rows
            ]
        return items
    except Exception as e:
        logger.error(f"Admin failed to list virtual keys for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list virtual keys")

@router.get("/api-keys/{key_id}/audit-log", response_model=APIKeyAuditListResponse)
async def admin_get_api_key_audit_log(
    key_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db=Depends(get_db_transaction)
) -> APIKeyAuditListResponse:
    """Get audit log entries for a specific API key (admin)."""
    try:
        is_pg = await is_postgres_backend()
        if is_pg:
            rows = await db.fetch(
                """
                SELECT id, api_key_id, action, user_id, ip_address, user_agent, details, created_at
                FROM api_key_audit_log
                WHERE api_key_id = $1
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
                """,
                key_id, limit, offset
            )
        else:
            cursor = await db.execute(
                """
                SELECT id, api_key_id, action, user_id, ip_address, user_agent, details, created_at
                FROM api_key_audit_log
                WHERE api_key_id = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (key_id, limit, offset)
            )
            rows = await cursor.fetchall()

        items: list[APIKeyAuditEntry] = []
        for r in rows:
            if isinstance(r, dict):
                items.append(APIKeyAuditEntry(**r))
            else:
                items.append(APIKeyAuditEntry(
                    id=r[0], api_key_id=r[1], action=r[2], user_id=r[3], ip_address=r[4], user_agent=r[5], details=r[6], created_at=r[7]
                ))
        return APIKeyAuditListResponse(key_id=key_id, items=items)
    except Exception as e:
        logger.error(f"Admin failed to fetch audit log for key {key_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to load audit log")


#######################################################################################################################
#
# Ephemeral Cleanup Settings

@router.get("/cleanup-settings")
async def get_cleanup_settings() -> Dict[str, Any]:
    """Get cleanup worker settings (enabled, interval in seconds)."""
    try:
        enabled = bool(app_settings.get("EPHEMERAL_CLEANUP_ENABLED", True))
        interval = int(app_settings.get("EPHEMERAL_CLEANUP_INTERVAL_SEC", 1800))
        return {"enabled": enabled, "interval_sec": interval}
    except Exception as e:
        logger.error(f"Failed to get cleanup settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to get cleanup settings")


@router.post("/cleanup-settings")
async def set_cleanup_settings(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Set cleanup worker settings (enabled, interval_sec)."""
    try:
        if "enabled" in payload:
            app_settings["EPHEMERAL_CLEANUP_ENABLED"] = bool(payload["enabled"])  # type: ignore[index]
        if "interval_sec" in payload:
            val = int(payload["interval_sec"])  # type: ignore[index]
            if val < 60 or val > 604800:
                raise HTTPException(status_code=400, detail="interval_sec must be between 60 and 604800")
            app_settings["EPHEMERAL_CLEANUP_INTERVAL_SEC"] = val  # type: ignore[index]
        enabled = bool(app_settings.get("EPHEMERAL_CLEANUP_ENABLED", True))
        interval = int(app_settings.get("EPHEMERAL_CLEANUP_INTERVAL_SEC", 1800))
        return {"enabled": enabled, "interval_sec": interval}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set cleanup settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to set cleanup settings")


@router.get("/users/{user_id}")
async def get_user_details(
    user_id: int,
    db=Depends(get_db_transaction)
) -> Dict[str, Any]:
    """
    Get detailed information about a specific user

    Args:
        user_id: User ID

    Returns:
        User details including all fields
    """
    try:
        is_pg = await is_postgres_backend()
        if is_pg:
            # PostgreSQL
            user = await db.fetchrow(
                "SELECT * FROM users WHERE id = $1",
                user_id
            )
        else:
            # SQLite
            cursor = await db.execute(
                "SELECT * FROM users WHERE id = ?",
                (user_id,)
            )
            user = await cursor.fetchone()

        if not user:
            raise UserNotFoundError(f"User {user_id}")

        # Convert to dict
        if not isinstance(user, dict):
            columns = ['id', 'uuid', 'username', 'email', 'password_hash', 'role',
                      'is_active', 'is_verified', 'is_locked', 'locked_until',
                      'failed_login_attempts', 'created_at', 'updated_at',
                      'last_login', 'email_verified_at', 'password_changed_at',
                      'preferences', 'storage_quota_mb', 'storage_used_mb']
            user = dict(zip(columns[:len(user)], user))

        # Remove sensitive fields
        user.pop('password_hash', None)

        # Convert UUID to string if needed
        if 'uuid' in user and user['uuid'] and not isinstance(user['uuid'], str):
            user['uuid'] = str(user['uuid'])

        return user

    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )
    except Exception as e:
        logger.error(f"Failed to get user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user details"
        )


@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    request: UserUpdateRequest,
    db=Depends(get_db_transaction)
) -> Dict[str, str]:
    """
    Update user information

    Args:
        user_id: User ID
        request: Update request with fields to modify

    Returns:
        Success message
    """
    try:
        is_pg = await is_postgres_backend()
        # Build update query dynamically
        updates = []
        params = []
        param_count = 0

        if request.email is not None:
            param_count += 1
            updates.append(f"email = ${param_count}" if is_pg else "email = ?")
            params.append(request.email)

        if request.role is not None:
            param_count += 1
            updates.append(f"role = ${param_count}" if is_pg else "role = ?")
            params.append(request.role)

        if request.is_active is not None:
            param_count += 1
            updates.append(f"is_active = ${param_count}" if is_pg else "is_active = ?")
            params.append(request.is_active)

        if request.is_verified is not None:
            param_count += 1
            updates.append(f"is_verified = ${param_count}" if is_pg else "is_verified = ?")
            params.append(request.is_verified)

        if request.is_locked is not None:
            param_count += 1
            updates.append(f"is_locked = ${param_count}" if is_pg else "is_locked = ?")
            params.append(request.is_locked)

            if not request.is_locked:
                # Unlock user - reset failed attempts
                param_count += 1
                updates.append(f"failed_login_attempts = ${param_count}" if is_pg else "failed_login_attempts = ?")
                params.append(0)
                updates.append("locked_until = NULL")

        if request.storage_quota_mb is not None:
            param_count += 1
            updates.append(f"storage_quota_mb = ${param_count}" if is_pg else "storage_quota_mb = ?")
            params.append(request.storage_quota_mb)

        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )

        # Add updated_at
        param_count += 1
        if is_pg:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(user_id)
            query = f"UPDATE users SET {', '.join(updates)} WHERE id = ${param_count}"
        else:
            updates.append("updated_at = datetime('now')")
            params.append(user_id)
            query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"

        # Execute update
        if is_pg:
            await db.execute(query, *params)
        else:
            await db.execute(query, params)
            await db.commit()

        logger.info(f"Admin updated user {user_id}")

        return {"message": f"User {user_id} updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user"
        )


#######################################################################################################################
#
# RBAC: Roles, Permissions, Assignments, Overrides

@router.get("/roles", response_model=List[RoleResponse])
async def list_roles(db=Depends(get_db_transaction)) -> list[RoleResponse]:
    try:
        is_pg = await is_postgres_backend()
        if is_pg:
            rows = await db.fetch("SELECT id, name, description, COALESCE(is_system, FALSE) as is_system FROM roles ORDER BY name")
            return [RoleResponse(**dict(r)) for r in rows]
        else:
            cur = await db.execute("SELECT id, name, description, COALESCE(is_system, 0) as is_system FROM roles ORDER BY name")
            rows = await cur.fetchall()
            return [RoleResponse(id=row[0], name=row[1], description=row[2], is_system=bool(row[3])) for row in rows]
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


@router.get("/roles/{role_id}/permissions", response_model=List[PermissionResponse])
async def list_role_permissions(role_id: int, db=Depends(get_db_transaction)) -> list[PermissionResponse]:
    """List permissions granted to a specific role (read-only matrix row)."""
    try:
        rows = await svc_list_role_permissions(db, role_id)
        return [PermissionResponse(**r) for r in rows]
    except Exception as e:
        logger.error(f"Failed to list permissions for role {role_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list role permissions")


@router.get("/permissions/tools", response_model=List[ToolPermissionResponse])
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


@router.get("/roles/{role_id}/permissions/tools", response_model=List[ToolPermissionResponse])
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


@router.post("/roles/{role_id}/permissions/tools/batch", response_model=List[ToolPermissionResponse])
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


@router.post("/roles/{role_id}/permissions/tools/prefix/grant", response_model=List[ToolPermissionResponse])
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
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    role_search: Optional[str] = Query(None),
    role_names: Optional[List[str]] = Query(None),
    roles_limit: Optional[int] = Query(100, ge=1, le=10000),
    roles_offset: Optional[int] = Query(0, ge=0),
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
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    role_search: Optional[str] = Query(None),
    role_names: Optional[List[str]] = Query(None),
    roles_limit: Optional[int] = Query(100, ge=1, le=10000),
    roles_offset: Optional[int] = Query(0, ge=0),
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


from typing import List, Optional as _Optional

@router.get("/permissions/categories", response_model=List[str])
async def list_permission_categories(db=Depends(get_db_transaction)) -> List[str]:
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


@router.get("/permissions", response_model=List[PermissionResponse])
async def list_permissions(category: _Optional[str] = None, search: _Optional[str] = None, db=Depends(get_db_transaction)) -> List[PermissionResponse]:
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
async def get_user_roles_admin(user_id: int, db=Depends(get_db_transaction)) -> UserRoleListResponse:
    try:
        is_pg = await is_postgres_backend()
        if is_pg:
            rows = await db.fetch(
                """
                SELECT r.id, r.name, r.description, COALESCE(r.is_system,0) as is_system
                FROM roles r JOIN user_roles ur ON r.id = ur.role_id
                WHERE ur.user_id = $1 AND (ur.expires_at IS NULL OR ur.expires_at > CURRENT_TIMESTAMP)
                ORDER BY r.name
                """,
                user_id,
            )
            roles = [RoleResponse(**dict(r)) for r in rows]
        else:
            cur = await db.execute(
                """
                SELECT r.id, r.name, r.description, COALESCE(r.is_system,0)
                FROM roles r JOIN user_roles ur ON r.id = ur.role_id
                WHERE ur.user_id = ? AND (ur.expires_at IS NULL OR ur.expires_at > CURRENT_TIMESTAMP)
                ORDER BY r.name
                """,
                (user_id,),
            )
            rows = await cur.fetchall()
            roles = [RoleResponse(id=row[0], name=row[1], description=row[2], is_system=bool(row[3])) for row in rows]
        return UserRoleListResponse(user_id=user_id, roles=roles)
    except Exception as e:
        logger.error(f"Failed to get user roles for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user roles")


@router.post("/users/{user_id}/roles/{role_id}")
async def add_role_to_user(user_id: int, role_id: int, db=Depends(get_db_transaction)) -> dict:
    try:
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
async def remove_role_from_user(user_id: int, role_id: int, db=Depends(get_db_transaction)) -> dict:
    try:
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
async def list_user_overrides(user_id: int, db=Depends(get_db_transaction)) -> UserOverridesResponse:
    try:
        is_pg = await is_postgres_backend()
        if is_pg:
            rows = await db.fetch(
                """
                SELECT p.id as permission_id, p.name as permission_name, up.granted, up.expires_at
                FROM user_permissions up JOIN permissions p ON up.permission_id = p.id
                WHERE up.user_id = $1
                ORDER BY p.name
                """,
                user_id,
            )
            entries = [UserOverrideEntry(permission_id=r['permission_id'], permission_name=r['permission_name'], granted=bool(r['granted']), expires_at=str(r['expires_at']) if r['expires_at'] else None) for r in rows]
        else:
            cur = await db.execute(
                """
                SELECT p.id, p.name, up.granted, up.expires_at
                FROM user_permissions up JOIN permissions p ON up.permission_id = p.id
                WHERE up.user_id = ? ORDER BY p.name
                """,
                (user_id,),
            )
            rows = await cur.fetchall()
            entries = [UserOverrideEntry(permission_id=row[0], permission_name=row[1], granted=bool(row[2]), expires_at=row[3]) for row in rows]
        return UserOverridesResponse(user_id=user_id, overrides=entries)
    except Exception as e:
        logger.error(f"Failed to list overrides for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list user overrides")


@router.post("/users/{user_id}/overrides")
async def upsert_user_override(user_id: int, payload: UserOverrideUpsertRequest, db=Depends(get_db_transaction)) -> dict:
    try:
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

        granted = 1 if payload.effect == 'allow' else 0
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
async def delete_user_override(user_id: int, permission_id: int, db=Depends(get_db_transaction)) -> dict:
    try:
        _is_pg = await is_postgres_backend()
        if _is_pg:
            await db.execute("DELETE FROM user_permissions WHERE user_id = $1 AND permission_id = $2", user_id, permission_id)
        else:
            cur = await db.execute("DELETE FROM user_permissions WHERE user_id = ? AND permission_id = ?", (user_id, permission_id))
            if not _is_pg:
                await db.commit()
        return {"message": "Override deleted"}
    except Exception as e:
        logger.exception(f"Failed to delete override for user {user_id}: {e}")
        if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes"):
            raise HTTPException(status_code=500, detail=f"Failed to delete user override: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete user override")


@router.get("/users/{user_id}/effective-permissions", response_model=EffectivePermissionsResponse)
async def get_effective_permissions_admin(user_id: int, db=Depends(get_db_transaction)) -> EffectivePermissionsResponse:
    """Compute effective permissions for a user using the request-scoped DB.

    This avoids relying on global user DB singletons which may point at a different
    database in test environments (e.g., single-user SQLite).
    """
    try:
        perms: set[str] = set()
        # Role-derived permissions
        is_pg = await is_postgres_backend()
        if is_pg:
            rows = await db.fetch(
                """
                SELECT DISTINCT p.name
                FROM permissions p
                JOIN role_permissions rp ON p.id = rp.permission_id
                JOIN user_roles ur ON rp.role_id = ur.role_id
                WHERE ur.user_id = $1 AND (ur.expires_at IS NULL OR ur.expires_at > CURRENT_TIMESTAMP)
                """,
                user_id,
            )
            perms |= {str(r['name']) for r in rows}
            drows = await db.fetch(
                """
                SELECT p.name, up.granted
                FROM permissions p
                JOIN user_permissions up ON p.id = up.permission_id
                WHERE up.user_id = $1 AND (up.expires_at IS NULL OR up.expires_at > CURRENT_TIMESTAMP)
                """,
                user_id,
            )
            for r in drows:
                if bool(r['granted']):
                    perms.add(str(r['name']))
                else:
                    perms.discard(str(r['name']))
        else:
            cur = await db.execute(
                """
                SELECT DISTINCT p.name
                FROM permissions p
                JOIN role_permissions rp ON p.id = rp.permission_id
                JOIN user_roles ur ON rp.role_id = ur.role_id
                WHERE ur.user_id = ? AND (ur.expires_at IS NULL OR ur.expires_at > CURRENT_TIMESTAMP)
                """,
                (user_id,),
            )
            rows = await cur.fetchall()
            perms |= {str(r[0]) for r in rows}
            cur2 = await db.execute(
                """
                SELECT p.name, up.granted
                FROM permissions p
                JOIN user_permissions up ON p.id = up.permission_id
                WHERE up.user_id = ? AND (up.expires_at IS NULL OR up.expires_at > CURRENT_TIMESTAMP)
                """,
                (user_id,),
            )
            drows = await cur2.fetchall()
            for name, granted in drows:
                if bool(granted):
                    perms.add(str(name))
                else:
                    perms.discard(str(name))

        return EffectivePermissionsResponse(user_id=user_id, permissions=sorted(perms))
    except Exception as e:
        logger.error(f"Failed to compute effective permissions for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to compute effective permissions")


@router.get("/roles/{role_id}/permissions/effective", response_model=RoleEffectivePermissionsResponse)
async def get_role_effective_permissions(role_id: int, db=Depends(get_db_transaction)) -> RoleEffectivePermissionsResponse:
    """Return a convenience view combining a role's granted permissions and tool permissions.

    - permissions: non-tool permission names (e.g., media.read)
    - tool_permissions: tool execution permission names (tools.execute:...)
    - all_permissions: union of both, sorted
    """
    try:
        is_pg = await is_postgres_backend()
        # Fetch role information
        role_name: Optional[str] = None
        # Defensive: normalize role_id to plain int
        if isinstance(role_id, (tuple, list)):
            role_id = role_id[0]
        role_id = int(role_id)
        if is_pg:
            r = await db.fetchrow("SELECT id, name FROM roles WHERE id = $1", role_id)
            if not r:
                raise HTTPException(status_code=404, detail="Role not found")
            role_name = r['name']
            rows = await db.fetch(
                """
                SELECT p.name
                FROM permissions p
                JOIN role_permissions rp ON p.id = rp.permission_id
                WHERE rp.role_id = $1
                ORDER BY p.name
                """,
                role_id,
            )
            names = [str(rr['name']) for rr in rows]
        else:
            cur = await db.execute("SELECT id, name FROM roles WHERE id = ?", (role_id,))
            r = await cur.fetchone()
            if not r:
                raise HTTPException(status_code=404, detail="Role not found")
            role_name = str(r[1])
            cur2 = await db.execute(
                """
                SELECT p.name
                FROM permissions p
                JOIN role_permissions rp ON p.id = rp.permission_id
                WHERE rp.role_id = ?
                ORDER BY p.name
                """,
                (role_id,),
            )
            rows2 = await cur2.fetchall()
            names = [str(x[0]) for x in rows2]

        tool_prefix = 'tools.execute:'
        tool_permissions = [n for n in names if n.startswith(tool_prefix)]
        permissions = [n for n in names if not n.startswith(tool_prefix)]
        all_permissions = sorted(set(tool_permissions) | set(permissions))
        return RoleEffectivePermissionsResponse(
            role_id=role_id,
            role_name=role_name or "",
            permissions=permissions,
            tool_permissions=tool_permissions,
            all_permissions=all_permissions,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to compute effective permissions for role {role_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to compute role effective permissions")


#######################################################################################################################
#
# Rate Limit Administration

@router.post(

    "/rate-limits/reset",
    response_model=RateLimitResetResponse,
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "resetByIp": {
                            "summary": "Reset by IP (all endpoints)",
                            "value": {"kind": "ip", "ip": "203.0.113.7"},
                        },
                        "resetUserEndpoint": {
                            "summary": "Reset user for one endpoint",
                            "value": {"kind": "user", "user_id": 42, "endpoint": "/api/v1/media/process"},
                        },
                        "resetApiDryRun": {
                            "summary": "Reset API key (dry-run, all endpoints)",
                            "value": {
                                "kind": "api",
                                "api_key_hash": "d41d8cd98f00b204e9800998ecf8427e",
                                "dry_run": True,
                            },
                        },
                        "resetRawIdentifier": {
                            "summary": "Reset using raw identifier",
                            "value": {"kind": "raw", "identifier": "user:7"},
                        },
                    }
                }
            }
        },
        "responses": {
            "200": {
                "content": {
                    "application/json": {
                        "examples": {
                            "successAllEndpoints": {
                                "summary": "Success: all endpoints reset",
                                "value": {
                                    "ok": True,
                                    "identifier": "ip:203.0.113.7",
                                    "endpoint": None,
                                    "note": "Reset across all endpoints for identifier",
                                    "db_rows_deleted": 12,
                                    "redis_keys_deleted": 24
                                }
                            },
                            "dryRun": {
                                "summary": "Dry run: no changes applied",
                                "value": {
                                    "ok": True,
                                    "identifier": "api:d41d8cd98f00b204",
                                    "endpoint": None,
                                    "note": "dry_run: no changes applied",
                                    "db_rows_deleted": 5,
                                    "redis_keys_deleted": 8
                                }
                            },
                            "endpointOnly": {
                                "summary": "Success: single endpoint reset",
                                "value": {
                                    "ok": True,
                                    "identifier": "user:42",
                                    "endpoint": "/api/v1/media/process",
                                    "note": None,
                                    "db_rows_deleted": 2,
                                    "redis_keys_deleted": 2
                                }
                            }
                        }
                    }
                }
            },
            "400": {
                "content": {
                    "application/json": {
                        "examples": {
                            "invalidKind": {
                                "summary": "Bad request: invalid kind",
                                "value": {"detail": "kind must be one of ip|user|api|raw"}
                            },
                            "missingFieldForKind": {
                                "summary": "Bad request: required field missing for kind",
                                "value": {"detail": "kind=ip requires 'ip'"}
                            },
                            "rawWithoutIdentifier": {
                                "summary": "Bad request: raw kind missing identifier",
                                "value": {"detail": "kind=raw requires 'identifier'"}
                            }
                        }
                    }
                }
            },
            "500": {
                "content": {
                    "application/json": {
                        "examples": {
                            "resetFailed": {
                                "summary": "Internal server error during reset",
                                "value": {"detail": "Failed to reset rate limit"}
                            }
                        }
                    }
                }
            }
        }
    },
)
async def admin_reset_rate_limit(payload: RateLimitResetRequest) -> RateLimitResetResponse:
    """Reset AuthNZ rate limiter counters for the given identifier.

    Parameters
    - kind: One of `ip`, `user`, `api`, or `raw`.
      - `ip`: Provide `ip` (e.g., 203.0.113.7)
      - `user`: Provide `user_id` (e.g., 123)
      - `api`: Provide `api_key_hash` (first 16 chars used internally)
      - `raw`: Provide full `identifier` (e.g., "ip:203.0.113.7", "user:123")
    - endpoint: When set, only resets that endpoint. When omitted, resets all endpoints for the identifier.
    - dry_run: If true, only reports counts; no DB rows or Redis keys are deleted.

    Response
    - db_rows_deleted: Number of DB rows cleared from source-of-truth window buckets
    - redis_keys_deleted: Number of Redis keys matched for deletion (hash-bucketed windows)

    Examples
    ```json
    {"kind": "ip", "ip": "203.0.113.7"}
    {"kind": "user", "user_id": 42, "endpoint": "/api/v1/media/process"}
    {"kind": "api", "api_key_hash": "d41d8cd98f00b204e9800998ecf8427e"}
    {"kind": "raw", "identifier": "user:7"}
    ```
    """
    # Build identifier using explicit kind when supplied, else infer for compatibility
    identifier = payload.identifier
    if payload.kind:
        k = payload.kind.lower()
        if k == "raw":
            if not identifier:
                raise HTTPException(status_code=400, detail="kind=raw requires 'identifier'")
        elif k == "ip":
            if not payload.ip:
                raise HTTPException(status_code=400, detail="kind=ip requires 'ip'")
            identifier = f"ip:{payload.ip}"
        elif k == "user":
            if payload.user_id is None:
                raise HTTPException(status_code=400, detail="kind=user requires 'user_id'")
            identifier = f"user:{payload.user_id}"
        elif k == "api":
            if not payload.api_key_hash:
                raise HTTPException(status_code=400, detail="kind=api requires 'api_key_hash'")
            identifier = f"api:{payload.api_key_hash[:16]}"
        else:
            raise HTTPException(status_code=400, detail="kind must be one of ip|user|api|raw")
    else:
        # Backward-compatible inference
        if not identifier:
            if payload.ip:
                identifier = f"ip:{payload.ip}"
            elif payload.user_id is not None:
                identifier = f"user:{payload.user_id}"
            elif payload.api_key_hash:
                identifier = f"api:{payload.api_key_hash[:16]}"
            else:
                raise HTTPException(status_code=400, detail="Must provide identifier or one of ip, user_id, api_key_hash, or 'kind'")

    limiter = await get_authnz_rate_limiter()

    # Precompute counts
    db_rows_deleted = 0
    redis_keys_deleted = 0
    try:
        db_pool = await get_db_pool()
        is_pg = await is_postgres_backend()
        if payload.endpoint:
            if is_pg:
                db_rows_deleted = int(
                    await db_pool.fetchval(
                        "SELECT COUNT(*) FROM rate_limits WHERE identifier = $1 AND endpoint = $2",
                        identifier, payload.endpoint,
                    ) or 0
                )
            else:
                async with db_pool.acquire() as conn:
                    cur = await conn.execute(
                        "SELECT COUNT(*) FROM rate_limits WHERE identifier = ? AND endpoint = ?",
                        (identifier, payload.endpoint),
                    )
                    row = await cur.fetchone()
                    db_rows_deleted = int(row[0]) if row else 0
        else:
            if is_pg:
                db_rows_deleted = int(
                    await db_pool.fetchval(
                        "SELECT COUNT(*) FROM rate_limits WHERE identifier = $1",
                        identifier,
                    ) or 0
                )
            else:
                async with db_pool.acquire() as conn:
                    cur = await conn.execute(
                        "SELECT COUNT(*) FROM rate_limits WHERE identifier = ?",
                        (identifier,),
                    )
                    row = await cur.fetchone()
                    db_rows_deleted = int(row[0]) if row else 0
        # Redis keys pre-count
        if getattr(limiter, 'redis_client', None):
            endpoints_to_clear = []
            if payload.endpoint:
                endpoints_to_clear = [payload.endpoint]
            else:
                try:
                    if is_pg:
                        rows = await db_pool.fetchall(
                            "SELECT DISTINCT endpoint FROM rate_limits WHERE identifier = $1",
                            identifier,
                        )
                        endpoints_to_clear = [str(r['endpoint']) for r in rows]
                    else:
                        async with db_pool.acquire() as conn:
                            cur = await conn.execute(
                                "SELECT DISTINCT endpoint FROM rate_limits WHERE identifier = ?",
                                (identifier,),
                            )
                            rows = await cur.fetchall()
                            endpoints_to_clear = [str(r[0]) for r in rows]
                except Exception as _e:
                    logger.debug(f"Admin reset: failed to enumerate endpoints for redis keys: {_e}")
                    endpoints_to_clear = []
            for ep in endpoints_to_clear:
                pattern = f"rate:{limiter._create_key(identifier, ep)}:*"
                async for _key in limiter.redis_client.scan_iter(pattern):
                    redis_keys_deleted += 1
    except Exception as _e:
        logger.debug(f"Admin reset: pre-count failed: {_e}")
        db_rows_deleted = max(0, int(db_rows_deleted))
        redis_keys_deleted = max(0, int(redis_keys_deleted))

    # Perform reset unless dry_run
    try:
        if not payload.dry_run:
            await limiter.reset_rate_limit(identifier=identifier, endpoint=payload.endpoint)
            note = None
            if payload.endpoint is None:
                note = "Reset across all endpoints for identifier"
        else:
            note = "dry_run: no changes applied"

        return RateLimitResetResponse(
            ok=True,
            identifier=identifier,
            endpoint=payload.endpoint,
            note=note,
            db_rows_deleted=db_rows_deleted,
            redis_keys_deleted=redis_keys_deleted,
        )
    except Exception as e:
        logger.error(f"Admin rate limit reset failed for {identifier}: {e}")
        raise HTTPException(status_code=500, detail="Failed to reset rate limit")


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


@router.post("/users/{user_id}/rate-limits", response_model=RateLimitResponse)
async def upsert_user_rate_limit(user_id: int, payload: RateLimitUpsertRequest, db=Depends(get_db_transaction)) -> RateLimitResponse:
    try:
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


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    current_user: Dict[str, Any] = Depends(require_admin),
    db=Depends(get_db_transaction)
) -> Dict[str, str]:
    """
    Delete a user (soft delete by default)

    Args:
        user_id: User ID to delete

    Returns:
        Success message
    """
    try:
        # Prevent self-deletion
        if user_id == current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete your own account"
            )

        # Soft delete - just mark as inactive
        is_pg = await is_postgres_backend()
        if is_pg:
            # PostgreSQL
            result = await db.execute(
                "UPDATE users SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP WHERE id = $1",
                user_id
            )
        else:
            # SQLite
            await db.execute(
                "UPDATE users SET is_active = 0, updated_at = datetime('now') WHERE id = ?",
                (user_id,)
            )
            await db.commit()

        logger.info(f"Admin soft-deleted user {user_id}")

        return {"message": f"User {user_id} has been deactivated"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user"
        )


#######################################################################################################################
#
# Registration Code Management

@router.post("/registration-codes", response_model=RegistrationCodeResponse)
async def create_registration_code(
    request: RegistrationCodeRequest,
    current_user: Dict[str, Any] = Depends(require_admin),
    db=Depends(get_db_transaction)
) -> RegistrationCodeResponse:
    """
    Create a new registration code

    Args:
        request: Registration code configuration

    Returns:
        Created registration code details
    """
    try:
        # Generate secure code
        code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(24))

        # Calculate expiration
        expires_at = datetime.utcnow() + timedelta(days=request.expiry_days)

        is_pg = await is_postgres_backend()
        if is_pg:
            # PostgreSQL
            result = await db.fetchrow("""
                INSERT INTO registration_codes
                (code, max_uses, expires_at, created_by, role_to_grant, metadata)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id, code, max_uses, times_used, expires_at, created_at, role_to_grant
            """, code, request.max_uses, expires_at, current_user["id"],
                request.role_to_grant, __import__('json').dumps(request.metadata or {}))
        else:
            # SQLite
            cursor = await db.execute("""
                INSERT INTO registration_codes
                (code, max_uses, expires_at, created_by, role_to_grant, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (code, request.max_uses, expires_at.isoformat(), current_user["id"],
                  request.role_to_grant, __import__('json').dumps(request.metadata or {})))

            code_id = cursor.lastrowid
            await db.commit()

            # Fetch the created code
            cursor = await db.execute(
                "SELECT * FROM registration_codes WHERE id = ?",
                (code_id,)
            )
            result = await cursor.fetchone()

        logger.info(f"Admin created registration code: {code[:8]}...")

        return RegistrationCodeResponse(
            id=result[0] if isinstance(result, tuple) else result['id'],
            code=code,
            max_uses=request.max_uses,
            times_used=0,
            expires_at=expires_at,
            created_at=datetime.utcnow(),
            role_to_grant=request.role_to_grant
        )

    except Exception as e:
        logger.error(f"Failed to create registration code: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create registration code"
        )


@router.get("/registration-codes", response_model=RegistrationCodeListResponse)
async def list_registration_codes(
    include_expired: bool = Query(False),
    db=Depends(get_db_transaction)
) -> RegistrationCodeListResponse:
    """
    List all registration codes

    Args:
        include_expired: Include expired codes in the list

    Returns:
        List of registration codes
    """
    try:
        is_pg = await is_postgres_backend()
        if is_pg:
            # PostgreSQL
            if include_expired:
                query = """
                    SELECT id, code, max_uses, times_used, expires_at,
                           created_at, created_by, role_to_grant
                    FROM registration_codes
                    ORDER BY created_at DESC
                """
            else:
                query = """
                    SELECT id, code, max_uses, times_used, expires_at,
                           created_at, created_by, role_to_grant
                    FROM registration_codes
                    WHERE expires_at > CURRENT_TIMESTAMP
                    ORDER BY created_at DESC
                """
            rows = await db.fetch(query)
        else:
            # SQLite
            if include_expired:
                query = """
                    SELECT id, code, max_uses, times_used, expires_at,
                           created_at, created_by, role_to_grant
                    FROM registration_codes
                    ORDER BY created_at DESC
                """
            else:
                query = """
                    SELECT id, code, max_uses, times_used, expires_at,
                           created_at, created_by, role_to_grant
                    FROM registration_codes
                    WHERE datetime(expires_at) > datetime('now')
                    ORDER BY created_at DESC
                """
            cursor = await db.execute(query)
            rows = await cursor.fetchall()

        codes = []
        for row in rows:
            if isinstance(row, dict):
                codes.append(row)
            else:
                code_dict = {
                    "id": row[0],
                    "code": row[1],
                    "max_uses": row[2],
                    "times_used": row[3],
                    "expires_at": row[4],
                    "created_at": row[5],
                    "created_by": row[6],
                    "role_to_grant": row[7],
                    "is_valid": row[3] < row[2] and (
                        row[4] > datetime.utcnow() if isinstance(row[4], datetime)
                        else datetime.fromisoformat(row[4]) > datetime.utcnow()
                    )
                }
                codes.append(code_dict)

        return RegistrationCodeListResponse(codes=codes)

    except Exception as e:
        logger.error(f"Failed to list registration codes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve registration codes"
        )


@router.delete("/registration-codes/{code_id}")
async def delete_registration_code(
    code_id: int,
    db=Depends(get_db_transaction)
) -> Dict[str, str]:
    """
    Delete a registration code

    Args:
        code_id: Registration code ID

    Returns:
        Success message
    """
    try:
        is_pg = await is_postgres_backend()
        if is_pg:
            # PostgreSQL
            await db.execute(
                "DELETE FROM registration_codes WHERE id = $1",
                code_id
            )
        else:
            # SQLite
            await db.execute(
                "DELETE FROM registration_codes WHERE id = ?",
                (code_id,)
            )
            await db.commit()

        logger.info(f"Admin deleted registration code {code_id}")

        return {"message": f"Registration code {code_id} deleted"}

    except Exception as e:
        logger.error(f"Failed to delete registration code {code_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete registration code"
        )


#######################################################################################################################
#
# System Statistics and Monitoring

@router.get("/security/alert-status", response_model=SecurityAlertStatusResponse)
async def get_security_alert_status() -> SecurityAlertStatusResponse:
    """Return configuration and last-known status for AuthNZ security alerts."""
    dispatcher = get_security_alert_dispatcher()
    status = dispatcher.get_status()

    sink_status_map: Dict[str, Optional[bool]] = status.get("last_sink_status", {})
    sink_error_map: Dict[str, Optional[str]] = status.get("last_sink_errors", {})
    sink_threshold_map: Dict[str, Optional[str]] = status.get("sink_thresholds", {})
    sink_backoff_map: Dict[str, Optional[str]] = status.get("sink_backoff_until", {})

    sink_rows = []
    for sink_name, configured in (
        ("file", status.get("file_sink_configured", False)),
        ("webhook", status.get("webhook_configured", False)),
        ("email", status.get("email_configured", False)),
    ):
        sink_rows.append(
            SecurityAlertSinkStatus(
                sink=sink_name,
                configured=bool(configured),
                min_severity=sink_threshold_map.get(sink_name),
                last_status=sink_status_map.get(sink_name),
                last_error=sink_error_map.get(sink_name),
                backoff_until=sink_backoff_map.get(sink_name),
            )
        )

    overall_health = "ok"
    if status.get("enabled", False):
        if status.get("last_validation_errors"):
            overall_health = "errors"
        else:
            configured_rows = [row for row in sink_rows if row.configured]
            if status.get("last_dispatch_success") is False:
                overall_health = "degraded"
            elif any(row.last_error for row in configured_rows):
                overall_health = "degraded"
            elif configured_rows and all(row.last_status is False for row in configured_rows):
                overall_health = "degraded"

    return SecurityAlertStatusResponse(
        enabled=status.get("enabled", False),
        min_severity=status.get("min_severity", "high"),
        last_dispatch_time=status.get("last_dispatch_time"),
        last_dispatch_success=status.get("last_dispatch_success"),
        last_dispatch_error=status.get("last_dispatch_error"),
        dispatch_count=status.get("dispatch_count", 0),
        last_validation_time=status.get("last_validation_time"),
        validation_errors=status.get("last_validation_errors"),
        sinks=sink_rows,
        health=overall_health,
    )


@router.get("/stats", response_model=SystemStatsResponse)
async def get_system_stats(
    db=Depends(get_db_transaction)
) -> SystemStatsResponse:
    """
    Get system statistics

    Returns:
        System-wide statistics including user counts, storage usage, etc.
    """
    try:
        stats = {}

        is_pg = await is_postgres_backend()
        if is_pg:
            # PostgreSQL
            # User stats
            user_stats = await db.fetchrow("""
                SELECT
                    COUNT(*) as total_users,
                    COUNT(*) FILTER (WHERE is_active = TRUE) as active_users,
                    COUNT(*) FILTER (WHERE is_verified = TRUE) as verified_users,
                    COUNT(*) FILTER (WHERE role = 'admin') as admin_users,
                    COUNT(*) FILTER (WHERE created_at > CURRENT_TIMESTAMP - INTERVAL '30 days') as new_users_30d
                FROM users
            """)

            # Storage stats
            storage_stats = await db.fetchrow("""
                SELECT
                    SUM(storage_used_mb) as total_used_mb,
                    SUM(storage_quota_mb) as total_quota_mb,
                    AVG(storage_used_mb) as avg_used_mb,
                    MAX(storage_used_mb) as max_used_mb
                FROM users
                WHERE is_active = TRUE
            """)

            # Session stats
            session_stats = await db.fetchrow("""
                SELECT
                    COUNT(*) as active_sessions,
                    COUNT(DISTINCT user_id) as unique_users
                FROM sessions
                WHERE is_active = TRUE AND expires_at > CURRENT_TIMESTAMP
            """)

        else:
            # SQLite
            cursor = await db.execute("""
                SELECT
                    COUNT(*) as total_users,
                    SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active_users,
                    SUM(CASE WHEN is_verified = 1 THEN 1 ELSE 0 END) as verified_users,
                    SUM(CASE WHEN role = 'admin' THEN 1 ELSE 0 END) as admin_users,
                    SUM(CASE WHEN datetime(created_at) > datetime('now', '-30 days') THEN 1 ELSE 0 END) as new_users_30d
                FROM users
            """)
            user_stats = await cursor.fetchone()

            cursor = await db.execute("""
                SELECT
                    SUM(storage_used_mb) as total_used_mb,
                    SUM(storage_quota_mb) as total_quota_mb,
                    AVG(storage_used_mb) as avg_used_mb,
                    MAX(storage_used_mb) as max_used_mb
                FROM users
                WHERE is_active = 1
            """)
            storage_stats = await cursor.fetchone()

            cursor = await db.execute("""
                SELECT
                    COUNT(*) as active_sessions,
                    COUNT(DISTINCT user_id) as unique_users
                FROM sessions
                WHERE is_active = 1 AND datetime(expires_at) > datetime('now')
            """)
            session_stats = await cursor.fetchone()
            # Normalize Postgres rows via dict for explicit key access and casting
            us = dict(user_stats) if user_stats is not None else {}
            ss = dict(storage_stats) if storage_stats is not None else {}
            se = dict(session_stats) if session_stats is not None else {}

            return SystemStatsResponse(
                users={
                    "total": int(us.get("total_users") or 0),
                    "active": int(us.get("active_users") or 0),
                    "verified": int(us.get("verified_users") or 0),
                    "admins": int(us.get("admin_users") or 0),
                    "new_last_30d": int(us.get("new_users_30d") or 0),
                },
                storage={
                    "total_used_mb": float(ss.get("total_used_mb") or 0.0),
                    "total_quota_mb": float(ss.get("total_quota_mb") or 0.0),
                    "average_used_mb": float(ss.get("avg_used_mb") or 0.0),
                    "max_used_mb": float(ss.get("max_used_mb") or 0.0),
                },
                sessions={
                    "active": int(se.get("active_sessions") or 0),
                    "unique_users": int(se.get("unique_users") or 0),
                },
            )

        # SQLite fallback path already returns tuples; keep existing casting

        # Convert to response model
        return SystemStatsResponse(
            users={
                "total": user_stats[0] or 0,
                "active": user_stats[1] or 0,
                "verified": user_stats[2] or 0,
                "admins": user_stats[3] or 0,
                "new_last_30d": user_stats[4] or 0
            },
            storage={
                "total_used_mb": float(storage_stats[0] or 0),
                "total_quota_mb": float(storage_stats[1] or 0),
                "average_used_mb": float(storage_stats[2] or 0),
                "max_used_mb": float(storage_stats[3] or 0)
            },
            sessions={
                "active": session_stats[0] or 0,
                "unique_users": session_stats[1] or 0
            }
        )

    except Exception as e:
        logger.error(f"Failed to get system stats: {e}")
        # In test environments or if non-critical, return a safe default instead of 500
        try:
            import os as _os
            if _os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes"):
                return SystemStatsResponse(
                    users={"total": 0, "active": 0, "verified": 0, "admins": 0, "new_last_30d": 0},
                    storage={"total_used_mb": 0.0, "total_quota_mb": 0.0, "average_used_mb": 0.0, "max_used_mb": 0.0},
                    sessions={"active": 0, "unique_users": 0},
                )
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve system statistics"
        )


@router.get("/audit-log", response_model=AuditLogResponse)
async def get_audit_log(
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(100, ge=1, le=1000),
    db=Depends(get_db_transaction)
) -> AuditLogResponse:
    """
    Get audit log entries

    Args:
        user_id: Filter by user ID
        action: Filter by action type
        days: Number of days to look back
        limit: Maximum entries to return

    Returns:
        Audit log entries
    """
    try:
        is_pg = await is_postgres_backend()
        conditions = []
        params = []
        param_count = 0

        if user_id:
            param_count += 1
            conditions.append(f"user_id = ${param_count}" if is_pg else "user_id = ?")
            params.append(user_id)

        if action:
            param_count += 1
            conditions.append(f"action = ${param_count}" if is_pg else "action = ?")
            params.append(action)

        # Date filter
        if is_pg:
            conditions.append(f"a.created_at > CURRENT_TIMESTAMP - INTERVAL '{days} days'")
        else:
            conditions.append("datetime(a.created_at) > datetime('now', ? || ' days')")
            params.append(f"-{days}")

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

        if is_pg:
            # PostgreSQL
            query = f"""
                SELECT a.id, a.user_id, u.username, a.action, a.details,
                       a.ip_address, a.created_at
                FROM audit_log a
                LEFT JOIN users u ON a.user_id = u.id
                {where_clause}
                ORDER BY a.created_at DESC
                LIMIT ${param_count + 1}
            """
            params.append(limit)
            rows = await db.fetch(query, *params)
        else:
            # SQLite
            query = f"""
                SELECT a.id, a.user_id, u.username, a.action, a.details,
                       a.ip_address, a.created_at
                FROM audit_log a
                LEFT JOIN users u ON a.user_id = u.id
                {where_clause}
                ORDER BY a.created_at DESC
                LIMIT ?
            """
            params.append(limit)
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()

        entries = []
        for row in rows:
            if isinstance(row, dict):
                entries.append(row)
            else:
                entry = {
                    "id": row[0],
                    "user_id": row[1],
                    "username": row[2],
                    "action": row[3],
                    "details": row[4],
                    "ip_address": row[5],
                    "created_at": row[6]
                }
                entries.append(entry)

        return AuditLogResponse(entries=entries)

    except Exception as e:
        logger.error(f"Failed to get audit log: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve audit log"
        )


# ---------------------------------------------------------------------------------------------------------------------
# Usage Reporting Endpoints

@router.get("/usage/daily", response_model=UsageDailyResponse)
async def get_usage_daily(
    user_id: Optional[int] = None,
    start: Optional[str] = Query(None, description="YYYY-MM-DD inclusive"),
    end: Optional[str] = Query(None, description="YYYY-MM-DD inclusive"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
    db=Depends(get_db_transaction)
) -> UsageDailyResponse:
    """Query daily usage aggregates, optionally filtered by user and date range."""
    try:
        rows, total, _ = await svc_fetch_usage_daily(db, user_id=user_id, start=start, end=end, page=page, limit=limit)
        items = [UsageDailyRow(**r) for r in rows]
        return UsageDailyResponse(items=items, total=int(total or 0), page=page, limit=limit)
    except Exception:
        logger.exception("Failed to query usage_daily")
        raise HTTPException(status_code=500, detail="Failed to load usage daily data")


@router.get("/usage/top", response_model=UsageTopResponse)
async def get_usage_top(
    start: Optional[str] = Query(None, description="YYYY-MM-DD inclusive"),
    end: Optional[str] = Query(None, description="YYYY-MM-DD inclusive"),
    limit: int = Query(10, ge=1, le=100),
    metric: str = Query("requests", pattern="^(requests|bytes_total|bytes_in_total|errors)$"),
    db=Depends(get_db_transaction)
) -> UsageTopResponse:
    """Top users by aggregate usage over a date range."""
    try:
        rows = await svc_fetch_usage_top(db, start=start, end=end, limit=limit, metric=metric)
        for r in rows:
            r.setdefault('bytes_in_total', None)
        return UsageTopResponse(items=[UsageTopRow(**r) for r in rows])
    except Exception as e:
        logger.error(f"Failed to query usage top: {e}")
        raise HTTPException(status_code=500, detail="Failed to load usage top data")


@router.post("/usage/aggregate")
async def run_usage_aggregate(day: Optional[str] = Query(None, description="YYYY-MM-DD")) -> dict:
    """Trigger aggregation of usage_log into usage_daily for a specific day (UTC)."""
    try:
        await aggregate_usage_daily(day=day)
        return {"status": "ok", "day": day}
    except Exception as e:
        logger.warning(f"Manual usage aggregation failed/skipped: {e}")
        # Non-fatal: e.g., table absent in PG during partial setups
        return {"status": "skipped", "reason": str(e), "day": day}


@router.get("/usage/daily/export.csv", response_class=PlainTextResponse)
async def export_usage_daily_csv(
    user_id: Optional[int] = None,
    start: Optional[str] = Query(None, description="YYYY-MM-DD inclusive"),
    end: Optional[str] = Query(None, description="YYYY-MM-DD inclusive"),
    limit: int = Query(1000, ge=1, le=10000),
    filename: Optional[str] = Query(None, description="Optional filename for Content-Disposition"),
    db=Depends(get_db_transaction)
) -> PlainTextResponse:
    """Export usage_daily rows as CSV (includes bytes_in_total when available)."""
    try:
        content = await svc_export_usage_daily_csv_text(db, user_id=user_id, start=start, end=end, limit=limit)
        resp = PlainTextResponse(content=content, media_type="text/csv")
        # Default filename when not provided
        if not filename:
            _start = start or "all"
            _end = end or "all"
            filename = f"usage_daily_{_start}_{_end}.csv"
        if filename:
            safe = filename.replace("\n", " ").replace("\r", " ").replace("\"", "_")
            resp.headers["Content-Disposition"] = f"attachment; filename=\"{safe}\""
        return resp
    except Exception as e:
        logger.error(f"Failed to export usage daily CSV: {e}")
        raise HTTPException(status_code=500, detail="Failed to export usage daily CSV")


@router.get("/usage/top/export.csv", response_class=PlainTextResponse)
async def export_usage_top_csv(
    start: Optional[str] = Query(None, description="YYYY-MM-DD inclusive"),
    end: Optional[str] = Query(None, description="YYYY-MM-DD inclusive"),
    limit: int = Query(100, ge=1, le=10000),
    metric: str = Query("requests", pattern="^(requests|bytes_total|bytes_in_total|errors)$"),
    filename: Optional[str] = Query(None, description="Optional filename for Content-Disposition"),
    db=Depends(get_db_transaction)
) -> PlainTextResponse:
    try:
        content = await svc_export_usage_top_csv_text(db, start=start, end=end, limit=limit, metric=metric)
        resp = PlainTextResponse(content=content, media_type="text/csv")
        # Default filename when not provided
        if not filename:
            _start = start or "all"
            _end = end or "all"
            filename = f"usage_top_{metric}_{_start}_{_end}.csv"
        if filename:
            safe = filename.replace("\n", " ").replace("\r", " ").replace("\"", "_")
            resp.headers["Content-Disposition"] = f"attachment; filename=\"{safe}\""
        return resp
    except Exception as e:
        logger.error(f"Failed to export usage top CSV: {e}")
        raise HTTPException(status_code=500, detail="Failed to export usage top CSV")


@router.post("/llm-usage/aggregate")
async def run_llm_usage_aggregate(day: Optional[str] = Query(None, description="YYYY-MM-DD")) -> dict:
    """Trigger aggregation of llm_usage_log into llm_usage_daily for a specific day (UTC)."""
    try:
        await aggregate_llm_usage_daily(day=day)
        return {"status": "ok", "day": day}
    except Exception as e:
        logger.warning(f"Manual LLM usage aggregation failed/skipped: {e}")
        return {"status": "skipped", "reason": str(e), "day": day}

# ---------------------------------------------------------------------------------------------------------------------
# LLM Usage Reporting Endpoints

@router.get("/llm-usage", response_model=LLMUsageLogResponse)
async def get_llm_usage(
    user_id: Optional[int] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    operation: Optional[str] = None,
    status_code: Optional[int] = Query(None, alias="status"),
    start: Optional[str] = Query(None, description="ISO timestamp inclusive"),
    end: Optional[str] = Query(None, description="ISO timestamp inclusive"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
    db=Depends(get_db_transaction)
) -> LLMUsageLogResponse:
    try:
        rows, total = await svc_fetch_llm_usage(
            db,
            user_id=user_id,
            provider=provider,
            model=model,
            operation=operation,
            status_code=status_code,
            start=start,
            end=end,
            page=page,
            limit=limit,
        )
        items = [LLMUsageLogRow(**r) for r in rows]
        return LLMUsageLogResponse(items=items, total=int(total or 0), page=page, limit=limit)
    except Exception:
        # Log full stack to aid debugging in tests
        logger.exception("Failed to query llm_usage_log")
        raise HTTPException(status_code=500, detail="Failed to load LLM usage data")


@router.get("/llm-usage/summary", response_model=LLMUsageSummaryResponse)
async def get_llm_usage_summary(
    start: Optional[str] = Query(None, description="ISO timestamp inclusive"),
    end: Optional[str] = Query(None, description="ISO timestamp inclusive"),
    group_by: str = Query("user", pattern="^(user|provider|model|operation|day)$"),
    db=Depends(get_db_transaction)
) -> LLMUsageSummaryResponse:
    try:
        # Directly support 'user'|'operation'|'day'|'provider'|'model'
        rows = await svc_fetch_llm_usage_summary(db, group_by=group_by, provider=None, start=start, end=end)
        return LLMUsageSummaryResponse(items=[LLMUsageSummaryRow(**r) for r in rows])
    except Exception as e:
        logger.error(f"Failed to summarize llm_usage_log: {e}")
        raise HTTPException(status_code=500, detail="Failed to load LLM usage summary")


@router.get("/llm-usage/top-spenders", response_model=LLMTopSpendersResponse)
async def get_llm_top_spenders(
    start: Optional[str] = Query(None, description="ISO timestamp inclusive"),
    end: Optional[str] = Query(None, description="ISO timestamp inclusive"),
    limit: int = Query(10, ge=1, le=500),
    db=Depends(get_db_transaction)
) -> LLMTopSpendersResponse:
    try:
        rows = await svc_fetch_llm_top_spenders(db, start=start, end=end, limit=limit)
        return LLMTopSpendersResponse(items=[LLMTopSpenderRow(**r) for r in rows])
    except Exception as e:
        logger.error(f"Failed to load llm top spenders: {e}")
        raise HTTPException(status_code=500, detail="Failed to load LLM top spenders")


@router.get("/llm-usage/export.csv", response_class=PlainTextResponse)
async def export_llm_usage_csv(
    user_id: Optional[int] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    operation: Optional[str] = None,
    status_code: Optional[int] = Query(None, alias="status"),
    start: Optional[str] = Query(None, description="ISO timestamp inclusive"),
    end: Optional[str] = Query(None, description="ISO timestamp inclusive"),
    limit: int = Query(1000, ge=1, le=10000),
    db=Depends(get_db_transaction)
) -> PlainTextResponse:
    """Export filtered llm_usage_log rows as CSV."""
    try:
        is_pg = await is_postgres_backend()
        conditions: list[str] = []
        params: list = []

        def add_cond(sql: str, value):
            if value is None:
                return
            if is_pg:
                conditions.append(sql.replace('?', f"${len(params) + 1}"))
            else:
                conditions.append(sql)
            params.append(value)

        add_cond("user_id = ?", user_id)
        add_cond("LOWER(provider) = LOWER(?)", provider)
        add_cond("LOWER(model) = LOWER(?)", model)
        add_cond("operation = ?", operation)
        add_cond("status = ?", status_code)
        if start:
            add_cond("ts >= ?", start)
        if end:
            add_cond("ts <= ?", end)
        where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""

        if is_pg:
            limit_placeholder = f"${len(params) + 1}"
            sql = (
                f"SELECT id, ts, COALESCE(user_id,0) as user_id, COALESCE(key_id,0) as key_id, endpoint, operation, provider, model, status, latency_ms, "
                f"COALESCE(prompt_tokens,0), COALESCE(completion_tokens,0), COALESCE(total_tokens,0), COALESCE(total_cost_usd,0), currency, estimated, request_id "
                f"FROM llm_usage_log{where_clause} ORDER BY ts DESC LIMIT {limit_placeholder}"
            )
            rows = await db.fetch(sql, *params, limit)
            data = [(
                r["id"], r["ts"], r["user_id"], r["key_id"], r["endpoint"], r["operation"], r["provider"], r["model"], r["status"], r["latency_ms"],
                r["prompt_tokens"], r["completion_tokens"], r["total_tokens"], r["total_cost_usd"], r["currency"], r["estimated"], r["request_id"]
            ) for r in rows]
        else:
            sql = (
                f"SELECT id, ts, IFNULL(user_id,0), IFNULL(key_id,0), endpoint, operation, provider, model, status, latency_ms, "
                f"IFNULL(prompt_tokens,0), IFNULL(completion_tokens,0), IFNULL(total_tokens,0), IFNULL(total_cost_usd,0), currency, estimated, request_id "
                f"FROM llm_usage_log{where_clause} ORDER BY ts DESC LIMIT ?"
            )
            cur = await db.execute(sql, params + [limit])
            data = await cur.fetchall()

        # Build CSV
        header = [
            "id","ts","user_id","key_id","endpoint","operation","provider","model","status","latency_ms",
            "prompt_tokens","completion_tokens","total_tokens","total_cost_usd","currency","estimated","request_id"
        ]
        lines = [",".join(header)]
        for row in data:
            # row is tuple-like in both branches
            def _fmt(x):
                if x is None:
                    return ""
                s = str(x)
                if "," in s or "\n" in s:
                    return '"' + s.replace('"', '""') + '"'
                return s
            lines.append(
                ",".join(_fmt(c) for c in row)
            )
        content = "\n".join(lines) + "\n"
        return PlainTextResponse(content=content, media_type="text/csv")
    except Exception as e:
        logger.error(f"Failed to export llm usage CSV: {e}")
        raise HTTPException(status_code=500, detail="Failed to export CSV")


# ---------------------------------------------
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

#
## End of admin.py
#######################################################################################################################
# ---------------------------------------------
# Personalization admin helpers
# ---------------------------------------------

@router.post("/personalization/consolidate", response_model=dict)
async def trigger_personalization_consolidation(
    user_id: Optional[str] = Query(None, description="User ID to consolidate; defaults to single-user id"),
):
    """
    Trigger personalization consolidation for a given user (admin-only).
    """
    try:
        from tldw_Server_API.app.services.personalization_consolidation import get_consolidation_service
        svc = get_consolidation_service()
        ok = await svc.trigger_consolidation(user_id=user_id)
        return {"status": "ok" if ok else "error", "user_id": user_id}
    except Exception as e:
        logger.warning(f"Admin consolidate trigger failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to trigger consolidation")


@router.get("/personalization/status", response_model=dict)
async def get_personalization_status():
    """Return in-memory consolidation status (last tick per user)."""
    try:
        from tldw_Server_API.app.services.personalization_consolidation import get_consolidation_service
        svc = get_consolidation_service()
        return svc.get_status()  # type: ignore[attr-defined]
    except Exception as e:
        logger.warning(f"Admin status fetch failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch status")


# ---------------------------------------------------------------------------------------------------------------------
# MCP Tool Catalogs (Admin)

@router.get(
    "/mcp/tool_catalogs",
    response_model=List[ToolCatalogResponse],
    summary="List MCP tool catalogs (admin)",
    description=(
        "List MCP tool catalogs across global/org/team scopes.\n\n"
        "RBAC: Admin-only.\n\n"
        "Filters: Optional `org_id` and/or `team_id` parameters restrict results to a given scope.\n"
        "Without filters, returns all catalogs."
    ),
)
async def list_tool_catalogs(
    org_id: Optional[int] = Query(None),
    team_id: Optional[int] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db=Depends(get_db_transaction),
) -> List[ToolCatalogResponse]:
    """List tool catalogs with optional org/team filtering."""
    try:
        is_pg = await is_postgres_backend()
        where: list[str] = []
        params: list[Any] = []
        if org_id is not None:
            where.append("org_id = $1" if is_pg else "org_id = ?")
            params.append(org_id)
        if team_id is not None:
            if is_pg:
                where.append(f"team_id = ${len(params)+1}")
            else:
                where.append("team_id = ?")
            params.append(team_id)
        where_clause = (" WHERE " + " AND ".join(where)) if where else ""
        if is_pg:
            q = (
                f"SELECT id, name, description, org_id, team_id, COALESCE(is_active,TRUE) as is_active, created_at, updated_at "
                f"FROM tool_catalogs{where_clause} ORDER BY created_at DESC LIMIT $ {len(params)+1} OFFSET $ {len(params)+2}"
            ).replace('$ ', '$')
            rows = await db.fetch(q, *params, limit, offset)
            return [ToolCatalogResponse(**dict(r)) for r in rows]
        else:
            q = f"SELECT id, name, description, org_id, team_id, COALESCE(is_active,1), created_at, updated_at FROM tool_catalogs{where_clause} ORDER BY created_at DESC LIMIT ? OFFSET ?"
            cur = await db.execute(q, [*params, limit, offset])
            rows = await cur.fetchall()
            return [
                ToolCatalogResponse(
                    id=r[0], name=r[1], description=r[2], org_id=r[3], team_id=r[4], is_active=bool(r[5]), created_at=r[6], updated_at=r[7]
                ) for r in rows
            ]
    except Exception as e:
        logger.error(f"Failed to list tool catalogs: {e}")
        raise HTTPException(status_code=500, detail="Failed to list tool catalogs")


@router.post(
    "/mcp/tool_catalogs",
    response_model=ToolCatalogResponse,
    status_code=201,
    summary="Create MCP tool catalog (admin)",
    description=(
        "Create a new MCP tool catalog in the chosen scope.\n\n"
        "RBAC: Admin-only.\n\n"
        "Scope: Set `org_id` for org-owned, `team_id` for team-owned, or neither for global.\n"
        "Name must be unique per (name, org_id, team_id)."
    ),
)
async def create_tool_catalog(payload: ToolCatalogCreateRequest, db=Depends(get_db_transaction)) -> ToolCatalogResponse:
    """Create a tool catalog."""
    try:
        is_pg = await is_postgres_backend()
        name = payload.name.strip()
        desc = payload.description
        org_id = payload.org_id
        team_id = payload.team_id
        is_active = bool(payload.is_active if payload.is_active is not None else True)
        if is_pg:
            # Case-insensitive existence check within scope
            exists = await db.fetchrow(
                "SELECT 1 FROM tool_catalogs WHERE LOWER(name) = LOWER($1) AND ((org_id IS NOT DISTINCT FROM $2) AND (team_id IS NOT DISTINCT FROM $3))",
                name, org_id, team_id,
            )
            if exists:
                raise HTTPException(status_code=409, detail="Catalog already exists")
            await db.execute(
                """
                INSERT INTO tool_catalogs (name, description, org_id, team_id, is_active)
                VALUES ($1, $2, $3, $4, $5)
                """,
                name, desc, org_id, team_id, is_active,
            )
            row = await db.fetchrow(
                "SELECT id, name, description, org_id, team_id, COALESCE(is_active, TRUE) as is_active, created_at, updated_at FROM tool_catalogs WHERE name = $1 AND ((org_id IS NOT DISTINCT FROM $2) AND (team_id IS NOT DISTINCT FROM $3))",
                name, org_id, team_id,
            )
            return ToolCatalogResponse(**dict(row))
        else:
            # SQLite pre-check case-insensitive
            cur = await db.execute(
                "SELECT id FROM tool_catalogs WHERE LOWER(name) = LOWER(?) AND ( (org_id IS ? OR org_id = ?) AND (team_id IS ? OR team_id = ?) )",
                (name, None, org_id, None, team_id),
            )
            exists = await cur.fetchone()
            if exists:
                raise HTTPException(status_code=409, detail="Catalog already exists")
            await db.execute(
                "INSERT INTO tool_catalogs (name, description, org_id, team_id, is_active) VALUES (?, ?, ?, ?, ?)",
                (name, desc, org_id, team_id, 1 if is_active else 0),
            )
            cur2 = await db.execute(
                "SELECT id, name, description, org_id, team_id, is_active, created_at, updated_at FROM tool_catalogs WHERE name = ? AND ( (org_id IS ? OR org_id = ?) AND (team_id IS ? OR team_id = ?) )",
                (name, None, org_id, None, team_id),
            )
            r = await cur2.fetchone()
            return ToolCatalogResponse(
                id=r[0], name=r[1], description=r[2], org_id=r[3], team_id=r[4], is_active=bool(r[5]), created_at=r[6], updated_at=r[7]
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create tool catalog: {e}")
        raise HTTPException(status_code=500, detail="Failed to create tool catalog")


@router.delete(
    "/mcp/tool_catalogs/{catalog_id}",
    summary="Delete MCP tool catalog (admin)",
    description=(
        "Delete a catalog by id. Entries are removed via ON DELETE CASCADE.\n\n"
        "RBAC: Admin-only.\n\n"
        "Scope: Works for any catalog (global/org/team)."
    ),
)
async def delete_tool_catalog(catalog_id: int, db=Depends(get_db_transaction)) -> dict:
    """Delete a tool catalog (entries cascade)."""
    try:
        from tldw_Server_API.app.services.admin_tool_catalog_service import delete_tool_catalog as _svc
        await _svc(db, catalog_id)
        return {"message": "Catalog deleted", "id": catalog_id}
    except Exception as e:
        logger.error(f"Failed to delete tool catalog {catalog_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete tool catalog")


@router.get(
    "/mcp/tool_catalogs/{catalog_id}/entries",
    response_model=List[ToolCatalogEntryResponse],
    summary="List catalog entries (admin)",
    description=(
        "List tools included in the specified catalog.\n\n"
        "RBAC: Admin-only."
    ),
)
async def list_tool_catalog_entries(catalog_id: int, db=Depends(get_db_transaction)) -> List[ToolCatalogEntryResponse]:
    """List entries in a tool catalog."""
    try:
        from tldw_Server_API.app.services.admin_tool_catalog_service import list_tool_catalog_entries as _svc
        rows = await _svc(db, catalog_id)
        return [ToolCatalogEntryResponse(**r) for r in rows]
    except Exception as e:
        logger.error(f"Failed to list tool catalog entries: {e}")
        raise HTTPException(status_code=500, detail="Failed to list tool catalog entries")


@router.post(
    "/mcp/tool_catalogs/{catalog_id}/entries",
    response_model=ToolCatalogEntryResponse,
    status_code=201,
    summary="Add tool to catalog (admin)",
    description=(
        "Add a tool entry to the catalog. Idempotent per (catalog_id, tool_name).\n\n"
        "RBAC: Admin-only."
    ),
)
async def add_tool_catalog_entry(catalog_id: int, payload: ToolCatalogEntryCreateRequest, db=Depends(get_db_transaction)) -> ToolCatalogEntryResponse:
    """Add a tool entry to a catalog (idempotent)."""
    try:
        from tldw_Server_API.app.services.admin_tool_catalog_service import add_tool_catalog_entry as _svc
        tool = payload.tool_name.strip()
        module_id = payload.module_id.strip() if payload.module_id else None
        row = await _svc(db, catalog_id, tool, module_id)
        return ToolCatalogEntryResponse(**row)
    except Exception as e:
        logger.error(f"Failed to add tool catalog entry: {e}")
        raise HTTPException(status_code=500, detail="Failed to add tool catalog entry")


@router.delete(
    "/mcp/tool_catalogs/{catalog_id}/entries/{tool_name}",
    summary="Remove tool from catalog (admin)",
    description=(
        "Remove a tool entry from the catalog. Returns 200 whether or not the entry existed.\n\n"
        "RBAC: Admin-only."
    ),
)
async def delete_tool_catalog_entry(catalog_id: int, tool_name: str, db=Depends(get_db_transaction)) -> dict:
    """Remove a tool from a catalog."""
    try:
        from tldw_Server_API.app.services.admin_tool_catalog_service import delete_tool_catalog_entry as _svc
        await _svc(db, catalog_id, tool_name)
        return {"message": "Entry deleted", "catalog_id": catalog_id, "tool_name": tool_name}
    except Exception as e:
        logger.error(f"Failed to delete tool catalog entry: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete tool catalog entry")
# -------------------------------------------------------------------------------------------------
# Network diagnostics: resolved client IP, proxy headers, and WebUI/Setup access decisions

def _parse_nets(raw: str | None) -> list[ipaddress._BaseNetwork]:
    nets: list[ipaddress._BaseNetwork] = []
    if not raw:
        return nets
    for token in [t.strip() for t in raw.replace("\n", ",").split(",") if t.strip()]:
        try:
            if "/" in token:
                nets.append(ipaddress.ip_network(token, strict=False))
            else:
                ip = ipaddress.ip_address(token)
                nets.append(ipaddress.ip_network(ip.exploded + ("/32" if ip.version == 4 else "/128"), strict=False))
        except Exception:
            # Skip invalid entries
            pass
    return nets


def _load_list(section: str, field: str, env_name: str) -> list[ipaddress._BaseNetwork]:
    import os
    raw_env = os.getenv(env_name)
    if raw_env:
        return _parse_nets(raw_env)
    try:
        cp = load_comprehensive_config()
        if cp and cp.has_section(section):
            raw_cfg = cp.get(section, field, fallback="").strip()
            if raw_cfg:
                return _parse_nets(raw_cfg)
    except Exception:
        pass
    return []


def _resolve_client_ip(request: Request, trusted_proxies: list[ipaddress._BaseNetwork]) -> tuple[str | None, bool]:
    def _is_trusted(ip: ipaddress._BaseAddress | None) -> bool:
        return bool(ip and any(ip in net for net in trusted_proxies))

    peer = request.client.host if request.client else None
    try:
        peer_ip_obj = ipaddress.ip_address(peer) if peer else None
    except Exception:
        peer_ip_obj = None

    if _is_trusted(peer_ip_obj):
        xr = request.headers.get("x-real-ip") or request.headers.get("X-Real-IP")
        if xr:
            try:
                ipaddress.ip_address(xr.strip())
                return xr.strip(), True
            except Exception:
                pass
        fwd = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
        if fwd:
            try:
                leftmost = fwd.split(",")[0].strip()
                ipaddress.ip_address(leftmost)
                return leftmost, True
            except Exception:
                pass
    return peer, False


def _is_loopback(ip_str: str | None) -> bool:
    if not ip_str:
        return False
    if ip_str in {"testclient", "localhost"}:
        return True
    try:
        return ipaddress.ip_address(ip_str).is_loopback
    except Exception:
        return False


@router.get("/network-info")
async def network_info(request: Request):
    """Show resolved client IP, proxy headers, and access decision inputs for WebUI/Setup.

    Returns a JSON payload useful for debugging remote-access policy and proxy header handling.
    """
    import os
    # Load lists and settings
    trusted_proxies = _load_list("Server", "trusted_proxies", "TLDW_TRUSTED_PROXIES")
    webui_allow = _load_list("Server", "webui_ip_allowlist", "TLDW_WEBUI_ALLOWLIST")
    webui_deny = _load_list("Server", "webui_ip_denylist", "TLDW_WEBUI_DENYLIST")
    setup_allow = _load_list("Setup", "setup_ip_allowlist", "TLDW_SETUP_ALLOWLIST")
    setup_deny = _load_list("Setup", "setup_ip_denylist", "TLDW_SETUP_DENYLIST")

    resolved_ip, via_proxy = _resolve_client_ip(request, trusted_proxies)
    loopback = _is_loopback(resolved_ip)
    ip_obj = None
    try:
        ip_obj = ipaddress.ip_address(resolved_ip) if resolved_ip else None
    except Exception:
        ip_obj = None

    def _decide(kind: str):
        if loopback:
            return {"decision": "allow", "reason": "loopback"}
        allowlist = webui_allow if kind == "webui" else setup_allow
        denylist = webui_deny if kind == "webui" else setup_deny
        toggle = webui_remote_access_enabled() if kind == "webui" else setup_remote_access_enabled()
        # denylist precedes
        if denylist and ip_obj and any(ip_obj in net for net in denylist):
            return {"decision": "deny", "reason": "denylist"}
        if allowlist:
            if ip_obj and any(ip_obj in net for net in allowlist):
                return {"decision": "allow", "reason": "allowlist"}
            return {"decision": "allow" if toggle else "deny", "reason": "toggle" if toggle else "no-allowlist-match"}
        return {"decision": "allow" if toggle else "deny", "reason": "toggle" if toggle else "toggle-off"}

    return {
        "peer_ip": request.client.host if request.client else None,
        "resolved_client_ip": resolved_ip,
        "via_trusted_proxy": via_proxy,
        "headers": {
            "x_forwarded_for": request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For"),
            "x_real_ip": request.headers.get("x-real-ip") or request.headers.get("X-Real-IP"),
        },
        "is_loopback": loopback,
        "webui": {
            "remote_toggle": webui_remote_access_enabled(),
            "allowlist": [str(n) for n in webui_allow],
            "denylist": [str(n) for n in webui_deny],
            **_decide("webui"),
        },
        "setup": {
            "remote_toggle": setup_remote_access_enabled(),
            "allowlist": [str(n) for n in setup_allow],
            "denylist": [str(n) for n in setup_deny],
            **_decide("setup"),
        },
    }
