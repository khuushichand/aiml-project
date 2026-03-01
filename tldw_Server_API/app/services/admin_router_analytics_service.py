from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from loguru import logger

from tldw_Server_API.app.api.v1.schemas.admin_schemas import (
    RouterAnalyticsBreakdownRow,
    RouterAnalyticsBreakdownsResponse,
    RouterAnalyticsDataWindow,
    RouterAnalyticsGranularity,
    RouterAnalyticsMetaOption,
    RouterAnalyticsMetaResponse,
    RouterAnalyticsRange,
    RouterAnalyticsSeriesPoint,
    RouterAnalyticsStatusKpis,
    RouterAnalyticsStatusResponse,
)
from tldw_Server_API.app.core.AuthNZ.database import DatabasePool
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.services import admin_scope_service

_ADMIN_ROUTER_ANALYTICS_NONCRITICAL_EXCEPTIONS = (
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

_RANGE_TO_DELTA: dict[RouterAnalyticsRange, timedelta] = {
    "realtime": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "8h": timedelta(hours=8),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}

_DEFAULT_GRANULARITY_BY_RANGE: dict[RouterAnalyticsRange, RouterAnalyticsGranularity] = {
    "realtime": "1m",
    "1h": "1m",
    "8h": "5m",
    "24h": "15m",
    "7d": "1h",
    "30d": "1h",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _is_db_pool_object(db: Any) -> bool:
    return isinstance(db, DatabasePool)


def _is_postgres_connection(db: Any) -> bool:
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


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value or default)
    except _ADMIN_ROUTER_ANALYTICS_NONCRITICAL_EXCEPTIONS:
        return default


def _as_float(value: Any, default: float | None = 0.0) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except _ADMIN_ROUTER_ANALYTICS_NONCRITICAL_EXCEPTIONS:
        return default


def _as_text(value: Any, default: str = "unknown") -> str:
    if value is None:
        return default
    try:
        text = str(value).strip()
    except _ADMIN_ROUTER_ANALYTICS_NONCRITICAL_EXCEPTIONS:
        return default
    return text or default


def _row_value(row: Any, key: str, index: int, default: Any = None) -> Any:
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    if hasattr(row, "keys"):
        try:
            return row[key]
        except _ADMIN_ROUTER_ANALYTICS_NONCRITICAL_EXCEPTIONS:
            pass
    try:
        return row[index]
    except _ADMIN_ROUTER_ANALYTICS_NONCRITICAL_EXCEPTIONS:
        return default


def _coerce_utc_datetime(raw: Any, *, fallback: datetime) -> datetime:
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=timezone.utc)
        return raw.astimezone(timezone.utc)

    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return fallback
        normalized = text.replace("Z", "+00:00")
        if " " in normalized and "T" not in normalized:
            normalized = normalized.replace(" ", "T")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return fallback
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    return fallback


def _resolve_window(range_value: RouterAnalyticsRange) -> tuple[datetime, datetime]:
    end = _utcnow().astimezone(timezone.utc)
    start = end - _RANGE_TO_DELTA[range_value]
    return start, end


def _resolve_granularity(
    range_value: RouterAnalyticsRange,
    granularity: RouterAnalyticsGranularity | None,
) -> RouterAnalyticsGranularity:
    if granularity is not None:
        return granularity
    return _DEFAULT_GRANULARITY_BY_RANGE[range_value]


def _to_db_ts(dt: datetime, *, is_pg: bool) -> Any:
    utc_dt = dt.astimezone(timezone.utc)
    if is_pg:
        return utc_dt.replace(tzinfo=None)
    return utc_dt.strftime("%Y-%m-%d %H:%M:%S")


