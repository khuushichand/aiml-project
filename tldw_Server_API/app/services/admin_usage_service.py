from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from loguru import logger

from tldw_Server_API.app.api.v1.schemas.admin_schemas import (
    LLMTopSpenderRow,
    LLMTopSpendersResponse,
    LLMUsageLogResponse,
    LLMUsageLogRow,
    LLMUsageSummaryResponse,
    LLMUsageSummaryRow,
    UsageDailyResponse,
    UsageDailyRow,
    UsageTopResponse,
    UsageTopRow,
)
from tldw_Server_API.app.core.AuthNZ.database import is_postgres_backend
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.Metrics import get_metrics_registry
from tldw_Server_API.app.services import admin_scope_service
from tldw_Server_API.app.services.llm_usage_aggregator import aggregate_llm_usage_daily
from tldw_Server_API.app.services.usage_aggregator import aggregate_usage_daily

_ADMIN_USAGE_NONCRITICAL_EXCEPTIONS = (
    AssertionError,
    AttributeError,
    ConnectionError,
    FileNotFoundError,
    ImportError,
    IndexError,
    KeyError,
    LookupError,
    OSError,
    PermissionError,
    RuntimeError,
    TimeoutError,
    TypeError,
    UnicodeDecodeError,
    ValueError,
)


def _fmt_csv_value(x: Any) -> str:
    if x is None:
        return ""
    s = str(x)
    if "," in s or "\n" in s or '"' in s:
        return '"' + s.replace('"', '""') + '"'
    return s


