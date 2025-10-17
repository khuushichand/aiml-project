from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse

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
        # Handle trailing 'Z' (UTC) which fromisoformat doesn't accept directly
        s = val.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
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


def _sanitize_filename(name: str, default_name: str) -> str:
    """Sanitize a user-supplied filename for Content-Disposition.

    - Drop directories
    - Allow only alphanumerics, dash, underscore, and dot
    - Fallback to default if empty
    """
    base = Path(name).name
    safe = []
    for ch in base:
        if ch.isalnum() or ch in {"-", "_", "."}:
            safe.append(ch)
        else:
            safe.append("_")
    sanitized = "".join(safe).strip("._")
    return sanitized or default_name


@router.get(
    "/audit/export",
    summary="Export audit events (JSON/JSONL/CSV)",
)
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
    ip_address: Optional[str] = Query(None, description="Filter by IP address"),
    session_id: Optional[str] = Query(None, description="Filter by session id"),
    endpoint: Optional[str] = Query(None, description="Filter by endpoint path"),
    method: Optional[str] = Query(None, description="Filter by HTTP method"),
    max_rows: Optional[int] = Query(None, description="Hard maximum rows to export"),
    filename: Optional[str] = Query(None),
    stream: bool = Query(False, description="Stream JSON/JSONL output incrementally (format=json or jsonl)"),
    audit_service: UnifiedAuditService = Depends(get_audit_service_for_user),
    _: dict = Depends(require_admin),
):
    """Export audit events (JSON, JSONL, CSV). Requires admin.

    Parameters (filters):
    - start_time, end_time: ISO8601; accepts trailing Z (UTC)
    - event_type, category: comma-separated enum names or values
    - min_risk_score: minimum risk score
    - user_id, request_id, correlation_id
    - ip_address, session_id, endpoint, method (context-based filters)
    - max_rows: hard cap to limit output size

    Output control:
    - format: json (default), jsonl (NDJSON), csv
    - stream: true enables streaming for JSON/JSONL
    - filename: suggested download name (sanitized; extension normalized)
    """
    fmt = format.lower()
    if fmt not in {"json", "csv", "jsonl"}:
        raise HTTPException(status_code=400, detail="format must be 'json', 'csv', or 'jsonl'")
    if fmt == "csv" and stream:
        raise HTTPException(status_code=400, detail="Streaming is only supported for JSON format")

    st = _parse_dt(start_time)
    et = _parse_dt(end_time)
    ets = _map_event_types(event_type)
    cats = _map_categories(category)

    # Streaming applies to JSON and JSONL
    do_stream = bool(stream and fmt in {"json", "jsonl"})
    content = await audit_service.export_events(
        start_time=st,
        end_time=et,
        event_types=ets,
        categories=cats,
        user_id=user_id,
        request_id=request_id,
        correlation_id=correlation_id,
        ip_address=ip_address,
        session_id=session_id,
        endpoint=endpoint,
        method=method,
        min_risk_score=min_risk_score,
        format=fmt,
        file_path=None,
        stream=do_stream,
        max_rows=max_rows,
    )

    if fmt == "json":
        media = "application/json"
        default_name = "audit_export.json"
    elif fmt == "jsonl":
        media = "application/x-ndjson"
        default_name = "audit_export.jsonl"
    else:
        media = "text/csv"
        default_name = "audit_export.csv"

    def _normalize_ext(name: str, expected_ext: str) -> str:
        # Preserve known compound extensions in the stem (e.g., archive.tar.gz -> archive.tar)
        name_l = name.lower()
        compound = [".tar.gz", ".tar.bz2", ".tar.xz", ".tar.Z"]
        for ce in compound:
            if name_l.endswith(ce):
                base = name[: -len(ce)]  # keep without compound ext
                stem = base
                break
        else:
            p = Path(name)
            stem = p.stem or name
        if not expected_ext.startswith("."):
            expected_ext = "." + expected_ext
        return f"{stem}{expected_ext}"

    fname = _sanitize_filename(filename, default_name) if filename else default_name
    # Normalize extension to match format to reduce client confusion
    if fmt == "json":
        fname = _normalize_ext(fname, "json")
    elif fmt == "jsonl":
        fname = _normalize_ext(fname, "jsonl")
    else:
        fname = _normalize_ext(fname, "csv")
    headers = {"Content-Disposition": f"attachment; filename={fname}"}

    if do_stream:
        # content is an async generator from export_events
        return StreamingResponse(content=content, media_type=media, headers=headers)
    return Response(content=content, media_type=media, headers=headers)


@router.get(
    "/audit/count",
    summary="Count audit events for pagination",
)
async def count_audit_events(
    start_time: Optional[str] = Query(None, description="ISO8601 start timestamp"),
    end_time: Optional[str] = Query(None, description="ISO8601 end timestamp"),
    event_type: Optional[str] = Query(None, description="Event types (enum name or value), comma-separated"),
    category: Optional[str] = Query(None, description="Categories (enum name or value), comma-separated"),
    min_risk_score: Optional[int] = Query(None),
    user_id: Optional[str] = Query(None),
    request_id: Optional[str] = Query(None),
    correlation_id: Optional[str] = Query(None),
    ip_address: Optional[str] = Query(None, description="Filter by IP address"),
    session_id: Optional[str] = Query(None, description="Filter by session id"),
    endpoint: Optional[str] = Query(None, description="Filter by endpoint path"),
    method: Optional[str] = Query(None, description="Filter by HTTP method"),
    audit_service: UnifiedAuditService = Depends(get_audit_service_for_user),
    _: dict = Depends(require_admin),
):
    """Count audit events for pagination UIs. Requires admin.

    Accepts the same filters as the export endpoint (except format/stream/filename).
    Returns a JSON object: {"count": <int>}.
    """
    st = _parse_dt(start_time)
    et = _parse_dt(end_time)
    ets = _map_event_types(event_type)
    cats = _map_categories(category)

    count = await audit_service.count_events(
        start_time=st,
        end_time=et,
        event_types=ets,
        categories=cats,
        user_id=user_id,
        request_id=request_id,
        correlation_id=correlation_id,
        ip_address=ip_address,
        session_id=session_id,
        endpoint=endpoint,
        method=method,
        min_risk_score=min_risk_score,
    )
    return {"count": int(count)}
