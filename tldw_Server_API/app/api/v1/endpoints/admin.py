# admin.py
# Description: Admin endpoints for user management, registration codes, and system administration
#
# Imports
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import secrets
import string
#
# 3rd-party imports
from fastapi import APIRouter, Depends, HTTPException, status, Query
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
    AuditLogResponse,
    UserQuotaUpdateRequest
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
)
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import (
    require_admin,
    get_db_transaction,
    get_storage_service_dep
)
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

#######################################################################################################################
#
# Router Configuration

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],  # All endpoints require admin role
    responses={403: {"description": "Not authorized"}}
)


#######################################################################################################################
#
# User Management Endpoints

@router.get("/users", response_model=UserListResponse)
async def list_users(
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
    try:
        offset = (page - 1) * limit
        
        # Build query conditions
        conditions = []
        params = []
        param_count = 0
        
        if role:
            param_count += 1
            conditions.append(f"role = ${param_count}" if hasattr(db, 'fetchrow') else "role = ?")
            params.append(role)
        
        if is_active is not None:
            param_count += 1
            conditions.append(f"is_active = ${param_count}" if hasattr(db, 'fetchrow') else "is_active = ?")
            params.append(is_active)
        
        if search:
            param_count += 1
            search_pattern = f"%{search}%"
            if hasattr(db, 'fetchrow'):
                conditions.append(f"(username ILIKE ${param_count} OR email ILIKE ${param_count})")
            else:
                conditions.append("(username LIKE ? OR email LIKE ?)")
                params.append(search_pattern)  # Add twice for SQLite
            params.append(search_pattern)
        
        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        
        # Get total count
        if hasattr(db, 'fetchrow'):
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
        
        # Convert to list of dicts
        users = []
        for row in rows:
            if isinstance(row, dict):
                users.append(row)
            else:
                user_dict = {
                    "id": row[0],
                    "uuid": str(row[1]) if row[1] and not isinstance(row[1], str) else row[1],
                    "username": row[2],
                    "email": row[3],
                    "role": row[4],
                    "is_active": bool(row[5]),
                    "is_verified": bool(row[6]),
                    "created_at": row[7],
                    "last_login": row[8],
                    "storage_quota_mb": row[9],
                    "storage_used_mb": float(row[10]) if row[10] else 0
                }
                users.append(user_dict)
        
        return UserListResponse(
            users=users,
            total=total,
            page=page,
            limit=limit,
            pages=(total + limit - 1) // limit
        )
        
    except Exception as e:
        logger.error(f"Failed to list users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve users"
        )


#######################################################################################################################
#
# Per-User API Key Management (Admin)

@router.get("/users/{user_id}/api-keys", response_model=list[APIKeyMetadata])
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
        import json
        fields = []
        params = []
        if request.rate_limit is not None:
            fields.append("rate_limit = ${}" if hasattr(db, 'fetchrow') else "rate_limit = ?")
            params.append(request.rate_limit)
        if request.allowed_ips is not None:
            fields.append("allowed_ips = ${}" if hasattr(db, 'fetchrow') else "allowed_ips = ?")
            params.append(json.dumps(request.allowed_ips))
        if not fields:
            raise HTTPException(status_code=400, detail="No updates provided")

        if hasattr(db, 'fetchrow'):
            # PostgreSQL numbered params
            set_clause = ", ".join(fields[i].format(i + 1) for i in range(len(fields)))
            query = f"UPDATE api_keys SET {set_clause} WHERE id = $ {len(fields) + 1} AND user_id = $ {len(fields) + 2}"
            # Fix spacing: replace '$ ' with '$'
            query = query.replace('$ ', '$')
            await db.execute(query, *params, key_id, user_id)
            row = await db.fetchrow("SELECT * FROM api_keys WHERE id = $1 AND user_id = $2", key_id, user_id)
        else:
            # SQLite
            set_clause = ", ".join(fields)
            params2 = list(params) + [key_id, user_id]
            await db.execute(f"UPDATE api_keys SET {set_clause} WHERE id = ? AND user_id = ?", params2)
            await db.commit()
            cursor = await db.execute("SELECT * FROM api_keys WHERE id = ? AND user_id = ?", (key_id, user_id))
            row = await cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="API key not found")

        # Normalize row to dict
        if not isinstance(row, dict):
            try:
                row = dict(row)
            except Exception:
                # Map by column order (SQLite fallback)
                cols = [
                    'id','user_id','key_hash','key_prefix','name','description','scope','status','created_at','expires_at',
                    'last_used_at','last_used_ip','usage_count','rate_limit','allowed_ips','metadata','rotated_from','rotated_to',
                    'revoked_at','revoked_by','revoke_reason'
                ]
                row = {cols[i]: row[i] for i in range(min(len(cols), len(row)))}

        # Drop sensitive hash field and return metadata-like view
        row.pop('key_hash', None)
        return APIKeyMetadata(**row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin failed to update API key {key_id} for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update API key")


@router.get("/api-keys/{key_id}/audit-log", response_model=APIKeyAuditListResponse)
async def admin_get_api_key_audit_log(
    key_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db=Depends(get_db_transaction)
) -> APIKeyAuditListResponse:
    """Get audit log entries for a specific API key (admin)."""
    try:
        if hasattr(db, 'fetchrow'):
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
        if hasattr(db, 'fetchrow'):
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
        # Build update query dynamically
        updates = []
        params = []
        param_count = 0
        
        if request.email is not None:
            param_count += 1
            updates.append(f"email = ${param_count}" if hasattr(db, 'fetchrow') else "email = ?")
            params.append(request.email)
        
        if request.role is not None:
            param_count += 1
            updates.append(f"role = ${param_count}" if hasattr(db, 'fetchrow') else "role = ?")
            params.append(request.role)
        
        if request.is_active is not None:
            param_count += 1
            updates.append(f"is_active = ${param_count}" if hasattr(db, 'fetchrow') else "is_active = ?")
            params.append(request.is_active)
        
        if request.is_verified is not None:
            param_count += 1
            updates.append(f"is_verified = ${param_count}" if hasattr(db, 'fetchrow') else "is_verified = ?")
            params.append(request.is_verified)
        
        if request.is_locked is not None:
            param_count += 1
            updates.append(f"is_locked = ${param_count}" if hasattr(db, 'fetchrow') else "is_locked = ?")
            params.append(request.is_locked)
            
            if not request.is_locked:
                # Unlock user - reset failed attempts
                param_count += 1
                updates.append(f"failed_login_attempts = ${param_count}" if hasattr(db, 'fetchrow') else "failed_login_attempts = ?")
                params.append(0)
                updates.append("locked_until = NULL")
        
        if request.storage_quota_mb is not None:
            param_count += 1
            updates.append(f"storage_quota_mb = ${param_count}" if hasattr(db, 'fetchrow') else "storage_quota_mb = ?")
            params.append(request.storage_quota_mb)
        
        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )
        
        # Add updated_at
        param_count += 1
        if hasattr(db, 'fetchrow'):
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(user_id)
            query = f"UPDATE users SET {', '.join(updates)} WHERE id = ${param_count}"
        else:
            updates.append("updated_at = datetime('now')")
            params.append(user_id)
            query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
        
        # Execute update
        if hasattr(db, 'fetchrow'):
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