async def fetch_usage_daily(
    db,
    *,
    user_id: int | None,
    org_ids: list[int] | None,
    start: str | None,
    end: str | None,
    page: int,
    limit: int,
) -> tuple[list[dict[str, Any]], int, bool]:
    """Return (rows, total, has_bytes_in_total). Rows keys: user_id, day, requests, errors, bytes_total, bytes_in_total, latency_avg_ms."""
    offset = (page - 1) * limit
    conditions: list[str] = []
    params: list[Any] = []
    pg = await is_postgres_backend()
    if org_ids is not None and len(org_ids) == 0:
        return [], 0, True

    def _add(cond_sql: str, val: Any, typed_date: bool = False):
        if val is None:
            return
        if pg:
            idx = len(params) + 1
            cond = cond_sql.replace("?", f"${idx}{'::date' if typed_date else ''}")
            conditions.append(cond)
        else:
            conditions.append(cond_sql)
        params.append(val)

    _add("user_id = ?", user_id)
    _add("day >= ?", start, typed_date=True)
    _add("day <= ?", end, typed_date=True)
    join_clause = ""
    if org_ids is not None:
        join_clause = " JOIN org_members om ON om.user_id = usage_daily.user_id"
        if pg:
            conditions.append(f"om.org_id = ANY(${len(params) + 1})")
            params.append(org_ids)
        else:
            placeholders = ",".join("?" for _ in org_ids)
            conditions.append(f"om.org_id IN ({placeholders})")
            params.extend(org_ids)
    where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    if pg:
        total = await db.fetchval(f"SELECT COUNT(*) FROM usage_daily{join_clause}{where_clause}", *params)
        has_in = True
        try:
            sql = (
                f"SELECT user_id, day, requests, errors, bytes_total, COALESCE(bytes_in_total,0) as bytes_in_total, latency_avg_ms "
                f"FROM usage_daily{join_clause}{where_clause} ORDER BY day DESC, user_id ASC LIMIT ${len(params)+1} OFFSET ${len(params)+2}"
            )
            rows = await db.fetch(sql, *params, limit, offset)
        except _ADMIN_USAGE_NONCRITICAL_EXCEPTIONS as e:
            logger.debug(f"usage_daily: falling back without bytes_in_total (pg): {e}")
            try:
                get_metrics_registry().increment(
                    "app_warning_events_total",
                    labels={"component": "admin_usage", "event": "daily_bytes_in_missing_fallback"},
                )
            except _ADMIN_USAGE_NONCRITICAL_EXCEPTIONS:
                logger.debug("metrics increment failed for daily_bytes_in_missing_fallback")
            has_in = False
            sql = (
                f"SELECT user_id, day, requests, errors, bytes_total, latency_avg_ms "
                f"FROM usage_daily{join_clause}{where_clause} ORDER BY day DESC, user_id ASC LIMIT ${len(params)+1} OFFSET ${len(params)+2}"
            )
            rows = await db.fetch(sql, *params, limit, offset)
        # Normalize
        out: list[dict[str, Any]] = []
        for r in rows:
            # asyncpg.Record supports dict(), sqlite rows don't reliably;
            # build a name-keyed dict defensively.
            try:
                d = dict(r)
            except _ADMIN_USAGE_NONCRITICAL_EXCEPTIONS:
                d = {k: r[k] for k in r} if hasattr(r, "keys") else {}
            if not has_in:
                d.setdefault("bytes_in_total", None)
            out.append(d)
        return out, int(total or 0), has_in
    # SQLite
    # Prefer pool-style helpers when available (e.g., DatabasePool in tests)
    if hasattr(db, "fetchval"):
        total = int(
            (await db.fetchval(f"SELECT COUNT(*) FROM usage_daily{join_clause}{where_clause}", params))
            or 0
        )
    else:
        cur = await db.execute(f"SELECT COUNT(*) FROM usage_daily{join_clause}{where_clause}", params)
        total_row = await cur.fetchone()
        total = int(total_row[0] if total_row else 0)
    has_in = True
    try:
        sql = (
            f"SELECT user_id, day, requests, errors, bytes_total, IFNULL(bytes_in_total,0) as bytes_in_total, latency_avg_ms "
            f"FROM usage_daily{join_clause}{where_clause} ORDER BY day DESC, user_id ASC LIMIT ? OFFSET ?"
        )
        if hasattr(db, "fetchall"):
            rows = await db.fetchall(sql, params + [limit, offset])
        else:
            cur = await db.execute(sql, params + [limit, offset])
            rows = await cur.fetchall()
    except _ADMIN_USAGE_NONCRITICAL_EXCEPTIONS as e:
        logger.debug(f"usage_daily: falling back without bytes_in_total (sqlite): {e}")
        try:
            get_metrics_registry().increment(
                "app_warning_events_total",
                labels={"component": "admin_usage", "event": "daily_bytes_in_missing_fallback"},
            )
        except _ADMIN_USAGE_NONCRITICAL_EXCEPTIONS:
            logger.debug("metrics increment failed for daily_bytes_in_missing_fallback")
        has_in = False
        sql = (
            f"SELECT user_id, day, requests, errors, bytes_total, latency_avg_ms "
            f"FROM usage_daily{join_clause}{where_clause} ORDER BY day DESC, user_id ASC LIMIT ? OFFSET ?"
        )
        if hasattr(db, "fetchall"):
            rows = await db.fetchall(sql, params + [limit, offset])
        else:
            cur = await db.execute(sql, params + [limit, offset])
            rows = await cur.fetchall()
    out = []
    for r in rows:
        if hasattr(r, 'keys'):
            # sqlite3.Row supports key access but not get(); avoid dict(r)
            if has_in:
                d = {
                    "user_id": r["user_id"],
                    "day": r["day"],
                    "requests": r["requests"],
                    "errors": r["errors"],
                    "bytes_total": r["bytes_total"],
                    "bytes_in_total": r.get("bytes_in_total") if hasattr(r, "get") else r["bytes_in_total"],
                    "latency_avg_ms": r["latency_avg_ms"],
                }
            else:
                d = {
                    "user_id": r["user_id"],
                    "day": r["day"],
                    "requests": r["requests"],
                    "errors": r["errors"],
                    "bytes_total": r["bytes_total"],
                    "bytes_in_total": None,
                    "latency_avg_ms": r["latency_avg_ms"],
                }
        else:
            if has_in:
                d = {"user_id": r[0], "day": r[1], "requests": r[2], "errors": r[3], "bytes_total": r[4], "bytes_in_total": r[5], "latency_avg_ms": r[6]}
            else:
                d = {"user_id": r[0], "day": r[1], "requests": r[2], "errors": r[3], "bytes_total": r[4], "bytes_in_total": None, "latency_avg_ms": r[5]}
        out.append(d)
    return out, total, has_in


async def export_usage_daily_csv_text(
    db,
    *,
    user_id: int | None,
    org_ids: list[int] | None,
    start: str | None,
    end: str | None,
    limit: int,
) -> str:
    rows, _, has_in = await fetch_usage_daily(
        db,
        user_id=user_id,
        org_ids=org_ids,
        start=start,
        end=end,
        page=1,
        limit=limit,
    )
    header = ["user_id","day","requests","errors","bytes_total","bytes_in_total","latency_avg_ms"]
    lines = [",".join(header)]
    for r in rows:
        row = [r.get("user_id"), r.get("day"), r.get("requests"), r.get("errors"), r.get("bytes_total"), (r.get("bytes_in_total") if has_in else None), r.get("latency_avg_ms")]
        lines.append(",".join(_fmt_csv_value(c) for c in row))
    return "\n".join(lines) + "\n"


