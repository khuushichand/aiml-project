# test_circuit_breaker.py
"""Tests for the unified circuit breaker module."""

import asyncio
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from tldw_Server_API.app.core.Infrastructure.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    CircuitBreakerRegistry,
    CircuitState,
    circuit_breaker,
    registry,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TransientError(Exception):
    """Test exception that should trip the breaker."""


class PermanentError(Exception):
    """Test exception that should NOT trip the breaker."""


def _succeed() -> str:
    return "ok"


def _fail_transient() -> str:
    raise TransientError("boom")


def _fail_permanent() -> str:
    raise PermanentError("fatal")


async def _async_succeed() -> str:
    return "ok"


async def _async_fail() -> str:
    raise TransientError("boom")


# ---------------------------------------------------------------------------
# TestConfig
# ---------------------------------------------------------------------------

class TestConfig:
    def test_defaults(self):
        cfg = CircuitBreakerConfig()
        assert cfg.failure_threshold == 5
        assert cfg.success_threshold == 2
        assert cfg.recovery_timeout == 60.0
        assert cfg.half_open_max_calls == 1
        assert cfg.expected_exception is Exception
        assert cfg.window_size == 0
        assert cfg.failure_rate_threshold == 0.5
        assert cfg.backoff_factor == 1.0
        assert cfg.max_recovery_timeout == 300.0

    def test_custom_values(self):
        cfg = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=1,
            recovery_timeout=30.0,
            half_open_max_calls=2,
            expected_exception=TransientError,
            window_size=10,
            failure_rate_threshold=0.3,
            backoff_factor=2.0,
            max_recovery_timeout=600.0,
            category="test",
            service="svc",
            operation="op",
        )
        assert cfg.failure_threshold == 3
        assert cfg.window_size == 10
        assert cfg.backoff_factor == 2.0


# ---------------------------------------------------------------------------
# TestOpenError
# ---------------------------------------------------------------------------

class TestOpenError:
    def test_attributes(self):
        err = CircuitBreakerOpenError(
            "test msg",
            breaker_name="b1",
            category="cat",
            service="svc",
            recovery_timeout=30.0,
            failure_count=5,
        )
        assert str(err) == "test msg"
        assert err.breaker_name == "b1"
        assert err.category == "cat"
        assert err.service == "svc"
        assert err.recovery_timeout == 30.0
        assert err.failure_count == 5

    def test_default_attributes(self):
        err = CircuitBreakerOpenError("test")
        assert err.breaker_name == ""
        assert err.recovery_timeout == 0.0


# ---------------------------------------------------------------------------
# TestStateTransitions (sync)
# ---------------------------------------------------------------------------

class TestStateTransitionsSync:
    def test_starts_closed(self):
        cb = CircuitBreaker("test", config=CircuitBreakerConfig(failure_threshold=2))
        assert cb.state == CircuitState.CLOSED
        assert cb.is_closed

    def test_opens_after_threshold(self):
        cb = CircuitBreaker("test", config=CircuitBreakerConfig(failure_threshold=2))
        for _ in range(2):
            with pytest.raises(TransientError):
                cb.call(_fail_transient)
        assert cb.is_open

    def test_rejects_when_open(self):
        cb = CircuitBreaker("test", config=CircuitBreakerConfig(failure_threshold=1))
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        assert cb.is_open
        with pytest.raises(CircuitBreakerOpenError):
            cb.call(_succeed)

    def test_half_open_after_timeout(self):
        cb = CircuitBreaker(
            "test",
            config=CircuitBreakerConfig(failure_threshold=1, recovery_timeout=0.05),
        )
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        assert cb.is_open
        time.sleep(0.06)
        assert cb.is_half_open

    def test_closes_after_success_threshold(self):
        cb = CircuitBreaker(
            "test",
            config=CircuitBreakerConfig(
                failure_threshold=1,
                recovery_timeout=0.05,
                success_threshold=2,
            ),
        )
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        time.sleep(0.06)
        # Two successes needed
        cb.call(_succeed)
        assert cb.is_half_open  # still half-open after 1
        cb.call(_succeed)
        assert cb.is_closed

    def test_reopens_on_half_open_failure(self):
        cb = CircuitBreaker(
            "test",
            config=CircuitBreakerConfig(
                failure_threshold=1,
                recovery_timeout=0.05,
                success_threshold=2,
            ),
        )
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        time.sleep(0.06)
        assert cb.is_half_open
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        assert cb.is_open

    def test_success_resets_failure_count_in_closed(self):
        cb = CircuitBreaker("test", config=CircuitBreakerConfig(failure_threshold=3))
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        cb.call(_succeed)
        # failure count reset, so 2 more failures should NOT open
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        assert cb.is_closed
        # 3rd failure (from 0) opens
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        assert cb.is_open


