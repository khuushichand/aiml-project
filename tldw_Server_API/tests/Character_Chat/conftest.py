import pytest


@pytest.fixture(autouse=True)
def _override_character_chat_rate_limits_for_character_chat(monkeypatch):
    """Relax Character-Chat rate limits for this test package to avoid flakiness.

    Tests focused on behavior, not rate enforcement, should not fail due to
    incidental shared limiter state. Specific rate-limit tests can override
    these env vars in their own scope when needed.
    """
    monkeypatch.setenv("CHARACTER_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("CHARACTER_RATE_LIMIT_OPS", "1000000")
    monkeypatch.setenv("CHARACTER_RATE_LIMIT_WINDOW", "60")
    monkeypatch.setenv("MAX_CHARACTERS_PER_USER", "1000000")
    monkeypatch.setenv("MAX_CHATS_PER_USER", "1000000")
    monkeypatch.setenv("MAX_MESSAGES_PER_CHAT", "1000000")
    monkeypatch.setenv("MAX_CHAT_COMPLETIONS_PER_MINUTE", "1000000")
    monkeypatch.setenv("MAX_MESSAGE_SENDS_PER_MINUTE", "1000000")

    try:
        from tldw_Server_API.app.core.Character_Chat import character_rate_limiter as _crl
        _crl._rate_limiter = None  # type: ignore[attr-defined]
    except Exception:
        pass

    yield

    try:
        from tldw_Server_API.app.core.Character_Chat import character_rate_limiter as _crl
        _crl._rate_limiter = None  # type: ignore[attr-defined]
    except Exception:
        pass
