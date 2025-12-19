# provider_manager.py
# Description: Provider management with health checks, circuit breaker, and fallback support
#
# Imports
import asyncio
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from loguru import logger

#######################################################################################################################
#
# Types:

class ProviderStatus(Enum):
    """Provider health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CIRCUIT_OPEN = "circuit_open"

@dataclass
class ProviderHealth:
    """Provider health information."""
    provider_name: str
    status: ProviderStatus
    success_count: int = 0
    failure_count: int = 0
    last_success: Optional[float] = None
    last_failure: Optional[float] = None
    consecutive_failures: int = 0
    response_times: deque = field(default_factory=lambda: deque(maxlen=100))

#######################################################################################################################
#
# Constants:

# Circuit breaker thresholds
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5  # Open circuit after 5 consecutive failures
CIRCUIT_BREAKER_TIMEOUT = 60  # Try again after 60 seconds
CIRCUIT_BREAKER_HALF_OPEN_REQUESTS = 3  # Number of test requests in half-open state

# Health check intervals
HEALTH_CHECK_INTERVAL = 30  # Check health every 30 seconds
DEGRADED_THRESHOLD = 0.5  # Mark degraded if error rate > 50%

#######################################################################################################################
#
# Classes:

class CircuitBreaker:
    """
    Circuit breaker pattern implementation for provider failures.
    States: CLOSED (normal), OPEN (failing), HALF_OPEN (testing)

    Thread-safe: All state transitions are protected by a lock.
    """

    def __init__(
        self,
        failure_threshold: int = CIRCUIT_BREAKER_FAILURE_THRESHOLD,
        timeout: int = CIRCUIT_BREAKER_TIMEOUT,
        half_open_requests: int = CIRCUIT_BREAKER_HALF_OPEN_REQUESTS
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.half_open_requests = half_open_requests
        self._lock = threading.Lock()
        # Protected state - only access under _lock
        self._failure_count = 0
        self._last_failure_time = None
        self._state = "CLOSED"
        self._half_open_count = 0

    @property
    def failure_count(self) -> int:
        """Read-only access to failure count."""
        with self._lock:
            return self._failure_count

    @property
    def last_failure_time(self) -> Optional[float]:
        """Read-only access to last failure time."""
        with self._lock:
            return self._last_failure_time

    @property
    def state(self) -> str:
        """Read-only access to current state."""
        with self._lock:
            return self._state

    @property
    def half_open_count(self) -> int:
        """Read-only access to half-open count."""
        with self._lock:
            return self._half_open_count

    def call_succeeded(self):
        """Record a successful call. Thread-safe."""
        with self._lock:
            self._failure_count = 0
            if self._state == "HALF_OPEN":
                self._half_open_count += 1
                if self._half_open_count >= self.half_open_requests:
                    self._state = "CLOSED"
                    logger.info("Circuit breaker closed after successful recovery")

    def call_failed(self):
        """Record a failed call. Thread-safe."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == "HALF_OPEN":
                self._state = "OPEN"
                logger.warning("Circuit breaker reopened after failure in half-open state")
            elif self._failure_count >= self.failure_threshold:
                self._state = "OPEN"
                logger.warning(f"Circuit breaker opened after {self._failure_count} failures")

    def can_attempt_call(self) -> bool:
        """Check if a call can be attempted. Thread-safe."""
        with self._lock:
            if self._state == "CLOSED":
                return True

            if self._state == "OPEN":
                if self._last_failure_time and (time.time() - self._last_failure_time) > self.timeout:
                    self._state = "HALF_OPEN"
                    self._half_open_count = 0
                    logger.info("Circuit breaker entering half-open state for testing")
                    return True
                return False

            # HALF_OPEN state
            return self._half_open_count < self.half_open_requests


