# circuit_breaker.py
"""
Unified circuit breaker module for the tldw_server project.

Provides a single, shared implementation of the circuit breaker pattern
used across all modules (Embeddings, Evaluations, TTS, RAG, Chat, MCP,
WebSearch). Supports both sync and async callers, counter and rolling-window
failure detection, exponential backoff on recovery timeout, serial half-open
probes, state-change callbacks, and Prometheus-style metrics emission.

Design decisions
----------------
- **In-memory only** -- no DB persistence.
- **Serial half-open probes** (``half_open_max_calls=1`` by default).
- **Always starts CLOSED.**
- **Original exceptions re-raised as-is** -- the breaker records failures
  internally but never wraps the original error.
- **State-change callbacks** for modules that need them (TTS health
  monitoring, RAG coordinator).
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections import deque
from dataclasses import dataclass
from enum import IntEnum
from functools import wraps
from typing import Any, Callable, TypeVar

from loguru import logger

T = TypeVar("T")

# ---------------------------------------------------------------------------
# Metrics helpers -- graceful no-op if metrics_manager is unavailable
# ---------------------------------------------------------------------------

try:
    from tldw_Server_API.app.core.Metrics.metrics_manager import (
        increment_counter as _increment_counter,
    )
    from tldw_Server_API.app.core.Metrics.metrics_manager import (
        set_gauge as _set_gauge,
    )
except Exception:  # noqa: BLE001
    def _increment_counter(metric_name: str, value: float = 1, labels: dict[str, str] | None = None) -> None:  # type: ignore[misc]
        pass

    def _set_gauge(metric_name: str, value: float = 0, labels: dict[str, str] | None = None) -> None:  # type: ignore[misc]
        pass


# ---------------------------------------------------------------------------
# Metrics configuration
# ---------------------------------------------------------------------------

# When True, emit metrics with legacy ``service="{category}:{name}"`` labels
# in addition to the standard labels.
_EMIT_LEGACY_ALIASES: bool = True

# Label validation allow-lists (unknown labels normalised to ``"other"``)
_VALID_CATEGORIES: set[str] = {
    "", "embeddings", "evaluations", "tts", "rag", "chat", "mcp",
    "websearch", "test_cat", "test", "my_cat",
}
_VALID_REASONS: set[str] = {
    "", "unknown", "threshold", "half_open_failure", "timeout",
}

_warned_labels: set[str] = set()


def _validate_label(value: str, valid_set: set[str], kind: str) -> str:
    """Return *value* if known, else ``"other"`` with a one-shot warning."""
    if value in valid_set:
        return value
    key = f"{kind}:{value}"
    if key not in _warned_labels:
        _warned_labels.add(key)
        logger.warning("Unknown circuit-breaker {} label {!r}, normalising to 'other'", kind, value)
    return "other"


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

class CircuitState(IntEnum):
    """Circuit breaker states (int values for gauge metric compatibility)."""
    CLOSED = 0
    OPEN = 1
    HALF_OPEN = 2


@dataclass(frozen=True)
class CircuitBreakerConfig:
    """Configuration for a :class:`CircuitBreaker` instance.

    This dataclass is frozen (immutable).  Use :meth:`CircuitBreaker.update_config`
    to replace the config at runtime.
    """

    failure_threshold: int = 5
    """Consecutive failures (counter mode) before tripping to OPEN."""

    success_threshold: int = 2
    """Consecutive successes in HALF_OPEN before returning to CLOSED."""

    recovery_timeout: float = 60.0
    """Seconds to wait in OPEN before transitioning to HALF_OPEN."""

    half_open_max_calls: int = 1
    """Max concurrent probe calls allowed in HALF_OPEN (serial by default)."""

    expected_exception: type | tuple = Exception
    """Exception type(s) that count as circuit-breaker failures.
    Exceptions *not* matching this are always re-raised without recording."""

    # Rolling-window mode (disabled when window_size == 0)
    window_size: int = 0
    """Rolling-window size.  ``0`` = counter mode; ``>0`` = rolling-window."""

    failure_rate_threshold: float = 0.5
    """Failure rate (0..1) at which the breaker trips in rolling-window mode."""

    # Minimum calls before tripping
    min_calls: int = 0
    """Minimum number of calls in the rolling window before the breaker can
    trip.  ``0`` means use *window_size* as minimum (backward-compat)."""

    # Call timeout (async only)
    call_timeout: float | None = None
    """If set, wraps ``call_async`` in ``asyncio.wait_for()`` with this timeout."""

    # Exponential backoff on recovery timeout
    backoff_factor: float = 1.0
    """Multiplier applied to *recovery_timeout* after each HALF_OPEN → OPEN
    transition.  ``1.0`` = no backoff; ``2.0`` = double each time."""

    max_recovery_timeout: float = 300.0
    """Upper bound for the recovery timeout after backoff."""

    # Metrics labels
    category: str = ""
    """Arbitrary label emitted with every metric (e.g. ``"embeddings"``)."""

    service: str = ""
    """Service label for metrics; falls back to the breaker's *name*."""

    operation: str = "call"
    """Operation label for success/failure counters."""

    # Metrics opt-out
    emit_metrics: bool = True
    """Set to ``False`` to suppress all metric emissions for this breaker."""


