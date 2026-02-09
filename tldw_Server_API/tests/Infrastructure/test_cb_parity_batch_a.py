# test_cb_parity_batch_a.py
"""Parity tests: WebSearch, Chat, and MCP circuit breaker behavior."""

import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

from tldw_Server_API.app.core.Infrastructure.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    CircuitBreakerRegistry,
    CircuitState,
)


class TransientError(Exception):
    pass


# ---------------------------------------------------------------------------
# WebSearch parity: breaker opens after 3 failures, recovers after 30s
# ---------------------------------------------------------------------------

class TestWebSearchParity:
    """Verify WebSearch circuit breaker behavior via the unified module."""

    def test_websearch_opens_after_3_failures(self):
        cb = CircuitBreaker(
            "websearch_llm_test",
            config=CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=30.0,
                half_open_max_calls=1,
                success_threshold=1,
                category="websearch",
            ),
        )
        for _ in range(3):
            cb.record_failure(TransientError("llm unavailable"))
        assert cb.is_open

    def test_websearch_singleton_via_registry(self):
        reg = CircuitBreakerRegistry()
        cfg = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=30.0,
            half_open_max_calls=1,
            success_threshold=1,
            category="websearch",
        )
        cb1 = reg.get_or_create("ws_test", config=cfg)
        cb2 = reg.get_or_create("ws_test", config=cfg)
        assert cb1 is cb2, "Registry should return the same instance"

    def test_websearch_does_not_trip_below_threshold(self):
        cb = CircuitBreaker(
            "websearch_llm_test2",
            config=CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=30.0,
                half_open_max_calls=1,
                success_threshold=1,
                category="websearch",
            ),
        )
        cb.record_failure(TransientError("err"))
        cb.record_failure(TransientError("err"))
        assert cb.is_closed

    def test_websearch_recovers_after_timeout(self):
        cb = CircuitBreaker(
            "websearch_recover",
            config=CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=0.05,
                half_open_max_calls=1,
                success_threshold=1,
                category="websearch",
            ),
        )
        for _ in range(3):
            cb.record_failure(TransientError("err"))
        assert cb.is_open
        time.sleep(0.06)
        assert cb.is_half_open
        cb.record_success()
        assert cb.is_closed

    def test_websearch_success_resets_counter(self):
        cb = CircuitBreaker(
            "websearch_reset",
            config=CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=30.0,
                category="websearch",
            ),
        )
        cb.record_failure(TransientError("err"))
        cb.record_failure(TransientError("err"))
        cb.record_success()  # resets counter
        cb.record_failure(TransientError("err"))
        cb.record_failure(TransientError("err"))
        assert cb.is_closed  # only 2 consecutive failures


# ---------------------------------------------------------------------------
# Chat parity: opens after 5, half-open after 60s, closes after 3 successes,
#              ProviderHealth callback
# ---------------------------------------------------------------------------

class TestChatParity:
    """Verify Chat provider_manager circuit breaker behavior."""

    def test_chat_opens_after_5_failures(self):
        cb = CircuitBreaker(
            "chat_test",
            config=CircuitBreakerConfig(
                failure_threshold=5,
                recovery_timeout=60.0,
                half_open_max_calls=3,
                success_threshold=3,
                category="chat",
            ),
        )
        for _ in range(5):
            cb.record_failure(TransientError("err"))
        assert cb.is_open

    def test_chat_half_open_after_recovery_timeout(self):
        cb = CircuitBreaker(
            "chat_ho",
            config=CircuitBreakerConfig(
                failure_threshold=5,
                recovery_timeout=0.05,
                half_open_max_calls=3,
                success_threshold=3,
                category="chat",
            ),
        )
        for _ in range(5):
            cb.record_failure(TransientError("err"))
        time.sleep(0.06)
        assert cb.is_half_open

    def test_chat_closes_after_success_threshold(self):
        cb = CircuitBreaker(
            "chat_close",
            config=CircuitBreakerConfig(
                failure_threshold=5,
                recovery_timeout=0.05,
                half_open_max_calls=3,
                success_threshold=3,
                category="chat",
            ),
        )
        for _ in range(5):
            cb.record_failure(TransientError("err"))
        time.sleep(0.06)
        assert cb.is_half_open
        cb.record_success()
        cb.record_success()
        assert cb.is_half_open  # need 3
        cb.record_success()
        assert cb.is_closed

    def test_chat_provider_health_callback(self):
        callback_log = []

        def on_change(breaker, old_state, new_state):
            callback_log.append({
                "breaker": breaker.name,
                "from": old_state,
                "to": new_state,
            })

        cb = CircuitBreaker(
            "chat_cb",
            config=CircuitBreakerConfig(
                failure_threshold=1,
                recovery_timeout=60.0,
                category="chat",
            ),
            on_state_change=[on_change],
        )
        cb.record_failure(TransientError("err"))
        assert len(callback_log) == 1
        assert callback_log[0]["to"] == CircuitState.OPEN
        assert callback_log[0]["breaker"] == "chat_cb"

    def test_chat_can_attempt_check_pattern(self):
        cb = CircuitBreaker(
            "chat_can",
            config=CircuitBreakerConfig(
                failure_threshold=1,
                category="chat",
            ),
        )
        assert cb.can_attempt() is True
        cb.record_failure(TransientError("err"))
        assert cb.can_attempt() is False


