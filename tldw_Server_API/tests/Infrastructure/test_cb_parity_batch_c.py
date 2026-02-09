# test_cb_parity_batch_c.py
"""Parity tests: TTS and RAG circuit breaker behavior."""

import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

from tldw_Server_API.app.core.Infrastructure.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    CircuitState,
)


class TransientError(Exception):
    pass


def _fail():
    raise TransientError("boom")


def _succeed():
    return "ok"


async def _async_fail():
    raise TransientError("async boom")


async def _async_succeed():
    return "async ok"


# ---------------------------------------------------------------------------
# TTS parity: backoff, health monitor callbacks, error categorization,
#             multi-provider
# ---------------------------------------------------------------------------

class TestTTSParity:
    """Verify TTS circuit breaker behavior via the unified module."""

    def test_tts_backoff_increases(self):
        cb = CircuitBreaker(
            "tts_backoff",
            config=CircuitBreakerConfig(
                failure_threshold=1,
                recovery_timeout=10.0,
                success_threshold=1,
                backoff_factor=2.0,
                max_recovery_timeout=120.0,
                category="tts",
            ),
        )
        cb.record_failure(TransientError("err"))
        assert cb.is_open
        assert cb._current_recovery_timeout == 10.0

        # Transition to half-open and fail again
        with cb._lock:
            cb._last_failure_time = time.time() - 11.0
        assert cb.is_half_open
        cb.record_failure(TransientError("err"))
        assert cb.is_open
        assert cb._current_recovery_timeout == 20.0

    def test_tts_backoff_resets_on_close(self):
        cb = CircuitBreaker(
            "tts_backoff_reset",
            config=CircuitBreakerConfig(
                failure_threshold=1,
                recovery_timeout=0.05,
                success_threshold=1,
                backoff_factor=2.0,
                category="tts",
            ),
        )
        # Trip the breaker
        with pytest.raises(TransientError):
            cb.call(_fail)
        assert cb.is_open
        time.sleep(0.06)
        assert cb.is_half_open
        # Fail again in half-open → backoff kicks in
        with pytest.raises(TransientError):
            cb.call(_fail)
        assert cb._current_recovery_timeout == pytest.approx(0.10)
        time.sleep(0.11)
        # Succeed → closes and resets backoff
        cb.call(_succeed)
        assert cb.is_closed
        assert cb._current_recovery_timeout == pytest.approx(0.05)

    def test_tts_health_monitor_callback(self):
        """State-change callbacks simulate TTS health monitoring."""
        health_log = []

        def health_callback(breaker, old, new):
            health_log.append({
                "provider": breaker.name,
                "old": old.name,
                "new": new.name,
            })

        cb = CircuitBreaker(
            "tts_health",
            config=CircuitBreakerConfig(
                failure_threshold=3,
                category="tts",
                service="elevenlabs",
            ),
            on_state_change=[health_callback],
        )
        for _ in range(3):
            cb.record_failure(TransientError("err"))

        assert len(health_log) == 1
        assert health_log[0]["new"] == "OPEN"
        assert health_log[0]["provider"] == "tts_health"

    def test_tts_error_categorization_independent(self):
        """Error categorization happens in TTS wrapper, not in unified breaker.
        Unified breaker just records the failure."""
        cb = CircuitBreaker(
            "tts_err_cat",
            config=CircuitBreakerConfig(
                failure_threshold=5,
                category="tts",
            ),
        )
        # Different exception types all get recorded as failures
        cb.record_failure(ConnectionError("network"))
        cb.record_failure(TimeoutError("timeout"))
        cb.record_failure(ValueError("invalid"))
        assert cb.failure_count == 3

    def test_tts_multi_provider_isolation(self):
        """Each TTS provider has an independent circuit breaker."""
        providers = {}
        for name in ["elevenlabs", "openai_tts", "kokoro"]:
            providers[name] = CircuitBreaker(
                f"tts_{name}",
                config=CircuitBreakerConfig(
                    failure_threshold=3,
                    recovery_timeout=60.0,
                    category="tts",
                    service=name,
                ),
            )

        # Open one provider
        for _ in range(3):
            providers["elevenlabs"].record_failure(TransientError("err"))
        assert providers["elevenlabs"].is_open
        assert providers["openai_tts"].is_closed
        assert providers["kokoro"].is_closed

    def test_tts_half_open_probe_limit(self):
        cb = CircuitBreaker(
            "tts_probe",
            config=CircuitBreakerConfig(
                failure_threshold=1,
                recovery_timeout=0.05,
                half_open_max_calls=1,
                success_threshold=1,
                category="tts",
            ),
        )
        cb.record_failure(TransientError("err"))
        time.sleep(0.06)
        assert cb.is_half_open
        # First call takes the slot
        cb.call(_succeed)
        assert cb.is_closed

    @pytest.mark.asyncio
    async def test_tts_async_call_through_breaker(self):
        cb = CircuitBreaker(
            "tts_async",
            config=CircuitBreakerConfig(
                failure_threshold=3,
                category="tts",
            ),
        )
        result = await cb.call_async(_async_succeed)
        assert result == "async ok"
        assert cb.is_closed


