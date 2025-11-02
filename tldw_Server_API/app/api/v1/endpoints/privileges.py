from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, StreamingResponse
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_current_active_user
from tldw_Server_API.app.api.v1.schemas.privileges import (
    PrivilegeDetailResponse,
    PrivilegeOrgResponse,
    PrivilegeSelfResponse,
    PrivilegeSnapshotAcceptedResponse,
    PrivilegeSnapshotCreateRequest,
    PrivilegeSnapshotDetailResponse,
    PrivilegeSnapshotListResponse,
    PrivilegeSnapshotRecord,
    PrivilegeSnapshotSummary,
)
from tldw_Server_API.app.core.AuthNZ.settings import is_single_user_mode
from tldw_Server_API.app.core.PrivilegeMaps import (
    PrivilegeMapService,
    PrivilegeSnapshotStore,
    get_privilege_map_service,
    get_privilege_snapshot_store,
)
from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Logging.log_context import ensure_request_id, get_ps_logger


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


@router.get("/self", response_model=PrivilegeSelfResponse)
async def get_self_privilege_map(
    *,
    resource: Optional[str] = Query(None),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    service: PrivilegeMapService = Depends(get_privilege_map_service),
) -> PrivilegeSelfResponse:
    user_id = str(current_user.get("id"))
    try:
        return await service.get_self_map(user_id=user_id, resource=resource)
    except ValueError as exc:
        logger.warning("Invalid self privilege request: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


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
    dependency: Optional[str] = Query(None),
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
                dependency=dependency,
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
    group_by: str = Query("member", pattern="^(member|resource)$"),
    view: str = Query("summary", pattern="^(summary|detail)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    resource: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    dependency: Optional[str] = Query(None),
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
                dependency=dependency,
                role_filter=role,
            )
        return await service.get_team_summary(
            team_id=team_id,
            group_by=group_by,
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


@router.get("/snapshots/{snapshot_id}", response_model=PrivilegeSnapshotDetailResponse)
async def get_privilege_snapshot(
    *,
    snapshot_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(500, ge=1, le=500),
    current_user: Dict[str, Any] = Depends(require_privilege_admin),
    store: PrivilegeSnapshotStore = Depends(get_privilege_snapshot_store),
) -> PrivilegeSnapshotDetailResponse:
    del current_user
    snapshot = await store.get_snapshot(snapshot_id=snapshot_id, page=page, page_size=page_size)
    if not snapshot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found.")
    return snapshot


@router.get("/snapshots/{snapshot_id}/export.json")
async def export_privilege_snapshot_json(
    *,
    snapshot_id: str,
    current_user: Dict[str, Any] = Depends(require_privilege_admin),
    store: PrivilegeSnapshotStore = Depends(get_privilege_snapshot_store),
) -> JSONResponse:
    del current_user
    export_data = await store.export_snapshot(snapshot_id=snapshot_id)
    if not export_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found.")

    generated_at = export_data.get("generated_at")
    if isinstance(generated_at, datetime):
        generated_at_iso = generated_at.astimezone(timezone.utc).isoformat()
    else:
        generated_at_iso = str(generated_at) if generated_at else None

    payload = {
        "snapshot_id": export_data.get("snapshot_id"),
        "catalog_version": export_data.get("catalog_version"),
        "generated_at": generated_at_iso,
        "generated_by": export_data.get("generated_by"),
        "target_scope": export_data.get("target_scope"),
        "org_id": export_data.get("org_id"),
        "team_id": export_data.get("team_id"),
        "summary": export_data.get("summary"),
        "total_items": export_data.get("total_items"),
        "detail_items": export_data.get("detail_items", []),
        "metadata": {
            "exported_at": datetime.now(timezone.utc).isoformat(),
        },
    }

    response = JSONResponse(content=jsonable_encoder(payload))
    filename = f"privilege-snapshot-{snapshot_id}.json"
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    etag = export_data.get("etag")
    if etag:
        response.headers["ETag"] = etag
    return response


@router.get("/snapshots/{snapshot_id}/export.csv")
async def export_privilege_snapshot_csv(
    *,
    snapshot_id: str,
    current_user: Dict[str, Any] = Depends(require_privilege_admin),
    store: PrivilegeSnapshotStore = Depends(get_privilege_snapshot_store),
) -> StreamingResponse:
    del current_user
    export_data = await store.export_snapshot(snapshot_id=snapshot_id)
    if not export_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found.")

    generated_at = export_data.get("generated_at")
    if isinstance(generated_at, datetime):
        generated_at_iso = generated_at.astimezone(timezone.utc).isoformat()
    else:
        generated_at_iso = str(generated_at) if generated_at else None

    detail_items = export_data.get("detail_items", [])
    fieldnames = [
        "snapshot_id",
        "catalog_version",
        "generated_at",
        "generated_by",
        "target_scope",
        "org_id",
        "team_id",
        "user_id",
        "endpoint",
        "method",
        "privilege_scope_id",
        "status",
        "blocked_reason",
        "feature_flag_id",
        "sensitivity_tier",
        "ownership_predicates",
        "dependencies",
        "dependency_modules",
        "rate_limit_class",
        "rate_limit_resources",
        "source_module",
        "summary",
        "tags",
    ]

    def _flatten_detail(detail: Dict[str, Any]) -> Dict[str, Any]:
        dependencies = detail.get("dependencies") or []
        dependency_ids = ";".join(dep.get("id", "") for dep in dependencies if dep)
        dependency_modules = ";".join(
            dep.get("module", "") for dep in dependencies if dep and dep.get("module")
        )
        ownership_predicates = ";".join(detail.get("ownership_predicates") or [])
        rate_limit_resources = ";".join(detail.get("rate_limit_resources") or [])
        tags = ";".join(detail.get("tags") or [])

        return {
            "snapshot_id": export_data.get("snapshot_id"),
            "catalog_version": export_data.get("catalog_version"),
            "generated_at": generated_at_iso,
            "generated_by": export_data.get("generated_by"),
            "target_scope": export_data.get("target_scope"),
            "org_id": export_data.get("org_id"),
            "team_id": export_data.get("team_id"),
            "user_id": detail.get("user_id"),
            "endpoint": detail.get("endpoint"),
            "method": detail.get("method"),
            "privilege_scope_id": detail.get("privilege_scope_id"),
            "status": detail.get("status"),
            "blocked_reason": detail.get("blocked_reason"),
            "feature_flag_id": detail.get("feature_flag_id"),
            "sensitivity_tier": detail.get("sensitivity_tier"),
            "ownership_predicates": ownership_predicates,
            "dependencies": dependency_ids,
            "dependency_modules": dependency_modules,
            "rate_limit_class": detail.get("rate_limit_class"),
            "rate_limit_resources": rate_limit_resources,
            "source_module": detail.get("source_module"),
            "summary": detail.get("summary"),
            "tags": tags,
        }

    def iter_csv():
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=fieldnames)
        writer.writeheader()
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)

        for detail in detail_items:
            writer.writerow(_flatten_detail(detail))
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)

    response = StreamingResponse(iter_csv(), media_type="text/csv")
    filename = f"privilege-snapshot-{snapshot_id}.csv"
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    etag = export_data.get("etag")
    if etag:
        response.headers["ETag"] = etag
    return response


