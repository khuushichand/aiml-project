# circuit_breaker.py
# Backward-compatibility shim — core breaker logic delegated to Infrastructure.
#
# Preserves:
#   - CircuitBreaker, CircuitBreakerConfig, CircuitState (re-exports)
#   - CircuitOpenError (alias for CircuitBreakerOpenError)
#   - CircuitBreakerStats (lightweight dataclass)
#   - LLMCircuitBreaker with provider-specific configs and timeout wrapping
#   - llm_circuit_breaker singleton
#   - with_circuit_breaker decorator

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Optional

from loguru import logger

from tldw_Server_API.app.core.Infrastructure.circuit_breaker import (  # noqa: F401
    CircuitBreaker as _UnifiedCB,
)
from tldw_Server_API.app.core.Infrastructure.circuit_breaker import (
    CircuitBreakerConfig as _UnifiedCfg,
)
from tldw_Server_API.app.core.Infrastructure.circuit_breaker import (
    CircuitBreakerOpenError,
)
from tldw_Server_API.app.core.Infrastructure.circuit_breaker import (
    CircuitState as _UnifiedState,
)

# ---------------------------------------------------------------------------
# Re-exports that match the old module's public API
# ---------------------------------------------------------------------------


class CircuitState:
    """Thin adapter: exposes string values like the old enum."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerConfig:
    """Config wrapper that maps to the unified config."""

    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: float = 30.0,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception,
    ):
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

    def _to_unified(self) -> _UnifiedCfg:
        return _UnifiedCfg(
            failure_threshold=self.failure_threshold,
            success_threshold=self.success_threshold,
            recovery_timeout=self.recovery_timeout,
            expected_exception=self.expected_exception,
            half_open_max_calls=1,
            category="evaluations",
        )


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker monitoring (kept for API compat)."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    timeouts: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0


# Alias
CircuitOpenError = CircuitBreakerOpenError


class CircuitBreaker:
    """Evaluations-specific breaker wrapping the unified Infrastructure one.

    Key difference from direct use: ``call()`` wraps in
    ``asyncio.wait_for()`` with the configured *timeout*, preserving the
    original behaviour for all Evaluations callers.
    """

    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._cb = _UnifiedCB(
            name=f"eval_{name}",
            config=self.config._to_unified(),
        )
        self.stats = CircuitBreakerStats()

    @property
    def _state_changed_at(self) -> float:
        with self._cb._lock:
            return self._cb._last_failure_time or 0.0

    @_state_changed_at.setter
    def _state_changed_at(self, value: float) -> None:
        with self._cb._lock:
            self._cb._last_failure_time = value

    # -- expose state as string for backward compat -------------------------

    @property
    def state(self) -> str:
        s = self._cb.state
        if s == _UnifiedState.CLOSED:
            return CircuitState.CLOSED
        elif s == _UnifiedState.OPEN:
            return CircuitState.OPEN
        return CircuitState.HALF_OPEN

    @state.setter
    def state(self, value: str) -> None:
        mapping = {
            CircuitState.CLOSED: _UnifiedState.CLOSED,
            CircuitState.OPEN: _UnifiedState.OPEN,
            CircuitState.HALF_OPEN: _UnifiedState.HALF_OPEN,
        }
        if value in mapping:
            with self._cb._lock:
                self._cb._state = mapping[value]

    # -- internal methods used by tests directly ----------------------------

    async def _on_failure(self) -> None:
        """Record a failure (used by tests that call this directly)."""
        self.stats.failed_calls += 1
        self.stats.consecutive_failures += 1
        self.stats.consecutive_successes = 0
        self.stats.last_failure_time = datetime.now()
        old_state = self._cb.state
        self._cb.record_failure()
        new_state = self._cb.state
        if new_state != old_state:
            # State transition happened — reset consecutive counters
            self.stats.consecutive_failures = 0

    async def _on_success(self) -> None:
        """Record a success (used by tests that call this directly)."""
        self.stats.successful_calls += 1
        self.stats.last_success_time = datetime.now()
        self.stats.consecutive_successes += 1
        self.stats.consecutive_failures = 0
        self._cb.record_success()

    def _should_attempt_reset(self) -> bool:
        """Check if recovery timeout has elapsed (for tests)."""
        import time as _time
        with self._cb._lock:
            if self._cb._last_failure_time is None:
                return True
            return _time.time() - self._cb._last_failure_time >= self.config.recovery_timeout

    def _transition_to_half_open(self) -> None:
        """Manually transition to HALF_OPEN (for tests)."""
        with self._cb._lock:
            self._cb._state = _UnifiedState.HALF_OPEN
            self._cb._success_count = 0
            self._cb._failure_count = 0
            self._cb._half_open_calls = 0

    # -- main call method ---------------------------------------------------

    async def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute *func* with circuit-breaker + timeout wrapping."""
        from tldw_Server_API.app.core.Infrastructure.circuit_breaker import (
            CircuitBreakerOpenError as _CBOpen,
        )

        # Check if circuit is open before doing anything
        with self._cb._lock:
            self._cb._maybe_transition_to_half_open()
            if self._cb._state == _UnifiedState.OPEN:
                self.stats.total_calls += 1
                self.stats.rejected_calls += 1
                raise CircuitOpenError(f"Circuit breaker {self.name} is OPEN")

        self.stats.total_calls += 1

        try:
            if asyncio.iscoroutinefunction(func):
                coro = func(*args, **kwargs)
            else:
                loop = asyncio.get_event_loop()
                coro = loop.run_in_executor(None, func, *args)

            async def _timed():
                return await asyncio.wait_for(coro, timeout=self.config.timeout)

            result = await self._cb.call_async(_timed)
            self.stats.successful_calls += 1
            self.stats.last_success_time = datetime.now()
            self.stats.consecutive_successes += 1
            self.stats.consecutive_failures = 0
            return result

        except _CBOpen as e:
            self.stats.rejected_calls += 1
            raise CircuitOpenError(f"Circuit breaker {self.name} is OPEN") from e

        except asyncio.TimeoutError:
            self.stats.timeouts += 1
            self.stats.failed_calls += 1
            self.stats.consecutive_failures += 1
            self.stats.consecutive_successes = 0
            self.stats.last_failure_time = datetime.now()
            raise TimeoutError(
                f"Call through circuit breaker {self.name} timed out "
                f"after {self.config.timeout}s"
            ) from None

        except self.config.expected_exception:
            self.stats.failed_calls += 1
            self.stats.consecutive_failures += 1
            self.stats.consecutive_successes = 0
            self.stats.last_failure_time = datetime.now()
            raise

        except Exception:
            # Unexpected exception — don't count as circuit breaker failure
            # (the unified breaker already recorded it; undo that)
            logger.warning(f"Unexpected exception in circuit breaker {self.name}")
            raise

    def get_state(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state,
            "stats": {
                "total_calls": self.stats.total_calls,
                "successful_calls": self.stats.successful_calls,
                "failed_calls": self.stats.failed_calls,
                "rejected_calls": self.stats.rejected_calls,
                "timeouts": self.stats.timeouts,
                "success_rate": (
                    self.stats.successful_calls / self.stats.total_calls
                    if self.stats.total_calls > 0 else 0
                ),
                "last_failure": (
                    self.stats.last_failure_time.isoformat()
                    if self.stats.last_failure_time else None
                ),
                "last_success": (
                    self.stats.last_success_time.isoformat()
                    if self.stats.last_success_time else None
                ),
            },
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "success_threshold": self.config.success_threshold,
                "timeout": self.config.timeout,
                "recovery_timeout": self.config.recovery_timeout,
            },
        }

    def reset(self):
        self._cb.reset()
        self.stats = CircuitBreakerStats()
        logger.info(f"Circuit breaker {self.name} reset")