# ---------------------------------------------------------------------------
# RAG parity: rolling-window rate, RetryPolicy wrapping, FallbackChain
#             after open, coordinator tracking
# ---------------------------------------------------------------------------

class TestRAGParity:
    """Verify RAG circuit breaker behavior via the unified module."""

    def test_rag_rolling_window_rate(self):
        cb = CircuitBreaker(
            "rag_window",
            config=CircuitBreakerConfig(
                window_size=10,
                failure_rate_threshold=0.5,
                category="rag",
            ),
        )
        # 5 successes, 5 failures → 50% rate at window full
        for _ in range(5):
            cb.record_success()
        for _ in range(4):
            cb.record_failure(TransientError("err"))
        assert cb.is_closed  # only 9 calls, need 10
        cb.record_failure(TransientError("err"))
        assert cb.is_open  # 10 calls, 50% failure rate

    def test_rag_window_does_not_trip_below_rate(self):
        cb = CircuitBreaker(
            "rag_window_ok",
            config=CircuitBreakerConfig(
                window_size=10,
                failure_rate_threshold=0.5,
                category="rag",
            ),
        )
        for _ in range(7):
            cb.record_success()
        for _ in range(3):
            cb.record_failure(TransientError("err"))
        assert cb.is_closed  # 30% rate < 50% threshold

    def test_rag_min_calls_support(self):
        """min_calls allows tripping before window is full."""
        cb = CircuitBreaker(
            "rag_min_calls",
            config=CircuitBreakerConfig(
                window_size=10,
                min_calls=4,
                failure_rate_threshold=0.5,
                category="rag",
            ),
        )
        # 2 successes, 2 failures → 4 calls ≥ min_calls, 50% rate
        cb.record_success()
        cb.record_success()
        cb.record_failure(TransientError("err"))
        assert cb.is_closed  # only 3 calls < min_calls=4
        cb.record_failure(TransientError("err"))
        assert cb.is_open  # 4 calls, 50% rate

    @pytest.mark.asyncio
    async def test_rag_wrapper_sync_function_support(self):
        """RAG wrapper should handle sync functions via to_thread."""
        from tldw_Server_API.app.core.RAG.rag_service.resilience import (
            CircuitBreaker as RAGCB,
            CircuitBreakerConfig as RAGCfg,
        )
        cb = RAGCB("rag_sync", RAGCfg(failure_threshold=5))

        def sync_fn():
            return 42

        result = await cb.call(sync_fn)
        assert result == 42

    @pytest.mark.asyncio
    async def test_rag_wrapper_async_function_support(self):
        """RAG wrapper should handle async functions directly."""
        from tldw_Server_API.app.core.RAG.rag_service.resilience import (
            CircuitBreaker as RAGCB,
            CircuitBreakerConfig as RAGCfg,
        )
        cb = RAGCB("rag_async", RAGCfg(failure_threshold=5))

        async def async_fn():
            return 99

        result = await cb.call(async_fn)
        assert result == 99

    def test_rag_fallback_chain_after_open(self):
        """When breaker is open, calls should be rejected allowing fallback."""
        cb = CircuitBreaker(
            "rag_fallback",
            config=CircuitBreakerConfig(
                failure_threshold=1,
                category="rag",
            ),
        )
        cb.record_failure(TransientError("err"))
        assert cb.is_open

        # Caller can check and use fallback
        if not cb.can_attempt():
            result = "fallback_result"
        else:
            result = cb.call(_succeed)
        assert result == "fallback_result"

    def test_rag_coordinator_tracking(self):
        """ErrorRecoveryCoordinator tracks multiple breakers."""
        from tldw_Server_API.app.core.RAG.rag_service.resilience import (
            ErrorRecoveryCoordinator,
            CircuitBreakerConfig as RAGCfg,
        )
        coord = ErrorRecoveryCoordinator()
        cb1 = coord.register_circuit_breaker("retriever", RAGCfg(failure_threshold=3))
        cb2 = coord.register_circuit_breaker("reranker", RAGCfg(failure_threshold=5))
        assert "retriever" in coord.circuit_breakers
        assert "reranker" in coord.circuit_breakers
        stats = coord.get_recovery_stats()
        assert "retriever" in stats["circuit_breakers"]
        assert "reranker" in stats["circuit_breakers"]

    def test_rag_last_state_change_uses_property(self):
        """RAG wrapper should use last_state_change_time, not _last_failure_time."""
        from tldw_Server_API.app.core.RAG.rag_service.resilience import (
            CircuitBreaker as RAGCB,
            CircuitBreakerConfig as RAGCfg,
        )
        cb = RAGCB("rag_lsc", RAGCfg(failure_threshold=5))
        lsc = cb.last_state_change
        assert isinstance(lsc, float)
        assert lsc > 0

    def test_rag_get_stats_format(self):
        """RAG wrapper get_stats() returns backward-compatible format."""
        from tldw_Server_API.app.core.RAG.rag_service.resilience import (
            CircuitBreaker as RAGCB,
            CircuitBreakerConfig as RAGCfg,
        )
        cb = RAGCB("rag_stats", RAGCfg(failure_threshold=5))
        stats = cb.get_stats()
        assert "name" in stats
        assert "state" in stats
        assert stats["state"] == "closed"
        assert "failure_count" in stats
        assert "last_state_change" in stats