def _bucket_expression(*, is_pg: bool, granularity: RouterAnalyticsGranularity) -> str:
    if is_pg:
        if granularity == "1m":
            return "date_trunc('minute', ts AT TIME ZONE 'UTC')"
        if granularity == "5m":
            return "(to_timestamp(floor(extract(epoch from (ts AT TIME ZONE 'UTC')) / 300) * 300) AT TIME ZONE 'UTC')"
        if granularity == "15m":
            return "(to_timestamp(floor(extract(epoch from (ts AT TIME ZONE 'UTC')) / 900) * 900) AT TIME ZONE 'UTC')"
        return "date_trunc('hour', ts AT TIME ZONE 'UTC')"

    if granularity == "1m":
        return "strftime('%Y-%m-%d %H:%M:00', ts, 'utc')"
    if granularity == "5m":
        return "datetime((CAST(strftime('%s', ts, 'utc') AS INTEGER) / 300) * 300, 'unixepoch')"
    if granularity == "15m":
        return "datetime((CAST(strftime('%s', ts, 'utc') AS INTEGER) / 900) * 900, 'unixepoch')"
    return "strftime('%Y-%m-%d %H:00:00', ts, 'utc')"


async def _fetch_rows(db: Any, sql: str, params: list[Any]) -> list[Any]:
    if callable(getattr(db, "fetch", None)):
        return await db.fetch(sql, *params)
    cur = await db.execute(sql, params)
    return await cur.fetchall()


async def _fetch_value(db: Any, sql: str, params: list[Any]) -> Any:
    if callable(getattr(db, "fetchval", None)):
        return await db.fetchval(sql, *params)
    cur = await db.execute(sql, params)
    row = await cur.fetchone()
    return row[0] if row else None


async def _resolve_admin_org_scope(principal: AuthPrincipal, org_id: int | None) -> list[int] | None:
    org_ids = await admin_scope_service.get_admin_org_ids(principal)
    if org_id is not None:
        org_ids = [org_id] if org_ids is None else [org_id] if org_id in org_ids else []
    return org_ids


def _build_usage_where_clause(
    *,
    is_pg: bool,
    start: datetime,
    end: datetime,
    provider: str | None,
    model: str | None,
    token_id: int | None,
    org_ids: list[int] | None,
) -> tuple[str, str, list[Any]]:
    conditions: list[str] = []
    params: list[Any] = []

    if is_pg:
        conditions.append(f"ts >= ${len(params) + 1}")
        params.append(_to_db_ts(start, is_pg=True))
        conditions.append(f"ts <= ${len(params) + 1}")
        params.append(_to_db_ts(end, is_pg=True))
    else:
        conditions.append("datetime(ts) >= datetime(?)")
        params.append(_to_db_ts(start, is_pg=False))
        conditions.append("datetime(ts) <= datetime(?)")
        params.append(_to_db_ts(end, is_pg=False))

    if provider is not None and provider.strip():
        if is_pg:
            conditions.append(f"LOWER(provider) = LOWER(${len(params) + 1})")
        else:
            conditions.append("LOWER(provider) = LOWER(?)")
        params.append(provider.strip())

    if model is not None and model.strip():
        if is_pg:
            conditions.append(f"LOWER(model) = LOWER(${len(params) + 1})")
        else:
            conditions.append("LOWER(model) = LOWER(?)")
        params.append(model.strip())

    if token_id is not None:
        if is_pg:
            conditions.append(f"key_id = ${len(params) + 1}")
        else:
            conditions.append("key_id = ?")
        params.append(int(token_id))

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

    where_clause = " WHERE " + " AND ".join(conditions)
    return join_clause, where_clause, params


def _build_status_data_window(
    *,
    range_value: RouterAnalyticsRange,
    start: datetime,
    end: datetime,
) -> RouterAnalyticsDataWindow:
    return RouterAnalyticsDataWindow(start=start, end=end, range=range_value)


