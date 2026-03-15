from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import HTTPException
from loguru import logger

from tldw_Server_API.app.api.v1.schemas.admin_schemas import (
    ActivitySummaryResponse,
    AuditLogResponse,
    SecurityAlertSinkStatus,
    SecurityAlertStatusResponse,
    SystemLogEntry,
    SystemLogsResponse,
    SystemStatsResponse,
)
from tldw_Server_API.app.core.AuthNZ.alerting import get_security_alert_dispatcher
from tldw_Server_API.app.core.AuthNZ.database import DatabasePool
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.Logging.system_log_buffer import query_system_logs
from tldw_Server_API.app.core.Metrics import get_metrics_registry
from tldw_Server_API.app.core.testing import is_test_mode
from tldw_Server_API.app.services import admin_scope_service
from tldw_Server_API.app.services.admin_data_ops_service import (
    build_audit_log_csv as svc_build_audit_log_csv,
)
from tldw_Server_API.app.services.admin_data_ops_service import (
    build_audit_log_json as svc_build_audit_log_json,
)


def _is_db_pool_object(db: Any) -> bool:
    return isinstance(db, DatabasePool)


def _is_postgres_connection(db: Any) -> bool:
    """Resolve backend mode from connection/adapter shape without global probes."""
    if _is_db_pool_object(db):
        return getattr(db, "pool", None) is not None

    sqlite_hint = getattr(db, "_is_sqlite", None)
    if isinstance(sqlite_hint, bool):
        return not sqlite_hint

    if getattr(db, "_c", None) is not None:
        return False

    module_name = getattr(type(db), "__module__", "")
    if isinstance(module_name, str) and module_name.startswith("asyncpg"):
        return True

    return callable(getattr(db, "fetchrow", None))


def _parse_date_param(value: str | None, label: str, end_of_day: bool = False) -> datetime | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    raw = raw.replace("Z", "+00:00")
    try:
        if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
            dt = datetime.fromisoformat(raw)
            if end_of_day:
                dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
        else:
            dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid {label} date format") from None


async def get_security_alert_status() -> SecurityAlertStatusResponse:
    """Return configuration and last-known status for AuthNZ security alerts."""
    dispatcher = get_security_alert_dispatcher()
    status = dispatcher.get_status()

    sink_status_map: dict[str, bool | None] = status.get("last_sink_status", {})
    sink_error_map: dict[str, str | None] = status.get("last_sink_errors", {})
    sink_threshold_map: dict[str, str | None] = status.get("sink_thresholds", {})
    sink_backoff_map: dict[str, str | None] = status.get("sink_backoff_until", {})

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
            if status.get("last_dispatch_success") is False or any(row.last_error for row in configured_rows) or configured_rows and all(row.last_status is False for row in configured_rows):
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


