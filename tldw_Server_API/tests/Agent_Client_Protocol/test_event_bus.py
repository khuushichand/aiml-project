"""Unit tests for SessionEventBus."""
from __future__ import annotations

import asyncio

import pytest

from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEvent, AgentEventKind

pytestmark = pytest.mark.unit


def _make_event(session_id: str = "s1", kind: AgentEventKind = AgentEventKind.THINKING) -> AgentEvent:
    return AgentEvent(session_id=session_id, kind=kind, payload={"text": "hi"})


@pytest.mark.asyncio
async def test_bus_assigns_sequence_numbers():
    from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus

    bus = SessionEventBus(session_id="s1")
    e1 = _make_event()
    e2 = _make_event()
    e3 = _make_event()
    await bus.publish(e1)
    await bus.publish(e2)
    await bus.publish(e3)
    assert e1.sequence == 1
    assert e2.sequence == 2
    assert e3.sequence == 3
    assert bus.current_sequence == 3


@pytest.mark.asyncio
async def test_bus_fan_out_to_multiple_subscribers():
    from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus

    bus = SessionEventBus(session_id="s1")
    q1 = bus.subscribe("consumer-a")
    q2 = bus.subscribe("consumer-b")
    ev = _make_event()
    await bus.publish(ev)

    got1 = await asyncio.wait_for(q1.get(), timeout=1.0)
    got2 = await asyncio.wait_for(q2.get(), timeout=1.0)
    assert got1 is ev
    assert got2 is ev
    assert got1.sequence == 1


@pytest.mark.asyncio
async def test_bus_unsubscribe_stops_delivery():
    from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus

    bus = SessionEventBus(session_id="s1")
    q = bus.subscribe("consumer-a")
    await bus.publish(_make_event())
    bus.unsubscribe("consumer-a")
    await bus.publish(_make_event())

    # Only one event should be in the queue
    got = await asyncio.wait_for(q.get(), timeout=1.0)
    assert got.sequence == 1
    assert q.empty()


@pytest.mark.asyncio
async def test_bus_snapshot_returns_history():
    from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus

    bus = SessionEventBus(session_id="s1")
    for _ in range(5):
        await bus.publish(_make_event())

    # All history
    snap = bus.snapshot()
    assert len(snap) == 5
    assert [e.sequence for e in snap] == [1, 2, 3, 4, 5]

    # From sequence 3 onwards
    snap_from_3 = bus.snapshot(from_sequence=3)
    assert len(snap_from_3) == 3
    assert [e.sequence for e in snap_from_3] == [3, 4, 5]


@pytest.mark.asyncio
async def test_bus_snapshot_respects_buffer_limit():
    from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus

    bus = SessionEventBus(session_id="s1", max_buffer=3)
    for _ in range(5):
        await bus.publish(_make_event())

    snap = bus.snapshot()
    # Only last 3 events kept due to deque maxlen
    assert len(snap) == 3
    assert [e.sequence for e in snap] == [3, 4, 5]
    assert bus.min_sequence == 3


@pytest.mark.asyncio
async def test_bus_inject_delivers_event():
    from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus

    bus = SessionEventBus(session_id="s1")
    q = bus.subscribe("consumer-a")
    ev = _make_event()
    await bus.inject(ev)

    got = await asyncio.wait_for(q.get(), timeout=1.0)
    assert got is ev
    assert got.sequence == 1


@pytest.mark.asyncio
async def test_bus_backpressure_drops_to_full_queue():
    from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus

    bus = SessionEventBus(session_id="s1", subscriber_queue_size=2)
    q = bus.subscribe("consumer-a")

    # Publish 5 events without consuming -- queue holds only 2
    for _ in range(5):
        await bus.publish(_make_event())

    # Queue should contain exactly 2 events (the first 2 that fit)
    items = []
    while not q.empty():
        items.append(q.get_nowait())
    assert len(items) == 2
    # First two were accepted, rest dropped
    assert items[0].sequence == 1
    assert items[1].sequence == 2