async def fetch_usage_top(
    db,
    *,
    start: str | None,
    end: str | None,
    limit: int,
    metric: str,
    org_ids: list[int] | None,
) -> list[dict[str, Any]]:
    pg = await is_postgres_backend()
    conditions: list[str] = []
    params: list[Any] = []
    if org_ids is not None and len(org_ids) == 0:
        return []
    def _add(cond: str, val: Any, typed_date: bool = False):
        if val is None:
            return
        if pg:
            idx = len(params) + 1
            conditions.append(cond.replace('?', f"${idx}{'::date' if typed_date else ''}"))
        else:
            conditions.append(cond)
        params.append(val)
    _add("day >= ?", start, True)
    _add("day <= ?", end, True)
    join_clause = ""
    if org_ids is not None:
        join_clause = " JOIN org_members om ON om.user_id = usage_daily.user_id"
        if pg:
            conditions.append(f"om.org_id = ANY(${len(params) + 1})")
            params.append(org_ids)
        else:
            placeholders = ",".join("?" for _ in org_ids)
            conditions.append(f"om.org_id IN ({placeholders})")
            params.extend(org_ids)
    where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    order_map = {
        "requests": "SUM(requests) DESC",
        "bytes_total": "SUM(bytes_total) DESC",
        "bytes_in_total": "COALESCE(SUM(bytes_in_total),0) DESC" if pg else "IFNULL(SUM(bytes_in_total),0) DESC",
        "errors": "SUM(errors) DESC",
    }
    order_by = order_map[metric]
    if pg:
        try:
            sql = (
                f"SELECT user_id, SUM(requests) AS requests, SUM(errors) AS errors, SUM(bytes_total) AS bytes_total, COALESCE(SUM(bytes_in_total),0) AS bytes_in_total, AVG(latency_avg_ms)::float AS latency_avg_ms FROM usage_daily{join_clause}{where_clause} GROUP BY user_id ORDER BY {order_by} LIMIT $ {len(params) + 1}"
            ).replace('$ ', '$')
            rows = await db.fetch(sql, *params, limit)
        except _ADMIN_USAGE_NONCRITICAL_EXCEPTIONS as e:
            logger.debug(f"usage_top: falling back without bytes_in_total (pg): {e}")
            try:
                get_metrics_registry().increment(
                    "app_warning_events_total",
                    labels={"component": "admin_usage", "event": "top_bytes_in_missing_fallback"},
                )
            except _ADMIN_USAGE_NONCRITICAL_EXCEPTIONS:
                logger.debug("metrics increment failed for top_bytes_in_missing_fallback")
            sql = (
                f"SELECT user_id, SUM(requests) AS requests, SUM(errors) AS errors, SUM(bytes_total) AS bytes_total, AVG(latency_avg_ms)::float AS latency_avg_ms FROM usage_daily{join_clause}{where_clause} GROUP BY user_id ORDER BY {order_by} LIMIT $ {len(params) + 1}"
            ).replace('$ ', '$')
            rows = await db.fetch(sql, *params, limit)
        return [dict(r) for r in rows]
    # SQLite
    try:
        sql = (
            f"SELECT user_id, SUM(requests) AS requests, SUM(errors) AS errors, SUM(bytes_total) AS bytes_total, IFNULL(SUM(bytes_in_total),0) AS bytes_in_total, AVG(latency_avg_ms) AS latency_avg_ms FROM usage_daily{join_clause}{where_clause} GROUP BY user_id ORDER BY {order_by} LIMIT ?"
        )
        if hasattr(db, "fetchall"):
            rows = await db.fetchall(sql, params + [limit])
        else:
            cur = await db.execute(sql, params + [limit])
            rows = await cur.fetchall()
        out_rows: list[dict[str, Any]] = []
        for r in rows:
            if hasattr(r, "keys"):
                # sqlite3.Row: use key access, not .get
                out_rows.append({
                    "user_id": r["user_id"],
                    "requests": r["requests"],
                    "errors": r["errors"],
                    "bytes_total": r["bytes_total"],
                    "bytes_in_total": r["bytes_in_total"],
                    "latency_avg_ms": r["latency_avg_ms"],
                })
            else:
                out_rows.append({
                    "user_id": r[0],
                    "requests": r[1],
                    "errors": r[2],
                    "bytes_total": r[3],
                    "bytes_in_total": r[4],
                    "latency_avg_ms": r[5],
                })
        return out_rows
    except _ADMIN_USAGE_NONCRITICAL_EXCEPTIONS as e:
        logger.debug(f"usage_top: falling back without bytes_in_total (sqlite): {e}")
        try:
            get_metrics_registry().increment(
                "app_warning_events_total",
                labels={"component": "admin_usage", "event": "top_bytes_in_missing_fallback"},
            )
        except _ADMIN_USAGE_NONCRITICAL_EXCEPTIONS:
            logger.debug("metrics increment failed for top_bytes_in_missing_fallback")
        sql = (
            f"SELECT user_id, SUM(requests) AS requests, SUM(errors) AS errors, SUM(bytes_total) AS bytes_total, AVG(latency_avg_ms) AS latency_avg_ms FROM usage_daily{join_clause}{where_clause} GROUP BY user_id ORDER BY {order_by} LIMIT ?"
        )
        if hasattr(db, "fetchall"):
            rows = await db.fetchall(sql, params + [limit])
        else:
            cur = await db.execute(sql, params + [limit])
            rows = await cur.fetchall()
        out_rows: list[dict[str, Any]] = []
        for r in rows:
            if hasattr(r, "keys"):
                out_rows.append({
                    "user_id": r["user_id"],
                    "requests": r["requests"],
                    "errors": r["errors"],
                    "bytes_total": r["bytes_total"],
                    "bytes_in_total": None,
                    "latency_avg_ms": r["latency_avg_ms"],
                })
            else:
                out_rows.append({
                    "user_id": r[0],
                    "requests": r[1],
                    "errors": r[2],
                    "bytes_total": r[3],
                    "bytes_in_total": None,
                    "latency_avg_ms": r[4],
                })
        return out_rows


