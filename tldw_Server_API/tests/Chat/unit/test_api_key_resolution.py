import pytest

from tldw_Server_API.app.api.v1.schemas import chat_request_schemas
from tldw_Server_API.app.api.v1.endpoints import chat as chat_endpoint
from tldw_Server_API.app.core.Chat.chat_service import resolve_provider_api_key


def test_resolver_prefers_module_keys_in_tests(monkeypatch):
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "chat/test")
    monkeypatch.delenv("TEST_MODE", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    monkeypatch.setattr(chat_request_schemas, "API_KEYS", {"openai": "module-test-key"}, raising=False)
    monkeypatch.setattr(chat_endpoint, "API_KEYS", {"openai": "module-test-key"}, raising=False)
    monkeypatch.setattr(chat_request_schemas, "get_api_keys", lambda: {"openai": "env-key"})

    assert chat_request_schemas.API_KEYS.get("openai") == "module-test-key"
    assert chat_request_schemas.get_api_keys().get("openai") == "env-key"

    resolved_key, debug_info = resolve_provider_api_key("openai")

    assert debug_info["selected_source"] == "module_override"
    assert resolved_key == "module-test-key", debug_info
    assert debug_info["test_flags"]["pytest"] is True


def test_resolver_ignores_module_keys_outside_tests(monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("TEST_MODE", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    monkeypatch.setattr(chat_request_schemas, "API_KEYS", {"openai": "module-test-key"}, raising=False)
    monkeypatch.setattr(chat_endpoint, "API_KEYS", {"openai": "module-test-key"}, raising=False)
    monkeypatch.setattr(chat_request_schemas, "get_api_keys", lambda: {"openai": "env-key"})

    resolved_key, debug_info = resolve_provider_api_key("openai")

    assert resolved_key == "env-key"
    assert debug_info["selected_source"] != "module_override"


def test_resolver_can_skip_module_preference(monkeypatch):
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "chat/test")
    monkeypatch.delenv("TEST_MODE", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    monkeypatch.setattr(chat_request_schemas, "API_KEYS", {"openai": "module-test-key"}, raising=False)
    monkeypatch.setattr(chat_endpoint, "API_KEYS", {"openai": "module-test-key"}, raising=False)
    monkeypatch.setattr(chat_request_schemas, "get_api_keys", lambda: {"openai": "env-key"})

    resolved_key, debug_info = resolve_provider_api_key(
        "openai",
        prefer_module_keys_in_tests=False,
    )

    assert resolved_key == "env-key"
    assert debug_info["selected_source"] != "module_override"


def test_get_api_keys_supports_hyphenated_provider_env_vars(monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_API_KEY", "local-key")
    monkeypatch.setenv("CUSTOM_OPENAI_API_KEY", "custom-key")
    monkeypatch.setattr(chat_request_schemas, "load_and_log_configs", lambda: {})

    keys = chat_request_schemas.get_api_keys()

    assert keys.get("local-llm") == "local-key"
    assert keys.get("custom-openai-api") == "custom-key"
