import os
import pytest


@pytest.mark.unit
def test_openrouter_preserves_namespaced_model(monkeypatch):
    # Ensure pytest test-mode alias logic is enabled if referenced
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "chat_service_normalization::preserve")
    from tldw_Server_API.app.core.Chat.chat_service import (
        normalize_request_provider_and_model,
    )

    class Req:
        def __init__(self):
            self.api_provider = "openrouter"
            self.model = "z-ai/glm-4.6"

    req = Req()
    provider = normalize_request_provider_and_model(req, default_provider="openrouter")
    assert provider == "openrouter"
    # For OpenRouter, provider namespaces (e.g., "z-ai/") must be preserved
    # The exact model may be mapped via catalog fallbacks, but the namespace must be preserved
    assert isinstance(req.model, str) and req.model.startswith("z-ai/")


@pytest.mark.unit
def test_openrouter_strips_redundant_openrouter_prefix(monkeypatch):
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "chat_service_normalization::strip_openrouter")
    from tldw_Server_API.app.core.Chat.chat_service import (
        normalize_request_provider_and_model,
    )

    class Req:
        def __init__(self):
            self.api_provider = "openrouter"
            self.model = "openrouter/gpt-4o-mini"

    req = Req()
    provider = normalize_request_provider_and_model(req, default_provider="openrouter")
    assert provider == "openrouter"
    # Redundant openrouter/ prefix is stripped to the plain model id
    # Catalog may normalize to a known model (e.g., gpt-4o)
    assert req.model in {"gpt-4o", "gpt-4o-mini"}


@pytest.mark.unit
def test_openrouter_alias_dummy_maps_and_preserves_namespace(monkeypatch):
    # Enable test-mode alias overrides inside normalize_request_provider_and_model
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "chat_service_normalization::alias_dummy")
    from tldw_Server_API.app.core.Chat.chat_service import (
        normalize_request_provider_and_model,
    )

    class Req:
        def __init__(self):
            self.api_provider = "openrouter"
            self.model = "dummy"

    req = Req()
    provider = normalize_request_provider_and_model(req, default_provider="openrouter")
    assert provider == "openrouter"
    # In tests, alias 'dummy' -> 'z-ai/glm-4.6' for OpenRouter and keep namespace
    assert req.model == "z-ai/glm-4.6"


@pytest.mark.unit
def test_model_availability_accepts_namespaced_request_for_plain_inventory(
    monkeypatch,
):
    from tldw_Server_API.app.core.Chat import chat_service

    monkeypatch.setattr(
        chat_service,
        "known_models_for_provider_cached",
        lambda _provider: ("glm-4.6",),
    )

    assert (
        chat_service.is_model_known_for_provider("openrouter", "z-ai/glm-4.6")
        is True
    )


@pytest.mark.unit
def test_model_availability_accepts_plain_request_for_namespaced_inventory(
    monkeypatch,
):
    from tldw_Server_API.app.core.Chat import chat_service

    monkeypatch.setattr(
        chat_service,
        "known_models_for_provider_cached",
        lambda _provider: ("z-ai/glm-4.6",),
    )

    assert chat_service.is_model_known_for_provider("openrouter", "glm-4.6") is True


@pytest.mark.unit
def test_openrouter_model_availability_accepts_display_id_for_canonical_inventory(
    monkeypatch,
):
    from tldw_Server_API.app.core.Chat import chat_service

    monkeypatch.setattr(
        chat_service,
        "known_models_for_provider_cached",
        lambda _provider: ("moonshotai/kimi-k2.5-0127",),
    )

    assert (
        chat_service.is_model_known_for_provider("openrouter", "moonshotai/kimi-k2.5")
        is True
    )


@pytest.mark.unit
def test_openrouter_model_availability_accepts_canonical_id_for_display_inventory(
    monkeypatch,
):
    from tldw_Server_API.app.core.Chat import chat_service

    monkeypatch.setattr(
        chat_service,
        "known_models_for_provider_cached",
        lambda _provider: ("moonshotai/kimi-k2.5",),
    )

    assert (
        chat_service.is_model_known_for_provider(
            "openrouter",
            "moonshotai/kimi-k2.5-0127",
        )
        is True
    )


@pytest.mark.unit
def test_openrouter_model_availability_uses_discovered_inventory_when_catalog_empty(
    monkeypatch,
):
    from tldw_Server_API.app.core.Chat import chat_service

    monkeypatch.setattr(
        chat_service,
        "known_models_for_provider_cached",
        lambda _provider: tuple(),
    )
    monkeypatch.setattr(
        chat_service,
        "_discover_openrouter_models_for_chat",
        lambda force_refresh=False: ("moonshotai/kimi-k2.5",),
    )

    assert (
        chat_service.is_model_known_for_provider(
            "openrouter",
            "moonshotai/kimi-k2.5-0127",
        )
        is True
    )


@pytest.mark.unit
def test_together_preserves_namespaced_model(monkeypatch):
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "chat_service_normalization::together_namespace")
    from tldw_Server_API.app.core.Chat.chat_service import (
        normalize_request_provider_and_model,
    )

    class Req:
        def __init__(self):
            self.api_provider = "together"
            self.model = "meta-llama/Llama-3.3-70B-Instruct-Turbo"

    req = Req()
    provider = normalize_request_provider_and_model(req, default_provider="together")
    assert provider == "together"
    assert req.model == "meta-llama/Llama-3.3-70B-Instruct-Turbo"


@pytest.mark.unit
def test_model_availability_accepts_namespaced_request_for_together_inventory(monkeypatch):
    from tldw_Server_API.app.core.Chat import chat_service

    monkeypatch.setattr(
        chat_service,
        "known_models_for_provider_cached",
        lambda _provider: ("Llama-3.3-70B-Instruct-Turbo",),
    )

    assert (
        chat_service.is_model_known_for_provider(
            "together",
            "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        )
        is True
    )
