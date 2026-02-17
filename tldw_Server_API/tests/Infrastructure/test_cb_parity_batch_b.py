# test_cb_parity_batch_b.py
"""Parity tests: Embeddings and Evaluations circuit breaker behavior."""

import asyncio
import importlib
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from tldw_Server_API.app.core.Infrastructure.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    CircuitBreakerRegistry,
)

_infra_cb_module = importlib.import_module(
    "tldw_Server_API.app.core.Infrastructure.circuit_breaker"
)


class TransientError(Exception):
    pass


# ---------------------------------------------------------------------------
# Embeddings parity: metrics, registry, connection pool
# ---------------------------------------------------------------------------

class TestEmbeddingsParity:
    """Verify Embeddings circuit breaker behavior via the unified module."""

    @patch.object(_infra_cb_module, "_increment_counter")
    @patch.object(_infra_cb_module, "_set_gauge")
    def test_embeddings_metrics_on_trip(self, mock_gauge, mock_counter):
        cb = CircuitBreaker(
            "emb_metrics",
            config=CircuitBreakerConfig(
                failure_threshold=1,
                category="embeddings",
                service="chromadb",
            ),
        )
        cb.record_failure(TransientError("err"))
        trip_calls = [
            c for c in mock_counter.call_args_list
            if c[0][0] == "circuit_breaker_trips_total"
        ]
        assert len(trip_calls) >= 1
        # Verify category label
        labels = trip_calls[0][1]["labels"]
        assert labels["category"] == "embeddings"

    def test_embeddings_registry_integration(self):
        """Embeddings module uses the global registry."""
        reg = CircuitBreakerRegistry()
        cb = reg.get_or_create(
            "embeddings_test",
            config=CircuitBreakerConfig(
                failure_threshold=3,
                category="embeddings",
            ),
        )
        assert reg.get("embeddings_test") is cb

    def test_embeddings_imports_unified_breaker_directly(self):
        """Embeddings runtime modules should import Infrastructure breaker directly."""
        connection_pool_path = (
            Path(__file__).resolve().parents[2]
            / "app"
            / "core"
            / "Embeddings"
            / "connection_pool.py"
        )
        source = connection_pool_path.read_text(encoding="utf-8")
        assert (
            "from tldw_Server_API.app.core.Infrastructure.circuit_breaker import CircuitBreaker"
            in source
        )

    def test_embeddings_connection_pool_independent(self):
        """Circuit breaker is independent of connection pool behavior."""
        cb1 = CircuitBreaker(
            "emb_pool_a",
            config=CircuitBreakerConfig(
                failure_threshold=3,
                category="embeddings",
                service="pool_a",
            ),
        )
        cb2 = CircuitBreaker(
            "emb_pool_b",
            config=CircuitBreakerConfig(
                failure_threshold=3,
                category="embeddings",
                service="pool_b",
            ),
        )
        # Different services have independent state
        cb1.record_failure(TransientError("err"))
        cb1.record_failure(TransientError("err"))
        cb1.record_failure(TransientError("err"))
        assert cb1.is_open
        assert cb2.is_closed

    @patch.object(_infra_cb_module, "_increment_counter")
    @patch.object(_infra_cb_module, "_set_gauge")
    def test_embeddings_metrics_on_success(self, mock_gauge, mock_counter):
        cb = CircuitBreaker(
            "emb_succ",
            config=CircuitBreakerConfig(
                failure_threshold=3,
                category="embeddings",
                service="chromadb",
            ),
        )
        result = cb.call(lambda: "vector")
        assert result == "vector"
        success_calls = [
            c for c in mock_counter.call_args_list
            if c[0][0] == "circuit_breaker_successes_total"
        ]
        assert len(success_calls) >= 1

    def test_embeddings_emit_metrics_opt_out(self):
        """When emit_metrics=False, no metrics should be emitted."""
        with patch.object(_infra_cb_module, "_increment_counter") as mock_counter:
            with patch.object(_infra_cb_module, "_set_gauge"):
                cb = CircuitBreaker(
                    "emb_no_metrics",
                    config=CircuitBreakerConfig(
                        failure_threshold=1,
                        category="embeddings",
                        emit_metrics=False,
                    ),
                )
                cb.record_failure(TransientError("err"))
                assert cb.is_open
                # No metrics should be emitted
                assert mock_counter.call_count == 0


# ---------------------------------------------------------------------------
# Evaluations parity: per-provider config, timeout interaction,
#                     CircuitOpenError compat
# ---------------------------------------------------------------------------