async def get_router_analytics_status(
    *,
    principal: AuthPrincipal,
    db: Any,
    range_value: RouterAnalyticsRange,
    org_id: int | None,
    provider: str | None,
    model: str | None,
    token_id: int | None,
    granularity: RouterAnalyticsGranularity | None,
) -> RouterAnalyticsStatusResponse:
    try:
        org_ids = await _resolve_admin_org_scope(principal, org_id)
        window_start, window_end = _resolve_window(range_value)
        data_window = _build_status_data_window(range_value=range_value, start=window_start, end=window_end)
        generated_at = _utcnow()

        if org_ids is not None and len(org_ids) == 0:
            return RouterAnalyticsStatusResponse(
                kpis=RouterAnalyticsStatusKpis(),
                series=[],
                providers_available=0,
                providers_online=0,
                generated_at=generated_at,
                data_window=data_window,
            )

        is_pg = _is_postgres_connection(db)
        _, _ = _resolve_granularity(range_value, granularity), granularity
        join_clause, where_clause, params = _build_usage_where_clause(
            is_pg=is_pg,
            start=window_start,
            end=window_end,
            provider=provider,
            model=model,
            token_id=token_id,
            org_ids=org_ids,
        )

        if is_pg:
            kpi_sql = (  # nosec B608
                "SELECT "  # nosec B608
                "COUNT(*) AS requests, "
                "COALESCE(SUM(prompt_tokens),0) AS prompt_tokens, "
                "COALESCE(SUM(completion_tokens),0) AS generated_tokens, "
                "COALESCE(SUM(total_tokens),0) AS total_tokens, "
                "AVG(latency_ms)::float AS avg_latency_ms, "
                "COALESCE(SUM(CASE WHEN latency_ms > 0 THEN completion_tokens ELSE 0 END),0) AS gen_tokens_for_rate, "
                "COALESCE(SUM(CASE WHEN latency_ms > 0 THEN latency_ms ELSE 0 END),0) AS latency_ms_for_rate "
                f"FROM llm_usage_log{join_clause}{where_clause}"
            )
            provider_summary_sql = (  # nosec B608
                "SELECT "  # nosec B608
                "COUNT(DISTINCT COALESCE(NULLIF(TRIM(provider), ''), 'unknown')) AS providers_available, "
                "COUNT(DISTINCT CASE WHEN status < 500 THEN COALESCE(NULLIF(TRIM(provider), ''), 'unknown') END) AS providers_online "
                f"FROM llm_usage_log{join_clause}{where_clause}"
            )
        else:
            kpi_sql = (  # nosec B608
                "SELECT "  # nosec B608
                "COUNT(*) AS requests, "
                "IFNULL(SUM(prompt_tokens),0) AS prompt_tokens, "
                "IFNULL(SUM(completion_tokens),0) AS generated_tokens, "
                "IFNULL(SUM(total_tokens),0) AS total_tokens, "
                "AVG(latency_ms) AS avg_latency_ms, "
                "IFNULL(SUM(CASE WHEN latency_ms > 0 THEN completion_tokens ELSE 0 END),0) AS gen_tokens_for_rate, "
                "IFNULL(SUM(CASE WHEN latency_ms > 0 THEN latency_ms ELSE 0 END),0) AS latency_ms_for_rate "
                f"FROM llm_usage_log{join_clause}{where_clause}"
            )
            provider_summary_sql = (  # nosec B608
                "SELECT "  # nosec B608
                "COUNT(DISTINCT COALESCE(NULLIF(TRIM(provider), ''), 'unknown')) AS providers_available, "
                "COUNT(DISTINCT CASE WHEN status < 500 THEN COALESCE(NULLIF(TRIM(provider), ''), 'unknown') END) AS providers_online "
                f"FROM llm_usage_log{join_clause}{where_clause}"
            )

        kpi_rows = await _fetch_rows(db, kpi_sql, params)
        kpi_row = kpi_rows[0] if kpi_rows else None

        requests = _as_int(_row_value(kpi_row, "requests", 0, 0))
        prompt_tokens = _as_int(_row_value(kpi_row, "prompt_tokens", 1, 0))
        generated_tokens = _as_int(_row_value(kpi_row, "generated_tokens", 2, 0))
        total_tokens = _as_int(_row_value(kpi_row, "total_tokens", 3, 0))
        avg_latency_ms = _as_float(_row_value(kpi_row, "avg_latency_ms", 4, None), None)
        gen_tokens_for_rate = _as_float(_row_value(kpi_row, "gen_tokens_for_rate", 5, 0.0), 0.0) or 0.0
        latency_ms_for_rate = _as_float(_row_value(kpi_row, "latency_ms_for_rate", 6, 0.0), 0.0) or 0.0

        avg_gen_toks_per_s: float | None
        if latency_ms_for_rate > 0:
            avg_gen_toks_per_s = float(gen_tokens_for_rate) / (float(latency_ms_for_rate) / 1000.0)
        else:
            avg_gen_toks_per_s = None

        summary_rows = await _fetch_rows(db, provider_summary_sql, params)
        summary_row = summary_rows[0] if summary_rows else None
        providers_available = _as_int(_row_value(summary_row, "providers_available", 0, 0))
        providers_online = _as_int(_row_value(summary_row, "providers_online", 1, 0))

        resolved_granularity = _resolve_granularity(range_value, granularity)
        bucket_expr = _bucket_expression(is_pg=is_pg, granularity=resolved_granularity)

        if is_pg:
            series_sql = (
                f"SELECT {bucket_expr} AS bucket_ts, "  # nosec B608
                "COALESCE(NULLIF(TRIM(provider), ''), 'unknown') AS provider, "
                "COALESCE(NULLIF(TRIM(model), ''), 'unknown') AS model, "
                "COUNT(*) AS requests, "
                "COALESCE(SUM(prompt_tokens),0) AS prompt_tokens, "
                "COALESCE(SUM(completion_tokens),0) AS completion_tokens, "
                "COALESCE(SUM(total_tokens),0) AS total_tokens, "
                "AVG(latency_ms)::float AS avg_latency_ms "
                f"FROM llm_usage_log{join_clause}{where_clause} "
                "GROUP BY 1,2,3 ORDER BY 1 ASC, 4 DESC"
            )
        else:
            series_sql = (
                f"SELECT {bucket_expr} AS bucket_ts, "  # nosec B608
                "COALESCE(NULLIF(TRIM(provider), ''), 'unknown') AS provider, "
                "COALESCE(NULLIF(TRIM(model), ''), 'unknown') AS model, "
                "COUNT(*) AS requests, "
                "IFNULL(SUM(prompt_tokens),0) AS prompt_tokens, "
                "IFNULL(SUM(completion_tokens),0) AS completion_tokens, "
                "IFNULL(SUM(total_tokens),0) AS total_tokens, "
                "AVG(latency_ms) AS avg_latency_ms "
                f"FROM llm_usage_log{join_clause}{where_clause} "
                "GROUP BY 1,2,3 ORDER BY 1 ASC, 4 DESC"
            )

        series_rows = await _fetch_rows(db, series_sql, params)
        series: list[RouterAnalyticsSeriesPoint] = []
        for row in series_rows:
            bucket_raw = _row_value(row, "bucket_ts", 0)
            bucket_ts = _coerce_utc_datetime(bucket_raw, fallback=window_start)
            series.append(
                RouterAnalyticsSeriesPoint(
                    ts=bucket_ts,
                    provider=_as_text(_row_value(row, "provider", 1, "unknown")),
                    model=_as_text(_row_value(row, "model", 2, "unknown")),
                    requests=_as_int(_row_value(row, "requests", 3, 0)),
                    prompt_tokens=_as_int(_row_value(row, "prompt_tokens", 4, 0)),
                    completion_tokens=_as_int(_row_value(row, "completion_tokens", 5, 0)),
                    total_tokens=_as_int(_row_value(row, "total_tokens", 6, 0)),
                    avg_latency_ms=_as_float(_row_value(row, "avg_latency_ms", 7, None), None),
                )
            )

        return RouterAnalyticsStatusResponse(
            kpis=RouterAnalyticsStatusKpis(
                requests=requests,
                prompt_tokens=prompt_tokens,
                generated_tokens=generated_tokens,
                total_tokens=total_tokens,
                avg_latency_ms=avg_latency_ms,
                avg_gen_toks_per_s=avg_gen_toks_per_s,
            ),
            series=series,
            providers_available=providers_available,
            providers_online=providers_online,
            generated_at=generated_at,
            data_window=data_window,
        )
    except _ADMIN_ROUTER_ANALYTICS_NONCRITICAL_EXCEPTIONS:
        logger.exception("Failed to build router analytics status payload")
        raise HTTPException(status_code=500, detail="Failed to load router analytics status") from None


