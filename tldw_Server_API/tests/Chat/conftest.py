"""Chat test configuration.

Fixtures for Chat tests are provided by explicitly importing
`tldw_Server_API.tests._plugins.chat_fixtures` here and by
Chat/integration/conftest_isolated.py for isolated tests.

Additionally, we relax Character-Chat rate limits for this package to avoid
flakiness in tests that incidentally hit persona chat endpoints.
"""

# Re-export shared Chat fixtures without using `pytest_plugins` in a non-top-level
# conftest (pytest>=8 restriction).
try:
    from tldw_Server_API.tests._plugins.chat_fixtures import *  # noqa: F401,F403
except Exception:
    pass

import pytest


@pytest.fixture(autouse=True)
def _override_character_chat_rate_limits_for_chat(monkeypatch):
     # Generous limits to avoid incidental 429s in tests
    monkeypatch.setenv("CHARACTER_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("CHARACTER_RATE_LIMIT_OPS", "1000000")
    monkeypatch.setenv("CHARACTER_RATE_LIMIT_WINDOW", "60")
    monkeypatch.setenv("MAX_CHARACTERS_PER_USER", "1000000")
    monkeypatch.setenv("MAX_CHATS_PER_USER", "1000000")
    monkeypatch.setenv("MAX_MESSAGES_PER_CHAT", "1000000")
    monkeypatch.setenv("MAX_CHAT_COMPLETIONS_PER_MINUTE", "1000000")
    monkeypatch.setenv("MAX_MESSAGE_SENDS_PER_MINUTE", "1000000")

    # Reset cached Character-Chat limiter so overrides take effect
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