async def get_system_stats(db) -> SystemStatsResponse:
    """Get system statistics."""
    try:
        def _row_to_dict(row, keys: list[str]) -> dict:
            if row is None:
                return {}
            if isinstance(row, dict):
                return row
            if hasattr(row, "keys"):
                return {key: row[key] for key in row}
            return {key: row[idx] if idx < len(row) else None for idx, key in enumerate(keys)}

        is_pg = _is_postgres_connection(db)
        if is_pg:
            # PostgreSQL
            user_stats = await db.fetchrow(
                """
                SELECT
                    COUNT(*) as total_users,
                    COUNT(*) FILTER (WHERE is_active = TRUE) as active_users,
                    COUNT(*) FILTER (WHERE is_verified = TRUE) as verified_users,
                    COUNT(*) FILTER (WHERE role = 'admin') as admin_users,
                    COUNT(*) FILTER (WHERE created_at > CURRENT_TIMESTAMP - INTERVAL '30 days') as new_users_30d
                FROM users
                """
            )

            storage_stats = await db.fetchrow(
                """
                SELECT
                    SUM(storage_used_mb) as total_used_mb,
                    SUM(storage_quota_mb) as total_quota_mb,
                    AVG(storage_used_mb) as avg_used_mb,
                    MAX(storage_used_mb) as max_used_mb
                FROM users
                WHERE is_active = TRUE
                """
            )

            session_stats = await db.fetchrow(
                """
                SELECT
                    COUNT(*) as active_sessions,
                    COUNT(DISTINCT user_id) as unique_users
                FROM sessions
                WHERE is_active = TRUE AND expires_at > CURRENT_TIMESTAMP
                """
            )

        else:
            # SQLite
            cursor = await db.execute(
                """
                SELECT
                    COUNT(*) as total_users,
                    SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active_users,
                    SUM(CASE WHEN is_verified = 1 THEN 1 ELSE 0 END) as verified_users,
                    SUM(CASE WHEN role = 'admin' THEN 1 ELSE 0 END) as admin_users,
                    SUM(CASE WHEN datetime(created_at) > datetime('now', '-30 days') THEN 1 ELSE 0 END) as new_users_30d
                FROM users
                """
            )
            user_stats = await cursor.fetchone()

            cursor = await db.execute(
                """
                SELECT
                    SUM(storage_used_mb) as total_used_mb,
                    SUM(storage_quota_mb) as total_quota_mb,
                    AVG(storage_used_mb) as avg_used_mb,
                    MAX(storage_used_mb) as max_used_mb
                FROM users
                WHERE is_active = 1
                """
            )
            storage_stats = await cursor.fetchone()

            cursor = await db.execute(
                """
                SELECT
                    COUNT(*) as active_sessions,
                    COUNT(DISTINCT user_id) as unique_users
                FROM sessions
                WHERE is_active = 1 AND datetime(expires_at) > datetime('now')
                """
            )
            session_stats = await cursor.fetchone()

        user_keys = ["total_users", "active_users", "verified_users", "admin_users", "new_users_30d"]
        storage_keys = ["total_used_mb", "total_quota_mb", "avg_used_mb", "max_used_mb"]
        session_keys = ["active_sessions", "unique_users"]
        us = _row_to_dict(user_stats, user_keys)
        ss = _row_to_dict(storage_stats, storage_keys)
        se = _row_to_dict(session_stats, session_keys)

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

    except Exception as exc:
        logger.error(f"Failed to get system stats: {exc}")
        try:
            if is_test_mode():
                return SystemStatsResponse(
                    users={"total": 0, "active": 0, "verified": 0, "admins": 0, "new_last_30d": 0},
                    storage={"total_used_mb": 0.0, "total_quota_mb": 0.0, "average_used_mb": 0.0, "max_used_mb": 0.0},
                    sessions={"active": 0, "unique_users": 0},
                )
        except Exception as db_summary_error:
            logger.debug("Admin system service failed to build fallback DB summary", exc_info=db_summary_error)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve system statistics",
        ) from exc


