from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_current_active_user
from tldw_Server_API.app.api.v1.schemas.privileges import (
    PrivilegeDetailResponse,
    PrivilegeOrgResponse,
    PrivilegeSnapshotListResponse,
)
from tldw_Server_API.app.core.AuthNZ.settings import is_single_user_mode
from tldw_Server_API.app.core.PrivilegeMaps import (
    PrivilegeMapService,
    PrivilegeSnapshotStore,
    get_privilege_map_service,
    get_privilege_snapshot_store,
)


router = APIRouter(prefix="/privileges", tags=["privileges"])


async def require_privilege_admin(
    current_user: Dict[str, Any] = Depends(get_current_active_user),
) -> Dict[str, Any]:
    if is_single_user_mode():
        return current_user
    role = (current_user or {}).get("role")
    if current_user.get("is_admin") or role in {"admin", "owner", "platform_admin"}:
        return current_user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Administrator privileges required to access privilege maps.",
    )


async def require_privilege_admin_or_self(
    user_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
) -> Dict[str, Any]:
    if is_single_user_mode():
        return current_user
    if current_user.get("is_admin") or str(current_user.get("id")) == str(user_id):
        return current_user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient privileges to inspect requested user.",
    )


@router.get("/org", response_model=PrivilegeOrgResponse)
async def get_org_privilege_map(
    *,
    group_by: str = Query("role", pattern="^(role|team|resource)$"),
    include_trends: bool = Query(False),
    since: Optional[datetime] = Query(None),
    view: str = Query("summary", pattern="^(summary|detail)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    resource: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    current_user: Dict[str, Any] = Depends(require_privilege_admin),
    service: PrivilegeMapService = Depends(get_privilege_map_service),
) -> PrivilegeOrgResponse:
    del current_user  # dependency enforcement only
    try:
        if view == "detail":
            return await service.get_org_detail(
                page=page,
                page_size=page_size,
                resource=resource,
                role_filter=role,
            )
        return await service.get_org_summary(
            group_by=group_by,
            include_trends=include_trends,
            since=since,
        )
    except ValueError as exc:
        logger.warning("Invalid privilege detail request: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/teams/{team_id}", response_model=PrivilegeOrgResponse)
async def get_team_privilege_map(
    *,
    team_id: str,
    view: str = Query("summary", pattern="^(summary|detail)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    resource: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    include_trends: bool = Query(False),
    since: Optional[datetime] = Query(None),
    current_user: Dict[str, Any] = Depends(require_privilege_admin),
    service: PrivilegeMapService = Depends(get_privilege_map_service),
) -> PrivilegeOrgResponse:
    del current_user
    try:
        if view == "detail":
            return await service.get_team_detail(
                team_id=team_id,
                page=page,
                page_size=page_size,
                resource=resource,
                role_filter=role,
            )
        return await service.get_team_summary(
            team_id=team_id,
            include_trends=include_trends,
            since=since,
        )
    except ValueError as exc:
        logger.warning("Invalid team privilege request: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/users/{user_id}", response_model=PrivilegeDetailResponse)
async def get_user_privilege_map(
    *,
    user_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    resource: Optional[str] = Query(None),
    current_user: Dict[str, Any] = Depends(require_privilege_admin_or_self),
    service: PrivilegeMapService = Depends(get_privilege_map_service),
) -> PrivilegeDetailResponse:
    del current_user
    try:
        return await service.get_user_detail(
            user_id=user_id,
            page=page,
            page_size=page_size,
            resource=resource,
        )
    except ValueError as exc:
        logger.warning("Invalid user privilege request: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/snapshots", response_model=PrivilegeSnapshotListResponse)
async def list_privilege_snapshots(
    *,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    generated_by: Optional[str] = Query(None),
    org_id: Optional[str] = Query(None),
    team_id: Optional[str] = Query(None),
    catalog_version: Optional[str] = Query(None),
    scope: Optional[str] = Query(None),
    include_counts: bool = Query(False),
    current_user: Dict[str, Any] = Depends(require_privilege_admin),
    store: PrivilegeSnapshotStore = Depends(get_privilege_snapshot_store),
) -> PrivilegeSnapshotListResponse:
    del current_user
    if org_id and team_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either org_id or team_id filter, not both.",
        )
    if scope and not include_counts:
        include_counts = True

    payload = await store.list_snapshots(
        page=page,
        page_size=page_size,
        date_from=date_from,
        date_to=date_to,
        generated_by=generated_by,
        org_id=org_id,
        team_id=team_id,
        catalog_version=catalog_version,
        scope=scope,
        include_counts=include_counts,
    )
    return payload
