from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from tldw_Server_API.app.core.Audit.unified_audit_service import (
    UnifiedAuditService,
    AuditEventType,
    AuditEventCategory,
)
from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import get_audit_service_for_user
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import require_admin

router = APIRouter()


def _parse_dt(val: Optional[str]) -> Optional[datetime]:
    if not val:
        return None
    try:
        dt = datetime.fromisoformat(val)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _map_event_types(values: Optional[List[str]] | Optional[str]) -> Optional[List[AuditEventType]]:
    if not values:
        return None
    # Accept comma-separated string or list of strings
    if isinstance(values, str):
        raw_vals = [s.strip() for s in values.split(',') if s.strip()]
    else:
        raw_vals = [v for v in values if v]
    mapped: List[AuditEventType] = []
    for v in raw_vals:
        if not v:
            continue
        # Accept either enum name (AUTH_LOGIN_SUCCESS) or value (auth.login.success)
        try:
            mapped.append(AuditEventType[v])
            continue
        except Exception:
            pass
        try:
            mapped.append(AuditEventType(v))
        except Exception:
            # Skip unknown types silently to be user-friendly
            continue
    return mapped or None


def _map_categories(values: Optional[List[str]] | Optional[str]) -> Optional[List[AuditEventCategory]]:
    if not values:
        return None
    if isinstance(values, str):
        raw_vals = [s.strip() for s in values.split(',') if s.strip()]
    else:
        raw_vals = [v for v in values if v]
    mapped: List[AuditEventCategory] = []
    for v in raw_vals:
        if not v:
            continue
        try:
            mapped.append(AuditEventCategory[v])
            continue
        except Exception:
            pass
        try:
            mapped.append(AuditEventCategory(v))
        except Exception:
            continue
    return mapped or None


@router.get("/audit/export")
async def export_audit_events(
    format: str = Query("json"),
    start_time: Optional[str] = Query(None, description="ISO8601 start timestamp"),
    end_time: Optional[str] = Query(None, description="ISO8601 end timestamp"),
    event_type: Optional[str] = Query(None, description="Event types (enum name or value), comma-separated"),
    category: Optional[str] = Query(None, description="Categories (enum name or value), comma-separated"),
    min_risk_score: Optional[int] = Query(None),
    user_id: Optional[str] = Query(None),
    request_id: Optional[str] = Query(None),
    correlation_id: Optional[str] = Query(None),
    filename: Optional[str] = Query(None),
    audit_service: UnifiedAuditService = Depends(get_audit_service_for_user),
    _: dict = Depends(require_admin),
):
    """Export audit events as JSON or CSV. Requires authentication.

    Note: In multi-user deployments, protect this route with admin/RBAC in upstream middleware.
    """
    fmt = format.lower()
    if fmt not in {"json", "csv"}:
        raise HTTPException(status_code=400, detail="format must be 'json' or 'csv'")

    st = _parse_dt(start_time)
    et = _parse_dt(end_time)
    ets = _map_event_types(event_type)
    cats = _map_categories(category)

    content = await audit_service.export_events(
        start_time=st,
        end_time=et,
        event_types=ets,
        categories=cats,
        user_id=user_id,
        request_id=request_id,
        correlation_id=correlation_id,
        min_risk_score=min_risk_score,
        format=fmt,
        file_path=None,
    )

    if fmt == "json":
        media = "application/json"
        default_name = "audit_export.json"
    else:
        media = "text/csv"
        default_name = "audit_export.csv"

    fname = filename or default_name
    headers = {"Content-Disposition": f"attachment; filename={fname}"}
    return Response(content=content, media_type=media, headers=headers)
