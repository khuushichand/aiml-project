from __future__ import annotations

from collections.abc import Awaitable
from typing import Any, Callable

from fastapi import HTTPException, status
from loguru import logger

from tldw_Server_API.app.api.v1.schemas.admin_schemas import (
    AdminUserCreateRequest,
    UserUpdateRequest,
)
from tldw_Server_API.app.core.AuthNZ.exceptions import (
    DuplicateUserError,
    RegistrationDisabledError,
    RegistrationError,
    UserNotFoundError,
    WeakPasswordError,
)
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.AuthNZ.repos.users_repo import AuthnzUsersRepo
from tldw_Server_API.app.core.AuthNZ.settings import get_profile
from tldw_Server_API.app.services import admin_scope_service
from tldw_Server_API.app.services.admin_data_ops_service import (
    build_users_csv as svc_build_users_csv,
)
from tldw_Server_API.app.services.admin_data_ops_service import (
    build_users_json as svc_build_users_json,
)


async def create_user(
    payload: AdminUserCreateRequest,
    principal: AuthPrincipal,
    registration_service,
):
    profile = get_profile()
    if isinstance(profile, str) and profile.strip().lower() in {"local-single-user", "single_user"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User creation is not allowed in local-single-user profile",
        )

    created_by = int(principal.user_id) if principal.user_id is not None else None
    try:
        user_info = await registration_service.register_user(
            username=payload.username,
            email=payload.email,
            password=payload.password,
            created_by=created_by,
            role_override=payload.role,
            is_active_override=payload.is_active,
            is_verified_override=payload.is_verified,
            storage_quota_override=payload.storage_quota_mb,
        )
        repo = await AuthnzUsersRepo.from_pool()
        user = await repo.get_user_by_id(int(user_info["user_id"]))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to load created user",
            )
        logger.info("Admin created user {} (id={})", payload.username, user_info["user_id"])
        return user
    except DuplicateUserError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except WeakPasswordError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RegistrationDisabledError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except RegistrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to create user: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user",
        ) from exc


async def list_users(
    principal: AuthPrincipal,
    *,
    page: int,
    limit: int,
    role: str | None,
    is_active: bool | None,
    search: str | None,
    org_id: int | None,
) -> tuple[list[dict[str, Any]], int]:
    try:
        offset = (page - 1) * limit
        repo = await AuthnzUsersRepo.from_pool()
        org_ids = await admin_scope_service.get_admin_org_ids(principal)
        if org_id is not None:
            org_ids = [org_id] if org_ids is None else [org_id] if org_id in org_ids else []
        users, total = await repo.list_users(
            offset=offset,
            limit=limit,
            role=role,
            is_active=is_active,
            search=search,
            org_ids=org_ids,
        )
        return users, total
    except Exception as e:
        logger.error(f"Failed to list users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve users",
        ) from e


async def export_users(
    principal: AuthPrincipal,
    *,
    role: str | None,
    is_active: bool | None,
    search: str | None,
    org_id: int | None,
    limit: int,
    offset: int,
    format: str,
) -> tuple[str, str, str]:
    try:
        org_ids = await admin_scope_service.get_admin_org_ids(principal)
        if org_id is not None:
            org_ids = [org_id] if org_ids is None else [org_id] if org_id in org_ids else []
        repo = await AuthnzUsersRepo.from_pool()
        users, total = await repo.list_users(
            offset=offset,
            limit=limit,
            role=role,
            is_active=is_active,
            search=search,
            org_ids=org_ids,
        )
        if format == "json":
            content = svc_build_users_json(users, total=total, limit=limit, offset=offset)
            media_type = "application/json"
            default_name = "users.json"
        else:
            content = svc_build_users_csv(users)
            media_type = "text/csv"
            default_name = "users.csv"
        return content, media_type, default_name
    except Exception as exc:
        logger.error(f"Failed to export users: {exc}")
        raise HTTPException(status_code=500, detail="Failed to export users") from exc


async def get_user_details(
    principal: AuthPrincipal,
    user_id: int,
) -> dict[str, Any]:
    try:
        await admin_scope_service.enforce_admin_user_scope(
            principal,
            user_id,
            require_hierarchy=False,
        )

        repo = await AuthnzUsersRepo.from_pool()
        user = await repo.get_user_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User {user_id}")

        user_dict: dict[str, Any] = dict(user)
        user_dict.pop("password_hash", None)

        return user_dict
    except UserNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        ) from err
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user details",
        ) from e


async def update_user(
    principal: AuthPrincipal,
    user_id: int,
    request: UserUpdateRequest,
    db,
    *,
    is_pg_fn: Callable[[], Awaitable[bool]],
) -> dict[str, str]:
    try:
        await admin_scope_service.enforce_admin_user_scope(
            principal,
            user_id,
            require_hierarchy=True,
        )

        is_pg = await is_pg_fn()
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
                detail="No fields to update",
            )

        param_count += 1
        if is_pg:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(user_id)
            query = f"UPDATE users SET {', '.join(updates)} WHERE id = ${param_count}"
        else:
            updates.append("updated_at = datetime('now')")
            params.append(user_id)
            query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"

        if is_pg:
            row = await db.fetchrow(query + " RETURNING id", *params)
            if not row:
                raise UserNotFoundError(f"User {user_id}")
        else:
            cursor = await db.execute(query, params)
            affected = int(getattr(cursor, "rowcount", 0) or 0)
            if affected == 0:
                cursor = await db.execute("SELECT 1 FROM users WHERE id = ?", (user_id,))
                if not await cursor.fetchone():
                    raise UserNotFoundError(f"User {user_id}")
            await db.commit()

        logger.info(f"Admin updated user {user_id}")

        return {"message": f"User {user_id} updated successfully"}

    except UserNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        ) from err
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user",
        ) from e


async def delete_user(
    principal: AuthPrincipal,
    user_id: int,
    db,
    *,
    is_pg_fn: Callable[[], Awaitable[bool]],
) -> dict[str, str]:
    try:
        if principal.user_id is not None and str(user_id) == str(principal.user_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete your own account",
            )
        await admin_scope_service.enforce_admin_user_scope(
            principal,
            user_id,
            require_hierarchy=True,
        )

        is_pg = await is_pg_fn()
        if is_pg:
            await db.execute(
                "UPDATE users SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP WHERE id = $1",
                user_id,
            )
        else:
            await db.execute(
                "UPDATE users SET is_active = 0, updated_at = datetime('now') WHERE id = ?",
                (user_id,),
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
            detail="Failed to delete user",
        ) from e
