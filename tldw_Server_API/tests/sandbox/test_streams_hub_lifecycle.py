from __future__ import annotations

import pytest


@pytest.mark.unit
def test_hub_end_dedup_and_cleanup_drain_buffer() -> None:
    # Use a fresh hub instance to avoid global state
    from tldw_Server_API.app.core.Sandbox.streams import RunStreamHub

    hub = RunStreamHub()
    run_id = "run-hub-1"

    q = hub.subscribe(run_id)
    hub.publish_event(run_id, "start", {"ok": True})
    hub.publish_stdout(run_id, b"hello", max_log_bytes=64)
    hub.publish_event(run_id, "end", {})
    # Duplicate end should be ignored by deduplication
    hub.publish_event(run_id, "end", {})

    # Drain buffered frames into the queue (no loop configured)
    hub.drain_buffer(run_id, q)

    frames = []
    while True:
        try:
            frames.append(q.get_nowait())
        except Exception:
            break

    # Exactly one end event
    end_frames = [f for f in frames if f.get("type") == "event" and f.get("event") == "end"]
    assert len(end_frames) == 1

    # Sequence numbers should be present and strictly increasing
    seqs = [int(f["seq"]) for f in frames if "seq" in f]
    assert seqs == sorted(seqs) and len(seqs) == len(set(seqs))

    # Close should cleanup all per-run state
    hub.close(run_id)
    assert run_id not in hub._queues
    assert run_id not in hub._buffers
    assert run_id not in hub._log_bytes
    assert run_id not in hub._truncated
    assert run_id not in hub._ended
    assert run_id not in hub._seq


@pytest.mark.unit
def test_hub_close_publishes_end_and_cleans(monkeypatch: pytest.MonkeyPatch) -> None:
    from tldw_Server_API.app.core.Sandbox.streams import RunStreamHub

    hub = RunStreamHub()
    run_id = "run-hub-2"

    published: list[tuple[str, dict]] = []

    def _fake_publish(rid: str, frame: dict) -> None:
        published.append((rid, frame))

    # Intercept low-level publish to observe frames emitted by close()
    monkeypatch.setattr(hub, "_publish", _fake_publish, raising=True)

    # No prior end event; close should emit exactly one end event then cleanup
    hub.close(run_id)

    ends = [f for rid, f in published if rid == run_id and f.get("type") == "event" and f.get("event") == "end"]
    assert len(ends) == 1

    # Cleanup performed
    assert run_id not in hub._queues
    assert run_id not in hub._buffers
    assert run_id not in hub._log_bytes
    assert run_id not in hub._truncated
    assert run_id not in hub._ended
    assert run_id not in hub._seq


@pytest.mark.unit
def test_hub_close_respects_dedup_after_end(monkeypatch: pytest.MonkeyPatch) -> None:
    from tldw_Server_API.app.core.Sandbox.streams import RunStreamHub

    hub = RunStreamHub()
    run_id = "run-hub-3"

    published: list[tuple[str, dict]] = []

    def _fake_publish(rid: str, frame: dict) -> None:
        published.append((rid, frame))

    monkeypatch.setattr(hub, "_publish", _fake_publish, raising=True)

    # First end emission via publish_event
    hub.publish_event(run_id, "end", {})
    ends_before_close = [f for rid, f in published if rid == run_id and f.get("type") == "event" and f.get("event") == "end"]
    assert len(ends_before_close) == 1

    # close() should not emit another end due to deduplication, and should cleanup
    hub.close(run_id)
    ends_after_close = [f for rid, f in published if rid == run_id and f.get("type") == "event" and f.get("event") == "end"]
    assert len(ends_after_close) == 1  # unchanged

    # Cleanup performed
    assert run_id not in hub._queues
    assert run_id not in hub._buffers
    assert run_id not in hub._log_bytes
    assert run_id not in hub._truncated
    assert run_id not in hub._ended
    assert run_id not in hub._seq