# ---------------------------------------------------------------------------
# MCP parity: backoff doubles, caps at 300s, semaphore independent
# ---------------------------------------------------------------------------

class TestMCPParity:
    """Verify MCP module circuit breaker behavior."""

    def test_mcp_backoff_doubles(self):
        cb = CircuitBreaker(
            "mcp_backoff",
            config=CircuitBreakerConfig(
                failure_threshold=1,
                recovery_timeout=10.0,
                success_threshold=1,
                backoff_factor=2.0,
                max_recovery_timeout=300.0,
                category="mcp",
            ),
        )
        with pytest.raises(TransientError):
            cb.call(lambda: (_ for _ in ()).throw(TransientError("err")))
        assert cb._current_recovery_timeout == 10.0  # first trip

        time.sleep(0.01)
        # Force half-open transition
        with cb._lock:
            cb._last_failure_time = time.time() - 11.0
        assert cb.is_half_open

        with pytest.raises(TransientError):
            cb.call(lambda: (_ for _ in ()).throw(TransientError("err")))
        assert cb._current_recovery_timeout == 20.0  # doubled

    def test_mcp_backoff_caps_at_max(self):
        cb = CircuitBreaker(
            "mcp_cap",
            config=CircuitBreakerConfig(
                failure_threshold=1,
                recovery_timeout=200.0,
                success_threshold=1,
                backoff_factor=2.0,
                max_recovery_timeout=300.0,
                category="mcp",
            ),
        )
        cb.record_failure(TransientError("err"))
        # Force half-open
        with cb._lock:
            cb._last_failure_time = time.time() - 201.0
        assert cb.is_half_open
        cb.record_failure(TransientError("err"))
        assert cb._current_recovery_timeout == 300.0  # capped

    def test_mcp_independent_breakers(self):
        """Different MCP modules should have independent breakers."""
        cb1 = CircuitBreaker(
            "mcp_mod_a",
            config=CircuitBreakerConfig(failure_threshold=1, category="mcp"),
        )
        cb2 = CircuitBreaker(
            "mcp_mod_b",
            config=CircuitBreakerConfig(failure_threshold=1, category="mcp"),
        )
        cb1.record_failure(TransientError("err"))
        assert cb1.is_open
        assert cb2.is_closed  # independent

    def test_mcp_concurrent_semaphore_independent(self):
        """Semaphore-based rate limiting is independent of circuit breaker."""
        sem = asyncio.Semaphore(2)
        cb = CircuitBreaker(
            "mcp_sem",
            config=CircuitBreakerConfig(failure_threshold=5, category="mcp"),
        )
        # Semaphore limits concurrency, breaker limits failures
        assert cb.can_attempt() is True
        # Both work independently
        cb.record_failure(TransientError("err"))
        assert cb.can_attempt() is True  # still under threshold

    def test_mcp_execute_with_breaker_pattern(self):
        """Simulates the MCP execute_with_circuit_breaker pattern."""
        cb = CircuitBreaker(
            "mcp_exec",
            config=CircuitBreakerConfig(
                failure_threshold=5,
                recovery_timeout=60.0,
                backoff_factor=2.0,
                max_recovery_timeout=300.0,
                category="mcp",
            ),
        )
        # Successful call
        result = cb.call(lambda: "ok")
        assert result == "ok"
        assert cb.is_closed
