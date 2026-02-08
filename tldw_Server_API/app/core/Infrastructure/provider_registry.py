from __future__ import annotations

"""
Shared provider registry foundation.

This module provides a reusable registry for provider-backed adapter domains
such as LLM, TTS, and STT. It is intentionally domain-agnostic: wrappers can
enforce adapter interfaces and domain-specific capability payloads.
"""

import importlib
import math
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Generic, TypeVar

from loguru import logger

AdapterT = TypeVar("AdapterT")


class ProviderStatus(str, Enum):
    """Canonical availability state for a provider entry."""

    ENABLED = "enabled"
    FAILED = "failed"
    DISABLED = "disabled"
    UNKNOWN = "unknown"


@dataclass
class ProviderRegistryConfig:
    """
    Base registry behavior toggles.

    Attributes:
        failure_retry_seconds:
            Retry window after initialization failure. `None` or non-positive
            values disable retries for failed providers (infinite backoff).
        normalize_names:
            When true, provider names are normalized using `normalize_name`
            (or the default normalizer when no callback is set).
        normalize_name:
            Optional callback to normalize provider names. Wrappers can inject
            domain-specific name canonicalization.
    """

    failure_retry_seconds: float | None = None
    normalize_names: bool = True
    normalize_name: Callable[[str], str] | None = None


@dataclass
class _ProviderRecord(Generic[AdapterT]):
    spec: Any
    enabled: bool = True


