"""Tests for agent health monitoring."""
import asyncio

import pytest
from unittest.mock import MagicMock

from tldw_Server_API.app.core.Agent_Client_Protocol.health_monitor import (
    AgentHealthMonitor,
    AgentHealthStatus,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_registry():
    registry = MagicMock()
    entry1 = MagicMock()
    entry1.type = "claude_code"
    entry1.check_availability.return_value = {"status": "available", "is_configured": True}
    entry2 = MagicMock()
    entry2.type = "codex"
    entry2.check_availability.return_value = {"status": "unavailable", "is_configured": False}
    registry.entries = [entry1, entry2]
    return registry


def test_check_all_agents(mock_registry):
    monitor = AgentHealthMonitor(registry=mock_registry)
    monitor.check_all()
    status = monitor.get_status("claude_code")
    assert status is not None
    assert status.health == "healthy"
    assert status.consecutive_failures == 0


def test_unavailable_agent_marked_degraded(mock_registry):
    monitor = AgentHealthMonitor(registry=mock_registry, failure_threshold=3)
    monitor.check_all()
    status = monitor.get_status("codex")
    assert status.health == "degraded"
    assert status.consecutive_failures == 1


def test_consecutive_failures_disable(mock_registry):
    monitor = AgentHealthMonitor(registry=mock_registry, failure_threshold=2)
    monitor.check_all()
    monitor.check_all()
    status = monitor.get_status("codex")
    assert status.health == "unavailable"
    assert status.consecutive_failures == 2


def test_recovery_re_enables(mock_registry):
    monitor = AgentHealthMonitor(registry=mock_registry, failure_threshold=1)
    monitor.check_all()  # codex fails, marked unavailable
    status = monitor.get_status("codex")
    assert status.health == "unavailable"

    # Now codex becomes available
    mock_registry.entries[1].check_availability.return_value = {
        "status": "available",
        "is_configured": True,
    }
    monitor.check_all()
    status = monitor.get_status("codex")
    assert status.health == "healthy"
    assert status.consecutive_failures == 0
    assert status.last_healthy is not None


def test_get_all_statuses(mock_registry):
    monitor = AgentHealthMonitor(registry=mock_registry)
    monitor.check_all()
    all_status = monitor.get_all_statuses()
    assert len(all_status) == 2
    types = {s.agent_type for s in all_status}
    assert types == {"claude_code", "codex"}


def test_get_status_unknown(mock_registry):
    monitor = AgentHealthMonitor(registry=mock_registry)
    assert monitor.get_status("nonexistent") is None


def test_check_all_no_registry():
    monitor = AgentHealthMonitor(registry=None)
    result = monitor.check_all()
    assert result == {}


def test_last_check_is_set(mock_registry):
    monitor = AgentHealthMonitor(registry=mock_registry)
    monitor.check_all()
    status = monitor.get_status("claude_code")
    assert status.last_check is not None
    assert len(status.last_check) > 0


def test_details_populated(mock_registry):
    monitor = AgentHealthMonitor(registry=mock_registry)
    monitor.check_all()
    status = monitor.get_status("claude_code")
    assert status.details["status"] == "available"
    assert status.details["is_configured"] is True


def test_healthy_agent_has_last_healthy(mock_registry):
    monitor = AgentHealthMonitor(registry=mock_registry)
    monitor.check_all()
    status = monitor.get_status("claude_code")
    assert status.last_healthy is not None


def test_degraded_agent_no_last_healthy(mock_registry):
    monitor = AgentHealthMonitor(registry=mock_registry, failure_threshold=3)
    monitor.check_all()
    status = monitor.get_status("codex")
    assert status.last_healthy is None


def test_multiple_checks_accumulate_failures(mock_registry):
    monitor = AgentHealthMonitor(registry=mock_registry, failure_threshold=5)
    for _ in range(4):
        monitor.check_all()
    status = monitor.get_status("codex")
    assert status.consecutive_failures == 4
    assert status.health == "degraded"
    # One more pushes it to unavailable
    monitor.check_all()
    status = monitor.get_status("codex")
    assert status.consecutive_failures == 5
    assert status.health == "unavailable"


# --- Async lifecycle tests ---


@pytest.mark.asyncio
async def test_start_and_stop(mock_registry):
    """start() creates a background task, stop() cancels it."""
    monitor = AgentHealthMonitor(
        registry=mock_registry, check_interval=0.05,
    )
    await monitor.start()
    assert monitor._running is True
    assert monitor._task is not None

    # Let one check happen
    await asyncio.sleep(0.1)
    assert monitor.get_status("claude_code") is not None

    await monitor.stop()
    assert monitor._running is False
    assert monitor._task is None


@pytest.mark.asyncio
async def test_double_start_is_idempotent(mock_registry):
    """Calling start() twice doesn't create duplicate tasks."""
    monitor = AgentHealthMonitor(
        registry=mock_registry, check_interval=0.05,
    )
    await monitor.start()
    task1 = monitor._task
    await monitor.start()  # second call
    assert monitor._task is task1  # same task

    await monitor.stop()


@pytest.mark.asyncio
async def test_check_loop_survives_exception():
    """The background loop continues after check_all raises."""
    registry = MagicMock()
    call_count = 0

    def flaky_entries():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("transient failure")
        entry = MagicMock()
        entry.type = "agent"
        entry.check_availability.return_value = {"status": "available"}
        return [entry]

    type(registry).entries = property(lambda self: flaky_entries())

    monitor = AgentHealthMonitor(registry=registry, check_interval=0.05)
    await monitor.start()
    await asyncio.sleep(0.2)
    await monitor.stop()

    # Should have recovered after the first exception
    assert call_count >= 2