class CircuitBreakerOpenError(Exception):
    """Raised when a call is rejected because the circuit is OPEN.

    Attributes carry enough context for callers to build rich error
    responses (HTTP 503, retry-after headers, etc.).
    """

    def __init__(
        self,
        message: str,
        *,
        breaker_name: str = "",
        category: str = "",
        service: str = "",
        recovery_timeout: float = 0.0,
        failure_count: int = 0,
        recovery_at: float | None = None,
    ):
        super().__init__(message)
        self.breaker_name = breaker_name
        self.category = category
        self.service = service
        self.recovery_timeout = recovery_timeout
        self.failure_count = failure_count
        self.recovery_at = recovery_at


# ---------------------------------------------------------------------------
# CircuitBreaker
# ---------------------------------------------------------------------------

class CircuitBreaker:
    """Unified circuit breaker supporting sync and async callers.

    Parameters are supplied via a :class:`CircuitBreakerConfig` dataclass
    (or as individual keyword arguments for backward compatibility).

    Two failure-detection modes are supported:

    * **Counter mode** (``config.window_size == 0``): the circuit opens after
      ``failure_threshold`` consecutive failures.  A single success resets
      the counter.
    * **Rolling-window mode** (``config.window_size > 0``): a fixed-size
      deque records recent call outcomes and the breaker trips when the
      failure *rate* reaches ``failure_rate_threshold`` **and** the window
      is full.
    """

    def __init__(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
        *,
        on_state_change: list[Callable] | None = None,
        # Convenience kwargs that populate a config when *config* is None:
        failure_threshold: int | None = None,
        recovery_timeout: float | None = None,
        expected_exception: type | tuple | None = None,
        success_threshold: int | None = None,
        half_open_max_calls: int | None = None,
        category: str | None = None,
        service: str | None = None,
        operation: str | None = None,
        window_size: int | None = None,
        failure_rate_threshold: float | None = None,
        backoff_factor: float | None = None,
        max_recovery_timeout: float | None = None,
    ):
        if config is None:
            kwargs: dict[str, Any] = {}
            if failure_threshold is not None:
                kwargs["failure_threshold"] = failure_threshold
            if recovery_timeout is not None:
                kwargs["recovery_timeout"] = recovery_timeout
            if expected_exception is not None:
                kwargs["expected_exception"] = expected_exception
            if success_threshold is not None:
                kwargs["success_threshold"] = success_threshold
            if half_open_max_calls is not None:
                kwargs["half_open_max_calls"] = half_open_max_calls
            if category is not None:
                kwargs["category"] = category
            if service is not None:
                kwargs["service"] = service
            if operation is not None:
                kwargs["operation"] = operation
            if window_size is not None:
                kwargs["window_size"] = window_size
            if failure_rate_threshold is not None:
                kwargs["failure_rate_threshold"] = failure_rate_threshold
            if backoff_factor is not None:
                kwargs["backoff_factor"] = backoff_factor
            if max_recovery_timeout is not None:
                kwargs["max_recovery_timeout"] = max_recovery_timeout
            config = CircuitBreakerConfig(**kwargs)

        self.name = name
        self.config = config

        # Resolve metrics labels
        self._category = config.category or ""
        self._service = config.service or name
        self._operation = config.operation or "call"

        # State
        self._state: CircuitState = CircuitState.CLOSED
        self._failure_count: int = 0
        self._success_count: int = 0
        self._last_failure_time: float | None = None
        self._half_open_calls: int = 0

        # Rolling window (only used when window_size > 0)
        self._window: deque[bool] | None = None
        if config.window_size > 0:
            self._window = deque(maxlen=config.window_size)

        # State-change tracking
        self._last_state_change_time: float = time.time()

        # Exponential backoff state
        self._current_recovery_timeout: float = config.recovery_timeout

        # Callbacks: list[Callable[[CircuitBreaker, CircuitState, CircuitState], None]]
        self.on_state_change: list[Callable] = list(on_state_change or [])

        # Thread safety (sync path)
        self._lock = threading.RLock()

        # Async lock (lazy-initialized per event-loop)
        self._async_lock: asyncio.Lock | None = None

        logger.debug(
            "Circuit breaker '{}' initialized: failure_threshold={}, "
            "recovery_timeout={}s, window_size={}",
            name,
            config.failure_threshold,
            config.recovery_timeout,
            config.window_size,
        )

    # -- convenience properties ---------------------------------------------

    @property
    def state(self) -> CircuitState:
        with self._lock:
            self._maybe_transition_to_half_open()
            return self._state

    @property
    def failure_count(self) -> int:
        with self._lock:
            return self._failure_count

    @property
    def success_count(self) -> int:
        with self._lock:
            return self._success_count

    @property
    def is_closed(self) -> bool:
        return self.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        return self.state == CircuitState.HALF_OPEN

    @property
    def last_state_change_time(self) -> float:
        """Timestamp of the most recent state transition."""
        with self._lock:
            return self._last_state_change_time

    @property
    def last_failure_time(self) -> float | None:
        """Timestamp of the most recent recorded failure."""
        with self._lock:
            return self._last_failure_time

    @property
    def current_recovery_timeout(self) -> float:
        """Current recovery timeout (may differ from config if backoff active)."""
        with self._lock:
            return self._current_recovery_timeout

    @property
    def half_open_calls(self) -> int:
        """Number of currently active half-open probe calls."""
        with self._lock:
            return self._half_open_calls

    # -- check-pattern API (for Chat, WebSearch) ----------------------------

    def can_attempt(self) -> bool:
        """Return *True* if a call would be allowed right now.

        Does **not** consume a half-open slot; use :meth:`call` /
        :meth:`call_async` for gated execution, or pair ``can_attempt``
        with ``record_success`` / ``record_failure`` manually.
        """
        with self._lock:
            self._maybe_transition_to_half_open()
            if self._state == CircuitState.OPEN:
                return False
            if self._state == CircuitState.HALF_OPEN:
                return self._half_open_calls < self.config.half_open_max_calls
            return True

    def record_success(self) -> None:
        """Manually record a success (check-pattern API)."""
        with self._lock:
            self._on_success()

    def record_failure(self, error: Exception | None = None) -> None:
        """Manually record a failure (check-pattern API)."""
        with self._lock:
            self._on_failure(error)

    # -- sync execution -----------------------------------------------------

    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute *func* through the circuit breaker (sync).

        Raises :class:`CircuitBreakerOpenError` when the circuit is OPEN
        (or HALF_OPEN with no probe slots left).  On failure, the original
        exception is re-raised after being recorded.
        """
        with self._lock:
            self._maybe_transition_to_half_open()
            self._guard_or_raise()
            acquired_slot = self._acquire_half_open_slot()

        try:
            result = func(*args, **kwargs)
        except BaseException as exc:
            if isinstance(exc, self.config.expected_exception):
                with self._lock:
                    self._on_failure(exc)
            raise
        else:
            with self._lock:
                self._on_success()
            return result
        finally:
            if acquired_slot:
                with self._lock:
                    if self._half_open_calls > 0:
                        self._half_open_calls -= 1

    # -- async execution ----------------------------------------------------

    async def call_async(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute *func* through the circuit breaker (async).

        Works identically to :meth:`call` but awaits the wrapped function.
        If ``config.call_timeout`` is set, wraps the call in
        ``asyncio.wait_for()``.
        """
        # Use threading lock for state checks (fast, no I/O).
        with self._lock:
            self._maybe_transition_to_half_open()
            self._guard_or_raise()
            acquired_slot = self._acquire_half_open_slot()

        try:
            if self.config.call_timeout is not None:
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=self.config.call_timeout,
                )
            else:
                result = await func(*args, **kwargs)
        except asyncio.TimeoutError:
            with self._lock:
                self._on_failure(None)
                self._emit_timeout()
            raise
        except BaseException as exc:
            if isinstance(exc, self.config.expected_exception):
                with self._lock:
                    self._on_failure(exc)
            raise
        else:
            with self._lock:
                self._on_success()
            return result
        finally:
            if acquired_slot:
                with self._lock:
                    if self._half_open_calls > 0:
                        self._half_open_calls -= 1

    # -- admin / introspection ----------------------------------------------

    def reset(self) -> None:
        """Manually reset to CLOSED (e.g. after a deploy or config change)."""
        with self._lock:
            old = self._state
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._half_open_calls = 0
            self._last_failure_time = None
            self._last_state_change_time = time.time()
            self._current_recovery_timeout = self.config.recovery_timeout
            if self._window is not None:
                self._window.clear()
            self._emit_state_gauge()
            if old != CircuitState.CLOSED:
                self._fire_callbacks(old, CircuitState.CLOSED)
            logger.info("Circuit breaker '{}' manually reset", self.name)

    def update_config(self, new_config: CircuitBreakerConfig) -> None:
        """Replace the breaker's config with *new_config* under lock.

        Since ``CircuitBreakerConfig`` is frozen, this replaces the entire
        object.  Re-derives metrics labels and adjusts the rolling window
        if ``window_size`` changed.
        """
        with self._lock:
            old_config = self.config
            self.config = new_config
            self._category = new_config.category or ""
            self._service = new_config.service or self.name
            self._operation = new_config.operation or "call"
            self._current_recovery_timeout = new_config.recovery_timeout

            # Adjust window if window_size changed
            if new_config.window_size > 0:
                if self._window is None or self._window.maxlen != new_config.window_size:
                    self._window = deque(maxlen=new_config.window_size)
            elif new_config.window_size == 0:
                self._window = None

            logger.info(
                "Circuit breaker '{}' config updated: {} -> {}",
                self.name,
                old_config,
                new_config,
            )

    def get_status(self) -> dict[str, Any]:
        """Return a JSON-serialisable snapshot of the breaker's state."""
        with self._lock:
            self._maybe_transition_to_half_open()
            result: dict[str, Any] = {
                "name": self.name,
                "state": self._state.name,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "last_failure_time": self._last_failure_time,
                "last_state_change_time": self._last_state_change_time,
                "half_open_calls": self._half_open_calls,
                "current_recovery_timeout": self._current_recovery_timeout,
                "settings": {
                    "failure_threshold": self.config.failure_threshold,
                    "recovery_timeout": self.config.recovery_timeout,
                    "success_threshold": self.config.success_threshold,
                    "half_open_max_calls": self.config.half_open_max_calls,
                    "window_size": self.config.window_size,
                    "failure_rate_threshold": self.config.failure_rate_threshold,
                    "backoff_factor": self.config.backoff_factor,
                    "max_recovery_timeout": self.config.max_recovery_timeout,
                    "min_calls": self.config.min_calls,
                    "call_timeout": self.config.call_timeout,
                    "emit_metrics": self.config.emit_metrics,
                },
            }
            if self._window is not None:
                result["window"] = list(self._window)
                result["failure_rate"] = (
                    sum(1 for r in self._window if not r) / len(self._window)
                    if self._window
                    else 0.0
                )
            return result

    # -- internal state machine ---------------------------------------------

    def _maybe_transition_to_half_open(self) -> None:
        """If OPEN and recovery timeout elapsed, move to HALF_OPEN.

        Must be called while ``self._lock`` is held.
        """
        if (
            self._state == CircuitState.OPEN
            and self._last_failure_time is not None
            and time.time() - self._last_failure_time >= self._current_recovery_timeout
        ):
            self._transition(CircuitState.HALF_OPEN)

    def _guard_or_raise(self) -> None:
        """Raise :class:`CircuitBreakerOpenError` if the call should be rejected.

        Must be called while ``self._lock`` is held.
        """
        if self._state == CircuitState.OPEN:
            self._emit_rejection()
            recovery_at = (
                self._last_failure_time + self._current_recovery_timeout
                if self._last_failure_time else None
            )
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.name}' is OPEN",
                breaker_name=self.name,
                category=self._category,
                service=self._service,
                recovery_timeout=self._current_recovery_timeout,
                failure_count=self._failure_count,
                recovery_at=recovery_at,
            )
        if self._state == CircuitState.HALF_OPEN:
            if self._half_open_calls >= self.config.half_open_max_calls:
                self._emit_rejection()
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' HALF_OPEN probe limit reached",
                    breaker_name=self.name,
                    category=self._category,
                    service=self._service,
                    recovery_timeout=self._current_recovery_timeout,
                    failure_count=self._failure_count,
                )

    def _acquire_half_open_slot(self) -> bool:
        """Try to acquire a half-open probe slot.  Returns *True* if acquired.

        Must be called while ``self._lock`` is held.
        """
        if self._state == CircuitState.HALF_OPEN:
            self._half_open_calls += 1
            return True
        return False

    def _on_success(self) -> None:
        """Record a successful call.  Must be called while ``self._lock`` is held."""
        self._emit_success()

        if self._window is not None:
            self._window.append(True)

        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.config.success_threshold:
                self._transition(CircuitState.CLOSED)
        elif self._state == CircuitState.CLOSED:
            # In counter mode a success resets the failure counter
            if self._window is None:
                self._failure_count = 0

    def _on_failure(self, error: Exception | None = None) -> None:
        """Record a failed call.  Must be called while ``self._lock`` is held."""
        self._emit_failure(error)
        self._last_failure_time = time.time()

        if self._window is not None:
            self._window.append(False)

        self._failure_count += 1

        if self._state == CircuitState.HALF_OPEN:
            # Any failure in half-open re-opens the circuit
            self._transition(CircuitState.OPEN, reason="half_open_failure")
        elif self._state == CircuitState.CLOSED:
            if self._should_trip():
                self._transition(CircuitState.OPEN, reason="threshold")

    def _should_trip(self) -> bool:
        """Decide whether the breaker should trip from CLOSED → OPEN.

        Must be called while ``self._lock`` is held.
        """
        if self._window is not None:
            # Rolling-window mode
            effective_min = self.config.min_calls or self.config.window_size
            if len(self._window) >= effective_min:
                rate = sum(1 for r in self._window if not r) / len(self._window)
                return rate >= self.config.failure_rate_threshold
            return False
        # Counter mode
        return self._failure_count >= self.config.failure_threshold

    def _transition(self, new_state: CircuitState, *, reason: str = "") -> None:
        """Perform a state transition.  Must be called while ``self._lock`` is held."""
        old = self._state
        if old == new_state:
            return

        self._state = new_state
        self._last_state_change_time = time.time()

        if new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._success_count = 0
            self._half_open_calls = 0
            self._current_recovery_timeout = self.config.recovery_timeout
            if self._window is not None:
                self._window.clear()
            logger.info("Circuit breaker '{}' CLOSED", self.name)

        elif new_state == CircuitState.OPEN:
            if old == CircuitState.HALF_OPEN and self.config.backoff_factor > 1.0:
                self._current_recovery_timeout = min(
                    self._current_recovery_timeout * self.config.backoff_factor,
                    self.config.max_recovery_timeout,
                )
            self._failure_count = 0
            self._success_count = 0
            self._half_open_calls = 0
            self._last_failure_time = time.time()
            self._emit_trip(reason)
            logger.warning(
                "Circuit breaker '{}' OPEN — retry in {:.1f}s",
                self.name,
                self._current_recovery_timeout,
            )

        elif new_state == CircuitState.HALF_OPEN:
            self._success_count = 0
            self._failure_count = 0
            self._half_open_calls = 0
            logger.info("Circuit breaker '{}' HALF_OPEN (probing)", self.name)

        self._emit_state_gauge()
        self._fire_callbacks(old, new_state)

    # -- callbacks ----------------------------------------------------------

    def _fire_callbacks(self, old: CircuitState, new: CircuitState) -> None:
        for cb in self.on_state_change:
            try:
                cb(self, old, new)
            except Exception:  # noqa: BLE001
                logger.opt(exception=True).warning(
                    "State-change callback error in breaker '{}'", self.name
                )

    # -- metrics emission ---------------------------------------------------

    def _metric_labels(self, operation: str) -> dict[str, str]:
        return {
            "category": self._category,
            "service": self._service,
            "operation": operation,
        }

    def _emit_state_gauge(self) -> None:
        if not self.config.emit_metrics:
            return
        _set_gauge(
            "circuit_breaker_state",
            float(self._state.value),
            labels=self._metric_labels("state_change"),
        )

    def _emit_trip(self, reason: str) -> None:
        if not self.config.emit_metrics:
            return
        validated_reason = _validate_label(reason or "unknown", _VALID_REASONS, "reason")
        labels = {
            "category": self._category,
            "service": self._service,
            "reason": validated_reason,
        }
        _increment_counter("circuit_breaker_trips_total", labels=labels)
        if _EMIT_LEGACY_ALIASES and self._category:
            _increment_counter(
                "circuit_breaker_trips_total",
                labels={**labels, "service": f"{self._category}:{self._service}"},
            )

    def _emit_rejection(self) -> None:
        if not self.config.emit_metrics:
            return
        _increment_counter(
            "circuit_breaker_rejections_total",
            labels=self._metric_labels(self._operation),
        )

    def _emit_success(self) -> None:
        if not self.config.emit_metrics:
            return
        _increment_counter(
            "circuit_breaker_successes_total",
            labels=self._metric_labels(self._operation),
        )

    def _emit_failure(self, error: Exception | None = None) -> None:
        if not self.config.emit_metrics:
            return
        outcome = type(error).__name__ if error else "error"
        _increment_counter(
            "circuit_breaker_failures_total",
            labels={
                "category": self._category,
                "service": self._service,
                "operation": self._operation,
                "outcome": outcome,
            },
        )

    def _emit_timeout(self) -> None:
        """Emit the ``circuit_breaker_timeouts_total`` counter."""
        if not self.config.emit_metrics:
            return
        _increment_counter(
            "circuit_breaker_timeouts_total",
            labels=self._metric_labels(self._operation),
        )

    # -- repr ---------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"<CircuitBreaker name={self.name!r} state={self._state.name} "
            f"failures={self._failure_count}>"
        )