async def _fetch_breakdown_rows(
    *,
    db: Any,
    is_pg: bool,
    join_clause: str,
    where_clause: str,
    params: list[Any],
    dimension_expr: str,
    dimension_name: str,
    limit: int,
) -> list[RouterAnalyticsBreakdownRow]:
    if is_pg:
        limit_placeholder = f"${len(params) + 1}"
        sql = (
            f"SELECT {dimension_expr} AS key, "  # nosec B608
            "COUNT(*) AS requests, "
            "COALESCE(SUM(prompt_tokens),0) AS prompt_tokens, "
            "COALESCE(SUM(completion_tokens),0) AS completion_tokens, "
            "COALESCE(SUM(total_tokens),0) AS total_tokens, "
            "SUM(CASE WHEN status >= 400 THEN 1 ELSE 0 END) AS errors, "
            "AVG(latency_ms)::float AS avg_latency_ms "
            f"FROM llm_usage_log{join_clause}{where_clause} "
            "GROUP BY 1 ORDER BY requests DESC, key ASC "
            f"LIMIT {limit_placeholder}"
        )
    else:
        sql = (
            f"SELECT {dimension_expr} AS key, "  # nosec B608
            "COUNT(*) AS requests, "
            "IFNULL(SUM(prompt_tokens),0) AS prompt_tokens, "
            "IFNULL(SUM(completion_tokens),0) AS completion_tokens, "
            "IFNULL(SUM(total_tokens),0) AS total_tokens, "
            "SUM(CASE WHEN status >= 400 THEN 1 ELSE 0 END) AS errors, "
            "AVG(latency_ms) AS avg_latency_ms "
            f"FROM llm_usage_log{join_clause}{where_clause} "
            "GROUP BY 1 ORDER BY requests DESC, key ASC LIMIT ?"
        )

    try:
        rows = await _fetch_rows(db, sql, [*params, limit])
    except _ADMIN_ROUTER_ANALYTICS_NONCRITICAL_EXCEPTIONS as exc:
        logger.debug(
            "Router analytics breakdown fallback for %s due to query error: %s",
            dimension_name,
            exc,
        )
        if is_pg:
            fallback_sql = (  # nosec B608
                "SELECT "  # nosec B608
                "COUNT(*) AS requests, "
                "COALESCE(SUM(prompt_tokens),0) AS prompt_tokens, "
                "COALESCE(SUM(completion_tokens),0) AS completion_tokens, "
                "COALESCE(SUM(total_tokens),0) AS total_tokens, "
                "SUM(CASE WHEN status >= 400 THEN 1 ELSE 0 END) AS errors, "
                "AVG(latency_ms)::float AS avg_latency_ms "
                f"FROM llm_usage_log{join_clause}{where_clause}"
            )
        else:
            fallback_sql = (  # nosec B608
                "SELECT "  # nosec B608
                "COUNT(*) AS requests, "
                "IFNULL(SUM(prompt_tokens),0) AS prompt_tokens, "
                "IFNULL(SUM(completion_tokens),0) AS completion_tokens, "
                "IFNULL(SUM(total_tokens),0) AS total_tokens, "
                "SUM(CASE WHEN status >= 400 THEN 1 ELSE 0 END) AS errors, "
                "AVG(latency_ms) AS avg_latency_ms "
                f"FROM llm_usage_log{join_clause}{where_clause}"
            )
        fallback_rows = await _fetch_rows(db, fallback_sql, params)
        fallback_row = fallback_rows[0] if fallback_rows else None
        fallback_requests = _as_int(_row_value(fallback_row, "requests", 0, 0))
        if fallback_requests <= 0:
            return []
        return [
            RouterAnalyticsBreakdownRow(
                key="unknown",
                label="unknown",
                requests=fallback_requests,
                prompt_tokens=_as_int(_row_value(fallback_row, "prompt_tokens", 1, 0)),
                completion_tokens=_as_int(_row_value(fallback_row, "completion_tokens", 2, 0)),
                total_tokens=_as_int(_row_value(fallback_row, "total_tokens", 3, 0)),
                errors=_as_int(_row_value(fallback_row, "errors", 4, 0)),
                avg_latency_ms=_as_float(_row_value(fallback_row, "avg_latency_ms", 5, None), None),
            )
        ]

    out: list[RouterAnalyticsBreakdownRow] = []
    for row in rows:
        out.append(
            RouterAnalyticsBreakdownRow(
                key=_as_text(_row_value(row, "key", 0, "unknown")),
                label=_as_text(_row_value(row, "key", 0, "unknown")),
                requests=_as_int(_row_value(row, "requests", 1, 0)),
                prompt_tokens=_as_int(_row_value(row, "prompt_tokens", 2, 0)),
                completion_tokens=_as_int(_row_value(row, "completion_tokens", 3, 0)),
                total_tokens=_as_int(_row_value(row, "total_tokens", 4, 0)),
                errors=_as_int(_row_value(row, "errors", 5, 0)),
                avg_latency_ms=_as_float(_row_value(row, "avg_latency_ms", 6, None), None),
            )
        )
    return out


