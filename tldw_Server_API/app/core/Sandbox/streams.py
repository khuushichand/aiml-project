from __future__ import annotations

import asyncio
import base64
import threading
from typing import Any, Dict, Optional

from loguru import logger


class RunStreamHub:
    """In-memory pub/sub for run log/event streaming with caps and backpressure."""

    def __init__(self) -> None:
        # Map run_id -> list of subscriber queues (fan-out to all subscribers)
        self._queues: dict[str, list[asyncio.Queue]] = {}
        self._buffers: dict[str, list[dict]] = {}
        self._log_bytes: dict[str, int] = {}
        self._truncated: set[str] = set()
        self._ended: set[str] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._lock = threading.RLock()
        self._max_queue = 1000
        self._max_log_bytes_default = 10 * 1024 * 1024
        self._seq: dict[str, int] = {}

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
            self._queues.setdefault(run_id, []).append(q)
            return q

    def subscribe(self, run_id: str) -> asyncio.Queue:
        return self._get_queue(run_id)

    def _next_seq(self, run_id: str) -> int:
        cur = self._seq.get(run_id, 0) + 1
        self._seq[run_id] = cur
        return cur

    def _publish(self, run_id: str, frame: dict) -> None:
        with self._lock:
            if "seq" not in frame:
                # Attach monotonically increasing sequence number per run
                frame = dict(frame)
                frame["seq"] = self._next_seq(run_id)
            # Do not buffer heartbeat frames to avoid pushing out important events
            if not (isinstance(frame, dict) and frame.get("type") == "heartbeat"):
                self._buffers.setdefault(run_id, []).append(frame)
            # Trim buffer to avoid unbounded mem (keep last 100 frames)
            buf = self._buffers.get(run_id)
            if buf is not None and len(buf) > 100:
                del buf[:-100]
            subs = self._queues.get(run_id)
            if subs and self._loop is not None:
                for q in list(subs):
                    try:
                        self._loop.call_soon_threadsafe(self._queue_put_nowait, q, frame)
                    except Exception as e:
                        logger.debug(f"queue publish failed: {e}")

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
            for frame in buf[-100:]:
                try:
                    q.put_nowait(frame)
                except Exception:
                    break

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