async def export_usage_top_csv_text(
    db,
    *,
    start: str | None,
    end: str | None,
    limit: int,
    metric: str,
    org_ids: list[int] | None,
) -> str:
    rows = await fetch_usage_top(db, start=start, end=end, limit=limit, metric=metric, org_ids=org_ids)
    header = ["user_id","requests","errors","bytes_total","bytes_in_total","latency_avg_ms"]
    out = [",".join(header)]
    for r in rows:
        out.append(",".join(_fmt_csv_value(r.get(k)) for k in ["user_id","requests","errors","bytes_total","bytes_in_total","latency_avg_ms"]))
    return "\n".join(out) + "\n"


async def fetch_llm_usage(
    db,
    *,
    user_id: int | None,
    provider: str | None,
    model: str | None,
    operation: str | None,
    status_code: int | None,
    start: str | None,
    end: str | None,
    page: int,
    limit: int,
    org_ids: list[int] | None,
) -> tuple[list[dict[str, Any]], int]:
    offset = (page - 1) * limit
    pg = await is_postgres_backend()
    conditions: list[str] = []
    params: list[Any] = []
    if org_ids is not None and len(org_ids) == 0:
        return [], 0

    def add_cond(sql: str, value):
        if value is None:
            return
        if pg:
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
    join_clause = ""
    if org_ids is not None:
        join_clause = " JOIN org_members om ON om.user_id = llm_usage_log.user_id"
        if pg:
            conditions.append(f"om.org_id = ANY(${len(params) + 1})")
            params.append(org_ids)
        else:
            placeholders = ",".join("?" for _ in org_ids)
            conditions.append(f"om.org_id IN ({placeholders})")
            params.extend(org_ids)
    where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    if pg:
        total = await db.fetchval(f"SELECT COUNT(*) FROM llm_usage_log{join_clause}{where_clause}", *params)
        data_sql = (
            f"SELECT id, ts, user_id, key_id, endpoint, operation, provider, model, status, latency_ms, prompt_tokens, completion_tokens, total_tokens, total_cost_usd, currency, estimated, request_id FROM llm_usage_log{join_clause}{where_clause} ORDER BY ts DESC LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}"
        )
        rows = await db.fetch(data_sql, *params, limit, offset)
        return [dict(r) for r in rows], int(total or 0)

    # SQLite
    cur = await db.execute(f"SELECT COUNT(*) FROM llm_usage_log{join_clause}{where_clause}", params)
    total_row = await cur.fetchone()
    total = int(total_row[0] if total_row else 0)
    data_sql = (
        f"SELECT id, ts, user_id, key_id, endpoint, operation, provider, model, status, latency_ms, prompt_tokens, completion_tokens, total_tokens, total_cost_usd, currency, estimated, request_id FROM llm_usage_log{join_clause}{where_clause} ORDER BY ts DESC LIMIT ? OFFSET ?"
    )
    cur = await db.execute(data_sql, params + [limit, offset])
    rows = await cur.fetchall()
    out = []
    for row in rows:
        if hasattr(row, 'keys'):
            d = dict(row)
        else:
            d = {
                "id": row[0], "ts": row[1], "user_id": row[2], "key_id": row[3], "endpoint": row[4], "operation": row[5],
                "provider": row[6], "model": row[7], "status": row[8], "latency_ms": row[9], "prompt_tokens": row[10],
                "completion_tokens": row[11], "total_tokens": row[12], "total_cost_usd": row[13], "currency": row[14],
                "estimated": bool(row[15]), "request_id": row[16],
            }
        out.append(d)
    return out, total


