from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from loguru import logger
from tldw_Server_API.app.core.Metrics import get_metrics_registry
from tldw_Server_API.app.core.AuthNZ.database import is_postgres_backend


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
    user_id: Optional[int],
    start: Optional[str],
    end: Optional[str],
    page: int,
    limit: int,
) -> Tuple[List[Dict[str, Any]], int, bool]:
    """Return (rows, total, has_bytes_in_total). Rows keys: user_id, day, requests, errors, bytes_total, bytes_in_total, latency_avg_ms."""
    offset = (page - 1) * limit
    conditions: List[str] = []
    params: List[Any] = []
    pg = await is_postgres_backend()

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
    where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    if pg:
        total = await db.fetchval(f"SELECT COUNT(*) FROM usage_daily{where_clause}", *params)
        has_in = True
        try:
            sql = (
                f"SELECT user_id, day, requests, errors, bytes_total, COALESCE(bytes_in_total,0) as bytes_in_total, latency_avg_ms "
                f"FROM usage_daily{where_clause} ORDER BY day DESC, user_id ASC LIMIT ${len(params)+1} OFFSET ${len(params)+2}"
            )
            rows = await db.fetch(sql, *params, limit, offset)
        except Exception as e:
            logger.debug(f"usage_daily: falling back without bytes_in_total (pg): {e}")
            try:
                get_metrics_registry().increment(
                    "app_warning_events_total",
                    labels={"component": "admin_usage", "event": "daily_bytes_in_missing_fallback"},
                )
            except Exception:
                logger.debug("metrics increment failed for daily_bytes_in_missing_fallback")
            has_in = False
            sql = (
                f"SELECT user_id, day, requests, errors, bytes_total, latency_avg_ms "
                f"FROM usage_daily{where_clause} ORDER BY day DESC, user_id ASC LIMIT ${len(params)+1} OFFSET ${len(params)+2}"
            )
            rows = await db.fetch(sql, *params, limit, offset)
        # Normalize
        out: List[Dict[str, Any]] = []
        for r in rows:
            # asyncpg.Record supports dict(), sqlite rows don't reliably;
            # build a name-keyed dict defensively.
            try:
                d = dict(r)
            except Exception:
                d = {k: r[k] for k in r.keys()} if hasattr(r, "keys") else {}
            if not has_in:
                d.setdefault("bytes_in_total", None)
            out.append(d)
        return out, int(total or 0), has_in
    # SQLite
    # Prefer pool-style helpers when available (e.g., DatabasePool in tests)
    if hasattr(db, "fetchval"):
        total = int(
            (await db.fetchval(f"SELECT COUNT(*) FROM usage_daily{where_clause}", params))
            or 0
        )
    else:
        cur = await db.execute(f"SELECT COUNT(*) FROM usage_daily{where_clause}", params)
        total_row = await cur.fetchone()
        total = int(total_row[0] if total_row else 0)
    has_in = True
    try:
        sql = (
            f"SELECT user_id, day, requests, errors, bytes_total, IFNULL(bytes_in_total,0) as bytes_in_total, latency_avg_ms "
            f"FROM usage_daily{where_clause} ORDER BY day DESC, user_id ASC LIMIT ? OFFSET ?"
        )
        if hasattr(db, "fetchall"):
            rows = await db.fetchall(sql, params + [limit, offset])
        else:
            cur = await db.execute(sql, params + [limit, offset])
            rows = await cur.fetchall()
    except Exception as e:
        logger.debug(f"usage_daily: falling back without bytes_in_total (sqlite): {e}")
        try:
            get_metrics_registry().increment(
                "app_warning_events_total",
                labels={"component": "admin_usage", "event": "daily_bytes_in_missing_fallback"},
            )
        except Exception:
            logger.debug("metrics increment failed for daily_bytes_in_missing_fallback")
        has_in = False
        sql = (
            f"SELECT user_id, day, requests, errors, bytes_total, latency_avg_ms "
            f"FROM usage_daily{where_clause} ORDER BY day DESC, user_id ASC LIMIT ? OFFSET ?"
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


async def export_usage_daily_csv_text(db, *, user_id: Optional[int], start: Optional[str], end: Optional[str], limit: int) -> str:
    rows, _, has_in = await fetch_usage_daily(db, user_id=user_id, start=start, end=end, page=1, limit=limit)
    header = ["user_id","day","requests","errors","bytes_total","bytes_in_total","latency_avg_ms"]
    lines = [",".join(header)]
    for r in rows:
        row = [r.get("user_id"), r.get("day"), r.get("requests"), r.get("errors"), r.get("bytes_total"), (r.get("bytes_in_total") if has_in else None), r.get("latency_avg_ms")]
        lines.append(",".join(_fmt_csv_value(c) for c in row))
    return "\n".join(lines) + "\n"


async def fetch_usage_top(
    db,
    *,
    start: Optional[str],
    end: Optional[str],
    limit: int,
    metric: str,
) -> List[Dict[str, Any]]:
    pg = await is_postgres_backend()
    conditions: List[str] = []
    params: List[Any] = []
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
                f"SELECT user_id, SUM(requests) AS requests, SUM(errors) AS errors, SUM(bytes_total) AS bytes_total, COALESCE(SUM(bytes_in_total),0) AS bytes_in_total, AVG(latency_avg_ms)::float AS latency_avg_ms FROM usage_daily{where_clause} GROUP BY user_id ORDER BY {order_by} LIMIT $ {len(params) + 1}"
            ).replace('$ ', '$')
            rows = await db.fetch(sql, *params, limit)
        except Exception as e:
            logger.debug(f"usage_top: falling back without bytes_in_total (pg): {e}")
            try:
                get_metrics_registry().increment(
                    "app_warning_events_total",
                    labels={"component": "admin_usage", "event": "top_bytes_in_missing_fallback"},
                )
            except Exception:
                logger.debug("metrics increment failed for top_bytes_in_missing_fallback")
            sql = (
                f"SELECT user_id, SUM(requests) AS requests, SUM(errors) AS errors, SUM(bytes_total) AS bytes_total, AVG(latency_avg_ms)::float AS latency_avg_ms FROM usage_daily{where_clause} GROUP BY user_id ORDER BY {order_by} LIMIT $ {len(params) + 1}"
            ).replace('$ ', '$')
            rows = await db.fetch(sql, *params, limit)
        return [dict(r) for r in rows]
    # SQLite
    try:
        sql = (
            f"SELECT user_id, SUM(requests) AS requests, SUM(errors) AS errors, SUM(bytes_total) AS bytes_total, IFNULL(SUM(bytes_in_total),0) AS bytes_in_total, AVG(latency_avg_ms) AS latency_avg_ms FROM usage_daily{where_clause} GROUP BY user_id ORDER BY {order_by} LIMIT ?"
        )
        if hasattr(db, "fetchall"):
            rows = await db.fetchall(sql, params + [limit])
        else:
            cur = await db.execute(sql, params + [limit])
            rows = await cur.fetchall()
        out_rows: List[Dict[str, Any]] = []
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
    except Exception as e:
        logger.debug(f"usage_top: falling back without bytes_in_total (sqlite): {e}")
        try:
            get_metrics_registry().increment(
                "app_warning_events_total",
                labels={"component": "admin_usage", "event": "top_bytes_in_missing_fallback"},
            )
        except Exception:
            logger.debug("metrics increment failed for top_bytes_in_missing_fallback")
        sql = (
            f"SELECT user_id, SUM(requests) AS requests, SUM(errors) AS errors, SUM(bytes_total) AS bytes_total, AVG(latency_avg_ms) AS latency_avg_ms FROM usage_daily{where_clause} GROUP BY user_id ORDER BY {order_by} LIMIT ?"
        )
        if hasattr(db, "fetchall"):
            rows = await db.fetchall(sql, params + [limit])
        else:
            cur = await db.execute(sql, params + [limit])
            rows = await cur.fetchall()
        out_rows: List[Dict[str, Any]] = []
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


