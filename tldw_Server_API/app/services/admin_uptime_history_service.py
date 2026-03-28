"""Admin uptime history service — record and query dependency health probes."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import DatabasePool, get_db_pool


@dataclass
class HealthProbeRecord:
    id: int
    service_name: str
    status: str
    latency_ms: int | None
    error_message: str | None
    checked_at: str


class AdminUptimeHistoryService:
    """Records health probe results and serves uptime history."""

    def __init__(self, db_pool: DatabasePool | None = None):
        self._pool = db_pool

    async def _get_pool(self) -> DatabasePool:
        if self._pool is not None:
            return self._pool
        return await get_db_pool()

    async def record_probe(
        self,
        *,
        service_name: str,
        status: str,
        latency_ms: int | None = None,
        error_message: str | None = None,
    ) -> None:
        """Write a health probe result to the time-series table."""
        pool = await self._get_pool()
        now = datetime.now(timezone.utc).isoformat()
        await pool.execute(
            """
            INSERT INTO admin_dependency_health_history
                (service_name, status, latency_ms, error_message, checked_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (service_name, status, latency_ms, error_message, now),
        )

    async def get_uptime_history(
        self,
        service_name: str,
        *,
        range_days: int = 30,
        bucket_hours: int = 24,
    ) -> list[dict[str, Any]]:
        """Return uptime percentage per bucket for a service.

        Returns a list of ``{"bucket": "YYYY-MM-DD", "uptime_pct": float, "probes": int}``
        entries ordered oldest-first.
        """
        pool = await self._get_pool()
        rows = await pool.fetchall(
            """
            SELECT
                DATE(checked_at) AS bucket,
                COUNT(*) AS probes,
                SUM(CASE WHEN status = 'healthy' THEN 1 ELSE 0 END) AS healthy_count
            FROM admin_dependency_health_history
            WHERE service_name = ?
              AND checked_at >= DATETIME('now', ?)
            GROUP BY bucket
            ORDER BY bucket ASC
            """,
            (service_name, f"-{range_days} days"),
        )
        result = []
        for row in rows:
            probes = row["probes"] if isinstance(row, dict) else row[1]
            healthy = row["healthy_count"] if isinstance(row, dict) else row[2]
            bucket = row["bucket"] if isinstance(row, dict) else row[0]
            pct = (healthy / probes * 100) if probes > 0 else 0
            result.append({
                "bucket": bucket,
                "uptime_pct": round(pct, 2),
                "probes": probes,
            })
        return result

    async def get_all_services_uptime(
        self, *, range_days: int = 30,
    ) -> dict[str, list[dict[str, Any]]]:
        """Return uptime history for all tracked services."""
        pool = await self._get_pool()
        rows = await pool.fetchall(
            """
            SELECT DISTINCT service_name
            FROM admin_dependency_health_history
            WHERE checked_at >= DATETIME('now', ?)
            """,
            (f"-{range_days} days",),
        )
        services = [
            (row["service_name"] if isinstance(row, dict) else row[0])
            for row in rows
        ]
        result = {}
        for svc in services:
            result[svc] = await self.get_uptime_history(svc, range_days=range_days)
        return result

    async def cleanup_old_probes(self, *, keep_days: int = 90) -> int:
        """Delete probes older than *keep_days*. Returns count deleted."""
        pool = await self._get_pool()
        result = await pool.execute(
            "DELETE FROM admin_dependency_health_history WHERE checked_at < DATETIME('now', ?)",
            (f"-{keep_days} days",),
        )
        count = getattr(result, "rowcount", 0) or 0
        if count:
            logger.info("Cleaned up {} old health probe records", count)
        return count


# Module-level singleton
_service: AdminUptimeHistoryService | None = None


def get_admin_uptime_history_service() -> AdminUptimeHistoryService:
    global _service
    if _service is None:
        _service = AdminUptimeHistoryService()
    return _service