async def fetch_llm_usage_summary(
    db,
    *,
    group_by: str,
    provider: str | None,
    start: str | None,
    end: str | None,
    org_ids: list[int] | None,
) -> list[dict[str, Any]]:
    """Summarize llm_usage_log grouped by a key.

    group_by: one of user|operation|day|endpoint|provider|model|status
    """
    pg = await is_postgres_backend()
    params: list[Any] = []
    where: list[str] = []
    if org_ids is not None and len(org_ids) == 0:
        return []
    def _add(cond: str, val: Any):
        if val is None:
            return
        if pg:
            where.append(cond.replace('?', f"${len(params)+1}"))
        else:
            where.append(cond)
        params.append(val)
    _add("LOWER(provider) = LOWER(?)", provider)
    _add("ts >= ?", start)
    _add("ts <= ?", end)
    join_clause = ""
    if org_ids is not None:
        join_clause = " JOIN org_members om ON om.user_id = llm_usage_log.user_id"
        if pg:
            where.append(f"om.org_id = ANY(${len(params) + 1})")
            params.append(org_ids)
        else:
            placeholders = ",".join("?" for _ in org_ids)
            where.append(f"om.org_id IN ({placeholders})")
            params.extend(org_ids)
    where_clause = (" WHERE " + " AND ".join(where)) if where else ""

    # Determine grouping expression per backend
    if group_by == 'user':
        key_expr = 'COALESCE(user_id,0)' if pg else 'IFNULL(user_id,0)'
    elif group_by == 'operation':
        key_expr = 'operation'
    elif group_by == 'day':
        # Align to UTC day boundary
        key_expr = "CAST(date_trunc('day', ts AT TIME ZONE 'UTC') AS date)" if pg else "strftime('%Y-%m-%d', ts, 'utc')"
    elif group_by in {'endpoint', 'provider', 'model', 'status'}:
        key_expr = group_by
    else:
        # Fallback to endpoint for unknown values
        key_expr = 'endpoint'
    if pg:
        sql = (
            f"SELECT {key_expr} as group_value, "
            "COUNT(*) AS requests, SUM(CASE WHEN status >= 400 THEN 1 ELSE 0 END) AS errors, "
            "SUM(COALESCE(prompt_tokens,0)) AS input_tokens, SUM(COALESCE(completion_tokens,0)) AS output_tokens, "
            "SUM(COALESCE(total_tokens,0)) AS total_tokens, SUM(COALESCE(total_cost_usd,0)) AS total_cost_usd, AVG(latency_ms)::float AS latency_avg_ms "
            f"FROM llm_usage_log{join_clause}{where_clause} GROUP BY {key_expr} ORDER BY requests DESC"
        )
        rows = await db.fetch(sql, *params)
        out: list[dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            try:
                d["group_value"] = str(d.get("group_value", ""))
            except _ADMIN_USAGE_NONCRITICAL_EXCEPTIONS:
                d["group_value"] = str(d.get("group_value"))
            out.append(d)
        return out
    # SQLite
    sql = (
        f"SELECT {key_expr} as group_value, "
        "COUNT(*) as requests, SUM(CASE WHEN status >= 400 THEN 1 ELSE 0 END) as errors, "
        "SUM(IFNULL(prompt_tokens,0)) as input_tokens, SUM(IFNULL(completion_tokens,0)) as output_tokens, "
        "SUM(IFNULL(total_tokens,0)) as total_tokens, SUM(IFNULL(total_cost_usd,0)) as total_cost_usd, AVG(latency_ms) as latency_avg_ms "
        f"FROM llm_usage_log{join_clause}{where_clause} GROUP BY {key_expr} ORDER BY requests DESC"
    )
    cur = await db.execute(sql, params)
    rows = await cur.fetchall()
    out_rows: list[dict[str, Any]] = []
    for r in rows:
        gv = r[0]
        try:
            gv_str = str(gv)
        except _ADMIN_USAGE_NONCRITICAL_EXCEPTIONS:
            gv_str = f"{gv}"
        out_rows.append({
            'group_value': gv_str,
            'requests': int(r[1] or 0),
            'errors': int(r[2] or 0),
            'input_tokens': int(r[3] or 0),
            'output_tokens': int(r[4] or 0),
            'total_tokens': int(r[5] or 0),
            'total_cost_usd': float(r[6] or 0.0),
            'latency_avg_ms': (float(r[7]) if r[7] is not None else None),
        })
    return out_rows


async def fetch_llm_top_spenders(
    db,
    *,
    start: str | None,
    end: str | None,
    limit: int,
    org_ids: list[int] | None,
) -> list[dict[str, Any]]:
    pg = await is_postgres_backend()
    params: list[Any] = []
    where: list[str] = []
    if org_ids is not None and len(org_ids) == 0:
        return []
    def _add(cond: str, val: Any):
        if val is None:
            return
        if pg:
            where.append(cond.replace('?', f"${len(params)+1}"))
        else:
            where.append(cond)
        params.append(val)
    _add("ts >= ?", start)
    _add("ts <= ?", end)
    join_clause = ""
    if org_ids is not None:
        join_clause = " JOIN org_members om ON om.user_id = llm_usage_log.user_id"
        if pg:
            where.append(f"om.org_id = ANY(${len(params) + 1})")
            params.append(org_ids)
        else:
            placeholders = ",".join("?" for _ in org_ids)
            where.append(f"om.org_id IN ({placeholders})")
            params.extend(org_ids)
    where_clause = (" WHERE " + " AND ".join(where)) if where else ""
    if pg:
        limit_placeholder = f"${len(params) + 1}"
        sql = (
            f"SELECT COALESCE(user_id,0) as user_id, COUNT(*) as requests, SUM(COALESCE(total_cost_usd,0)) as total_cost_usd "
            f"FROM llm_usage_log{join_clause}{where_clause} GROUP BY COALESCE(user_id,0) ORDER BY total_cost_usd DESC LIMIT {limit_placeholder}"
        )
        rows = await db.fetch(sql, *params, limit)
        return [
            {"user_id": int(r["user_id"] or 0), "requests": int(r["requests"] or 0), "total_cost_usd": float(r["total_cost_usd"] or 0.0)}
            for r in rows
        ]
    sql = (
        f"SELECT IFNULL(user_id,0) as user_id, COUNT(*) as requests, SUM(IFNULL(total_cost_usd,0)) as total_cost_usd "
        f"FROM llm_usage_log{join_clause}{where_clause} GROUP BY IFNULL(user_id,0) ORDER BY total_cost_usd DESC LIMIT ?"
    )
    cur = await db.execute(sql, params + [limit])
    rows = await cur.fetchall()
    return [
        {"user_id": int(r[0] or 0), "requests": int(r[1] or 0), "total_cost_usd": float(r[2] or 0.0)}
        for r in rows
    ]


async def get_usage_daily(
    *,
    principal: AuthPrincipal,
    db,
    user_id: int | None,
    start: str | None,
    end: str | None,
    page: int,
    limit: int,
    org_id: int | None,
) -> UsageDailyResponse:
    try:
        if user_id is not None:
            await admin_scope_service.enforce_admin_user_scope(principal, user_id, require_hierarchy=False)
        org_ids = await admin_scope_service.get_admin_org_ids(principal)
        if org_id is not None:
            org_ids = [org_id] if org_ids is None else [org_id] if org_id in org_ids else []
        rows, total, _ = await fetch_usage_daily(
            db,
            user_id=user_id,
            org_ids=org_ids,
            start=start,
            end=end,
            page=page,
            limit=limit,
        )
        items = [UsageDailyRow(**r) for r in rows]
        return UsageDailyResponse(items=items, total=int(total or 0), page=page, limit=limit)
    except _ADMIN_USAGE_NONCRITICAL_EXCEPTIONS:
        logger.exception("Failed to query usage_daily")
        raise HTTPException(status_code=500, detail="Failed to load usage daily data")


async def get_usage_top(
    *,
    principal: AuthPrincipal,
    db,
    start: str | None,
    end: str | None,
    limit: int,
    metric: str,
    org_id: int | None,
) -> UsageTopResponse:
    try:
        org_ids = await admin_scope_service.get_admin_org_ids(principal)
        if org_id is not None:
            org_ids = [org_id] if org_ids is None else [org_id] if org_id in org_ids else []
        rows = await fetch_usage_top(
            db,
            start=start,
            end=end,
            limit=limit,
            metric=metric,
            org_ids=org_ids,
        )
        for r in rows:
            r.setdefault("bytes_in_total", None)
        return UsageTopResponse(items=[UsageTopRow(**r) for r in rows])
    except _ADMIN_USAGE_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"Failed to query usage top: {exc}")
        raise HTTPException(status_code=500, detail="Failed to load usage top data")