# ---------------------------------------------------------------------------
# CircuitBreakerRegistry
# ---------------------------------------------------------------------------

class CircuitBreakerRegistry:
    """Thread-safe registry for managing named :class:`CircuitBreaker` instances."""

    def __init__(self) -> None:
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()

    def get_or_create(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
        **kwargs: Any,
    ) -> CircuitBreaker:
        """Return an existing breaker or create and register a new one.

        If a breaker with *name* already exists and *config* is provided,
        a warning is logged if the configs differ.
        """
        with self._lock:
            if name in self._breakers:
                existing = self._breakers[name]
                if config is not None and config != existing.config:
                    logger.warning(
                        "get_or_create('{}') called with different config; "
                        "returning existing breaker. Old: {}, New: {}",
                        name, existing.config, config,
                    )
                return existing
            breaker = CircuitBreaker(name, config=config, **kwargs)
            self._breakers[name] = breaker
            return breaker

    def register(self, breaker: CircuitBreaker) -> None:
        """Register a pre-built breaker (replaces any existing one with the same name)."""
        with self._lock:
            self._breakers[breaker.name] = breaker

    def get(self, name: str) -> CircuitBreaker | None:
        """Look up a breaker by *name* (or ``None``)."""
        return self._breakers.get(name)

    def remove(self, name: str) -> bool:
        """Remove a breaker by *name*.  Returns ``True`` if it was found."""
        with self._lock:
            return self._breakers.pop(name, None) is not None

    def get_all_status(self) -> dict[str, dict[str, Any]]:
        """Return ``{name: status_dict}`` for every registered breaker."""
        with self._lock:
            return {
                name: breaker.get_status()
                for name, breaker in self._breakers.items()
            }

    def reset_all(self) -> None:
        """Reset every registered breaker to CLOSED."""
        with self._lock:
            for breaker in self._breakers.values():
                breaker.reset()

    def reset(self, name: str) -> bool:
        """Reset a single breaker by name.  Returns ``True`` if found."""
        breaker = self._breakers.get(name)
        if breaker is not None:
            breaker.reset()
            return True
        return False


