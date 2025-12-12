import os
from typing import Dict, List

import pytest

from tldw_Server_API.app.core.Chat.rate_limiter import (
    ConversationRateLimiter,
    RateLimitConfig,
)


pytestmark = pytest.mark.rate_limit


@pytest.mark.asyncio
async def test_chat_rg_shadow_mismatch_records_metric(monkeypatch):
    """
    When ResourceGovernor denies but the legacy limiter allows, a shadow
    mismatch metric should be recorded.
    """
    # Ensure legacy-primary shadow semantics for this test.
    monkeypatch.setenv("RG_CHAT_ENFORCE_PRIMARY", "0")

    calls: List[Dict[str, str]] = []

    async def fake_rg_chat(**_: object) -> Dict[str, object]:
        return {"allowed": False, "policy_id": "chat.test", "retry_after": 1}

    def fake_record_shadow_mismatch(
        *,
        module: str,
        route: str,
        policy_id: str,
        legacy: str,
        rg: str,
    ) -> None:
        calls.append(
            {
                "module": module,
                "route": route,
                "policy_id": policy_id,
                "legacy": legacy,
                "rg": rg,
            }
        )

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Chat.rate_limiter._maybe_enforce_with_rg_chat",
        fake_rg_chat,
        raising=False,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Resource_Governance.metrics_rg.record_shadow_mismatch",
        fake_record_shadow_mismatch,
        raising=False,
    )

    config = RateLimitConfig(
        global_rpm=100,
        per_user_rpm=100,
        per_conversation_rpm=100,
        per_user_tokens_per_minute=100000,
        burst_multiplier=1.0,
    )
    limiter = ConversationRateLimiter(config)

    allowed, error = await limiter.check_rate_limit(
        user_id="user-shadow",
        conversation_id="conv-shadow",
        estimated_tokens=50,
    )

    # Legacy limiter should allow under generous config; RG denies.
    assert allowed is True
    assert error is None

    assert len(calls) == 1
    labels = calls[0]
    assert labels["module"] == "chat"
    assert labels["route"] == "/api/v1/chat/completions"
    assert labels["policy_id"] == "chat.test"
    assert labels["legacy"] == "allow"
    assert labels["rg"] == "deny"


@pytest.mark.asyncio
async def test_chat_rg_shadow_alignment_no_metric(monkeypatch):
    """
    When ResourceGovernor and legacy limiter agree on allow/deny, no
    mismatch metric should be emitted.
    """
    monkeypatch.setenv("RG_CHAT_ENFORCE_PRIMARY", "0")

    calls: List[Dict[str, str]] = []

    async def fake_rg_chat(**_: object) -> Dict[str, object]:
        return {"allowed": True, "policy_id": "chat.test", "retry_after": None}

    def fake_record_shadow_mismatch(
        *,
        module: str,
        route: str,
        policy_id: str,
        legacy: str,
        rg: str,
    ) -> None:
        calls.append(
            {
                "module": module,
                "route": route,
                "policy_id": policy_id,
                "legacy": legacy,
                "rg": rg,
            }
        )

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Chat.rate_limiter._maybe_enforce_with_rg_chat",
        fake_rg_chat,
        raising=False,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Resource_Governance.metrics_rg.record_shadow_mismatch",
        fake_record_shadow_mismatch,
        raising=False,
    )

    config = RateLimitConfig(
        global_rpm=100,
        per_user_rpm=100,
        per_conversation_rpm=100,
        per_user_tokens_per_minute=100000,
        burst_multiplier=1.0,
    )
    limiter = ConversationRateLimiter(config)

    allowed, error = await limiter.check_rate_limit(
        user_id="user-align",
        conversation_id="conv-align",
        estimated_tokens=0,
    )

    assert allowed is True
    assert error is None

    # Legacy and RG both allow; no mismatch should be recorded.
    assert calls == []


