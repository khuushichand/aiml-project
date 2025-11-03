from __future__ import annotations

"""
Embeddings provider adapter registry.

Lightweight registry to lazily construct embeddings adapters and expose
capability discovery for diagnostics.
"""

from typing import Any, Dict, Optional, Type
from loguru import logger
import importlib

from .providers.base import EmbeddingsProvider


class EmbeddingsProviderRegistry:
    """Registry for embeddings providers and their adapters."""

    DEFAULT_ADAPTERS: Dict[str, str] = {
        # Seed with OpenAI; others can be added later
        "openai": "tldw_Server_API.app.core.LLM_Calls.providers.openai_embeddings_adapter.OpenAIEmbeddingsAdapter",
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._adapters: Dict[str, EmbeddingsProvider] = {}
        self._adapter_specs: Dict[str, Any] = self.DEFAULT_ADAPTERS.copy()

    def register_adapter(self, name: str, adapter: Any) -> None:
        self._adapter_specs[name] = adapter
        try:
            n = adapter.__name__  # type: ignore[attr-defined]
        except Exception:
            n = str(adapter)
        logger.info(f"Registered Embeddings adapter {n} for provider '{name}'")

    def _resolve_adapter_class(self, spec: Any) -> Type[EmbeddingsProvider]:
        if isinstance(spec, str):
            module_path, _, class_name = spec.rpartition(".")
            if not module_path:
                raise ImportError(f"Invalid adapter spec '{spec}'")
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
            return cls
        return spec

    def get_adapter(self, name: str) -> Optional[EmbeddingsProvider]:
        if name in self._adapters:
            return self._adapters[name]
        spec = self._adapter_specs.get(name)
        if not spec:
            logger.debug(f"No embeddings adapter spec for provider '{name}'")
            return None
        try:
            adapter_cls = self._resolve_adapter_class(spec)
            adapter = adapter_cls()  # type: ignore[call-arg]
            if not isinstance(adapter, EmbeddingsProvider):
                logger.error(f"Embeddings adapter for '{name}' does not implement EmbeddingsProvider")
                return None
            self._adapters[name] = adapter
            return adapter
        except Exception as e:
            logger.error(f"Failed to initialize embeddings adapter for '{name}': {e}")
            return None

    def get_all_capabilities(self) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        for name in list(self._adapter_specs.keys()):
            adapter = self.get_adapter(name)
            if not adapter:
                continue
            try:
                out[name] = adapter.capabilities() or {}
            except Exception as e:
                logger.warning(f"Embeddings capability discovery failed for '{name}': {e}")
        return out


_emb_registry: Optional[EmbeddingsProviderRegistry] = None


def get_embeddings_registry() -> EmbeddingsProviderRegistry:
    global _emb_registry
    if _emb_registry is None:
        _emb_registry = EmbeddingsProviderRegistry()
    return _emb_registry

