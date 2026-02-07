from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import PlainTextResponse

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import (
    get_auth_principal,
    get_db_transaction,
)
from tldw_Server_API.app.api.v1.schemas.admin_schemas import (
    ActivitySummaryResponse,
    AuditLogResponse,
    SecurityAlertStatusResponse,
    SystemLogsResponse,
    SystemStatsResponse,
)
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.services import admin_system_service

router = APIRouter()


@router.get("/security/alert-status", response_model=SecurityAlertStatusResponse)
async def get_security_alert_status() -> SecurityAlertStatusResponse:
    return await admin_system_service.get_security_alert_status()


@router.get("/stats", response_model=SystemStatsResponse)
async def get_system_stats(
    db=Depends(get_db_transaction),
) -> SystemStatsResponse:
    return await admin_system_service.get_system_stats(db)


@router.get("/activity", response_model=ActivitySummaryResponse)
async def get_dashboard_activity(
    days: int = Query(7, ge=1, le=30),
    db=Depends(get_db_transaction),
) -> ActivitySummaryResponse:
    return await admin_system_service.get_dashboard_activity(days, db)


@router.get("/audit-log", response_model=AuditLogResponse)
async def get_audit_log(
    user_id: int | None = None,
    action: str | None = None,
    resource: str | None = Query(None, description="Filter by resource type or type:id"),
    start: str | None = Query(None, description="ISO date or datetime (start)"),
    end: str | None = Query(None, description="ISO date or datetime (end)"),
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    org_id: int | None = Query(None, description="Restrict to a specific organization"),
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> AuditLogResponse:
    return await admin_system_service.get_audit_log(
        user_id=user_id,
        action=action,
        resource=resource,
        start=start,
        end=end,
        days=days,
        limit=limit,
        offset=offset,
        org_id=org_id,
        principal=principal,
        db=db,
    )


@router.get("/audit-log/export")
async def export_audit_log(
    user_id: int | None = None,
    action: str | None = None,
    resource: str | None = Query(None, description="Filter by resource type or type:id"),
    start: str | None = Query(None, description="ISO date or datetime (start)"),
    end: str | None = Query(None, description="ISO date or datetime (end)"),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(10000, ge=1, le=50000),
    offset: int = Query(0, ge=0),
    org_id: int | None = Query(None, description="Restrict to a specific organization"),
    format: str = Query("csv", pattern="^(csv|json)$"),
    filename: str | None = Query(None, description="Optional filename for Content-Disposition"),
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> Response:
    content, media_type, default_filename = await admin_system_service.export_audit_log(
        user_id=user_id,
        action=action,
        resource=resource,
        start=start,
        end=end,
        days=days,
        limit=limit,
        offset=offset,
        org_id=org_id,
        format=format,
        principal=principal,
        db=db,
    )
    if format == "json":
        resp = Response(content=content, media_type=media_type)
    else:
        resp = PlainTextResponse(content=content, media_type=media_type)
    if not filename:
        filename = default_filename
    if filename:
        safe = filename.replace("\n", " ").replace("\r", " ").replace("\"", "_")
        resp.headers["Content-Disposition"] = f"attachment; filename=\"{safe}\""
    return resp


@router.get("/system/logs", response_model=SystemLogsResponse)
async def list_system_logs(
    start: str | None = Query(None, description="ISO date or datetime (start)"),
    end: str | None = Query(None, description="ISO date or datetime (end)"),
    level: str | None = Query(None, description="Log level (INFO, ERROR, etc.)"),
    service: str | None = Query(None, description="Logger or module filter"),
    query: str | None = Query(None, description="Substring search"),
    org_id: int | None = Query(None, description="Restrict to a specific organization"),
    user_id: int | None = Query(None, description="Restrict to a specific user"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> SystemLogsResponse:
    return await admin_system_service.list_system_logs(
        start=start,
        end=end,
        level=level,
        service=service,
        query=query,
        org_id=org_id,
        user_id=user_id,
        limit=limit,
        offset=offset,
        principal=principal,
    )
