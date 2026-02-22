import warnings

import pytest

from tldw_Server_API.app.core.Embeddings.Embeddings_Server import Embeddings_Create as EC


def test_embeddings_server_rg_allows_and_invokes_function(monkeypatch):
    """
    When ResourceGovernor is enabled and the governor allows, the
    TokenBucketLimiter wrapper should:
      - Call the RG helper once.
      - Call the wrapped function.
    """
    monkeypatch.setenv("RG_ENABLED", "1")

    calls = []
    rg_calls = []

    def _dummy():
        calls.append("called")
        return "ok"

    limiter = EC.TokenBucketLimiter(capacity=1, period=60)

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


def test_embeddings_server_rg_unavailable_fails_closed(monkeypatch):
    """
    When RG is enabled but the helper returns None (unavailable/misconfigured),
    the Phase 2 shim fails closed with a RuntimeError.
    """
    monkeypatch.setenv("RG_ENABLED", "1")

    calls = []

    def _dummy():
        calls.append("called")
        return "ok"

    limiter = EC.TokenBucketLimiter(capacity=1, period=60)

    def _fake_rg_sync_none():
        return None

    monkeypatch.setattr(EC, "_maybe_enforce_with_rg_embeddings_server_sync", _fake_rg_sync_none)
    monkeypatch.setattr(EC, "_rg_emb_server_fallback_logged", False)

    wrapped = limiter(_dummy)
    with pytest.raises(RuntimeError):
        wrapped()
    assert calls == []


def test_embeddings_server_rg_disabled_fail_open(monkeypatch):
    """Phase 2: RG disabled → fail-open with deprecation warning."""
    monkeypatch.setenv("RG_ENABLED", "0")
    monkeypatch.setattr(EC, "_EMB_SERVER_DEPRECATION_WARNED", False)

    calls = []

    def _dummy():
        calls.append("called")
        return "ok"

    limiter = EC.TokenBucketLimiter(capacity=1, period=60)

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        wrapped = limiter(_dummy)
        result = wrapped()

        assert result == "ok"
        assert calls == ["called"]

        deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(deprecation_warnings) >= 1
        assert "Phase 2" in str(deprecation_warnings[0].message)
