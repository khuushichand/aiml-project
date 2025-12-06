from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import DatabasePool
from tldw_Server_API.app.core.AuthNZ.exceptions import AuthnzMonitoringError


def _strip_tzinfo(dt: datetime) -> datetime:
    """Strip timezone info for backend-agnostic timestamp storage."""
    return dt.replace(tzinfo=None) if getattr(dt, "tzinfo", None) else dt


@dataclass
class AuthnzMonitoringRepo:
    """
    Repository for AuthNZ monitoring-related queries.

    This repo centralizes reads/writes against ``audit_logs``, ``sessions``,
    and ``api_keys`` used by the monitoring subsystem so that backend-specific
    SQL handling is not embedded directly in business logic.
    """

    db_pool: DatabasePool

    async def insert_metric_audit_log(self, action: str, details_json: str, created_at: datetime) -> None:
        """
        Insert a metric record into ``audit_logs``.

        Mirrors the existing monitoring behavior which stores metrics as
        audit_log entries with ``action`` = ``metric_*``.
        """
        try:
            normalized = _strip_tzinfo(created_at)
            async with self.db_pool.transaction() as conn:
                if hasattr(conn, "fetchrow"):
                    await conn.execute(
                        """
                        INSERT INTO audit_logs (action, details, created_at)
                        VALUES ($1, $2, $3)
                        """,
                        action,
                        details_json,
                        normalized,
                    )
                else:
                    await conn.execute(
                        """
                        INSERT INTO audit_logs (action, details, created_at)
                        VALUES (?, ?, ?)
                        """,
                        (action, details_json, normalized.isoformat()),
                    )
        except Exception as exc:  # pragma: no cover - surfaced through callers
            logger.error(
                "AuthnzMonitoringRepo.insert_metric_audit_log failed: {}", exc
            )
            raise AuthnzMonitoringError(
                "insert_metric_audit_log", detail=str(exc)
            ) from exc

    async def delete_audit_logs_before(self, cutoff: datetime) -> int:
        """
        Delete audit_log rows older than the provided cutoff.

        Returns a best-effort count of rows deleted.
        """
        try:
            async with self.db_pool.transaction() as conn:
                deleted = 0
                if hasattr(conn, "fetchrow"):
                    cutoff_param = _strip_tzinfo(cutoff)
                    result = await conn.execute(
                        "DELETE FROM audit_logs WHERE created_at < $1",
                        cutoff_param,
                    )
                    if isinstance(result, str):
                        try:
                            deleted = int(result.split()[-1])
                        except (ValueError, IndexError):
                            deleted = 0
                else:
                    cursor = await conn.execute(
                        "DELETE FROM audit_logs WHERE created_at < ?",
                        (cutoff.isoformat(),),
                    )
                    deleted = getattr(cursor, "rowcount", 0) or 0
                return int(deleted or 0)
        except Exception as exc:  # pragma: no cover - surfaced through callers
            logger.error(
                "AuthnzMonitoringRepo.delete_audit_logs_before failed: {}", exc
            )
            raise AuthnzMonitoringError(
                "delete_audit_logs_before", detail=str(exc)
            ) from exc

    async def get_metrics_window_summary(self, cutoff: datetime) -> Dict[str, int]:
        """
        Return aggregate authentication and rate-limit metrics for a time window.

        The result mirrors the row consumed by ``AuthNZMonitor.get_metrics_summary``.
        """
        try:
            is_postgres = getattr(self.db_pool, "pool", None) is not None
            if is_postgres:
                cutoff_param = _strip_tzinfo(cutoff)
            else:
                cutoff_param = cutoff.isoformat()

            row = await self.db_pool.fetchone(
                """
                SELECT
                    COUNT(CASE WHEN action = 'metric_auth_success' THEN 1 END) as successful_auths,
                    COUNT(CASE WHEN action = 'metric_auth_failure' THEN 1 END) as failed_auths,
                    COUNT(CASE WHEN action = 'metric_rate_limit_hit' THEN 1 END) as rate_limit_hits
                FROM audit_logs
                WHERE created_at > ?
                  AND action LIKE 'metric_%'
                """,
                cutoff_param,
            )
            if not row:
                return {
                    "successful_auths": 0,
                    "failed_auths": 0,
                    "rate_limit_hits": 0,
                }

            # Normalize to a plain mapping of int counts for callers.
            if isinstance(row, dict):
                data: Dict[str, Any] = row
            else:
                # Fallback for sequence-like rows
                keys = ("successful_auths", "failed_auths", "rate_limit_hits")
                data = {k: (row[idx] if idx < len(row) else 0) for idx, k in enumerate(keys)}  # type: ignore[index]

            result: Dict[str, int] = {}
            for key in ("successful_auths", "failed_auths", "rate_limit_hits"):
                try:
                    result[key] = int(data.get(key, 0) or 0)
                except (TypeError, ValueError):
                    result[key] = 0
            return result
        except Exception as exc:  # pragma: no cover - surfaced through callers
            logger.error(
                "AuthnzMonitoringRepo.get_metrics_window_summary failed: {}", exc
            )
            raise AuthnzMonitoringError(
                "get_metrics_window_summary", detail=str(exc)
            ) from exc

    async def get_active_sessions_count(self, now: datetime) -> int:
        """
        Return the count of active sessions at the given timestamp.
        """
        try:
            is_postgres = getattr(self.db_pool, "pool", None) is not None
            if is_postgres:
                expires_param = _strip_tzinfo(now)
            else:
                expires_param = now.isoformat()
            revoked_inactive_value = False

            row = await self.db_pool.fetchone(
                """
                SELECT COUNT(*) as active_sessions
                FROM sessions
                WHERE expires_at > ?
                  AND (is_revoked = ? OR is_revoked IS NULL)
                """,
                expires_param,
                revoked_inactive_value,
            )
            if not row:
                return 0
            value = row.get("active_sessions") if isinstance(row, dict) else row[0]
            try:
                return int(value or 0)
            except (TypeError, ValueError):
                return 0
        except Exception as exc:  # pragma: no cover - surfaced through callers
            logger.error(
                "AuthnzMonitoringRepo.get_active_sessions_count failed: {}", exc
            )
            raise AuthnzMonitoringError(
                "get_active_sessions_count", detail=str(exc)
            ) from exc

    async def get_active_api_keys_count(self) -> int:
        """
        Return the count of active API keys.
        """
        try:
            row = await self.db_pool.fetchone(
                """
                SELECT COUNT(*) as active_keys
                FROM api_keys
                WHERE status = 'active'
                """
            )
            if not row:
                return 0
            value = row.get("active_keys") if isinstance(row, dict) else row[0]
            try:
                return int(value or 0)
            except (TypeError, ValueError):
                return 0
        except Exception as exc:  # pragma: no cover - surfaced through callers
            logger.error(
                "AuthnzMonitoringRepo.get_active_api_keys_count failed: {}", exc
            )
            raise AuthnzMonitoringError(
                "get_active_api_keys_count", detail=str(exc)
            ) from exc

    async def get_recent_security_alerts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Return recent security-alert metric audit_log rows.

        Each item includes ``action``, ``details``, and ``created_at``.
        """
        try:
            rows = await self.db_pool.fetchall(
                """
                SELECT action, details, created_at
                FROM audit_logs
                WHERE action = 'metric_security_alert'
                ORDER BY created_at DESC
                LIMIT ?
                """,
                limit,
            )
            # Normalize to a list of plain dicts for all backends
            return [dict(r) for r in (rows or [])]
        except Exception as exc:  # pragma: no cover - surfaced through callers
            logger.error(
                "AuthnzMonitoringRepo.get_recent_security_alerts failed: {}", exc
            )
            raise AuthnzMonitoringError(
                "get_recent_security_alerts", detail=str(exc)
            ) from exc