async def get_router_analytics_status_breakdowns(
    *,
    principal: AuthPrincipal,
    db: Any,
    range_value: RouterAnalyticsRange,
    org_id: int | None,
    provider: str | None,
    model: str | None,
    token_id: int | None,
    granularity: RouterAnalyticsGranularity | None,
) -> RouterAnalyticsBreakdownsResponse:
    _ = granularity  # reserved for future per-breakdown bucketing variants
    try:
        org_ids = await _resolve_admin_org_scope(principal, org_id)
        window_start, window_end = _resolve_window(range_value)
        data_window = _build_status_data_window(range_value=range_value, start=window_start, end=window_end)
        generated_at = _utcnow()

        if org_ids is not None and len(org_ids) == 0:
            return RouterAnalyticsBreakdownsResponse(
                providers=[],
                models=[],
                token_names=[],
                remote_ips=[],
                user_agents=[],
                generated_at=generated_at,
                data_window=data_window,
            )

        is_pg = _is_postgres_connection(db)
        join_clause, where_clause, params = _build_usage_where_clause(
            is_pg=is_pg,
            start=window_start,
            end=window_end,
            provider=provider,
            model=model,
            token_id=token_id,
            org_ids=org_ids,
        )

        dimensions: dict[str, str] = {
            "providers": "COALESCE(NULLIF(TRIM(provider), ''), 'unknown')",
            "models": "COALESCE(NULLIF(TRIM(model), ''), 'unknown')",
            "token_names": "COALESCE(NULLIF(TRIM(token_name), ''), 'unknown')",  # nosec B105
            "remote_ips": "COALESCE(NULLIF(TRIM(remote_ip), ''), 'unknown')",
            "user_agents": "COALESCE(NULLIF(TRIM(user_agent), ''), 'unknown')",
        }

        providers = await _fetch_breakdown_rows(
            db=db,
            is_pg=is_pg,
            join_clause=join_clause,
            where_clause=where_clause,
            params=params,
            dimension_expr=dimensions["providers"],
            dimension_name="providers",
            limit=50,
        )
        models = await _fetch_breakdown_rows(
            db=db,
            is_pg=is_pg,
            join_clause=join_clause,
            where_clause=where_clause,
            params=params,
            dimension_expr=dimensions["models"],
            dimension_name="models",
            limit=50,
        )
        token_names = await _fetch_breakdown_rows(
            db=db,
            is_pg=is_pg,
            join_clause=join_clause,
            where_clause=where_clause,
            params=params,
            dimension_expr=dimensions["token_names"],
            dimension_name="token_names",
            limit=50,
        )
        remote_ips = await _fetch_breakdown_rows(
            db=db,
            is_pg=is_pg,
            join_clause=join_clause,
            where_clause=where_clause,
            params=params,
            dimension_expr=dimensions["remote_ips"],
            dimension_name="remote_ips",
            limit=50,
        )
        user_agents = await _fetch_breakdown_rows(
            db=db,
            is_pg=is_pg,
            join_clause=join_clause,
            where_clause=where_clause,
            params=params,
            dimension_expr=dimensions["user_agents"],
            dimension_name="user_agents",
            limit=50,
        )

        return RouterAnalyticsBreakdownsResponse(
            providers=providers,
            models=models,
            token_names=token_names,
            remote_ips=remote_ips,
            user_agents=user_agents,
            generated_at=generated_at,
            data_window=data_window,
        )
    except _ADMIN_ROUTER_ANALYTICS_NONCRITICAL_EXCEPTIONS:
        logger.exception("Failed to build router analytics breakdowns payload")
        raise HTTPException(status_code=500, detail="Failed to load router analytics breakdowns") from None