# ---------------------------------------------------------------------------
# TestStateTransitions (async)
# ---------------------------------------------------------------------------

class TestStateTransitionsAsync:
    @pytest.mark.asyncio
    async def test_async_success(self):
        cb = CircuitBreaker("test-async")
        result = await cb.call_async(_async_succeed)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_async_opens_after_threshold(self):
        cb = CircuitBreaker("test-async", config=CircuitBreakerConfig(failure_threshold=2))
        for _ in range(2):
            with pytest.raises(TransientError):
                await cb.call_async(_async_fail)
        assert cb.is_open

    @pytest.mark.asyncio
    async def test_async_rejects_when_open(self):
        cb = CircuitBreaker("test-async", config=CircuitBreakerConfig(failure_threshold=1))
        with pytest.raises(TransientError):
            await cb.call_async(_async_fail)
        with pytest.raises(CircuitBreakerOpenError):
            await cb.call_async(_async_succeed)

    @pytest.mark.asyncio
    async def test_async_half_open_recovery(self):
        cb = CircuitBreaker(
            "test-async",
            config=CircuitBreakerConfig(
                failure_threshold=1,
                recovery_timeout=0.05,
                success_threshold=1,
            ),
        )
        with pytest.raises(TransientError):
            await cb.call_async(_async_fail)
        await asyncio.sleep(0.06)
        result = await cb.call_async(_async_succeed)
        assert result == "ok"
        assert cb.is_closed


# ---------------------------------------------------------------------------
# TestCounterMode
# ---------------------------------------------------------------------------

class TestCounterMode:
    def test_counter_mode_default(self):
        cb = CircuitBreaker(
            "counter",
            config=CircuitBreakerConfig(failure_threshold=3, window_size=0),
        )
        assert cb._window is None
        for _ in range(2):
            with pytest.raises(TransientError):
                cb.call(_fail_transient)
        assert cb.is_closed
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        assert cb.is_open

    def test_counter_mode_success_resets(self):
        cb = CircuitBreaker(
            "counter",
            config=CircuitBreakerConfig(failure_threshold=3, window_size=0),
        )
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        cb.call(_succeed)
        # Counter reset; need 3 more failures
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        assert cb.is_closed


# ---------------------------------------------------------------------------
# TestRollingWindowMode
# ---------------------------------------------------------------------------

class TestRollingWindowMode:
    def test_window_mode_trips_on_rate(self):
        cb = CircuitBreaker(
            "window",
            config=CircuitBreakerConfig(
                window_size=4,
                failure_rate_threshold=0.5,
                failure_threshold=999,  # ignored in window mode
            ),
        )
        assert cb._window is not None
        # 2 successes, 2 failures = 50% rate → should trip
        cb.call(_succeed)
        cb.call(_succeed)
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        assert cb.is_closed  # only 3 calls, window not full
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        assert cb.is_open  # 4 calls, 50% failure rate

    def test_window_mode_does_not_trip_below_rate(self):
        cb = CircuitBreaker(
            "window",
            config=CircuitBreakerConfig(
                window_size=4,
                failure_rate_threshold=0.5,
            ),
        )
        cb.call(_succeed)
        cb.call(_succeed)
        cb.call(_succeed)
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        assert cb.is_closed  # 25% rate < 50% threshold

    def test_window_slides(self):
        cb = CircuitBreaker(
            "window",
            config=CircuitBreakerConfig(
                window_size=4,
                failure_rate_threshold=0.5,
                recovery_timeout=0.05,
                success_threshold=1,
            ),
        )
        # Fill window with 4 failures → trips
        for _ in range(4):
            with pytest.raises(TransientError):
                cb.call(_fail_transient)
        assert cb.is_open
        time.sleep(0.06)
        # Window cleared on close, start fresh
        cb.call(_succeed)
        assert cb.is_closed


