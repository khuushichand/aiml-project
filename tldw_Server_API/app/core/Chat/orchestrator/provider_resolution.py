"""Provider resolution helpers for the chat orchestrator."""

from __future__ import annotations


def resolve_provider(model: str | None, provider: str | None) -> str:
    """Resolve the effective provider name used by orchestration calls.

    Preserves explicit provider values and defaults to ``openai`` when the
    request omits a provider.
    """
    del model  # Reserved for future model-aware routing.
    if provider is None:
        return "openai"

    provider_name = str(provider).strip()
    return provider_name or "openai"
