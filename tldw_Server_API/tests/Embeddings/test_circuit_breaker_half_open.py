import time

import pytest

from tldw_Server_API.app.core.Embeddings.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerError,
)


def test_half_open_allows_sequential_calls_up_to_success_threshold():
    breaker = CircuitBreaker(
        name="half-open-test",
        failure_threshold=1,
        recovery_timeout=1.0,
        success_threshold=2,
        half_open_max_calls=1,
        expected_exception=ValueError,
    )

    def fail():
        raise ValueError("boom")

    with pytest.raises(ValueError):
        breaker.call(fail)

    assert breaker.is_open

    # Force transition to half-open for deterministic testing.
    breaker._last_failure_time = time.time() - 2.0  # beyond recovery_timeout
    assert breaker.state == CircuitState.HALF_OPEN

    def ok():
        return "ok"

    assert breaker.call(ok) == "ok"
    assert breaker.state == CircuitState.HALF_OPEN

    # Should not be rejected after the first half-open call completes.
    assert breaker.call(ok) == "ok"
    assert breaker.state == CircuitState.CLOSED

    with pytest.raises(CircuitBreakerError):
        # Confirm breaker stays closed/open behavior isn't impacted by the fix.
        breaker._state = CircuitState.OPEN
        breaker.call(ok)