class ProviderManager:
    """
    Manages LLM providers with health checks, circuit breakers, and fallback support.
    """

    def __init__(self, providers: List[str], primary_provider: Optional[str] = None):
        """
        Initialize the provider manager.

        Args:
            providers: List of available provider names
            primary_provider: Primary provider to use (defaults to first in list)

        Raises:
            ValueError: If providers list is empty
        """
        if not providers:
            raise ValueError("At least one provider must be specified")

        self.providers = providers
        self.primary_provider = primary_provider or self.providers[0]

        # Validate primary provider is in the list
        if self.primary_provider not in self.providers:
            logger.warning(
                f"Primary provider '{self.primary_provider}' not in providers list, "
                f"using first provider '{self.providers[0]}'"
            )
            self.primary_provider = self.providers[0]

        self.health_status: Dict[str, ProviderHealth] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}

        # Lock for thread-safe health metrics updates
        self._metrics_lock = threading.Lock()

        # Initialize health tracking for each provider
        for provider in self.providers:
            self.health_status[provider] = ProviderHealth(
                provider_name=provider,
                status=ProviderStatus.HEALTHY
            )
            self.circuit_breakers[provider] = CircuitBreaker()

        # Start background health check task
        self._health_check_task = None

    async def start_health_checks(self):
        """Start background health monitoring."""
        if not self._health_check_task:
            self._health_check_task = asyncio.create_task(self._health_check_loop())

    async def stop_health_checks(self):
        """Stop background health monitoring."""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

    async def _health_check_loop(self):
        """Background task to periodically check provider health."""
        while True:
            try:
                await asyncio.sleep(HEALTH_CHECK_INTERVAL)
                for provider in self.providers:
                    await self._update_health_status(provider)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")

    async def _update_health_status(self, provider: str):
        """Update health status for a provider based on recent metrics."""
        if provider not in self.health_status:
            return

        with self._metrics_lock:
            health = self.health_status[provider]

            # Calculate error rate
            total_calls = health.success_count + health.failure_count
            if total_calls > 0:
                error_rate = health.failure_count / total_calls

                # Update status based on error rate and circuit breaker
                if self.circuit_breakers[provider].state == "OPEN":
                    health.status = ProviderStatus.CIRCUIT_OPEN
                elif error_rate > DEGRADED_THRESHOLD:
                    health.status = ProviderStatus.DEGRADED
                elif health.consecutive_failures >= 3:
                    health.status = ProviderStatus.UNHEALTHY
                else:
                    health.status = ProviderStatus.HEALTHY

            # Reset counters periodically (with atomic update)
            if total_calls > 1000:
                health.success_count = int(health.success_count * 0.5)
                health.failure_count = int(health.failure_count * 0.5)

    def record_success(self, provider: str, response_time: float):
        """
        Record a successful API call.

        This method is thread-safe.

        Args:
            provider: Provider name
            response_time: Response time in seconds
        """
        if provider not in self.health_status:
            return

        with self._metrics_lock:
            health = self.health_status[provider]
            health.success_count += 1
            health.consecutive_failures = 0
            health.last_success = time.time()
            health.response_times.append(response_time)

        # Circuit breaker update (has its own synchronization)
        self.circuit_breakers[provider].call_succeeded()

    def record_failure(self, provider: str, error: Optional[Exception] = None):
        """
        Record a failed API call.

        This method is thread-safe.

        Args:
            provider: Provider name
            error: The exception that occurred
        """
        if provider not in self.health_status:
            return

        with self._metrics_lock:
            health = self.health_status[provider]
            health.failure_count += 1
            health.consecutive_failures += 1
            health.last_failure = time.time()

        # Circuit breaker update (has its own synchronization)
        self.circuit_breakers[provider].call_failed()

        logger.warning(f"Provider {provider} failure recorded: {error}")

    def get_available_provider(self, exclude: Optional[List[str]] = None) -> Optional[str]:
        """
        Get the best available provider.

        This method is thread-safe for accessing health metrics.

        Args:
            exclude: List of providers to exclude

        Returns:
            Provider name or None if no providers available
        """
        exclude = exclude or []

        # Try primary provider first
        if self.primary_provider and self.primary_provider not in exclude:
            if self.circuit_breakers[self.primary_provider].can_attempt_call():
                return self.primary_provider

        # Find next best provider with lock protection for health metrics
        candidates = []
        with self._metrics_lock:
            for provider in self.providers:
                if provider in exclude:
                    continue

                if not self.circuit_breakers[provider].can_attempt_call():
                    continue

                health = self.health_status[provider]
                if health.status in [ProviderStatus.HEALTHY, ProviderStatus.DEGRADED]:
                    # Calculate average response time (copy deque contents under lock)
                    response_times_copy = list(health.response_times)
                    avg_response_time = (
                        sum(response_times_copy) / len(response_times_copy)
                        if response_times_copy else float('inf')
                    )
                    candidates.append((provider, health.status, avg_response_time))

        # Sort by status (HEALTHY first) and then by response time
        candidates.sort(key=lambda x: (x[1].value, x[2]))

        if candidates:
            selected = candidates[0][0]
            logger.info(f"Selected fallback provider: {selected}")
            return selected

        logger.error("No available providers found")
        return None

    def get_health_report(self) -> Dict[str, Dict[str, Any]]:
        """
        Get a health report for all providers.

        This method is thread-safe.

        Returns:
            Dictionary with health information for each provider
        """
        report = {}
        with self._metrics_lock:
            for provider, health in self.health_status.items():
                # Copy response times under lock to calculate average safely
                response_times_copy = list(health.response_times)
                avg_response_time = (
                    sum(response_times_copy) / len(response_times_copy)
                    if response_times_copy else None
                )

                report[provider] = {
                    "status": health.status.value,
                    "success_count": health.success_count,
                    "failure_count": health.failure_count,
                    "consecutive_failures": health.consecutive_failures,
                    "average_response_time": avg_response_time,
                    "circuit_breaker_state": self.circuit_breakers[provider].state,
                    "last_success": health.last_success,
                    "last_failure": health.last_failure
                }

        return report


# Global provider manager instance
_provider_manager: Optional[ProviderManager] = None
_provider_manager_init_lock = threading.Lock()

def get_provider_manager() -> Optional[ProviderManager]:
    """Get the global provider manager instance."""
    return _provider_manager

def initialize_provider_manager(providers: List[str], primary_provider: Optional[str] = None):
    """
    Initialize the global provider manager.

    This function is thread-safe and uses locking to prevent race conditions
    during concurrent initialization.

    Args:
        providers: List of available providers
        primary_provider: Primary provider to use
    """
    global _provider_manager
    with _provider_manager_init_lock:
        _provider_manager = ProviderManager(providers, primary_provider)
        return _provider_manager