# Global singleton registry
registry = CircuitBreakerRegistry()


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------

def circuit_breaker(
    name: str | None = None,
    config: CircuitBreakerConfig | None = None,
    *,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    expected_exception: type | tuple = Exception,
    success_threshold: int = 2,
    half_open_max_calls: int = 1,
    category: str = "",
    service: str = "",
    operation: str = "call",
) -> Callable:
    """Decorator that wraps a function with a circuit breaker.

    The breaker is registered in the global :data:`registry`.  Auto-detects
    sync vs async callables.

    Example::

        @circuit_breaker(name="openai_api", failure_threshold=3)
        async def call_openai_api():
            ...
    """
    def decorator(func: Callable) -> Callable:
        breaker_name = name or f"{func.__module__}.{func.__qualname__}"
        cfg = config or CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=expected_exception,
            success_threshold=success_threshold,
            half_open_max_calls=half_open_max_calls,
            category=category,
            service=service or breaker_name,
            operation=operation,
        )
        breaker = registry.get_or_create(breaker_name, config=cfg)

        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args: Any, **kw: Any) -> Any:
                return await breaker.call_async(func, *args, **kw)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args: Any, **kw: Any) -> Any:
                return breaker.call(func, *args, **kw)
            return sync_wrapper

    return decorator


# ---------------------------------------------------------------------------
# Public API summary
# ---------------------------------------------------------------------------

__all__ = [
    "CircuitBreakerConfig",
    "CircuitBreakerOpenError",
    "CircuitBreaker",
    "CircuitBreakerRegistry",
    "CircuitState",
    "circuit_breaker",
    "registry",
]
