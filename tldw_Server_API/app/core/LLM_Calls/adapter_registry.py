from __future__ import annotations

"""
Chat provider adapter registry (LLM).

Mirrors the TTS adapter pattern with a lightweight registry that:
- Lazily resolves adapters from dotted paths or classes
- Caches initialized adapters
- Exposes capability discovery for endpoints/clients

Initial version ships without default adapters; providers can be registered
by initialization code or tests. Future phases may add defaults.
"""

import importlib
from typing import Any

from loguru import logger

from .providers.base import ChatProvider


class ChatProviderRegistry:
    """Registry for Chat (LLM) providers and their adapters."""

    # Default adapter mappings (lazy via dotted paths)
    DEFAULT_ADAPTERS: dict[str, str] = {
        "openai": "tldw_Server_API.app.core.LLM_Calls.providers.openai_adapter.OpenAIAdapter",
        "anthropic": "tldw_Server_API.app.core.LLM_Calls.providers.anthropic_adapter.AnthropicAdapter",
        "groq": "tldw_Server_API.app.core.LLM_Calls.providers.groq_adapter.GroqAdapter",
        "openrouter": "tldw_Server_API.app.core.LLM_Calls.providers.openrouter_adapter.OpenRouterAdapter",
        "google": "tldw_Server_API.app.core.LLM_Calls.providers.google_adapter.GoogleAdapter",
        "mistral": "tldw_Server_API.app.core.LLM_Calls.providers.mistral_adapter.MistralAdapter",
        "qwen": "tldw_Server_API.app.core.LLM_Calls.providers.qwen_adapter.QwenAdapter",
        "deepseek": "tldw_Server_API.app.core.LLM_Calls.providers.deepseek_adapter.DeepSeekAdapter",
        "huggingface": "tldw_Server_API.app.core.LLM_Calls.providers.huggingface_adapter.HuggingFaceAdapter",
        "bedrock": "tldw_Server_API.app.core.LLM_Calls.providers.bedrock_adapter.BedrockAdapter",
        "custom-openai-api": "tldw_Server_API.app.core.LLM_Calls.providers.custom_openai_adapter.CustomOpenAIAdapter",
        "custom-openai-api-2": "tldw_Server_API.app.core.LLM_Calls.providers.custom_openai_adapter.CustomOpenAIAdapter2",
        "mlx": "tldw_Server_API.app.core.LLM_Calls.providers.mlx_provider.MLXChatAdapter",
        "cohere": "tldw_Server_API.app.core.LLM_Calls.providers.cohere_adapter.CohereAdapter",
        "moonshot": "tldw_Server_API.app.core.LLM_Calls.providers.moonshot_adapter.MoonshotAdapter",
        "zai": "tldw_Server_API.app.core.LLM_Calls.providers.zai_adapter.ZaiAdapter",
        "llama.cpp": "tldw_Server_API.app.core.LLM_Calls.providers.local_adapters.LlamaCppAdapter",
        "kobold": "tldw_Server_API.app.core.LLM_Calls.providers.local_adapters.KoboldAdapter",
        "ooba": "tldw_Server_API.app.core.LLM_Calls.providers.local_adapters.OobaAdapter",
        "tabbyapi": "tldw_Server_API.app.core.LLM_Calls.providers.local_adapters.TabbyAPIAdapter",
        "vllm": "tldw_Server_API.app.core.LLM_Calls.providers.local_adapters.VLLMAdapter",
        "local-llm": "tldw_Server_API.app.core.LLM_Calls.providers.local_adapters.LocalLLMAdapter",
        "ollama": "tldw_Server_API.app.core.LLM_Calls.providers.local_adapters.OllamaAdapter",
        "aphrodite": "tldw_Server_API.app.core.LLM_Calls.providers.local_adapters.AphroditeAdapter",
    }

    def __init__(self, config: dict[str, Any] | None = None):
        # Keep config available for future adapter initialization needs
        self._config = config or {}
        self._adapters: dict[str, ChatProvider] = {}
        # Start with defaults; tests or init code can override/register more
        self._adapter_specs: dict[str, Any] = self.DEFAULT_ADAPTERS.copy()

    def register_adapter(self, name: str, adapter: Any) -> None:
        """Register an adapter class or dotted path for a provider name."""
        self._adapter_specs[name] = adapter
        try:
            n = adapter.__name__  # type: ignore[attr-defined]
        except Exception:
            n = str(adapter)
        logger.info(f"Registered LLM adapter {n} for provider '{name}'")

    def _resolve_adapter_class(self, spec: Any) -> type[ChatProvider]:
        if isinstance(spec, str):
            module_path, _, class_name = spec.rpartition(".")
            if not module_path:
                raise ImportError(f"Invalid adapter spec '{spec}'")
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
            return cls
        return spec

    def get_adapter(self, name: str) -> ChatProvider | None:
        """Return an initialized adapter instance for a provider name, if any."""
        if name in self._adapters:
            return self._adapters[name]

        spec = self._adapter_specs.get(name)
        if not spec:
            logger.debug(f"No adapter spec registered for provider '{name}'")
            return None

        try:
            adapter_cls = self._resolve_adapter_class(spec)
            adapter = adapter_cls()  # type: ignore[call-arg]
            if not isinstance(adapter, ChatProvider):
                logger.error(f"Adapter for '{name}' does not implement ChatProvider")
                return None
            self._adapters[name] = adapter
            return adapter
        except Exception as e:
            logger.error(f"Failed to initialize adapter for '{name}': {e}")
            return None

    def get_all_capabilities(self) -> dict[str, dict[str, Any]]:
        """Return capabilities for all registered providers, initializing as needed."""
        out: dict[str, dict[str, Any]] = {}
        for name in list(self._adapter_specs.keys()):
            adapter = self.get_adapter(name)
            if not adapter:
                continue
            try:
                out[name] = adapter.capabilities() or {}
            except Exception as e:
                logger.warning(f"Capability discovery failed for '{name}': {e}")
        return out

    def list_providers(self) -> list[str]:
        """Return a sorted list of registered provider names."""
        return sorted(self._adapter_specs.keys())


_registry: ChatProviderRegistry | None = None


def get_registry() -> ChatProviderRegistry:
    global _registry
    if _registry is None:
        _registry = ChatProviderRegistry()
    return _registry
