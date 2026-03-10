"""Agent health monitoring with auto-disable and recovery.

Periodically checks agent availability via the registry and tracks
health status with consecutive failure counting.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from loguru import logger


@dataclass
class AgentHealthStatus:
    """Health status for a single agent."""
    agent_type: str
    health: str  # "healthy" | "degraded" | "unavailable" | "unknown"
    consecutive_failures: int = 0
    last_check: str | None = None
    last_healthy: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class AgentHealthMonitor:
    """Monitors agent health by periodically calling check_availability().

    Auto-disables agents after consecutive failures hit threshold,
    auto-recovers when they come back online.
    """

    def __init__(
        self,
        registry: Any = None,
        check_interval: float = 60.0,
        failure_threshold: int = 3,
    ) -> None:
        self._registry = registry
        self._check_interval = check_interval
        self._failure_threshold = failure_threshold
        self._statuses: dict[str, AgentHealthStatus] = {}
        self._task: asyncio.Task | None = None
        self._running = False

    def check_all(self) -> dict[str, AgentHealthStatus]:
        """Check health of all registered agents synchronously."""
        if self._registry is None:
            return self._statuses

        now = _utcnow_iso()
        for entry in self._registry.entries:
            avail = entry.check_availability()
            status = self._statuses.get(entry.type)
            if status is None:
                status = AgentHealthStatus(agent_type=entry.type, health="unknown")
                self._statuses[entry.type] = status

            status.last_check = now
            status.details = avail

            is_available = avail.get("status") == "available"
            if is_available:
                if status.consecutive_failures > 0:
                    logger.info(
                        "Agent '{}' recovered after {} failures",
                        entry.type,
                        status.consecutive_failures,
                    )
                status.health = "healthy"
                status.consecutive_failures = 0
                status.last_healthy = now
            else:
                status.consecutive_failures += 1
                if status.consecutive_failures >= self._failure_threshold:
                    status.health = "unavailable"
                else:
                    status.health = "degraded"

        return self._statuses

    def get_status(self, agent_type: str) -> AgentHealthStatus | None:
        """Get health status for a specific agent."""
        return self._statuses.get(agent_type)

    def get_all_statuses(self) -> list[AgentHealthStatus]:
        """Get health statuses for all monitored agents."""
        return list(self._statuses.values())

    async def start(self) -> None:
        """Start the background health check loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._check_loop())
        logger.info(
            "Agent health monitor started (interval={}s, threshold={})",
            self._check_interval,
            self._failure_threshold,
        )

    async def stop(self) -> None:
        """Stop the background health check loop."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Agent health monitor stopped")

    async def _check_loop(self) -> None:
        """Background loop that periodically checks all agents."""
        while self._running:
            try:
                self.check_all()
            except Exception as exc:
                logger.error("Health check failed: {}", exc)
            await asyncio.sleep(self._check_interval)


def _utcnow_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


# Module-level singleton
_monitor: AgentHealthMonitor | None = None


def get_health_monitor() -> AgentHealthMonitor:
    """Return the module-level health monitor singleton."""
    global _monitor
    if _monitor is None:
        _monitor = AgentHealthMonitor()
    return _monitor
