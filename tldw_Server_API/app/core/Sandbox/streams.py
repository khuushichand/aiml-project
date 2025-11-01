from __future__ import annotations

import asyncio
import base64
import threading
from typing import Any, Dict, Optional

from loguru import logger


class RunStreamHub:
    """In-memory pub/sub for run log/event streaming with caps and backpressure."""

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue] = {}
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
        with self._lock:
            q = self._queues.get(run_id)
            if q is None:
                q = asyncio.Queue(self._max_queue)
                self._queues[run_id] = q
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
            self._buffers.setdefault(run_id, []).append(frame)
            # Trim buffer to avoid unbounded mem (keep last 100 frames)
            buf = self._buffers[run_id]
            if len(buf) > 100:
                del buf[:-100]
            q = self._queues.get(run_id)
            if q is not None and self._loop is not None:
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
            try:
                q.put_nowait(item)
            except Exception:
                pass

    def publish_event(self, run_id: str, event: str, data: Optional[dict] = None) -> None:
        # Deduplicate final end event to avoid double-emission from runner and service
        if event == "end":
            with self._lock:
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
                        increment_counter("sandbox_log_truncations_total", labels={"component": "sandbox"})
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
        self._publish(run_id, {"type": "event", "event": "end", "data": {}})

    def get_log_bytes(self, run_id: str) -> int:
        """Return the total number of bytes published to stdout/stderr for a run."""
        with self._lock:
            return int(self._log_bytes.get(run_id, 0))


_HUB = RunStreamHub()


def get_hub() -> RunStreamHub:
    return _HUB