# ---------------------------------------------------------------------------
# TestHalfOpenSerialProbes
# ---------------------------------------------------------------------------

class TestHalfOpenSerialProbes:
    def test_default_serial_probe(self):
        cb = CircuitBreaker(
            "serial",
            config=CircuitBreakerConfig(
                failure_threshold=1,
                recovery_timeout=0.05,
                half_open_max_calls=1,
                success_threshold=1,
            ),
        )
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        time.sleep(0.06)
        assert cb.is_half_open

        # First call takes the slot and succeeds → closes
        cb.call(_succeed)
        assert cb.is_closed

    def test_serial_probe_needs_multiple_successes(self):
        cb = CircuitBreaker(
            "serial",
            config=CircuitBreakerConfig(
                failure_threshold=1,
                recovery_timeout=0.05,
                half_open_max_calls=1,
                success_threshold=2,
            ),
        )
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        time.sleep(0.06)

        # First success doesn't close — still half-open
        cb.call(_succeed)
        assert cb.is_half_open
        # Second success closes
        cb.call(_succeed)
        assert cb.is_closed

    def test_multiple_probe_slots(self):
        cb = CircuitBreaker(
            "multi",
            config=CircuitBreakerConfig(
                failure_threshold=1,
                recovery_timeout=0.05,
                half_open_max_calls=3,
                success_threshold=2,
            ),
        )
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        time.sleep(0.06)
        cb.call(_succeed)
        cb.call(_succeed)
        assert cb.is_closed


# ---------------------------------------------------------------------------
# TestExponentialBackoff
# ---------------------------------------------------------------------------

class TestExponentialBackoff:
    def test_backoff_increases_timeout(self):
        cb = CircuitBreaker(
            "backoff",
            config=CircuitBreakerConfig(
                failure_threshold=1,
                recovery_timeout=0.05,
                success_threshold=1,
                backoff_factor=2.0,
                max_recovery_timeout=1.0,
            ),
        )
        # First trip
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        assert cb._current_recovery_timeout == 0.05  # no backoff on first trip from CLOSED
        time.sleep(0.06)
        assert cb.is_half_open
        # Fail again in half-open → re-opens with backoff
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        assert cb.is_open
        assert cb._current_recovery_timeout == pytest.approx(0.10)

    def test_backoff_caps_at_max(self):
        cb = CircuitBreaker(
            "backoff-cap",
            config=CircuitBreakerConfig(
                failure_threshold=1,
                recovery_timeout=0.05,
                success_threshold=1,
                backoff_factor=100.0,
                max_recovery_timeout=0.5,
            ),
        )
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        time.sleep(0.06)
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        assert cb._current_recovery_timeout == pytest.approx(0.5)

    def test_no_backoff_when_factor_is_one(self):
        cb = CircuitBreaker(
            "no-backoff",
            config=CircuitBreakerConfig(
                failure_threshold=1,
                recovery_timeout=0.05,
                success_threshold=1,
                backoff_factor=1.0,
            ),
        )
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        time.sleep(0.06)
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        assert cb._current_recovery_timeout == pytest.approx(0.05)

    def test_backoff_resets_on_close(self):
        cb = CircuitBreaker(
            "backoff-reset",
            config=CircuitBreakerConfig(
                failure_threshold=1,
                recovery_timeout=0.05,
                success_threshold=1,
                backoff_factor=2.0,
            ),
        )
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        time.sleep(0.06)
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        assert cb._current_recovery_timeout == pytest.approx(0.10)
        time.sleep(0.11)
        cb.call(_succeed)
        assert cb.is_closed
        assert cb._current_recovery_timeout == pytest.approx(0.05)


# ---------------------------------------------------------------------------
# TestExpectedExceptionFiltering
# ---------------------------------------------------------------------------

