from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import DatabasePool


@dataclass
class AuthnzUsageRepo:
    """
    Repository for AuthNZ LLM usage accounting tables.

    This class centralizes common aggregate queries over ``llm_usage_log``
    and related tables so callers do not need to embed backend-specific
    SQL or timestamp handling logic.
    """

    db_pool: DatabasePool

    async def summarize_key_day(
        self,
        *,
        key_id: int,
        day: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Summarize token and USD usage for a key over a specific UTC day.

        Returns a dict with:
        - ``tokens`` (int)
        - ``usd`` (float)
        """
        try:
            day_val: date
            if isinstance(day, date):
                day_val = day
            else:
                # Default to "today" in UTC; Date() on Postgres is always UTC.
                day_val = datetime.now(timezone.utc).date()

            if getattr(self.db_pool, "pool", None) is not None:
                total_tokens = await self.db_pool.fetchval(
                    """
                    SELECT COALESCE(SUM(total_tokens),0)
                    FROM llm_usage_log
                    WHERE date(ts AT TIME ZONE 'UTC') = $1
                      AND key_id = $2
                    """,
                    day_val,
                    key_id,
                )
                total_cost = await self.db_pool.fetchval(
                    """
                    SELECT COALESCE(SUM(total_cost_usd),0)
                    FROM llm_usage_log
                    WHERE date(ts AT TIME ZONE 'UTC') = $1
                      AND key_id = $2
                    """,
                    day_val,
                    key_id,
                )
            else:
                day_str = day_val.isoformat()
                total_tokens = await self.db_pool.fetchval(
                    """
                    SELECT COALESCE(SUM(total_tokens),0)
                    FROM llm_usage_log
                    WHERE DATE(datetime(ts)) = ?
                      AND key_id = ?
                    """,
                    day_str,
                    key_id,
                )
                total_cost = await self.db_pool.fetchval(
                    """
                    SELECT COALESCE(SUM(total_cost_usd),0)
                    FROM llm_usage_log
                    WHERE DATE(datetime(ts)) = ?
                      AND key_id = ?
                    """,
                    day_str,
                    key_id,
                )

            return {
                "tokens": int(total_tokens or 0),
                "usd": float(total_cost or 0.0),
            }
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.error(f"AuthnzUsageRepo.summarize_key_day failed: {exc}")
            raise

    async def summarize_key_rolling_window(
        self,
        *,
        key_id: int,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Summarize token and USD usage for a key over a rolling UTC window.

        The window is defined as ``[now - days, now)`` in UTC.

        Returns a dict with:
        - ``tokens`` (int)
        - ``usd`` (float)
        """
        window_days = max(1, int(days))
        try:
            now = datetime.now(timezone.utc)
            start_dt = now - timedelta(days=window_days)
            end_dt = now

            if getattr(self.db_pool, "pool", None) is not None:
                # Postgres path: ensure naive UTC timestamps for comparison
                _start = start_dt.replace(tzinfo=None)
                _end = end_dt.replace(tzinfo=None)
                row = await self.db_pool.fetchone(
                    """
                    SELECT
                        COALESCE(SUM(total_tokens),0) AS tokens,
                        COALESCE(SUM(total_cost_usd),0.0) AS usd
                    FROM llm_usage_log
                    WHERE ts >= $1 AND ts < $2 AND key_id = $3
                    """,
                    _start,
                    _end,
                    key_id,
                )
            else:
                # SQLite path: normalize timestamps to a consistent naive UTC string
                def _sqlite_fmt(value: datetime) -> str:
                    dt = value.astimezone(timezone.utc).replace(tzinfo=None)
                    return dt.strftime("%Y-%m-%d %H:%M:%S")

                start_str = _sqlite_fmt(start_dt)
                end_str = _sqlite_fmt(end_dt)
                row = await self.db_pool.fetchone(
                    """
                    SELECT
                        COALESCE(SUM(total_tokens),0) AS tokens,
                        COALESCE(SUM(total_cost_usd),0.0) AS usd
                    FROM llm_usage_log
                    WHERE datetime(ts) >= ?
                      AND datetime(ts) < ?
                      AND key_id = ?
                    """,
                    start_str,
                    end_str,
                    key_id,
                )

            tokens = 0
            usd = 0.0
            if row:
                if hasattr(row, "get"):
                    tokens = int(row.get("tokens") or 0)
                    usd = float(row.get("usd") or 0.0)
                else:
                    tokens = int((row["tokens"] if "tokens" in row else row[0]) or 0)
                    usd = float((row["usd"] if "usd" in row else row[1]) or 0.0)

            return {"tokens": tokens, "usd": usd}
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.error(f"AuthnzUsageRepo.summarize_key_rolling_window failed: {exc}")
            raise

    async def prune_llm_usage_log_before(self, cutoff: datetime) -> int:
        """
        Delete ``llm_usage_log`` rows older than the given cutoff timestamp.

        Returns the number of deleted rows (best-effort when the backend does
        not report an accurate rowcount).
        """
        try:
            async with self.db_pool.transaction() as conn:
                if hasattr(conn, "fetchrow"):
                    cutoff_param = cutoff.replace(tzinfo=None) if getattr(cutoff, "tzinfo", None) else cutoff
                    rows = await conn.fetch(
                        "DELETE FROM llm_usage_log WHERE ts < $1 RETURNING 1",
                        cutoff_param,
                    )
                    return len(rows)
                # SQLite path
                cursor = await conn.execute(
                    "DELETE FROM llm_usage_log WHERE ts < ?",
                    (cutoff.isoformat(),),
                )
                deleted = getattr(cursor, "rowcount", 0) or 0
                return int(deleted)
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.error(f"AuthnzUsageRepo.prune_llm_usage_log_before failed: {exc}")
            raise

    async def prune_usage_log_before(self, cutoff: datetime) -> int:
        """
        Delete ``usage_log`` rows older than the given cutoff timestamp.

        Returns the number of deleted rows (best-effort).
        """
        try:
            async with self.db_pool.transaction() as conn:
                if hasattr(conn, "fetchrow"):
                    cutoff_param = cutoff.replace(tzinfo=None) if getattr(cutoff, "tzinfo", None) else cutoff
                    rows = await conn.fetch(
                        "DELETE FROM usage_log WHERE ts < $1 RETURNING 1",
                        cutoff_param,
                    )
                    return len(rows)

                cursor = await conn.execute(
                    "DELETE FROM usage_log WHERE ts < ?",
                    (cutoff.isoformat(),),
                )
                deleted = getattr(cursor, "rowcount", 0) or 0
                return int(deleted)
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.error(f"AuthnzUsageRepo.prune_usage_log_before failed: {exc}")
            raise

    async def prune_usage_daily_before(self, cutoff_day: date) -> int:
        """
        Delete ``usage_daily`` rows older than the given cutoff day.

        Returns the number of deleted rows (best-effort).
        """
        try:
            async with self.db_pool.transaction() as conn:
                if hasattr(conn, "fetchrow"):
                    rows = await conn.fetch(
                        "DELETE FROM usage_daily WHERE day < $1::date RETURNING 1",
                        cutoff_day,
                    )
                    return len(rows)
                cursor = await conn.execute(
                    "DELETE FROM usage_daily WHERE day < ?",
                    (cutoff_day.isoformat(),),
                )
                deleted = getattr(cursor, "rowcount", 0) or 0
                return int(deleted)
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.error(f"AuthnzUsageRepo.prune_usage_daily_before failed: {exc}")
            raise

    async def insert_usage_log(
        self,
        *,
        user_id: Optional[int],
        key_id: Optional[int],
        endpoint: str,
        status: int,
        latency_ms: int,
        bytes_out: Optional[int],
        bytes_in: Optional[int],
        meta: str,
        request_id: Optional[str],
    ) -> None:
        """
        Insert a single row into ``usage_log``.

        This mirrors the insert logic previously embedded in
        ``UsageLoggingMiddleware`` while centralizing dialect differences
        and fallback behavior (with/without ``bytes_in``) in one place.
        """
        try:
            # Prefer the extended schema including bytes_in when available;
            # fall back to the legacy schema when the column is missing.
            try:
                await self.db_pool.execute(
                    """
                    INSERT INTO usage_log (
                        user_id, key_id, endpoint, status, latency_ms,
                        bytes, bytes_in, meta, request_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    user_id,
                    key_id,
                    endpoint,
                    int(status),
                    int(latency_ms),
                    int(bytes_out) if bytes_out is not None else None,
                    int(bytes_in) if bytes_in is not None else None,
                    meta,
                    request_id,
                )
            except Exception:
                await self.db_pool.execute(
                    """
                    INSERT INTO usage_log (
                        user_id, key_id, endpoint, status, latency_ms,
                        bytes, meta, request_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    user_id,
                    key_id,
                    endpoint,
                    int(status),
                    int(latency_ms),
                    int(bytes_out) if bytes_out is not None else None,
                    meta,
                    request_id,
                )
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.error(f"AuthnzUsageRepo.insert_usage_log failed: {exc}")
            raise

    async def prune_llm_usage_daily_before(self, cutoff_day: date) -> int:
        """
        Delete ``llm_usage_daily`` rows older than the given cutoff day.

        Returns the number of deleted rows (best-effort).
        """
        try:
            async with self.db_pool.transaction() as conn:
                if hasattr(conn, "fetchrow"):
                    result = await conn.execute(
                        "DELETE FROM llm_usage_daily WHERE day < $1::date",
                        cutoff_day,
                    )
                    try:
                        return int(result.split()[-1]) if isinstance(result, str) else 0
                    except Exception:
                        return 0
                cursor = await conn.execute(
                    "DELETE FROM llm_usage_daily WHERE day < ?",
                    (cutoff_day.isoformat(),),
                )
                deleted = getattr(cursor, "rowcount", 0) or 0
                return int(deleted)
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.error(f"AuthnzUsageRepo.prune_llm_usage_daily_before failed: {exc}")
            raise