@router.get("/roles", response_model=list[RoleResponse])
async def list_roles(db=Depends(get_db_transaction)) -> list[RoleResponse]:
    try:
        if hasattr(db, 'fetch'):
            rows = await db.fetch("SELECT id, name, description, COALESCE(is_system, 0) as is_system FROM roles ORDER BY name")
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
        if hasattr(db, 'fetchrow'):
            row = await db.fetchrow(
                "INSERT INTO roles (name, description, is_system) VALUES ($1, $2, $3) RETURNING id, name, description, is_system",
                payload.name, payload.description, False,
            )
            return RoleResponse(**dict(row))
        else:
            cur = await db.execute(
                "INSERT INTO roles (name, description, is_system) VALUES (?, ?, ?)",
                (payload.name, payload.description, 0),
            )
            await db.commit()
            rid = cur.lastrowid
            cur2 = await db.execute("SELECT id, name, description, COALESCE(is_system,0) FROM roles WHERE id = ?", (rid,))
            row = await cur2.fetchone()
            return RoleResponse(id=row[0], name=row[1], description=row[2], is_system=bool(row[3]))
    except Exception as e:
        logger.error(f"Failed to create role: {e}")
        raise HTTPException(status_code=500, detail="Failed to create role")


@router.delete("/roles/{role_id}")
async def delete_role(role_id: int, db=Depends(get_db_transaction)) -> dict:
    try:
        if hasattr(db, 'execute'):
            await db.execute("DELETE FROM roles WHERE id = $1 AND COALESCE(is_system, 0) = 0", role_id)
        else:
            await db.execute("DELETE FROM roles WHERE id = ? AND COALESCE(is_system, 0) = 0", (role_id,))
            await db.commit()
        return {"message": "Role deleted"}
    except Exception as e:
        logger.error(f"Failed to delete role {role_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete role")


