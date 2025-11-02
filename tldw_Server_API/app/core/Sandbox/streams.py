from __future__ import annotations

import asyncio
import base64
import threading
from typing import Any, Dict, Optional

from loguru import logger


class RunStreamHub:
    """In-memory pub/sub for run log/event streaming with caps and backpressure."""

    def __init__(self) -> None:
        # Map run_id -> list of (loop, subscriber queue) pairs (fan-out to all subscribers)
        self._queues: dict[str, list[tuple[asyncio.AbstractEventLoop, asyncio.Queue]]] = {}
        self._buffers: dict[str, list[dict]] = {}
        self._log_bytes: dict[str, int] = {}
        self._truncated: set[str] = set()
        self._ended: set[str] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._lock = threading.RLock()
        self._max_queue = 1000
        self._max_log_bytes_default = 10 * 1024 * 1024
        self._seq: dict[str, int] = {}
        # Per-run serialized dispatcher
        self._dispatch: dict[str, list[dict]] = {}
        self._dispatching: set[str] = set()

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        with self._lock:
            # Always update to the current running loop. In test environments,
            # TestClient may create transient loops per connection; using the
            # latest loop ensures call_soon_threadsafe targets a live loop.
            self._loop = loop

    def _get_queue(self, run_id: str) -> asyncio.Queue:
        """Create a new subscriber queue for the given run_id and register it.

        Each call returns a distinct asyncio.Queue so multiple subscribers
        receive the same frames independently and in the same order.
        """
        with self._lock:
            q = asyncio.Queue(self._max_queue)
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # Fallback to stored loop if called from a non-async context
                loop = self._loop or asyncio.get_event_loop()
            self._queues.setdefault(run_id, []).append((loop, q))
            return q

    def subscribe(self, run_id: str) -> asyncio.Queue:
        return self._get_queue(run_id)

    def subscribe_with_buffer(self, run_id: str) -> asyncio.Queue:
        """Subscribe a new consumer and pre-fill its queue with buffered frames.

        Ensures buffered frames have sequence numbers assigned before enqueueing
        them for this subscriber, avoiding races where live dispatch could stamp
        seq later and interleave frames. The subscriber is only registered after
        the buffered frames are enqueued, so it will start receiving new frames
        from the dispatcher afterwards while still seeing the historical frames
        first on its own queue.
        """
        with self._lock:
            q = asyncio.Queue(self._max_queue)
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = self._loop or asyncio.get_event_loop()
            # Stamp seq on buffered frames if missing, then copy into this queue
            buf = self._buffers.get(run_id) or []
            import copy as _copy
            for frame in buf[-100:]:
                if isinstance(frame, dict) and "seq" not in frame:
                    frame["seq"] = self._next_seq(run_id)
                try:
                    q.put_nowait(_copy.deepcopy(frame))
                except Exception:
                    break
            # Finally register this subscriber for future live frames
            self._queues.setdefault(run_id, []).append((loop, q))
            return q

    def _next_seq(self, run_id: str) -> int:
        with self._lock:
            cur = self._seq.get(run_id, 0) + 1
            self._seq[run_id] = cur
            return cur

    def _publish(self, run_id: str, frame: dict) -> None:
        with self._lock:
            # Buffer non-heartbeat frames for reconnects (seq is assigned at dispatch time)
            if not (isinstance(frame, dict) and frame.get("type") == "heartbeat"):
                self._buffers.setdefault(run_id, []).append(frame)
                buf = self._buffers.get(run_id)
                if buf is not None and len(buf) > 100:
                    del buf[:-100]
            # Enqueue for serialized dispatch (seq will be stamped in dispatcher)
            self._dispatch.setdefault(run_id, []).append(frame)
            if run_id not in self._dispatching:
                self._dispatching.add(run_id)
                self._schedule_dispatch(run_id)

    def _schedule_dispatch(self, run_id: str) -> None:
        # Choose a loop to trigger the dispatcher; prefer last known loop or any subscriber loop
        with self._lock:
            loop = self._loop
            if not loop:
                subs = self._queues.get(run_id) or []
                loop = subs[0][0] if subs else None
        if loop is None:
            # No loop available yet; retry shortly from a timer thread
            try:
                threading.Timer(0.005, lambda: self._schedule_dispatch(run_id)).start()
            except Exception:
                pass
            return
        try:
            loop.call_soon_threadsafe(self._do_dispatch, run_id)
        except Exception as e:
            logger.debug(f"dispatch schedule failed: {e}")

    def _do_dispatch(self, run_id: str) -> None:
        # Drain queued frames and fan-out to all subscribers in arrival order
        while True:
            with self._lock:
                queue = self._dispatch.get(run_id) or []
                if not queue:
                    self._dispatching.discard(run_id)
                    return
                frame = queue.pop(0)
                # Stamp sequence centrally here to ensure strict ordering for all subscribers.
                # Update in-place so the buffered frame also carries the seq for future drains.
                if isinstance(frame, dict) and "seq" not in frame:
                    frame["seq"] = self._next_seq(run_id)
                subs = list(self._queues.get(run_id) or [])
            for (lp, q) in subs:
                try:
                    import copy as _copy
                    lp.call_soon_threadsafe(self._queue_put_nowait, q, _copy.deepcopy(frame))
                except Exception:
                    # Swallow delivery errors to individual subscribers
                    pass

    @staticmethod
    def _queue_put_nowait(q: asyncio.Queue, item: dict) -> None:
        try:
            q.put_nowait(item)
        except asyncio.QueueFull:
            # Drop oldest by draining one, then put
            try:
                _ = q.get_nowait()
            except Exception:
                pass
            # Metrics: queue overflow/drop
            try:
                from tldw_Server_API.app.core.Metrics import increment_counter
                increment_counter(
                    "sandbox_ws_queue_drops_total",
                    labels={"component": "sandbox", "reason": "drop_oldest"},
                )
            except Exception:
                pass
            try:
                q.put_nowait(item)
            except Exception:
                pass

    def publish_event(self, run_id: str, event: str, data: Optional[dict] = None) -> None:
        # Deduplicate final end event to avoid double-emission from runner and service
        if event == "end":
            with self._lock:
                # Protect _ended access with the lock and avoid duplicates
                if run_id in self._ended:
                    return
                self._ended.add(run_id)
        frame = {"type": "event", "event": event, "data": data or {}}
        self._publish(run_id, frame)

    def publish_heartbeat(self, run_id: str) -> None:
        """Publish a heartbeat frame with seq attached by the hub."""
        self._publish(run_id, {"type": "heartbeat"})

    def publish_stdout(self, run_id: str, chunk: bytes, max_log_bytes: Optional[int] = None) -> None:
        self._publish_stream(run_id, "stdout", chunk, max_log_bytes=max_log_bytes)

    def publish_stderr(self, run_id: str, chunk: bytes, max_log_bytes: Optional[int] = None) -> None:
        self._publish_stream(run_id, "stderr", chunk, max_log_bytes=max_log_bytes)

    def _publish_stream(self, run_id: str, kind: str, chunk: bytes, *, max_log_bytes: Optional[int]) -> None:
        cap = max_log_bytes or self._max_log_bytes_default
        with self._lock:
            used = self._log_bytes.get(run_id, 0)
            if used >= cap:
                if run_id not in self._truncated:
                    self._truncated.add(run_id)
                    self._publish(run_id, {"type": "truncated", "reason": "log_cap"})
                    # Metrics: log truncations
                    try:
                        from tldw_Server_API.app.core.Metrics import increment_counter
                        increment_counter(
                            "sandbox_log_truncations_total",
                            labels={"component": "sandbox", "reason": "log_cap"},
                        )
                    except Exception:
                        pass
                return
            remaining = cap - used
        data = chunk[:remaining]
        try:
            text = data.decode("utf-8")
            frame = {"type": kind, "encoding": "utf8", "data": text}
        except UnicodeDecodeError:
            b64 = base64.b64encode(data).decode("ascii")
            frame = {"type": kind, "encoding": "base64", "data": b64}
        with self._lock:
            self._log_bytes[run_id] = self._log_bytes.get(run_id, 0) + len(data)
        self._publish(run_id, frame)

    def drain_buffer(self, run_id: str, q: asyncio.Queue) -> None:
        with self._lock:
            buf = self._buffers.get(run_id) or []
            if not buf:
                return
            # Emit up to the last 100 buffered frames with seq stamped
            for frame in buf[-100:]:
                try:
                    if isinstance(frame, dict) and "seq" not in frame:
                        frame["seq"] = self._next_seq(run_id)
                    import copy as _copy
                    q.put_nowait(_copy.deepcopy(frame))
                except Exception:
                    break

    def get_buffer_snapshot(self, run_id: str) -> list[dict]:
        """Return a deep-copied snapshot of the buffered frames for a run.

        The snapshot contains at most the last 100 frames and preserves any
        assigned sequence numbers. Heartbeats are not buffered and therefore
        are not included in this snapshot.
        """
        with self._lock:
            import copy as _copy
            buf = self._buffers.get(run_id) or []
            return [_copy.deepcopy(f) for f in buf[-100:]]

    def close(self, run_id: str) -> None:
        # Use publish_event so end-event deduplication applies
        self.publish_event(run_id, "end", {})
        # Cleanup all per-run state to prevent memory leaks
        self.cleanup_run(run_id)

    def get_log_bytes(self, run_id: str) -> int:
        """Return the total number of bytes published to stdout/stderr for a run."""
        with self._lock:
            return int(self._log_bytes.get(run_id, 0))

    def cleanup_run(self, run_id: str) -> None:
        """Remove all references for a run to avoid memory leaks.

        Thread-safe: acquires the internal lock before mutating any structures.
        Removes entries from queues, buffers, log counters, truncation/end markers,
        and sequence tracking.
        """
        with self._lock:
            # Remove any queue reference (the queue object may still be held by subscribers)
            self._queues.pop(run_id, None)
            # Drop buffered frames and counters
            self._buffers.pop(run_id, None)
            self._log_bytes.pop(run_id, None)
            # Clear truncation and end flags
            self._truncated.discard(run_id)
            self._ended.discard(run_id)
            # Clear sequence counter
            self._seq.pop(run_id, None)


_HUB = RunStreamHub()


def get_hub() -> RunStreamHub:
    return _HUB