@router.post(
    "/snapshots",
    response_model=PrivilegeSnapshotRecord,
    status_code=status.HTTP_201_CREATED,
)
async def create_privilege_snapshot(
    *,
    payload: PrivilegeSnapshotCreateRequest,
    current_user: Dict[str, Any] = Depends(require_privilege_admin),
    service: PrivilegeMapService = Depends(get_privilege_map_service),
    store: PrivilegeSnapshotStore = Depends(get_privilege_snapshot_store),
    request: Request = None,
):
    generated_by = str(current_user.get("id") or "system")
    user_ids = list(payload.user_ids or [])
    if payload.target_scope == "user" and not user_ids:
        user_ids = [generated_by]
    if payload.async_job:
        snapshot_id = f"snap-{uuid4()}"
        job_payload = {
            "action": "generate_snapshot",
            "snapshot_id": snapshot_id,
            "target_scope": payload.target_scope,
            "org_id": payload.org_id,
            "team_id": payload.team_id,
            "user_ids": user_ids,
            "catalog_version": payload.catalog_version or service.catalog.version,
            "requested_by": generated_by,
            "notes": payload.notes,
        }
        try:
            job_manager = JobManager()
            job_row = job_manager.create_job(
                domain="privilege_maps",
                queue="default",
                job_type="snapshot",
                payload=job_payload,
                owner_user_id=generated_by,
                request_id=snapshot_id,
            )
        except Exception as exc:
            rid = ensure_request_id(request) if request is not None else None
            get_ps_logger(request_id=rid, ps_component="endpoint", ps_job_kind="privilege_maps").error(
                "Failed to enqueue privilege snapshot job: %s", exc
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to queue privilege snapshot job.",
            ) from exc
        accepted = PrivilegeSnapshotAcceptedResponse(
            request_id=snapshot_id,
            status="queued",
            estimated_ready_at=datetime.now(timezone.utc),
        )
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content=jsonable_encoder(accepted),
        )
    try:
        summary_data, snapshot_users = await service.build_snapshot_summary(
            target_scope=payload.target_scope,
            org_id=payload.org_id,
            team_id=payload.team_id,
            user_ids=user_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    generated_at = datetime.now(timezone.utc)
    snapshot_id = f"snap-{generated_at.strftime('%Y%m%d-%H%M%S')}"
    summary_model = PrivilegeSnapshotSummary(**summary_data)
    detail_items = service.build_snapshot_detail(
        snapshot_users,
        restrict_to_team=payload.team_id if payload.target_scope == "team" else None,
    )
    record = PrivilegeSnapshotRecord(
        snapshot_id=snapshot_id,
        generated_at=generated_at,
        generated_by=generated_by,
        target_scope=payload.target_scope,
        org_id=payload.org_id,
        team_id=payload.team_id,
        catalog_version=payload.catalog_version or service.catalog.version,
        summary=summary_model,
    )
    await store.add_snapshot(
        {
            "snapshot_id": record.snapshot_id,
            "generated_at": record.generated_at,
            "generated_by": record.generated_by,
            "target_scope": record.target_scope,
            "org_id": record.org_id,
            "team_id": record.team_id,
            "catalog_version": record.catalog_version,
            "summary": summary_model.dict(),
        },
        detail_items=detail_items,
    )
    return record
