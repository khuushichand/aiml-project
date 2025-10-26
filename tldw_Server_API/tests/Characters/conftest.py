import os
import pytest


@pytest.fixture(autouse=True)
def _override_character_chat_rate_limits(monkeypatch):
    """Relax Character-Chat rate limits for this test package.

    Sets environment variables for rate-limiter knobs to high values and resets
    the cached limiter so overrides take effect. This avoids test flakiness from
    incidental rate limits while still allowing specific tests to set stricter
    limits via env in their own scope.
    """
    # High but finite values; tests can still override per-function/class/module
    monkeypatch.setenv("CHARACTER_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("CHARACTER_RATE_LIMIT_OPS", "1000000")
    monkeypatch.setenv("CHARACTER_RATE_LIMIT_WINDOW", "60")
    monkeypatch.setenv("MAX_CHARACTERS_PER_USER", "1000000")
    monkeypatch.setenv("MAX_CHATS_PER_USER", "1000000")
    monkeypatch.setenv("MAX_MESSAGES_PER_CHAT", "1000000")
    monkeypatch.setenv("MAX_CHAT_COMPLETIONS_PER_MINUTE", "1000000")
    monkeypatch.setenv("MAX_MESSAGE_SENDS_PER_MINUTE", "1000000")

    # Reset cached limiter to pick up overrides
    try:
        from tldw_Server_API.app.core.Character_Chat import character_rate_limiter as _crl
        _crl._rate_limiter = None  # type: ignore[attr-defined]
    except Exception:
        pass

    yield

    # Ensure no cross-test leakage of limiter instance
    try:
        from tldw_Server_API.app.core.Character_Chat import character_rate_limiter as _crl
        _crl._rate_limiter = None  # type: ignore[attr-defined]
    except Exception:
        pass