async def _fetch_distinct_dimension_values(
    *,
    db: Any,
    is_pg: bool,
    dimension_expr: str,
    join_clause: str,
    where_clause: str,
    params: list[Any],
) -> list[str]:
    if is_pg:
        limit_placeholder = f"${len(params) + 1}"
        sql = (
            f"SELECT DISTINCT {dimension_expr} AS value "  # nosec B608
            f"FROM llm_usage_log{join_clause}{where_clause} "
            "ORDER BY value ASC "
            f"LIMIT {limit_placeholder}"
        )
    else:
        sql = (
            f"SELECT DISTINCT {dimension_expr} AS value "  # nosec B608
            f"FROM llm_usage_log{join_clause}{where_clause} "
            "ORDER BY value ASC LIMIT ?"
        )

    rows = await _fetch_rows(db, sql, [*params, 500])
    values: list[str] = []
    for row in rows:
        values.append(_as_text(_row_value(row, "value", 0, "unknown")))
    return values


async def get_router_analytics_meta(
    *,
    principal: AuthPrincipal,
    db: Any,
    org_id: int | None = None,
) -> RouterAnalyticsMetaResponse:
    try:
        org_ids = await _resolve_admin_org_scope(principal, org_id)
        generated_at = _utcnow()

        if org_ids is not None and len(org_ids) == 0:
            return RouterAnalyticsMetaResponse(generated_at=generated_at)

        is_pg = _is_postgres_connection(db)
        join_clause = ""
        where_clause = ""
        params: list[Any] = []

        if org_ids is not None:
            join_clause = " JOIN org_members om ON om.user_id = llm_usage_log.user_id"
            if is_pg:
                where_clause = f" WHERE om.org_id = ANY(${len(params) + 1})"
                params.append(org_ids)
            else:
                placeholders = ",".join("?" for _ in org_ids)
                where_clause = f" WHERE om.org_id IN ({placeholders})"
                params.extend(org_ids)

        providers = await _fetch_distinct_dimension_values(
            db=db,
            is_pg=is_pg,
            dimension_expr="COALESCE(NULLIF(TRIM(provider), ''), 'unknown')",
            join_clause=join_clause,
            where_clause=where_clause,
            params=params,
        )
        models = await _fetch_distinct_dimension_values(
            db=db,
            is_pg=is_pg,
            dimension_expr="COALESCE(NULLIF(TRIM(model), ''), 'unknown')",
            join_clause=join_clause,
            where_clause=where_clause,
            params=params,
        )
        try:
            token_names = await _fetch_distinct_dimension_values(
                db=db,
                is_pg=is_pg,
                dimension_expr="COALESCE(NULLIF(TRIM(token_name), ''), 'unknown')",
                join_clause=join_clause,
                where_clause=where_clause,
                params=params,
            )
        except _ADMIN_ROUTER_ANALYTICS_NONCRITICAL_EXCEPTIONS as exc:
            logger.debug("Router analytics meta token names fallback due to query error: %s", exc)
            token_names = []

        return RouterAnalyticsMetaResponse(
            providers=[RouterAnalyticsMetaOption(value=value, label=value) for value in providers],
            models=[RouterAnalyticsMetaOption(value=value, label=value) for value in models],
            tokens=[RouterAnalyticsMetaOption(value=value, label=value) for value in token_names],
            generated_at=generated_at,
        )
    except _ADMIN_ROUTER_ANALYTICS_NONCRITICAL_EXCEPTIONS:
        logger.exception("Failed to build router analytics meta payload")
        raise HTTPException(status_code=500, detail="Failed to load router analytics metadata") from None