async def get_dashboard_activity(
    days: int,
    db,
    granularity: Literal["hour", "day", "auto"] = "auto",
) -> ActivitySummaryResponse:
    """Return recent request/user activity for the admin dashboard."""
    now_utc = datetime.now(timezone.utc)
    resolved_granularity: Literal["hour", "day"] = (
        "hour" if granularity == "auto" and days <= 1
        else "day" if granularity == "auto"
        else granularity
    )
    warnings: list[str] = []
    if resolved_granularity == "hour":
        end_hour = now_utc.replace(minute=0, second=0, microsecond=0)
        buckets = [
            end_hour - timedelta(hours=offset)
            for offset in range(23, -1, -1)
        ]
    else:
        end_day = now_utc.date()
        start_day = end_day - timedelta(days=days - 1)
        buckets = [
            datetime.combine(start_day + timedelta(days=offset), datetime.min.time(), tzinfo=timezone.utc)
            for offset in range(days)
        ]
    start_dt = buckets[0]
    activity_by_bucket = {
        bucket: {
            "date": bucket.date().isoformat(),
            "bucket_start": bucket.isoformat(),
            "requests": 0,
            "users": 0,
        }
        for bucket in buckets
    }

    def _bucket_for_datetime(timestamp: datetime) -> datetime:
        dt = timestamp.astimezone(timezone.utc)
        if resolved_granularity == "hour":
            return dt.replace(minute=0, second=0, microsecond=0)
        return datetime.combine(dt.date(), datetime.min.time(), tzinfo=timezone.utc)

    def _parse_row_bucket(value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            dt = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
            return _bucket_for_datetime(dt)
        raw = str(value).strip()
        if not raw:
            return None
        if resolved_granularity == "hour" and "T" not in raw and " " in raw:
            raw = raw.replace(" ", "T")
        if raw.endswith("Z"):
            raw = raw.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return _bucket_for_datetime(parsed)

    try:
        registry = get_metrics_registry()
        request_values = registry.values.get("http_requests_total", [])
        for metric_value in list(request_values):
            try:
                metric_day = datetime.fromtimestamp(
                    metric_value.timestamp,
                    timezone.utc,
                ).date()
            except (OSError, OverflowError, ValueError):
                continue
            metric_dt = datetime.combine(metric_day, datetime.min.time(), tzinfo=timezone.utc)
            if resolved_granularity == "hour":
                try:
                    metric_dt = datetime.fromtimestamp(
                        metric_value.timestamp,
                        timezone.utc,
                    )
                except (OSError, OverflowError, ValueError):
                    continue
            bucket = _bucket_for_datetime(metric_dt)
            if bucket in activity_by_bucket:
                activity_by_bucket[bucket]["requests"] += int(metric_value.value or 0)
    except Exception as exc:
        logger.warning("Admin activity request metrics unavailable: {}", exc)
        warnings.append("request_metrics_unavailable")

    try:
        is_pg = _is_postgres_connection(db)
        if is_pg:
            if resolved_granularity == "hour":
                rows = await db.fetch(
                    """
                    SELECT date_trunc('hour', created_at AT TIME ZONE 'UTC') as bucket,
                           COUNT(DISTINCT user_id) as active_users
                    FROM sessions
                    WHERE created_at >= $1
                    GROUP BY bucket
                    ORDER BY bucket
                    """,
                    start_dt,
                )
            else:
                rows = await db.fetch(
                    """
                    SELECT DATE(created_at) as bucket,
                           COUNT(DISTINCT user_id) as active_users
                    FROM sessions
                    WHERE created_at >= $1
                    GROUP BY bucket
                    ORDER BY bucket
                    """,
                    start_dt,
                )
        else:
            if resolved_granularity == "hour":
                cursor = await db.execute(
                    """
                    SELECT strftime('%Y-%m-%dT%H:00:00', datetime(created_at)) as bucket,
                           COUNT(DISTINCT user_id) as active_users
                    FROM sessions
                    WHERE datetime(created_at) >= datetime(?)
                    GROUP BY bucket
                    ORDER BY bucket
                    """,
                    (start_dt.isoformat(),),
                )
            else:
                cursor = await db.execute(
                    """
                    SELECT date(created_at) as bucket,
                           COUNT(DISTINCT user_id) as active_users
                    FROM sessions
                    WHERE datetime(created_at) >= datetime(?)
                    GROUP BY bucket
                    ORDER BY bucket
                    """,
                    (start_dt.isoformat(),),
                )
            rows = await cursor.fetchall()
        for row in rows:
            if isinstance(row, dict):
                bucket_value = row.get("bucket")
                active_users = row.get("active_users")
            else:
                bucket_value = row[0] if len(row) > 0 else None
                active_users = row[1] if len(row) > 1 else None
            bucket = _parse_row_bucket(bucket_value)
            if bucket in activity_by_bucket:
                activity_by_bucket[bucket]["users"] = int(active_users or 0)
    except Exception as exc:
        logger.warning("Admin activity user metrics unavailable: {}", exc)
        warnings.append("user_metrics_unavailable")

    points = [activity_by_bucket[bucket] for bucket in buckets]
    return ActivitySummaryResponse(
        days=days,
        granularity=resolved_granularity,
        points=points,
        warnings=warnings or None,
    )


async def get_audit_log(
    *,
    user_id: int | None,
    action: str | None,
    resource: str | None,
    start: str | None,
    end: str | None,
    days: int,
    limit: int,
    offset: int,
    org_id: int | None,
    principal: AuthPrincipal,
    db,
) -> AuditLogResponse:
    try:
        is_pg = _is_postgres_connection(db)
        conditions: list[str] = []
        params: list[Any] = []
        param_count = 0

        start_dt = _parse_date_param(start, "start")
        end_dt = _parse_date_param(end, "end", end_of_day=True)
        if start_dt and end_dt and start_dt > end_dt:
            raise HTTPException(status_code=400, detail="Start date must be on or before end date")

        org_ids = await admin_scope_service.get_admin_org_ids(principal)
        if org_id is not None:
            org_ids = [org_id] if org_ids is None else [org_id] if org_id in org_ids else []
        if org_ids is not None and len(org_ids) == 0:
            return AuditLogResponse(entries=[], total=0, limit=limit, offset=offset)

        if user_id:
            await admin_scope_service.enforce_admin_user_scope(principal, user_id, require_hierarchy=False)
            param_count += 1
            conditions.append(f"a.user_id = ${param_count}" if is_pg else "a.user_id = ?")
            params.append(user_id)

        if action:
            param_count += 1
            conditions.append(f"a.action = ${param_count}" if is_pg else "a.action = ?")
            params.append(action)

        if resource:
            resource_filter = resource.strip()
            if resource_filter:
                if ":" in resource_filter:
                    resource_type, resource_id = resource_filter.split(":", 1)
                    resource_type = resource_type.strip()
                    resource_id = resource_id.strip()
                    if resource_type:
                        param_count += 1
                        conditions.append(f"a.resource_type = ${param_count}" if is_pg else "a.resource_type = ?")
                        params.append(resource_type)
                    if resource_id.isdigit():
                        param_count += 1
                        conditions.append(f"a.resource_id = ${param_count}" if is_pg else "a.resource_id = ?")
                        params.append(int(resource_id))
                else:
                    param_count += 1
                    if is_pg:
                        conditions.append(f"a.resource_type ILIKE ${param_count}")
                        params.append(f"%{resource_filter}%")
                    else:
                        conditions.append("LOWER(a.resource_type) LIKE ?")
                        params.append(f"%{resource_filter.lower()}%")

        if start_dt or end_dt:
            if start_dt:
                param_count += 1
                conditions.append(f"a.created_at >= ${param_count}" if is_pg else "datetime(a.created_at) >= datetime(?)")
                params.append(start_dt.isoformat())
            if end_dt:
                param_count += 1
                conditions.append(f"a.created_at <= ${param_count}" if is_pg else "datetime(a.created_at) <= datetime(?)")
                params.append(end_dt.isoformat())
        else:
            if is_pg:
                conditions.append(f"a.created_at > CURRENT_TIMESTAMP - INTERVAL '{days} days'")
            else:
                conditions.append("datetime(a.created_at) > datetime('now', ? || ' days')")
                params.append(f"-{days}")

        join_clause = ""
        if org_ids is not None:
            join_clause = " JOIN org_members om ON om.user_id = a.user_id"
            if is_pg:
                param_count += 1
                conditions.append(f"om.org_id = ANY(${param_count})")
                params.append(org_ids)
            else:
                placeholders = ",".join("?" for _ in org_ids)
                conditions.append(f"om.org_id IN ({placeholders})")
                params.extend(org_ids)

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

        def _format_resource(resource_type: str | None, resource_id: int | None) -> str | None:
            if not resource_type and resource_id is None:
                return None
            if resource_type and resource_id is not None:
                return f"{resource_type}:{resource_id}"
            if resource_type:
                return str(resource_type)
            return str(resource_id)

        if is_pg:
            limit_pos = param_count + 1
            offset_pos = param_count + 2
            count_query_template = """
                SELECT COUNT(*)
                FROM audit_logs a
                {join_clause}
                {where_clause}
            """
            count_query = count_query_template.format_map(locals())  # nosec B608
            total = await db.fetchval(count_query, *params)
            query_template = """
                SELECT a.id, a.user_id, u.username, a.action, a.resource_type, a.resource_id, a.details,
                       a.ip_address, a.created_at
                FROM audit_logs a
                LEFT JOIN users u ON a.user_id = u.id
                {join_clause}
                {where_clause}
                ORDER BY a.created_at DESC
                LIMIT ${limit_pos}
                OFFSET ${offset_pos}
            """
            query = query_template.format_map(locals())  # nosec B608
            query_params = list(params)
            query_params.append(limit)
            query_params.append(offset)
            rows = await db.fetch(query, *query_params)
        else:
            count_query_template = """
                SELECT COUNT(*)
                FROM audit_logs a
                {join_clause}
                {where_clause}
            """
            count_query = count_query_template.format_map(locals())  # nosec B608
            count_cursor = await db.execute(count_query, params)
            count_row = await count_cursor.fetchone()
            total = int(count_row[0]) if count_row and count_row[0] is not None else 0
            query_template = """
                SELECT a.id, a.user_id, u.username, a.action, a.resource_type, a.resource_id, a.details,
                       a.ip_address, a.created_at
                FROM audit_logs a
                LEFT JOIN users u ON a.user_id = u.id
                {join_clause}
                {where_clause}
                ORDER BY a.created_at DESC
                LIMIT ?
                OFFSET ?
            """
            query = query_template.format_map(locals())  # nosec B608
            query_params = list(params)
            query_params.append(limit)
            query_params.append(offset)
            cursor = await db.execute(query, query_params)
            rows = await cursor.fetchall()

        entries = []
        for row in rows:
            if isinstance(row, dict):
                resource_value = _format_resource(row.get("resource_type"), row.get("resource_id"))
                row["resource"] = resource_value
                entries.append(row)
            else:
                resource_value = _format_resource(row[4], row[5])
                entry = {
                    "id": row[0],
                    "user_id": row[1],
                    "username": row[2],
                    "action": row[3],
                    "resource": resource_value,
                    "details": row[6],
                    "ip_address": row[7],
                    "created_at": row[8],
                }
                entries.append(entry)

        return AuditLogResponse(entries=entries, total=int(total or 0), limit=limit, offset=offset)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to get audit log: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve audit log",
        ) from exc


