from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import PlainTextResponse
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import (
    get_auth_principal,
    get_db_transaction,
    get_registration_service_dep,
)
from tldw_Server_API.app.api.v1.schemas.auth_schemas import MessageResponse
from tldw_Server_API.app.api.v1.schemas.admin_schemas import (
    AdminUserCreateRequest,
    UserDetailResponse,
    UserListResponse,
    UserSummary,
    UserUpdateRequest,
)
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.services import admin_users_service

router = APIRouter()


@router.post("/users", response_model=UserSummary)
async def admin_create_user(
    payload: AdminUserCreateRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
    registration_service=Depends(get_registration_service_dep),
) -> UserSummary:
    """
    Create a new user as an admin.
    """
    return await admin_users_service.create_user(
        payload=payload,
        principal=principal,
        registration_service=registration_service,
    )


@router.get("/users", response_model=UserListResponse)
async def list_users(
    request: Request,
    response: Response,
    principal: AuthPrincipal = Depends(get_auth_principal),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    role: str | None = None,
    is_active: bool | None = None,
    search: str | None = None,
    org_id: int | None = Query(None, description="Restrict to a specific organization"),
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
    if str(os.getenv("TEST_MODE", "")).lower() in ("1", "true", "yes"):
        try:
            pool = await get_db_pool()
            db_backend = "postgres" if getattr(pool, "pool", None) is not None else "sqlite"
            response.headers["X-TLDW-Admin-DB"] = db_backend
            response.headers["X-TLDW-Admin-Req"] = "ok"
            auth_hdr = request.headers.get("Authorization")
            logger.info(
                "Admin list_users TEST_MODE: Authorization present={}",
                bool(auth_hdr),
            )
        except Exception as diag_exc:  # noqa: BLE001 - diagnostics only, do not fail request
            response.headers["X-TLDW-Admin-Diag-Error"] = str(diag_exc)
            logger.debug(
                "Admin list_users TEST_MODE diagnostics failed: {}",
                diag_exc,
            )

    try:
        users, total = await admin_users_service.list_users(
            principal,
            page=page,
            limit=limit,
            role=role,
            is_active=is_active,
            search=search,
            org_id=org_id,
        )
        return UserListResponse(
            users=users,
            total=total,
            page=page,
            limit=limit,
            pages=(total + limit - 1) // limit if limit else 0,
        )
    except HTTPException as e:
        try:
            if str(os.getenv("TEST_MODE", "")).lower() in ("1", "true", "yes"):
                response.headers["X-TLDW-Admin-Error"] = str(e)
        except Exception:
            pass
        raise
    except Exception as e:
        logger.error(f"Failed to list users: {e}")
        try:
            if str(os.getenv("TEST_MODE", "")).lower() in ("1", "true", "yes"):
                response.headers["X-TLDW-Admin-Error"] = str(e)
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve users",
        )


@router.get("/users/export")
async def export_users(
    role: str | None = None,
    is_active: bool | None = None,
    search: str | None = None,
    org_id: int | None = Query(None, description="Restrict to a specific organization"),
    limit: int = Query(10000, ge=1, le=50000),
    offset: int = Query(0, ge=0),
    format: str = Query("csv", pattern="^(csv|json)$"),
    filename: str | None = Query(None, description="Optional filename for Content-Disposition"),
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> Response:
    try:
        content, media_type, default_name = await admin_users_service.export_users(
            principal,
            role=role,
            is_active=is_active,
            search=search,
            org_id=org_id,
            limit=limit,
            offset=offset,
            format=format,
        )
        if media_type == "application/json":
            resp = Response(content=content, media_type=media_type)
        else:
            resp = PlainTextResponse(content=content, media_type=media_type)
        if not filename:
            filename = default_name
        if filename:
            safe = filename.replace("\n", " ").replace("\r", " ").replace("\"", "_")
            resp.headers["Content-Disposition"] = f"attachment; filename=\"{safe}\""
        return resp
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to export users: {exc}")
        raise HTTPException(status_code=500, detail="Failed to export users")


@router.get("/users/{user_id}", response_model=UserDetailResponse)
async def get_user_details(
    user_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> UserDetailResponse:
    return await admin_users_service.get_user_details(principal, user_id)


def _get_is_pg_fn():
    from tldw_Server_API.app.api.v1.endpoints import admin as admin_mod

    return admin_mod._is_postgres_backend


@router.put("/users/{user_id}", response_model=MessageResponse)
async def update_user(
    user_id: int,
    request: UserUpdateRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> MessageResponse:
    return await admin_users_service.update_user(
        principal,
        user_id,
        request,
        db,
        is_pg_fn=_get_is_pg_fn(),
    )


@router.delete("/users/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> MessageResponse:
    return await admin_users_service.delete_user(
        principal,
        user_id,
        db,
        is_pg_fn=_get_is_pg_fn(),
    )
