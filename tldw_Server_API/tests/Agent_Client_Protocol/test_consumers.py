"""Tests for AuditLogger and MetricsRecorder event consumers."""
from __future__ import annotations

import asyncio

import pytest

from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus
from tldw_Server_API.app.core.Agent_Client_Protocol.events import (
    AgentEvent,
    AgentEventKind,
)
from tldw_Server_API.app.core.Agent_Client_Protocol.consumers.audit_logger import (
    AuditLogger,
)
from tldw_Server_API.app.core.Agent_Client_Protocol.consumers.metrics_recorder import (
    MetricsRecorder,
)


def _make_event(
    kind: AgentEventKind = AgentEventKind.TOOL_CALL,
    session_id: str = "sess-1",
) -> AgentEvent:
    return AgentEvent(session_id=session_id, kind=kind, payload={"data": kind.value})


async def _wait_for(predicate, *, timeout: float = 2.0, interval: float = 0.02):
    """Poll *predicate* until it returns True or *timeout* elapses."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if predicate():
            return
        await asyncio.sleep(interval)
    raise AssertionError(f"Timed out waiting for predicate after {timeout}s")


# --------------------------------------------------------------------------- #
# AuditLogger
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_audit_logger_batches_events():
    """When batch_size events are buffered, write_batch_fn should be called."""
    bus = SessionEventBus(session_id="sess-1")
    written_batches: list[list[AgentEvent]] = []

    async def fake_write(batch: list[AgentEvent]) -> None:
        written_batches.append(list(batch))

    audit = AuditLogger(
        write_batch_fn=fake_write,
        batch_size=3,
        flush_interval=10.0,  # long interval so only batch_size triggers
    )
    await audit.start(bus)

    for _ in range(3):
        await bus.publish(_make_event())

    await _wait_for(lambda: len(written_batches) >= 1)
    await audit.stop()

    assert len(written_batches) == 1
    assert len(written_batches[0]) == 3


@pytest.mark.asyncio
async def test_audit_logger_flushes_on_interval():
    """A partially-full buffer should flush after flush_interval elapses."""
    bus = SessionEventBus(session_id="sess-1")
    written_batches: list[list[AgentEvent]] = []

    async def fake_write(batch: list[AgentEvent]) -> None:
        written_batches.append(list(batch))

    audit = AuditLogger(
        write_batch_fn=fake_write,
        batch_size=100,  # high batch size so it never triggers
        flush_interval=0.1,
    )
    await audit.start(bus)

    await bus.publish(_make_event())

    await _wait_for(lambda: sum(len(b) for b in written_batches) >= 1)
    await audit.stop()

    total_events = sum(len(b) for b in written_batches)
    assert total_events == 1


# --------------------------------------------------------------------------- #
# MetricsRecorder
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_metrics_recorder_counts_tool_calls():
    """MetricsRecorder should count events by kind."""
    bus = SessionEventBus(session_id="sess-1")
    recorder = MetricsRecorder()
    await recorder.start(bus)

    await bus.publish(_make_event(AgentEventKind.TOOL_CALL))
    await bus.publish(_make_event(AgentEventKind.TOOL_CALL))
    await bus.publish(_make_event(AgentEventKind.COMPLETION))

    await _wait_for(lambda: sum(recorder.counters.values()) >= 3)
    await recorder.stop()

    assert recorder.counters["tool_call"] == 2
    assert recorder.counters["completion"] == 1