async def export_audit_log(
    *,
    user_id: int | None,
    action: str | None,
    resource: str | None,
    start: str | None,
    end: str | None,
    days: int,
    limit: int,
    offset: int,
    org_id: int | None,
    format: str,
    principal: AuthPrincipal,
    db,
) -> tuple[str, str, str]:
    audit = await get_audit_log(
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
    if format == "json":
        content = svc_build_audit_log_json(audit.entries, total=audit.total, limit=limit, offset=offset)
        return content, "application/json", "audit_log.json"
    content = svc_build_audit_log_csv(audit.entries)
    return content, "text/csv", "audit_log.csv"


async def list_system_logs(
    *,
    start: str | None,
    end: str | None,
    level: str | None,
    service: str | None,
    query: str | None,
    org_id: int | None,
    user_id: int | None,
    limit: int,
    offset: int,
    principal: AuthPrincipal,
) -> SystemLogsResponse:
    start_dt = _parse_date_param(start, "start")
    end_dt = _parse_date_param(end, "end", end_of_day=True)
    if start_dt and end_dt and start_dt > end_dt:
        raise HTTPException(status_code=400, detail="Start date must be on or before end date")

    org_ids = await admin_scope_service.get_admin_org_ids(principal)
    if org_id is not None:
        org_ids = [org_id] if org_ids is None else [org_id] if org_id in org_ids else []
    if org_ids is not None and len(org_ids) == 0:
        return SystemLogsResponse(items=[], total=0, limit=limit, offset=offset)

    items, total = query_system_logs(
        start=start_dt,
        end=end_dt,
        level=level,
        service=service,
        query=query,
        org_id=org_id if org_ids is None else None,
        org_ids=org_ids,
        user_id=user_id,
        limit=limit,
        offset=offset,
    )
    return SystemLogsResponse(
        items=[SystemLogEntry(**item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )
