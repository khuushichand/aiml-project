"""Registry for image generation backends."""

from __future__ import annotations

import importlib
import json
from typing import Any, Dict, Optional, Type

from loguru import logger

from tldw_Server_API.app.core.Image_Generation.adapters.base import ImageGenerationAdapter
from tldw_Server_API.app.core.Image_Generation.config import get_image_generation_config


class ImageAdapterRegistry:
    """Registry for image generation adapters."""

    DEFAULT_ADAPTERS: Dict[str, str] = {
        "stable_diffusion_cpp": "tldw_Server_API.app.core.Image_Generation.adapters.stable_diffusion_cpp_adapter.StableDiffusionCppAdapter",
    }

    def __init__(self, config_override: Optional[Dict[str, Any]] = None) -> None:
        config = get_image_generation_config()
        default_backend = config.default_backend
        enabled_backends = list(config.enabled_backends)
        if config_override:
            if "default_backend" in config_override:
                default_backend = str(config_override.get("default_backend") or "").strip() or None
            if "enabled_backends" in config_override:
                enabled_backends = self._parse_list(config_override.get("enabled_backends"))
        self._default_backend = default_backend
        self._enabled_backends = enabled_backends
        self._adapters: Dict[str, ImageGenerationAdapter] = {}
        self._adapter_specs: Dict[str, Any] = self.DEFAULT_ADAPTERS.copy()

    def register_adapter(self, name: str, adapter: Any) -> None:
        self._adapter_specs[name] = adapter
        try:
            adapter_name = adapter.__name__  # type: ignore[attr-defined]
        except Exception:
            adapter_name = str(adapter)
        logger.info("Registered image adapter %s for backend '%s'", adapter_name, name)

    def list_backend_names(self, *, include_disabled: bool = False) -> list[str]:
        names = list(self._adapter_specs.keys())
        if include_disabled:
            return names
        if not self._enabled_backends:
            return []
        return [name for name in names if name in self._enabled_backends]

    def _resolve_adapter_class(self, spec: Any) -> Type[ImageGenerationAdapter]:
        if isinstance(spec, str):
            module_path, _, class_name = spec.rpartition(".")
            if not module_path:
                raise ImportError(f"Invalid adapter spec '{spec}'")
            module = importlib.import_module(module_path)
            return getattr(module, class_name)
        return spec

    def _is_enabled(self, name: str) -> bool:
        if not self._enabled_backends:
            return False
        return name in self._enabled_backends

    def resolve_backend(self, requested: Optional[str]) -> Optional[str]:
        name = (requested or self._default_backend or "").strip()
        if not name:
            return None
        if not self._is_enabled(name):
            return None
        if name not in self._adapter_specs:
            return None
        return name

    def get_adapter(self, name: str) -> Optional[ImageGenerationAdapter]:
        if name in self._adapters:
            return self._adapters[name]

        spec = self._adapter_specs.get(name)
        if not spec:
            logger.debug("No image adapter spec registered for backend '%s'", name)
            return None

        try:
            adapter_cls = self._resolve_adapter_class(spec)
            adapter = adapter_cls()  # type: ignore[call-arg]
            self._adapters[name] = adapter
            return adapter
        except Exception as exc:
            logger.error("Failed to initialize image adapter for '%s': %s", name, exc)
            return None

    def get_adapter_class(self, name: str) -> Optional[Type[ImageGenerationAdapter]]:
        spec = self._adapter_specs.get(name)
        if not spec:
            logger.debug("No image adapter spec registered for backend '%s'", name)
            return None
        try:
            return self._resolve_adapter_class(spec)
        except Exception as exc:
            logger.error("Failed to resolve image adapter class for '%s': %s", name, exc)
            return None

    @staticmethod
    def _parse_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        raw = str(value).strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = None
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
        return [item.strip() for item in raw.split(",") if item.strip()]


_registry: Optional[ImageAdapterRegistry] = None


def get_registry() -> ImageAdapterRegistry:
    global _registry
    if _registry is None:
        _registry = ImageAdapterRegistry()
    return _registry


def reset_registry() -> None:
    global _registry
    _registry = None