async def run_usage_aggregate(day: str | None) -> dict:
    try:
        await aggregate_usage_daily(day=day)
        return {"status": "ok", "day": day}
    except _ADMIN_USAGE_NONCRITICAL_EXCEPTIONS:
        logger.exception("Manual usage aggregation failed/skipped")
        return {"status": "skipped", "reason": "aggregation failed or was skipped", "day": day}


async def export_usage_daily_csv(
    *,
    principal: AuthPrincipal,
    db,
    user_id: int | None,
    start: str | None,
    end: str | None,
    limit: int,
    org_id: int | None,
) -> tuple[str, str]:
    try:
        if user_id is not None:
            await admin_scope_service.enforce_admin_user_scope(principal, user_id, require_hierarchy=False)
        org_ids = await admin_scope_service.get_admin_org_ids(principal)
        if org_id is not None:
            org_ids = [org_id] if org_ids is None else [org_id] if org_id in org_ids else []
        content = await export_usage_daily_csv_text(
            db,
            user_id=user_id,
            org_ids=org_ids,
            start=start,
            end=end,
            limit=limit,
        )
        _start = start or "all"
        _end = end or "all"
        filename = f"usage_daily_{_start}_{_end}.csv"
        return content, filename
    except _ADMIN_USAGE_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"Failed to export usage daily CSV: {exc}")
        raise HTTPException(status_code=500, detail="Failed to export usage daily CSV")


