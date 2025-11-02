import pytest

def test_provider_requires_key_map_basic():
    from tldw_Server_API.app.core.Chat.provider_config import PROVIDER_REQUIRES_KEY

    # Commercial providers should require keys
    for prov in ["openai", "anthropic", "google", "mistral", "cohere", "groq", "openrouter"]:
        assert PROVIDER_REQUIRES_KEY.get(prov) is True

    # Local providers typically do not require keys
    for prov in ["llama.cpp", "kobold", "ooba", "tabbyapi", "vllm", "local-llm", "ollama", "aphrodite"]:
        assert PROVIDER_REQUIRES_KEY.get(prov) is False