@pytest.mark.asyncio
async def test_chat_rg_primary_enforces_rg_decision(monkeypatch):
    """
    When RG_CHAT_ENFORCE_PRIMARY=1 and a governor decision is available,
    the RG decision is treated as canonical for chat rate limiting.
    """

    monkeypatch.setenv("RG_CHAT_ENFORCE_PRIMARY", "1")

    async def fake_rg_chat(**_: object) -> Dict[str, object]:
        return {"allowed": False, "policy_id": "chat.primary", "retry_after": 2}

    # Avoid relying on metrics internals in this behavioral test.
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Resource_Governance.metrics_rg.record_shadow_mismatch",
        lambda **kwargs: None,
        raising=False,
    )

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Chat.rate_limiter._maybe_enforce_with_rg_chat",
        fake_rg_chat,
        raising=False,
    )

    config = RateLimitConfig(
        global_rpm=100,
        per_user_rpm=100,
        per_conversation_rpm=100,
        per_user_tokens_per_minute=100000,
        burst_multiplier=1.0,
    )
    limiter = ConversationRateLimiter(config)

    allowed, error = await limiter.check_rate_limit(
        user_id="user-primary",
        conversation_id="conv-primary",
        estimated_tokens=10,
    )

    assert allowed is False
    assert error is not None
    assert "ResourceGovernor policy=chat.primary" in error
    assert "retry_after=2s" in error

    # Clean up env override for other tests.
    monkeypatch.delenv("RG_CHAT_ENFORCE_PRIMARY", raising=False)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "global_rpm, per_user_rpm, estimated_tokens, rg_allowed, legacy_expected, mismatch_expected",
    [
        # Generous limits: legacy allows; RG denies → mismatch
        (100, 100, 0, False, True, True),
        # Tight per-user limit still allows first call; RG allows → alignment
        (100, 1, 0, True, True, False),
        # Both allow → no mismatch
        (100, 100, 0, True, True, False),
        # Low RPMs allow first call; RG denies → mismatch
        (1, 1, 0, False, True, True),
    ],
)
async def test_chat_rg_shadow_matrix_matches_expectations(
    monkeypatch,
    global_rpm,
    per_user_rpm,
    estimated_tokens,
    rg_allowed,
    legacy_expected,
    mismatch_expected,
):
    """
    Exercise a small matrix of RG vs legacy decisions and assert that
    record_shadow_mismatch is only emitted when the allow/deny outcomes
    differ.

    This focuses on the comparison logic and labels without relying on
    actual governor configuration or token-bucket timing.
    """
    monkeypatch.setenv("RG_CHAT_ENFORCE_PRIMARY", "0")

    calls: List[Dict[str, str]] = []

    async def fake_rg_chat(**_: object) -> Dict[str, object]:
        return {
            "allowed": bool(rg_allowed),
            "policy_id": "chat.matrix",
            "retry_after": 1,
        }

    def fake_record_shadow_mismatch(
        *,
        module: str,
        route: str,
        policy_id: str,
        legacy: str,
        rg: str,
    ) -> None:
        calls.append(
            {
                "module": module,
                "route": route,
                "policy_id": policy_id,
                "legacy": legacy,
                "rg": rg,
            }
        )

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Chat.rate_limiter._maybe_enforce_with_rg_chat",
        fake_rg_chat,
        raising=False,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Resource_Governance.metrics_rg.record_shadow_mismatch",
        fake_record_shadow_mismatch,
        raising=False,
    )

    # Configure the legacy limiter with deterministic, test-friendly limits.
    config = RateLimitConfig(
        global_rpm=global_rpm,
        per_user_rpm=per_user_rpm,
        per_conversation_rpm=per_user_rpm,
        per_user_tokens_per_minute=100000,
        burst_multiplier=1.0,
    )
    limiter = ConversationRateLimiter(config)

    # Drive a single check so legacy decisions are stable under the
    # configured RPMs. For the tight-RPM cases, this single call will
    # consume capacity and yield the expected deny/allow outcome.
    allowed, _ = await limiter.check_rate_limit(
        user_id="matrix-user",
        conversation_id="matrix-conv",
        estimated_tokens=estimated_tokens,
    )

    assert allowed is legacy_expected

    if mismatch_expected:
        assert len(calls) == 1
        labels = calls[0]
        assert labels["module"] == "chat"
        assert labels["route"] == "/api/v1/chat/completions"
        assert labels["policy_id"] == "chat.matrix"
        assert labels["legacy"] == ("allow" if legacy_expected else "deny")
        assert labels["rg"] == ("allow" if rg_allowed else "deny")
    else:
        assert calls == []