class TestExpectedExceptionFiltering:
    def test_expected_exception_trips(self):
        cb = CircuitBreaker(
            "filter",
            config=CircuitBreakerConfig(
                failure_threshold=1,
                expected_exception=TransientError,
            ),
        )
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        assert cb.is_open

    def test_unexpected_exception_does_not_trip(self):
        cb = CircuitBreaker(
            "filter",
            config=CircuitBreakerConfig(
                failure_threshold=1,
                expected_exception=TransientError,
            ),
        )
        with pytest.raises(PermanentError):
            cb.call(_fail_permanent)
        assert cb.is_closed  # PermanentError is not TransientError

    def test_tuple_expected_exceptions(self):
        cb = CircuitBreaker(
            "filter-tuple",
            config=CircuitBreakerConfig(
                failure_threshold=1,
                expected_exception=(TransientError, PermanentError),
            ),
        )
        with pytest.raises(PermanentError):
            cb.call(_fail_permanent)
        assert cb.is_open


# ---------------------------------------------------------------------------
# TestCallbacks
# ---------------------------------------------------------------------------

class TestCallbacks:
    def test_state_change_callback_fires(self):
        log = []

        def on_change(breaker, old, new):
            log.append((old, new))

        cb = CircuitBreaker(
            "cb-callback",
            config=CircuitBreakerConfig(failure_threshold=1, recovery_timeout=0.05),
            on_state_change=[on_change],
        )
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        assert (CircuitState.CLOSED, CircuitState.OPEN) in log

        time.sleep(0.06)
        _ = cb.state  # triggers half-open
        assert (CircuitState.OPEN, CircuitState.HALF_OPEN) in log

    def test_callback_error_does_not_propagate(self):
        def bad_callback(breaker, old, new):
            raise RuntimeError("callback error")

        cb = CircuitBreaker(
            "cb-bad",
            config=CircuitBreakerConfig(failure_threshold=1),
            on_state_change=[bad_callback],
        )
        # Should not raise even though callback throws
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        assert cb.is_open

    def test_callback_receives_breaker_ref(self):
        received = []

        def on_change(breaker, old, new):
            received.append(breaker.name)

        cb = CircuitBreaker(
            "cb-ref",
            config=CircuitBreakerConfig(failure_threshold=1),
            on_state_change=[on_change],
        )
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        assert received == ["cb-ref"]


# ---------------------------------------------------------------------------
# TestMetricsEmission
# ---------------------------------------------------------------------------

class TestMetricsEmission:
    @patch("tldw_Server_API.app.core.Infrastructure.circuit_breaker._increment_counter")
    @patch("tldw_Server_API.app.core.Infrastructure.circuit_breaker._set_gauge")
    def test_metrics_on_trip(self, mock_gauge, mock_counter):
        cb = CircuitBreaker(
            "metrics",
            config=CircuitBreakerConfig(
                failure_threshold=1,
                category="test_cat",
                service="test_svc",
            ),
        )
        with pytest.raises(TransientError):
            cb.call(_fail_transient)

        # Should have emitted failure counter and trip counter
        failure_calls = [
            c for c in mock_counter.call_args_list
            if c[0][0] == "circuit_breaker_failures_total"
        ]
        assert len(failure_calls) >= 1

        trip_calls = [
            c for c in mock_counter.call_args_list
            if c[0][0] == "circuit_breaker_trips_total"
        ]
        assert len(trip_calls) >= 1

        # Should have set state gauge
        gauge_calls = [
            c for c in mock_gauge.call_args_list
            if c[0][0] == "circuit_breaker_state"
        ]
        assert len(gauge_calls) >= 1

    @patch("tldw_Server_API.app.core.Infrastructure.circuit_breaker._increment_counter")
    @patch("tldw_Server_API.app.core.Infrastructure.circuit_breaker._set_gauge")
    def test_metrics_on_success(self, mock_gauge, mock_counter):
        cb = CircuitBreaker("metrics-ok")
        cb.call(_succeed)
        success_calls = [
            c for c in mock_counter.call_args_list
            if c[0][0] == "circuit_breaker_successes_total"
        ]
        assert len(success_calls) == 1

    @patch("tldw_Server_API.app.core.Infrastructure.circuit_breaker._increment_counter")
    @patch("tldw_Server_API.app.core.Infrastructure.circuit_breaker._set_gauge")
    def test_metrics_on_rejection(self, mock_gauge, mock_counter):
        cb = CircuitBreaker("metrics-rej", config=CircuitBreakerConfig(failure_threshold=1))
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        with pytest.raises(CircuitBreakerOpenError):
            cb.call(_succeed)
        rejection_calls = [
            c for c in mock_counter.call_args_list
            if c[0][0] == "circuit_breaker_rejections_total"
        ]
        assert len(rejection_calls) >= 1