@router.get("/permissions", response_model=list[PermissionResponse])
async def list_permissions(category: str | None = None, search: str | None = None, db=Depends(get_db_transaction)) -> list[PermissionResponse]:
    try:
        clauses = []
        params = []
        if category:
            clauses.append("category = $1" if hasattr(db, 'fetch') else "category = ?")
            params.append(category)
        if search:
            if hasattr(db, 'fetch'):
                clauses.append("(name ILIKE $%d OR description ILIKE $%d)" % (len(params)+1, len(params)+1))
                params.append(f"%{search}%")
            else:
                clauses.append("(name LIKE ? OR description LIKE ?)")
                params.append(f"%{search}%")
                params.append(f"%{search}%")
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        if hasattr(db, 'fetch'):
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
        if hasattr(db, 'fetchrow'):
            row = await db.fetchrow(
                "INSERT INTO permissions (name, description, category) VALUES ($1, $2, $3) RETURNING id, name, description, category",
                payload.name, payload.description, payload.category,
            )
            return PermissionResponse(**dict(row))
        else:
            cur = await db.execute(
                "INSERT INTO permissions (name, description, category) VALUES (?, ?, ?)",
                (payload.name, payload.description, payload.category),
            )
            await db.commit()
            pid = cur.lastrowid
            cur2 = await db.execute("SELECT id, name, description, category FROM permissions WHERE id = ?", (pid,))
            row = await cur2.fetchone()
            return PermissionResponse(id=row[0], name=row[1], description=row[2], category=row[3])
    except Exception as e:
        logger.error(f"Failed to create permission: {e}")
        raise HTTPException(status_code=500, detail="Failed to create permission")


@router.post("/roles/{role_id}/permissions/{permission_id}")
async def grant_permission_to_role(role_id: int, permission_id: int, db=Depends(get_db_transaction)) -> dict:
    try:
        if hasattr(db, 'execute'):
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
        if hasattr(db, 'execute'):
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
        if hasattr(db, 'fetch'):
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
        if hasattr(db, 'execute'):
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
        if hasattr(db, 'execute'):
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
        if hasattr(db, 'fetch'):
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
        # Resolve permission_id if only name provided
        perm_id = payload.permission_id
        if not perm_id and payload.permission_name:
            if hasattr(db, 'fetchval'):
                perm_id = await db.fetchval("SELECT id FROM permissions WHERE name = $1", payload.permission_name)
            else:
                cur = await db.execute("SELECT id FROM permissions WHERE name = ?", (payload.permission_name,))
                row = await cur.fetchone()
                perm_id = row[0] if row else None
        if not perm_id:
            raise HTTPException(status_code=400, detail="permission_id or permission_name required")

        granted = 1 if payload.effect == 'allow' else 0
        if hasattr(db, 'execute'):
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
            await db.execute(
                """
                INSERT OR REPLACE INTO user_permissions (user_id, permission_id, granted, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, perm_id, granted, payload.expires_at),
            )
            await db.commit()
        return {"message": "Override upserted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upsert override for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to upsert user override")


@router.delete("/users/{user_id}/overrides/{permission_id}")
async def delete_user_override(user_id: int, permission_id: int, db=Depends(get_db_transaction)) -> dict:
    try:
        if hasattr(db, 'execute'):
            await db.execute("DELETE FROM user_permissions WHERE user_id = $1 AND permission_id = $2", user_id, permission_id)
        else:
            await db.execute("DELETE FROM user_permissions WHERE user_id = ? AND permission_id = ?", (user_id, permission_id))
            await db.commit()
        return {"message": "Override deleted"}
    except Exception as e:
        logger.error(f"Failed to delete override for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete user override")


@router.get("/users/{user_id}/effective-permissions", response_model=EffectivePermissionsResponse)
async def get_effective_permissions_admin(user_id: int) -> EffectivePermissionsResponse:
    try:
        perms = get_effective_permissions(user_id)
        return EffectivePermissionsResponse(user_id=user_id, permissions=perms)
    except Exception as e:
        logger.error(f"Failed to compute effective permissions for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to compute effective permissions")


@router.post("/roles/{role_id}/rate-limits", response_model=RateLimitResponse)
async def upsert_role_rate_limit(role_id: int, payload: RateLimitUpsertRequest, db=Depends(get_db_transaction)) -> RateLimitResponse:
    try:
        if hasattr(db, 'execute'):
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
        if hasattr(db, 'execute'):
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
        if hasattr(db, 'fetchrow'):
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
        
        if hasattr(db, 'fetchrow'):
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
        if hasattr(db, 'fetchrow'):
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
        if hasattr(db, 'fetchrow'):
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
        
        if hasattr(db, 'fetchrow'):
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
        conditions = []
        params = []
        param_count = 0
        
        if user_id:
            param_count += 1
            conditions.append(f"user_id = ${param_count}" if hasattr(db, 'fetchrow') else "user_id = ?")
            params.append(user_id)
        
        if action:
            param_count += 1
            conditions.append(f"action = ${param_count}" if hasattr(db, 'fetchrow') else "action = ?")
            params.append(action)
        
        # Date filter
        if hasattr(db, 'fetchrow'):
            conditions.append(f"a.created_at > CURRENT_TIMESTAMP - INTERVAL '{days} days'")
        else:
            conditions.append("datetime(a.created_at) > datetime('now', ? || ' days')")
            params.append(f"-{days}")
        
        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        
        if hasattr(db, 'fetchrow'):
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


#
## End of admin.py
#######################################################################################################################