async def export_usage_top_csv(
    *,
    principal: AuthPrincipal,
    db,
    start: str | None,
    end: str | None,
    limit: int,
    metric: str,
    org_id: int | None,
) -> tuple[str, str]:
    try:
        org_ids = await admin_scope_service.get_admin_org_ids(principal)
        if org_id is not None:
            org_ids = [org_id] if org_ids is None else [org_id] if org_id in org_ids else []
        content = await export_usage_top_csv_text(
            db,
            start=start,
            end=end,
            limit=limit,
            metric=metric,
            org_ids=org_ids,
        )
        _start = start or "all"
        _end = end or "all"
        filename = f"usage_top_{metric}_{_start}_{_end}.csv"
        return content, filename
    except _ADMIN_USAGE_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"Failed to export usage top CSV: {exc}")
        raise HTTPException(status_code=500, detail="Failed to export usage top CSV")


async def run_llm_usage_aggregate(day: str | None) -> dict:
    try:
        await aggregate_llm_usage_daily(day=day)
        return {"status": "ok", "day": day}
    except _ADMIN_USAGE_NONCRITICAL_EXCEPTIONS as exc:
        logger.warning(f"Manual LLM usage aggregation failed/skipped: {exc}")
        return {
            "status": "skipped",
            "reason": "Manual LLM usage aggregation failed or was skipped",
            "day": day,
        }


async def get_llm_usage(
    *,
    principal: AuthPrincipal,
    db,
    user_id: int | None,
    provider: str | None,
    model: str | None,
    operation: str | None,
    status_code: int | None,
    start: str | None,
    end: str | None,
    page: int,
    limit: int,
    org_id: int | None,
) -> LLMUsageLogResponse:
    try:
        if user_id is not None:
            await admin_scope_service.enforce_admin_user_scope(principal, user_id, require_hierarchy=False)
        org_ids = await admin_scope_service.get_admin_org_ids(principal)
        if org_id is not None:
            org_ids = [org_id] if org_ids is None else [org_id] if org_id in org_ids else []
        rows, total = await fetch_llm_usage(
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
            org_ids=org_ids,
        )
        items = [LLMUsageLogRow(**r) for r in rows]
        return LLMUsageLogResponse(items=items, total=int(total or 0), page=page, limit=limit)
    except _ADMIN_USAGE_NONCRITICAL_EXCEPTIONS:
        logger.exception("Failed to query llm_usage_log")
        raise HTTPException(status_code=500, detail="Failed to load LLM usage data")