class TestEvaluationsParity:
    """Verify Evaluations circuit breaker behavior via the unified module."""

    def test_evals_per_provider_config(self):
        """Each LLM provider gets its own config."""
        openai_cb = CircuitBreaker(
            "eval_openai",
            config=CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=60.0,
                category="evaluations",
            ),
        )
        anthropic_cb = CircuitBreaker(
            "eval_anthropic",
            config=CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=60.0,
                category="evaluations",
            ),
        )
        local_cb = CircuitBreaker(
            "eval_local",
            config=CircuitBreakerConfig(
                failure_threshold=5,
                recovery_timeout=30.0,
                category="evaluations",
            ),
        )
        assert openai_cb.config.failure_threshold == 3
        assert anthropic_cb.config.failure_threshold == 3
        assert local_cb.config.failure_threshold == 5
        assert local_cb.config.recovery_timeout == 30.0

    @pytest.mark.asyncio
    async def test_evals_timeout_interaction(self):
        """Timeout fires on slow calls and records a failure."""
        cb = CircuitBreaker(
            "eval_timeout",
            config=CircuitBreakerConfig(
                failure_threshold=2,
                call_timeout=0.05,
                category="evaluations",
            ),
        )

        async def slow_func():
            await asyncio.sleep(1.0)
            return "done"

        with pytest.raises(asyncio.TimeoutError):
            await cb.call_async(slow_func)

        # The failure should have been recorded
        assert cb.failure_count == 1

    @pytest.mark.asyncio
    async def test_evals_timeout_no_trip_below_threshold(self):
        """Single timeout shouldn't trip if threshold > 1."""
        cb = CircuitBreaker(
            "eval_timeout2",
            config=CircuitBreakerConfig(
                failure_threshold=3,
                call_timeout=0.05,
                category="evaluations",
            ),
        )

        async def slow_func():
            await asyncio.sleep(1.0)

        with pytest.raises(asyncio.TimeoutError):
            await cb.call_async(slow_func)

        assert cb.is_closed  # threshold=3, only 1 failure

    def test_evals_circuit_open_error_compat(self):
        """CircuitOpenError should be catchable via CircuitBreakerOpenError."""
        cb = CircuitBreaker(
            "eval_compat",
            config=CircuitBreakerConfig(
                failure_threshold=1,
                category="evaluations",
            ),
        )
        cb.record_failure(TransientError("err"))
        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            cb.call(lambda: "should not run")
        assert "OPEN" in str(exc_info.value)
        assert exc_info.value.breaker_name == "eval_compat"

    def test_evals_recovery_at_populated(self):
        """CircuitBreakerOpenError should include recovery_at."""
        cb = CircuitBreaker(
            "eval_recovery_at",
            config=CircuitBreakerConfig(
                failure_threshold=1,
                recovery_timeout=60.0,
                category="evaluations",
            ),
        )
        cb.record_failure(TransientError("err"))
        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            cb.call(lambda: "nope")
        assert exc_info.value.recovery_at is not None
        assert exc_info.value.recovery_at > time.time() - 1

    def test_evals_state_changed_at_independent(self):
        """_state_changed_at in Evaluations wrapper is independent of _last_failure_time."""
        from tldw_Server_API.app.core.Evaluations.circuit_breaker import (
            CircuitBreaker as EvalCB,
        )
        from tldw_Server_API.app.core.Evaluations.circuit_breaker import (
            CircuitBreakerConfig as EvalCfg,
        )
        cb = EvalCB("eval_sca", EvalCfg(failure_threshold=5))
        original_lft = cb._cb._last_failure_time
        cb._state_changed_at = 999.0
        # Should NOT have affected the unified breaker's _last_failure_time
        assert cb._cb._last_failure_time == original_lft

    @pytest.mark.asyncio
    async def test_evals_wraps_function_metadata(self):
        """with_circuit_breaker decorator should preserve function metadata."""
        from tldw_Server_API.app.core.Evaluations.circuit_breaker import (
            with_circuit_breaker,
        )

        @with_circuit_breaker("test")
        async def my_eval_func():
            """This is a docstring."""
            return 42

        assert my_eval_func.__name__ == "my_eval_func"
        assert "docstring" in my_eval_func.__doc__

    def test_evals_get_state_format(self):
        """Evaluations CircuitBreaker.get_state() returns expected format."""
        from tldw_Server_API.app.core.Evaluations.circuit_breaker import (
            CircuitBreaker as EvalCB,
        )
        from tldw_Server_API.app.core.Evaluations.circuit_breaker import (
            CircuitBreakerConfig as EvalCfg,
        )
        cb = EvalCB("eval_state", EvalCfg(failure_threshold=3))
        state = cb.get_state()
        assert "name" in state
        assert "state" in state
        assert "stats" in state
        assert "config" in state
        assert state["state"] == "closed"
