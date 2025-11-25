import pytest

from tldw_Server_API.app.api.v1.schemas.chat_request_schemas import ChatCompletionRequest
from tldw_Server_API.app.core.Chat.chat_service import (
    resolve_provider_and_model,
    invalidate_model_alias_caches,
)


@pytest.mark.unit
def test_resolve_provider_and_model_inline_alias(monkeypatch):
    """Inline provider/model with alias should resolve to concrete model."""
    invalidate_model_alias_caches()

    request = ChatCompletionRequest(
        model="anthropic/claude-sonnet",
        messages=[{"role": "user", "content": "Hello"}],
    )

    metrics_provider, metrics_model, selected_provider, selected_model, debug_info = (
        resolve_provider_and_model(
            request_data=request,
            metrics_default_provider="openai",
            normalize_default_provider="openai",
        )
    )

    # Metrics view preserves inline provider and alias name
    assert metrics_provider == "anthropic"
    assert metrics_model == "claude-sonnet"

    # Normalized view should keep provider but resolve model via alias mapping
    assert selected_provider == "anthropic"
    assert selected_model.startswith("claude-sonnet")
    assert selected_model != metrics_model

    # Request model should reflect the normalized model (no provider prefix)
    assert request.model == selected_model

    # Debug info captures the change in model
    assert debug_info["changed"]["model_changed"] is True
    assert debug_info["raw"]["model"] == "anthropic/claude-sonnet"
    assert debug_info["normalized"]["provider"] == "anthropic"
    assert debug_info["normalized"]["model"] == selected_model