async def get_llm_usage_summary(
    *,
    principal: AuthPrincipal,
    db,
    start: str | None,
    end: str | None,
    group_by: str,
    org_id: int | None,
) -> LLMUsageSummaryResponse:
    try:
        org_ids = await admin_scope_service.get_admin_org_ids(principal)
        if org_id is not None:
            org_ids = [org_id] if org_ids is None else [org_id] if org_id in org_ids else []
        rows = await fetch_llm_usage_summary(
            db,
            group_by=group_by,
            provider=None,
            start=start,
            end=end,
            org_ids=org_ids,
        )
        return LLMUsageSummaryResponse(items=[LLMUsageSummaryRow(**r) for r in rows])
    except _ADMIN_USAGE_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"Failed to summarize llm_usage_log: {exc}")
        raise HTTPException(status_code=500, detail="Failed to load LLM usage summary")


async def get_llm_top_spenders(
    *,
    principal: AuthPrincipal,
    db,
    start: str | None,
    end: str | None,
    limit: int,
    org_id: int | None,
) -> LLMTopSpendersResponse:
    try:
        org_ids = await admin_scope_service.get_admin_org_ids(principal)
        if org_id is not None:
            org_ids = [org_id] if org_ids is None else [org_id] if org_id in org_ids else []
        rows = await fetch_llm_top_spenders(db, start=start, end=end, limit=limit, org_ids=org_ids)
        return LLMTopSpendersResponse(items=[LLMTopSpenderRow(**r) for r in rows])
    except _ADMIN_USAGE_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"Failed to load llm top spenders: {exc}")
        raise HTTPException(status_code=500, detail="Failed to load LLM top spenders")


async def export_llm_usage_csv(
    *,
    principal: AuthPrincipal,
    db,
    user_id: int | None,
    provider: str | None,
    model: str | None,
    operation: str | None,
    status_code: int | None,
    start: str | None,
    end: str | None,
    limit: int,
    org_id: int | None,
) -> str:
    try:
        if user_id is not None:
            await admin_scope_service.enforce_admin_user_scope(principal, user_id, require_hierarchy=False)
        org_ids = await admin_scope_service.get_admin_org_ids(principal)
        if org_id is not None:
            org_ids = [org_id] if org_ids is None else [org_id] if org_id in org_ids else []
        is_pg = await is_postgres_backend()
        conditions: list[str] = []
        params: list[Any] = []

        def add_cond(sql: str, value):
            if value is None:
                return
            if is_pg:
                conditions.append(sql.replace("?", f"${len(params) + 1}"))
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
        join_clause = ""
        if org_ids is not None:
            join_clause = " JOIN org_members om ON om.user_id = llm_usage_log.user_id"
            if is_pg:
                conditions.append(f"om.org_id = ANY(${len(params) + 1})")
                params.append(org_ids)
            else:
                placeholders = ",".join("?" for _ in org_ids)
                conditions.append(f"om.org_id IN ({placeholders})")
                params.extend(org_ids)
        where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""

        if is_pg:
            limit_placeholder = f"${len(params) + 1}"
            sql = (
                f"SELECT id, ts, COALESCE(user_id,0) as user_id, COALESCE(key_id,0) as key_id, endpoint, operation, provider, model, status, latency_ms, "
                f"COALESCE(prompt_tokens,0), COALESCE(completion_tokens,0), COALESCE(total_tokens,0), COALESCE(total_cost_usd,0), currency, estimated, request_id "
                f"FROM llm_usage_log{join_clause}{where_clause} ORDER BY ts DESC LIMIT {limit_placeholder}"
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
                f"FROM llm_usage_log{join_clause}{where_clause} ORDER BY ts DESC LIMIT ?"
            )
            cur = await db.execute(sql, params + [limit])
            data = await cur.fetchall()

        header = [
            "id","ts","user_id","key_id","endpoint","operation","provider","model","status","latency_ms",
            "prompt_tokens","completion_tokens","total_tokens","total_cost_usd","currency","estimated","request_id"
        ]
        lines = [",".join(header)]

        def _fmt(value):
            if value is None:
                return ""
            s = str(value)
            if "," in s or "\n" in s:
                return '"' + s.replace('"', '""') + '"'
            return s

        for row in data:
            lines.append(",".join(_fmt(c) for c in row))
        return "\n".join(lines) + "\n"
    except _ADMIN_USAGE_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"Failed to export llm usage CSV: {exc}")
        raise HTTPException(status_code=500, detail="Failed to export CSV")