async def export_usage_top_csv_text(db, *, start: Optional[str], end: Optional[str], limit: int, metric: str) -> str:
    rows = await fetch_usage_top(db, start=start, end=end, limit=limit, metric=metric)
    header = ["user_id","requests","errors","bytes_total","bytes_in_total","latency_avg_ms"]
    out = [",".join(header)]
    for r in rows:
        out.append(",".join(_fmt_csv_value(r.get(k)) for k in ["user_id","requests","errors","bytes_total","bytes_in_total","latency_avg_ms"]))
    return "\n".join(out) + "\n"


async def fetch_llm_usage(
    db,
    *,
    user_id: Optional[int],
    provider: Optional[str],
    model: Optional[str],
    operation: Optional[str],
    status_code: Optional[int],
    start: Optional[str],
    end: Optional[str],
    page: int,
    limit: int,
) -> Tuple[List[Dict[str, Any]], int]:
    offset = (page - 1) * limit
    pg = await is_postgres_backend()
    conditions: List[str] = []
    params: List[Any] = []

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
    where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    if pg:
        total = await db.fetchval(f"SELECT COUNT(*) FROM llm_usage_log{where_clause}", *params)
        data_sql = (
            f"SELECT id, ts, user_id, key_id, endpoint, operation, provider, model, status, latency_ms, prompt_tokens, completion_tokens, total_tokens, total_cost_usd, currency, estimated, request_id FROM llm_usage_log{where_clause} ORDER BY ts DESC LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}"
        )
        rows = await db.fetch(data_sql, *params, limit, offset)
        return [dict(r) for r in rows], int(total or 0)

    # SQLite
    cur = await db.execute(f"SELECT COUNT(*) FROM llm_usage_log{where_clause}", params)
    total_row = await cur.fetchone()
    total = int(total_row[0] if total_row else 0)
    data_sql = (
        f"SELECT id, ts, user_id, key_id, endpoint, operation, provider, model, status, latency_ms, prompt_tokens, completion_tokens, total_tokens, total_cost_usd, currency, estimated, request_id FROM llm_usage_log{where_clause} ORDER BY ts DESC LIMIT ? OFFSET ?"
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
    provider: Optional[str],
    start: Optional[str],
    end: Optional[str],
) -> List[Dict[str, Any]]:
    """Summarize llm_usage_log grouped by a key.

    group_by: one of user|operation|day|endpoint|provider|model|status
    """
    pg = await is_postgres_backend()
    params: List[Any] = []
    where: List[str] = []
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
            f"FROM llm_usage_log{where_clause} GROUP BY {key_expr} ORDER BY requests DESC"
        )
        rows = await db.fetch(sql, *params)
        out: List[Dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            try:
                d["group_value"] = str(d.get("group_value", ""))
            except Exception:
                d["group_value"] = str(d.get("group_value"))
            out.append(d)
        return out
    # SQLite
    sql = (
        f"SELECT {key_expr} as group_value, "
        "COUNT(*) as requests, SUM(CASE WHEN status >= 400 THEN 1 ELSE 0 END) as errors, "
        "SUM(IFNULL(prompt_tokens,0)) as input_tokens, SUM(IFNULL(completion_tokens,0)) as output_tokens, "
        "SUM(IFNULL(total_tokens,0)) as total_tokens, SUM(IFNULL(total_cost_usd,0)) as total_cost_usd, AVG(latency_ms) as latency_avg_ms "
        f"FROM llm_usage_log{where_clause} GROUP BY {key_expr} ORDER BY requests DESC"
    )
    cur = await db.execute(sql, params)
    rows = await cur.fetchall()
    out_rows: List[Dict[str, Any]] = []
    for r in rows:
        gv = r[0]
        try:
            gv_str = str(gv)
        except Exception:
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


async def fetch_llm_top_spenders(db, *, start: Optional[str], end: Optional[str], limit: int) -> List[Dict[str, Any]]:
    pg = await is_postgres_backend()
    params: List[Any] = []
    where: List[str] = []
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
    where_clause = (" WHERE " + " AND ".join(where)) if where else ""
    if pg:
        limit_placeholder = f"${len(params) + 1}"
        sql = (
            f"SELECT COALESCE(user_id,0) as user_id, COUNT(*) as requests, SUM(COALESCE(total_cost_usd,0)) as total_cost_usd "
            f"FROM llm_usage_log{where_clause} GROUP BY COALESCE(user_id,0) ORDER BY total_cost_usd DESC LIMIT {limit_placeholder}"
        )
        rows = await db.fetch(sql, *params, limit)
        return [
            {"user_id": int(r["user_id"] or 0), "requests": int(r["requests"] or 0), "total_cost_usd": float(r["total_cost_usd"] or 0.0)}
            for r in rows
        ]
    sql = (
        f"SELECT IFNULL(user_id,0) as user_id, COUNT(*) as requests, SUM(IFNULL(total_cost_usd,0)) as total_cost_usd "
        f"FROM llm_usage_log{where_clause} GROUP BY IFNULL(user_id,0) ORDER BY total_cost_usd DESC LIMIT ?"
    )
    cur = await db.execute(sql, params + [limit])
    rows = await cur.fetchall()
    return [
        {"user_id": int(r[0] or 0), "requests": int(r[1] or 0), "total_cost_usd": float(r[2] or 0.0)}
        for r in rows
    ]