# ---------------------------------------------------------------------------
# New features: update_config, remove, call_timeout, frozen config
# ---------------------------------------------------------------------------

class TestNewFeatures:
    """Test new features added in the unification."""

    def test_frozen_config(self):
        """CircuitBreakerConfig is immutable (frozen dataclass)."""
        cfg = CircuitBreakerConfig(failure_threshold=3)
        with pytest.raises(AttributeError):
            cfg.failure_threshold = 5

    def test_update_config(self):
        cb = CircuitBreaker(
            "update_test",
            config=CircuitBreakerConfig(failure_threshold=5),
        )
        assert cb.config.failure_threshold == 5
        new_cfg = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=30.0)
        cb.update_config(new_cfg)
        assert cb.config.failure_threshold == 3
        assert cb.config.recovery_timeout == 30.0

    def test_registry_remove(self):
        from tldw_Server_API.app.core.Infrastructure.circuit_breaker import (
            CircuitBreakerRegistry,
        )
        reg = CircuitBreakerRegistry()
        reg.get_or_create("remove_test")
        assert reg.get("remove_test") is not None
        assert reg.remove("remove_test") is True
        assert reg.get("remove_test") is None
        assert reg.remove("remove_test") is False

    def test_registry_config_mismatch_warning(self):
        from tldw_Server_API.app.core.Infrastructure.circuit_breaker import (
            CircuitBreakerRegistry,
        )
        reg = CircuitBreakerRegistry()
        cfg1 = CircuitBreakerConfig(failure_threshold=3)
        cfg2 = CircuitBreakerConfig(failure_threshold=5)
        cb1 = reg.get_or_create("mismatch", config=cfg1)
        with patch("tldw_Server_API.app.core.Infrastructure.circuit_breaker.logger") as mock_logger:
            cb2 = reg.get_or_create("mismatch", config=cfg2)
            mock_logger.warning.assert_called()
        assert cb1 is cb2  # returns existing

    @pytest.mark.asyncio
    async def test_call_timeout(self):
        cb = CircuitBreaker(
            "timeout_test",
            config=CircuitBreakerConfig(
                failure_threshold=3,
                call_timeout=0.05,
            ),
        )

        async def slow():
            await asyncio.sleep(1.0)
            return "done"

        with pytest.raises(asyncio.TimeoutError):
            await cb.call_async(slow)

        assert cb.failure_count == 1

    @pytest.mark.asyncio
    @patch("tldw_Server_API.app.core.Infrastructure.circuit_breaker._increment_counter")
    @patch("tldw_Server_API.app.core.Infrastructure.circuit_breaker._set_gauge")
    async def test_timeout_metric_emitted(self, mock_gauge, mock_counter):
        cb = CircuitBreaker(
            "timeout_metric",
            config=CircuitBreakerConfig(
                failure_threshold=3,
                call_timeout=0.05,
            ),
        )

        async def slow():
            await asyncio.sleep(1.0)

        with pytest.raises(asyncio.TimeoutError):
            await cb.call_async(slow)

        timeout_calls = [
            c for c in mock_counter.call_args_list
            if c[0][0] == "circuit_breaker_timeouts_total"
        ]
        assert len(timeout_calls) == 1

    def test_success_count_property(self):
        """success_count tracks consecutive successes in HALF_OPEN state."""
        cb = CircuitBreaker(
            "sc_test",
            config=CircuitBreakerConfig(
                failure_threshold=1,
                recovery_timeout=0.05,
                success_threshold=2,
            ),
        )
        with pytest.raises(TransientError):
            cb.call(_fail)
        time.sleep(0.06)
        cb.call(_succeed)
        assert cb.success_count == 1  # one success in half-open

    def test_last_failure_time_property(self):
        cb = CircuitBreaker("lft_test")
        assert cb.last_failure_time is None
        cb.record_failure(TransientError("err"))
        assert cb.last_failure_time is not None
        assert cb.last_failure_time > 0

    def test_current_recovery_timeout_property(self):
        cb = CircuitBreaker(
            "crt_test",
            config=CircuitBreakerConfig(recovery_timeout=42.0),
        )
        assert cb.current_recovery_timeout == 42.0

    def test_half_open_calls_property(self):
        cb = CircuitBreaker("hoc_test")
        assert cb.half_open_calls == 0