# ---------------------------------------------------------------------------
# TestRegistry
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_get_or_create(self):
        reg = CircuitBreakerRegistry()
        cb1 = reg.get_or_create("r1")
        cb2 = reg.get_or_create("r1")
        assert cb1 is cb2

    def test_get_or_create_different_names(self):
        reg = CircuitBreakerRegistry()
        cb1 = reg.get_or_create("r1")
        cb2 = reg.get_or_create("r2")
        assert cb1 is not cb2

    def test_register_and_get(self):
        reg = CircuitBreakerRegistry()
        cb = CircuitBreaker("manual")
        reg.register(cb)
        assert reg.get("manual") is cb

    def test_get_missing_returns_none(self):
        reg = CircuitBreakerRegistry()
        assert reg.get("nonexistent") is None

    def test_get_all_status(self):
        reg = CircuitBreakerRegistry()
        reg.get_or_create("s1")
        reg.get_or_create("s2")
        status = reg.get_all_status()
        assert "s1" in status
        assert "s2" in status
        assert status["s1"]["state"] == "CLOSED"

    def test_reset_all(self):
        reg = CircuitBreakerRegistry()
        cb = reg.get_or_create("reset-all", config=CircuitBreakerConfig(failure_threshold=1))
        cb.record_failure(TransientError("test"))
        assert cb.is_open
        reg.reset_all()
        assert cb.is_closed

    def test_reset_by_name(self):
        reg = CircuitBreakerRegistry()
        cb = reg.get_or_create("reset-one", config=CircuitBreakerConfig(failure_threshold=1))
        cb.record_failure(TransientError("test"))
        assert cb.is_open
        assert reg.reset("reset-one") is True
        assert cb.is_closed
        assert reg.reset("nonexistent") is False


# ---------------------------------------------------------------------------
# TestDecorator
# ---------------------------------------------------------------------------

class TestDecorator:
    def test_sync_decorator(self):
        @circuit_breaker(name="dec-sync-test", failure_threshold=1)
        def my_func():
            return 42

        assert my_func() == 42

    def test_sync_decorator_trips(self):
        @circuit_breaker(name="dec-sync-trip", failure_threshold=1)
        def my_func():
            raise TransientError("boom")

        with pytest.raises(TransientError):
            my_func()
        with pytest.raises(CircuitBreakerOpenError):
            my_func()

    @pytest.mark.asyncio
    async def test_async_decorator(self):
        @circuit_breaker(name="dec-async-test", failure_threshold=1)
        async def my_func():
            return 42

        assert await my_func() == 42

    @pytest.mark.asyncio
    async def test_async_decorator_trips(self):
        @circuit_breaker(name="dec-async-trip", failure_threshold=1)
        async def my_func():
            raise TransientError("boom")

        with pytest.raises(TransientError):
            await my_func()
        with pytest.raises(CircuitBreakerOpenError):
            await my_func()

    def test_decorator_registers_in_global_registry(self):
        @circuit_breaker(name="dec-global-test")
        def my_func():
            return 1

        assert registry.get("dec-global-test") is not None


# ---------------------------------------------------------------------------
# TestCheckPatternAPI
# ---------------------------------------------------------------------------

class TestCheckPatternAPI:
    def test_can_attempt_when_closed(self):
        cb = CircuitBreaker("check")
        assert cb.can_attempt() is True

    def test_can_attempt_when_open(self):
        cb = CircuitBreaker("check", config=CircuitBreakerConfig(failure_threshold=1))
        cb.record_failure(TransientError("test"))
        assert cb.can_attempt() is False

    def test_record_success_closes_from_half_open(self):
        cb = CircuitBreaker(
            "check",
            config=CircuitBreakerConfig(
                failure_threshold=1,
                recovery_timeout=0.05,
                success_threshold=1,
            ),
        )
        cb.record_failure(TransientError("test"))
        assert cb.is_open
        time.sleep(0.06)
        assert cb.can_attempt() is True
        cb.record_success()
        assert cb.is_closed

    def test_record_failure_reopens_from_half_open(self):
        cb = CircuitBreaker(
            "check",
            config=CircuitBreakerConfig(
                failure_threshold=1,
                recovery_timeout=0.05,
            ),
        )
        cb.record_failure(TransientError("test"))
        time.sleep(0.06)
        cb.record_failure(TransientError("again"))
        assert cb.is_open


