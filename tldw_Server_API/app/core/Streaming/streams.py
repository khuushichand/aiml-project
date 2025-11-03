"""
Streaming abstraction for SSE and WebSocket transports.

Provides a small, composable interface to standardize:
- emission of structured events and JSON payloads
- DONE and ERROR lifecycle frames (with canonical error code + message)
- optional heartbeat for long-lived streams

Notes
- SSEStream is queue-backed and exposes iter_sse() for FastAPI StreamingResponse.
- WebSocketStream wraps a Starlette/FastAPI WebSocket, with optional ping loop.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, Dict, Optional, Protocol, Tuple
import time as _time

try:
    # Prefer unified metrics module if available
    from tldw_Server_API.app.core.Metrics import observe_histogram, set_gauge, increment_counter
except Exception:  # pragma: no cover - metrics optional in minimal envs
    def observe_histogram(metric_name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:  # type: ignore
        return

    def set_gauge(metric_name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:  # type: ignore
        return

    def increment_counter(metric_name: str, value: float = 1, labels: Optional[Dict[str, str]] = None) -> None:  # type: ignore
        return

from tldw_Server_API.app.core.LLM_Calls.sse import (
    ensure_sse_line,
    sse_data,
    sse_done,
)


class AsyncStream(Protocol):
    async def send_event(self, event: str, data: Any | None = None) -> None: ...
    async def send_json(self, payload: Dict[str, Any]) -> None: ...
    async def done(self) -> None: ...
    async def error(self, code: str, message: str, *, data: Optional[Dict[str, Any]] = None) -> None: ...


class SSEStream:
    """Async queue-backed SSE stream with optional heartbeats.

    Usage
        stream = SSEStream(heartbeat_interval_s=10)
        return StreamingResponse(stream.iter_sse(), media_type="text/event-stream")
    """

    def __init__(
        self,
        *,
        heartbeat_interval_s: Optional[float] = 10.0,
        heartbeat_mode: str = "comment",  # "comment" or "data"
        queue_maxsize: int = 1000,
        close_on_error: bool = True,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        self._queue: "asyncio.Queue[Tuple[str, float]]" = asyncio.Queue(maxsize=max(1, int(queue_maxsize)))
        self._hb_task: Optional[asyncio.Task] = None
        self._heartbeat_interval = heartbeat_interval_s if (heartbeat_interval_s or 0) > 0 else None
        self._heartbeat_mode = heartbeat_mode
        self._done_emitted = False
        self._closed = False
        self._lock = asyncio.Lock()
        self._close_on_error = bool(close_on_error)
        self._q_highwater = 0
        self._labels = dict(labels) if labels else None

    def _merge_labels(self, extra: Optional[Dict[str, str]] = None) -> Optional[Dict[str, str]]:
        if self._labels and extra:
            merged = {**self._labels, **extra}
            return merged
        return self._labels or extra

    async def _enqueue(self, line: str) -> None:
        # Backpressure policy: block on full queue
        t_enq = _time.perf_counter()
        await self._queue.put((line, t_enq))
        # track high-water mark
        try:
            depth = self._queue.qsize()
            if depth > self._q_highwater:
                self._q_highwater = depth
                set_gauge(
                    "sse_queue_high_watermark",
                    float(self._q_highwater),
                    labels=self._merge_labels({"transport": "sse"}),
                )
        except Exception:
            pass

    async def send_event(self, event: str, data: Any | None = None) -> None:
        if self._closed:
            return
        payload = {} if data is None else data
        block = f"event: {event}\n" + sse_data(payload)
        await self._enqueue(block)

    async def send_json(self, payload: Dict[str, Any]) -> None:
        if self._closed:
            return
        await self._enqueue(sse_data(payload))

    async def send_raw_sse_line(self, line: str) -> None:
        """SSE-specific helper: enqueue a raw SSE line (ensuring terminators)."""
        if self._closed:
            return
        await self._enqueue(ensure_sse_line(line))

    async def error(self, code: str, message: str, *, data: Optional[Dict[str, Any]] = None, close: Optional[bool] = None) -> None:
        if self._closed:
            return
        err = {"error": {"code": code, "message": message, "data": data}}
        await self._enqueue(sse_data(err))
        # Determine closure policy
        do_close = self._close_on_error if close is None else bool(close)
        if do_close:
            await self.done()

    async def done(self) -> None:
        async with self._lock:
            if self._done_emitted:
                self._closed = True
                return
            await self._enqueue(sse_done())
            self._done_emitted = True
            self._closed = True
            # Stop heartbeat
            if self._hb_task is not None:
                self._hb_task.cancel()
                self._hb_task = None

    async def _heartbeat_loop(self) -> None:
        try:
            # Small initial delay to let first payloads through
            interval = self._heartbeat_interval or 0
            if interval <= 0:
                return
            while not self._closed:
                await asyncio.sleep(interval)
                if self._closed:
                    break
                if self._heartbeat_mode == "data":
                    await self._enqueue(sse_data({"heartbeat": True}))
                else:
                    await self._enqueue(ensure_sse_line(":"))
        except asyncio.CancelledError:
            pass
        except Exception:
            # Heartbeat failures should never crash the stream; ignore
            pass

    async def _ensure_heartbeat(self) -> None:
        if self._hb_task is None and self._heartbeat_interval and self._heartbeat_interval > 0:
            self._hb_task = asyncio.create_task(self._heartbeat_loop())

    async def close(self) -> None:
        await self.done()

    async def __aenter__(self) -> "SSEStream":  # optional convenience
        await self._ensure_heartbeat()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.done()

    async def _dequeue(self) -> Optional[Tuple[str, float]]:
        try:
            return await self._queue.get()
        except asyncio.CancelledError:
            return None

    async def iter_sse(self) -> AsyncIterator[str]:
        await self._ensure_heartbeat()
        try:
            while True:
                item = await self._dequeue()
                if item is None:
                    break
                line, t_enq = item
                # measure enqueue->yield latency
                try:
                    dt_ms = max(0.0, (_time.perf_counter() - t_enq) * 1000.0)
                    observe_histogram(
                        "sse_enqueue_to_yield_ms",
                        dt_ms,
                        labels=self._merge_labels({"transport": "sse"}),
                    )
                except Exception:
                    pass
                yield line
                # When closed and queue drained, exit
                if self._closed and self._queue.empty():
                    break
        finally:
            if self._hb_task is not None:
                self._hb_task.cancel()
                self._hb_task = None


class WebSocketStream:
    """WebSocket streaming wrapper with standardized lifecycle frames and optional pings."""

    def __init__(
        self,
        websocket: Any,
        *,
        heartbeat_interval_s: Optional[float] = 10.0,
        close_on_done: bool = True,
        idle_timeout_s: Optional[float] = None,
        compat_error_type: bool = False,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        self.websocket = websocket
        self._hb_interval = heartbeat_interval_s if (heartbeat_interval_s or 0) > 0 else None
        self._idle_timeout = idle_timeout_s if (idle_timeout_s or 0) > 0 else None
        self._close_on_done = close_on_done
        self._hb_task: Optional[asyncio.Task] = None
        self._closed = False
        self._last_activity = asyncio.get_event_loop().time()
        self._compat_error_type = bool(compat_error_type)
        self._labels = dict(labels) if labels else None

    def _merge_labels(self, extra: Optional[Dict[str, str]] = None) -> Optional[Dict[str, str]]:
        if self._labels and extra:
            merged = {**self._labels, **extra}
            return merged
        return self._labels or extra

    def record_activity(self) -> None:
        try:
            self._last_activity = asyncio.get_event_loop().time()
        except Exception:
            pass

    async def send_event(self, event: str, data: Any | None = None) -> None:
        if self._closed:
            return
        t0 = _time.perf_counter()
        await self.websocket.send_json({"type": "event", "event": event, "data": data})
        try:
            dt_ms = max(0.0, (_time.perf_counter() - t0) * 1000.0)
            observe_histogram(
                "ws_send_latency_ms",
                dt_ms,
                labels=self._merge_labels({"transport": "ws", "kind": "event"}),
            )
        except Exception:
            pass
        self.record_activity()

    async def send_json(self, payload: Dict[str, Any]) -> None:
        if self._closed:
            return
        t0 = _time.perf_counter()
        await self.websocket.send_json(payload)
        try:
            dt_ms = max(0.0, (_time.perf_counter() - t0) * 1000.0)
            observe_histogram(
                "ws_send_latency_ms",
                dt_ms,
                labels=self._merge_labels({"transport": "ws", "kind": "json"}),
            )
        except Exception:
            pass
        self.record_activity()

    async def error(self, code: str, message: str, *, data: Optional[Dict[str, Any]] = None) -> None:
        if self._closed:
            return
        payload = {"type": "error", "code": code, "message": message, "data": data}
        if self._compat_error_type:
            payload["error_type"] = code
        t0 = _time.perf_counter()
        await self.websocket.send_json(payload)
        try:
            dt_ms = max(0.0, (_time.perf_counter() - t0) * 1000.0)
            observe_histogram(
                "ws_send_latency_ms",
                dt_ms,
                labels=self._merge_labels({"transport": "ws", "kind": "error"}),
            )
        except Exception:
            pass
        self.record_activity()
        # Do not close automatically here; callers decide policy per endpoint

    async def done(self) -> None:
        if self._closed:
            return
        t0 = _time.perf_counter()
        await self.websocket.send_json({"type": "done"})
        try:
            dt_ms = max(0.0, (_time.perf_counter() - t0) * 1000.0)
            observe_histogram(
                "ws_send_latency_ms",
                dt_ms,
                labels=self._merge_labels({"transport": "ws", "kind": "done"}),
            )
        except Exception:
            pass
        self.record_activity()
        if self._close_on_done:
            try:
                await self.websocket.close(code=1000, reason="done")
            finally:
                self._closed = True

    async def close(self, *, code: int = 1000, reason: str = "") -> None:
        if self._closed:
            return
        try:
            await self.websocket.close(code=code, reason=reason)
        finally:
            self._closed = True

    async def _ping_loop(self) -> None:
        try:
            if not self._hb_interval or self._hb_interval <= 0:
                return
            while not self._closed:
                await asyncio.sleep(self._hb_interval)
                if self._closed:
                    break
                # Idle timeout
                now = asyncio.get_event_loop().time()
                if self._idle_timeout and (now - self._last_activity) > max(1.0, float(self._idle_timeout)):
                    try:
                        increment_counter("ws_idle_timeouts_total", labels=self._merge_labels({"transport": "ws"}))
                    except Exception:
                        pass
                    await self.close(code=1001, reason="Idle timeout")
                    break
                try:
                    t0 = _time.perf_counter()
                    await self.websocket.send_json({"type": "ping"})
                    try:
                        dt_ms = max(0.0, (_time.perf_counter() - t0) * 1000.0)
                        observe_histogram(
                            "ws_send_latency_ms",
                            dt_ms,
                            labels=self._merge_labels({"transport": "ws", "kind": "ping"}),
                        )
                        increment_counter("ws_pings_total", labels=self._merge_labels({"transport": "ws"}))
                    except Exception:
                        pass
                except Exception:
                    # Consider ping failure as transport error and close
                    try:
                        increment_counter("ws_ping_failures_total", labels=self._merge_labels({"transport": "ws"}))
                    except Exception:
                        pass
                    await self.close(code=1011, reason="Ping failure")
                    break
        except asyncio.CancelledError:
            pass
        except Exception:
            # Do not crash on ping loop errors
            pass

    async def start(self) -> None:
        if self._hb_task is None and self._hb_interval and self._hb_interval > 0:
            self._hb_task = asyncio.create_task(self._ping_loop())

    async def stop(self) -> None:
        if self._hb_task is not None:
            self._hb_task.cancel()
            self._hb_task = None


__all__ = [
    "AsyncStream",
    "SSEStream",
    "WebSocketStream",
]
