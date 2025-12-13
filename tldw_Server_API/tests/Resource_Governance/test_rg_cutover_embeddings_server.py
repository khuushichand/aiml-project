import os

import pytest

from tldw_Server_API.app.core.Embeddings.Embeddings_Server import Embeddings_Create as EC


class _SentinelError(Exception):
    """Raised when a legacy limiter path is unexpectedly invoked."""


def test_embeddings_server_rg_allows_and_skips_token_bucket(monkeypatch):
    """
    When ResourceGovernor is enabled and the governor allows, the
    TokenBucketLimiter wrapper should:
      - Call the RG helper once.
      - Call the wrapped function.
      - Not invoke the legacy _acquire() token-bucket path.
    """
    monkeypatch.setenv("RG_ENABLED", "1")

    calls = []
    rg_calls = []

    def _dummy():
        calls.append("called")
        return "ok"

    limiter = EC.TokenBucketLimiter(capacity=1, period=60)

    # If the legacy path is used when RG allows, this will fail the test.
    def _fail_acquire():
        raise _SentinelError("TokenBucketLimiter._acquire should not be called when RG allows")

    monkeypatch.setattr(limiter, "_acquire", _fail_acquire)

    def _fake_rg_sync():
        rg_calls.append(True)
        return {
            "allowed": True,
            "retry_after": None,
            "policy_id": "embeddings_server.default",
        }

    monkeypatch.setattr(EC, "_maybe_enforce_with_rg_embeddings_server_sync", _fake_rg_sync)

    wrapped = limiter(_dummy)
    result = wrapped()

    assert result == "ok"
    assert calls == ["called"]
    assert len(rg_calls) == 1


def test_embeddings_server_rg_unavailable_falls_back_to_token_bucket(monkeypatch):
    """
    When RG is enabled but the helper returns None (unavailable/disabled at
    runtime), the wrapper should fall back to the legacy token-bucket
    _acquire() path and still call the wrapped function exactly once.
    """
    monkeypatch.setenv("RG_ENABLED", "1")

    calls = []
    acquire_calls = []

    def _dummy():
        calls.append("called")
        return "ok"

    limiter = EC.TokenBucketLimiter(capacity=1, period=60)

    def _record_acquire():
        acquire_calls.append(True)
        return None

    monkeypatch.setattr(limiter, "_acquire", _record_acquire)

    def _fake_rg_sync_none():
        return None

    monkeypatch.setattr(EC, "_maybe_enforce_with_rg_embeddings_server_sync", _fake_rg_sync_none)

    wrapped = limiter(_dummy)
    result = wrapped()

    assert result == "ok"
    assert calls == ["called"]
    assert acquire_calls == [True]