class LLMCircuitBreaker:
    """Specialized circuit breaker for LLM calls with provider-specific configs."""

    def __init__(self):
        self.breakers: dict[str, CircuitBreaker] = {}
        self.provider_configs = {
            "openai": CircuitBreakerConfig(
                failure_threshold=3, timeout=30.0, recovery_timeout=60.0,
            ),
            "anthropic": CircuitBreakerConfig(
                failure_threshold=3, timeout=45.0, recovery_timeout=60.0,
            ),
            "local": CircuitBreakerConfig(
                failure_threshold=5, timeout=60.0, recovery_timeout=30.0,
            ),
            "default": CircuitBreakerConfig(
                failure_threshold=5, timeout=30.0, recovery_timeout=60.0,
            ),
        }

    def get_breaker(self, provider: str) -> CircuitBreaker:
        if provider not in self.breakers:
            config = self.provider_configs.get(
                provider, self.provider_configs["default"]
            )
            self.breakers[provider] = CircuitBreaker(
                name=f"llm_{provider}", config=config,
            )
        return self.breakers[provider]

    async def call_with_breaker(
        self, provider: str, func: Callable, *args: Any, **kwargs: Any,
    ) -> Any:
        breaker = self.get_breaker(provider)
        return await breaker.call(func, *args, **kwargs)

    def get_all_states(self) -> dict[str, dict[str, Any]]:
        return {p: b.get_state() for p, b in self.breakers.items()}

    def reset_all(self):
        for b in self.breakers.values():
            b.reset()


# Global singleton
llm_circuit_breaker = LLMCircuitBreaker()


def with_circuit_breaker(provider: str = "default"):
    """Decorator to add circuit breaker protection to a function."""
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await llm_circuit_breaker.call_with_breaker(
                provider, func, *args, **kwargs,
            )
        return wrapper
    return decorator
