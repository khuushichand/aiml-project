# circuit_breaker.py
# Circuit breaker pattern implementation for embeddings service
# Provides fault tolerance and prevents cascading failures

import asyncio
import threading
import time
from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

from loguru import logger

from tldw_Server_API.app.core.Metrics.metrics_manager import increment_counter, set_gauge

# Type variables for generic typing
T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = 0      # Normal operation, requests pass through
    OPEN = 1        # Circuit broken, requests fail immediately
    HALF_OPEN = 2   # Testing if service recovered


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open"""
    pass


class CircuitBreaker:
    """
    Circuit breaker implementation for fault tolerance.

    The circuit breaker pattern prevents cascading failures by failing fast
    when a service is unavailable, giving it time to recover.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service is failing, requests fail immediately
    - HALF_OPEN: Testing if service has recovered
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception,
        success_threshold: int = 2,
        half_open_max_calls: int = 3,
        category: str = "embeddings",
        service: Optional[str] = None,
        operation: str = "call",
    ):
        """
        Initialize circuit breaker.

        Args:
            name: Identifier for this circuit breaker
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before trying half-open
            expected_exception: Exception type to catch (others pass through)
            success_threshold: Successes needed in half-open to close circuit
            half_open_max_calls: Max concurrent calls in half-open state
            category: Metrics category label
            service: Metrics service label override
            operation: Metrics operation label for call outcomes
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.success_threshold = success_threshold
        self.half_open_max_calls = half_open_max_calls
        self.category = category
        self.service = service or name
        self.operation = operation

        # State management
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0

        # Thread safety
        self._lock = threading.RLock()

        logger.info(
            f"Circuit breaker '{name}' initialized: "
            f"failure_threshold={failure_threshold}, "
            f"recovery_timeout={recovery_timeout}s"
        )

    def _metric_labels(self, operation: str) -> dict[str, str]:
        return {
            "category": self.category,
            "service": self.service,
            "operation": operation,
        }

    def _record_state(self, state: "CircuitState"):
        set_gauge(
            "circuit_breaker_state",
            state.value,
            labels=self._metric_labels("state_change"),
        )

    def _record_trip(self, reason: str):
        increment_counter(
            "circuit_breaker_trips_total",
            labels={
                "category": self.category,
                "service": self.service,
                "reason": reason,
            },
        )

    def _record_rejection(self):
        increment_counter(
            "circuit_breaker_rejections_total",
            labels=self._metric_labels(self.operation),
        )

    @property
    def state(self) -> CircuitState:
        """Get current circuit state, updating if necessary"""
        with self._lock:
            self._update_state()
            return self._state

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)"""
        return self.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (failing)"""
        return self.state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing)"""
        return self.state == CircuitState.HALF_OPEN

    def _update_state(self):
        """Update circuit state based on current conditions"""
        if self._state == CircuitState.OPEN:
            if self._last_failure_time and \
               time.time() - self._last_failure_time >= self.recovery_timeout:
                # Enough time has passed, try half-open
                self._transition_to_half_open()

    def _transition_to_closed(self):
        """Transition to closed state"""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._record_state(CircuitState.CLOSED)

        logger.info(f"Circuit breaker '{self.name}' CLOSED")

    def _transition_to_open(self, reason: str):
        """Transition to open state"""
        self._state = CircuitState.OPEN
        self._last_failure_time = time.time()
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._record_state(CircuitState.OPEN)
        self._record_trip(reason)

        logger.warning(
            f"Circuit breaker '{self.name}' OPEN - "
            f"will retry in {self.recovery_timeout}s"
        )

    def _transition_to_half_open(self):
        """Transition to half-open state"""
        self._state = CircuitState.HALF_OPEN
        self._success_count = 0
        self._failure_count = 0
        self._half_open_calls = 0
        self._record_state(CircuitState.HALF_OPEN)

        logger.info(f"Circuit breaker '{self.name}' HALF-OPEN (testing recovery)")

    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute function through circuit breaker.

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerError: If circuit is open
            Exception: If function fails
        """
        acquired_half_open_slot = False
        with self._lock:
            self._update_state()

            if self._state == CircuitState.OPEN:
                self._record_rejection()
                raise CircuitBreakerError(
                    f"Circuit breaker '{self.name}' is OPEN"
                )

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    self._record_rejection()
                    raise CircuitBreakerError(
                        f"Circuit breaker '{self.name}' half-open call limit reached"
                    )
                self._half_open_calls += 1
                acquired_half_open_slot = True

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure(e)
            raise
        finally:
            if acquired_half_open_slot:
                with self._lock:
                    if self._state == CircuitState.HALF_OPEN and self._half_open_calls > 0:
                        self._half_open_calls -= 1

    async def call_async(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute async function through circuit breaker.

        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerError: If circuit is open
            Exception: If function fails
        """
        acquired_half_open_slot = False
        with self._lock:
            self._update_state()

            if self._state == CircuitState.OPEN:
                self._record_rejection()
                raise CircuitBreakerError(
                    f"Circuit breaker '{self.name}' is OPEN"
                )

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    self._record_rejection()
                    raise CircuitBreakerError(
                        f"Circuit breaker '{self.name}' half-open call limit reached"
                    )
                self._half_open_calls += 1
                acquired_half_open_slot = True

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure(e)
            raise
        finally:
            if acquired_half_open_slot:
                with self._lock:
                    if self._state == CircuitState.HALF_OPEN and self._half_open_calls > 0:
                        self._half_open_calls -= 1

    def _on_success(self):
        """Handle successful call"""
        with self._lock:
            increment_counter(
                "circuit_breaker_successes_total",
                labels=self._metric_labels(self.operation),
            )

            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    self._transition_to_closed()
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success in closed state
                self._failure_count = 0

    def _on_failure(self, error: Optional[Exception] = None):
        """Handle failed call"""
        with self._lock:
            outcome = type(error).__name__ if error else "error"
            increment_counter(
                "circuit_breaker_failures_total",
                labels={
                    "category": self.category,
                    "service": self.service,
                    "operation": self.operation,
                    "outcome": outcome,
                },
            )

            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                # Single failure in half-open reopens circuit
                self._transition_to_open("half_open_failure")
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.failure_threshold:
                    self._transition_to_open("failure_threshold")

    def reset(self):
        """Manually reset circuit breaker to closed state"""
        with self._lock:
            self._transition_to_closed()
            logger.info(f"Circuit breaker '{self.name}' manually reset")

    def get_status(self) -> dict[str, Any]:
        """Get circuit breaker status"""
        with self._lock:
            return {
                "name": self.name,
                "state": self._state.name,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "last_failure_time": self._last_failure_time,
                "half_open_calls": self._half_open_calls,
                "settings": {
                    "failure_threshold": self.failure_threshold,
                    "recovery_timeout": self.recovery_timeout,
                    "success_threshold": self.success_threshold,
                    "half_open_max_calls": self.half_open_max_calls
                }
            }