class ProviderRegistryBase(Generic[AdapterT]):
    """
    Shared, domain-agnostic provider registry.

    Public API:
        - register_adapter
        - register_alias
        - get_adapter
        - list_providers
        - resolve_provider_name
        - get_status / get_status_map
        - set_provider_enabled / enable_provider / disable_provider
    """

    def __init__(
        self,
        *,
        config: ProviderRegistryConfig | None = None,
        adapter_validator: Callable[[Any], bool] | None = None,
        aliases: dict[str, str] | None = None,
        normalize_name: Callable[[str], str] | None = None,
    ) -> None:
        self._config = config or ProviderRegistryConfig()
        self._adapter_validator = adapter_validator
        self._normalizer = (
            normalize_name
            or self._config.normalize_name
            or self._default_normalize_name
        )

        self._providers: dict[str, _ProviderRecord[AdapterT]] = {}
        self._aliases: dict[str, str] = {}
        self._adapter_cache: dict[str, AdapterT] = {}
        self._failed_providers: dict[str, float] = {}
        self._lock = threading.RLock()

        if aliases:
            for alias, provider_name in aliases.items():
                self.register_alias(alias, provider_name)

    @property
    def config(self) -> ProviderRegistryConfig:
        return self._config

    @staticmethod
    def _default_normalize_name(name: str) -> str:
        return str(name).strip().lower().replace("_", "-")

    def _normalize_name(self, name: str | None) -> str:
        raw = str(name or "").strip()
        if not raw:
            return ""
        if not self._config.normalize_names:
            return raw
        normalized = self._normalizer(raw)
        return str(normalized).strip()

    def resolve_provider_name(self, name: str | None) -> str:
        normalized = self._normalize_name(name)
        if not normalized:
            return ""
        return self._aliases.get(normalized, normalized)

    def register_alias(self, alias: str, provider_name: str) -> None:
        alias_key = self._normalize_name(alias)
        provider_key = self._normalize_name(provider_name)
        if not alias_key or not provider_key:
            raise ValueError("Alias and provider_name must be non-empty")
        with self._lock:
            self._aliases[alias_key] = provider_key

    def register_adapter(
        self,
        name: str,
        adapter: Any,
        *,
        aliases: list[str] | tuple[str, ...] | set[str] | None = None,
        enabled: bool = True,
    ) -> None:
        """
        Register a provider adapter spec.

        Supported adapter specs:
            - Adapter class (instantiated lazily)
            - Adapter instance (reused as-is)
            - Dotted path string ("package.module.ClassName")
        """

        provider_key = self._normalize_name(name)
        if not provider_key:
            raise ValueError("Provider name must be non-empty")

        with self._lock:
            self._providers[provider_key] = _ProviderRecord(spec=adapter, enabled=bool(enabled))
            self._adapter_cache.pop(provider_key, None)
            self._failed_providers.pop(provider_key, None)

        if aliases:
            for alias in aliases:
                self.register_alias(alias, provider_key)

    def _resolve_adapter_class(self, spec: Any) -> type[Any]:
        if isinstance(spec, str):
            module_path, _, class_name = spec.rpartition(".")
            if not module_path:
                raise ImportError(f"Invalid adapter spec '{spec}'")
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
            if not isinstance(cls, type):
                raise TypeError(f"Resolved adapter spec '{spec}' is not a class")
            return cls
        if isinstance(spec, type):
            return spec
        raise TypeError(f"Adapter spec must be class or dotted path string, got {type(spec)!r}")

    def _materialize_adapter(self, spec: Any) -> AdapterT:
        if isinstance(spec, str) or isinstance(spec, type):
            adapter_cls = self._resolve_adapter_class(spec)
            return adapter_cls()  # type: ignore[return-value,call-arg]
        return spec

    def _mark_failure_locked(self, provider_key: str) -> None:
        retry_seconds = self._config.failure_retry_seconds
        if retry_seconds is None or retry_seconds <= 0:
            self._failed_providers[provider_key] = math.inf
        else:
            self._failed_providers[provider_key] = time.time() + retry_seconds

    def _has_active_failure_locked(self, provider_key: str) -> bool:
        retry_after = self._failed_providers.get(provider_key)
        if retry_after is None:
            return False
        if math.isinf(retry_after):
            return True
        if retry_after > time.time():
            return True
        # Retry window has elapsed.
        self._failed_providers.pop(provider_key, None)
        return False

    def set_provider_enabled(self, name: str, enabled: bool) -> None:
        provider_key = self.resolve_provider_name(name)
        if not provider_key:
            raise ValueError("Provider name must be non-empty")
        with self._lock:
            record = self._providers.get(provider_key)
            if record is None:
                raise KeyError(f"Provider '{name}' is not registered")
            record.enabled = bool(enabled)
            if not enabled:
                self._adapter_cache.pop(provider_key, None)

    def enable_provider(self, name: str) -> None:
        self.set_provider_enabled(name, True)

    def disable_provider(self, name: str) -> None:
        self.set_provider_enabled(name, False)

    def get_adapter(self, name: str | None) -> AdapterT | None:
        provider_key = self.resolve_provider_name(name)
        if not provider_key:
            return None

        with self._lock:
            record = self._providers.get(provider_key)
            if record is None:
                return None
            if not record.enabled:
                return None
            if self._has_active_failure_locked(provider_key):
                return None
            cached = self._adapter_cache.get(provider_key)
            if cached is not None:
                return cached
            spec = record.spec

        try:
            adapter = self._materialize_adapter(spec)
            if self._adapter_validator and not self._adapter_validator(adapter):
                raise TypeError(f"Adapter for provider '{provider_key}' failed validation")
        except Exception as exc:
            with self._lock:
                self._mark_failure_locked(provider_key)
            logger.error("Failed to initialize adapter for provider '{}': {}", provider_key, exc)
            return None

        with self._lock:
            self._adapter_cache[provider_key] = adapter
            self._failed_providers.pop(provider_key, None)
        return adapter

    def list_providers(self, *, include_disabled: bool = True) -> list[str]:
        with self._lock:
            providers = []
            for provider_key, record in self._providers.items():
                if include_disabled or record.enabled:
                    providers.append(provider_key)
        return sorted(providers)

    def get_status(self, name: str | None) -> ProviderStatus:
        provider_key = self.resolve_provider_name(name)
        if not provider_key:
            return ProviderStatus.UNKNOWN
        with self._lock:
            record = self._providers.get(provider_key)
            if record is None:
                return ProviderStatus.UNKNOWN
            if not record.enabled:
                return ProviderStatus.DISABLED
            if self._has_active_failure_locked(provider_key):
                return ProviderStatus.FAILED
            return ProviderStatus.ENABLED

    def get_status_map(self) -> dict[str, ProviderStatus]:
        status_map: dict[str, ProviderStatus] = {}
        for provider_name in self.list_providers(include_disabled=True):
            status_map[provider_name] = self.get_status(provider_name)
        return status_map

    def clear_cache(self) -> None:
        with self._lock:
            self._adapter_cache.clear()

    def reset_failures(self) -> None:
        with self._lock:
            self._failed_providers.clear()


__all__ = [
    "ProviderRegistryBase",
    "ProviderRegistryConfig",
    "ProviderStatus",
]