# ---------------------------------------------------------------------------
# TestConcurrency
# ---------------------------------------------------------------------------

class TestConcurrency:
    def test_thread_safety(self):
        cb = CircuitBreaker(
            "concurrent",
            config=CircuitBreakerConfig(failure_threshold=100),
        )
        errors = []

        def worker():
            try:
                for _ in range(50):
                    try:
                        cb.call(_succeed)
                    except CircuitBreakerOpenError:
                        pass
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert cb.is_closed

    def test_concurrent_failures(self):
        cb = CircuitBreaker(
            "concurrent-fail",
            config=CircuitBreakerConfig(failure_threshold=10),
        )
        errors = []

        def worker():
            try:
                for _ in range(5):
                    try:
                        cb.call(_fail_transient)
                    except (TransientError, CircuitBreakerOpenError):
                        pass
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert cb.is_open


# ---------------------------------------------------------------------------
# TestGetStatus
# ---------------------------------------------------------------------------

class TestGetStatus:
    def test_status_fields(self):
        cb = CircuitBreaker("status-test", config=CircuitBreakerConfig(category="cat"))
        status = cb.get_status()
        assert status["name"] == "status-test"
        assert status["state"] == "CLOSED"
        assert status["failure_count"] == 0
        assert status["success_count"] == 0
        assert status["last_failure_time"] is None
        assert "settings" in status

    def test_status_with_window(self):
        cb = CircuitBreaker("status-win", config=CircuitBreakerConfig(window_size=5))
        cb.call(_succeed)
        status = cb.get_status()
        assert "window" in status
        assert "failure_rate" in status
        assert status["window"] == [True]
        assert status["failure_rate"] == 0.0


# ---------------------------------------------------------------------------
# TestReset
# ---------------------------------------------------------------------------

class TestReset:
    def test_reset_from_open(self):
        cb = CircuitBreaker("reset-test", config=CircuitBreakerConfig(failure_threshold=1))
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        assert cb.is_open
        cb.reset()
        assert cb.is_closed
        assert cb.failure_count == 0

    def test_reset_clears_window(self):
        cb = CircuitBreaker("reset-win", config=CircuitBreakerConfig(window_size=5))
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        cb.reset()
        assert len(cb._window) == 0

    def test_reset_resets_backoff(self):
        cb = CircuitBreaker(
            "reset-bo",
            config=CircuitBreakerConfig(
                failure_threshold=1,
                recovery_timeout=0.05,
                backoff_factor=2.0,
            ),
        )
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        time.sleep(0.06)
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        assert cb._current_recovery_timeout > 0.05
        cb.reset()
        assert cb._current_recovery_timeout == pytest.approx(0.05)

    def test_reset_fires_callback(self):
        log = []
        cb = CircuitBreaker(
            "reset-cb",
            config=CircuitBreakerConfig(failure_threshold=1),
            on_state_change=[lambda b, o, n: log.append((o, n))],
        )
        with pytest.raises(TransientError):
            cb.call(_fail_transient)
        log.clear()
        cb.reset()
        assert (CircuitState.OPEN, CircuitState.CLOSED) in log


# ---------------------------------------------------------------------------
# TestConvenienceKwargs
# ---------------------------------------------------------------------------

class TestConvenienceKwargs:
    def test_kwargs_create_config(self):
        cb = CircuitBreaker(
            "kw-test",
            failure_threshold=3,
            recovery_timeout=10.0,
            category="my_cat",
        )
        assert cb.config.failure_threshold == 3
        assert cb.config.recovery_timeout == 10.0
        assert cb._category == "my_cat"

    def test_config_takes_precedence(self):
        cfg = CircuitBreakerConfig(failure_threshold=7)
        cb = CircuitBreaker("kw-cfg", config=cfg, failure_threshold=3)
        assert cb.config.failure_threshold == 7  # config wins


# ---------------------------------------------------------------------------
# TestRepr
# ---------------------------------------------------------------------------

class TestRepr:
    def test_repr(self):
        cb = CircuitBreaker("repr-test")
        r = repr(cb)
        assert "repr-test" in r
        assert "CLOSED" in r