def circuit_breaker(
    name: Optional[str] = None,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    expected_exception: type = Exception,
    success_threshold: int = 2
):
    """
    Decorator to apply circuit breaker pattern to a function.

    Args:
        name: Circuit breaker name (defaults to function name)
        failure_threshold: Failures before opening circuit
        recovery_timeout: Seconds before trying half-open
        expected_exception: Exception type to catch
        success_threshold: Successes needed to close from half-open

    Example:
        @circuit_breaker(name="openai_api", failure_threshold=3)
        async def call_openai_api():
            # API call that might fail
            pass
    """
    def decorator(func):
        breaker_name = name or f"{func.__module__}.{func.__name__}"
        breaker = CircuitBreaker(
            name=breaker_name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=expected_exception,
            success_threshold=success_threshold
        )

        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await breaker.call_async(func, *args, **kwargs)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                return breaker.call(func, *args, **kwargs)
            return sync_wrapper

    return decorator


# Global circuit breaker registry for management
class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers"""

    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()

    def register(self, breaker: CircuitBreaker):
        """Register a circuit breaker"""
        with self._lock:
            self._breakers[breaker.name] = breaker

    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name"""
        return self._breakers.get(name)

    def get_all_status(self) -> dict[str, dict[str, Any]]:
        """Get status of all circuit breakers"""
        with self._lock:
            return {
                name: breaker.get_status()
                for name, breaker in self._breakers.items()
            }

    def reset_all(self):
        """Reset all circuit breakers"""
        with self._lock:
            for breaker in self._breakers.values():
                breaker.reset()


# Global registry instance
registry = CircuitBreakerRegistry()
