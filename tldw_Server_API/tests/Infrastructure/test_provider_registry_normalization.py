from __future__ import annotations

import pytest

from tldw_Server_API.app.core.Infrastructure.provider_registry import (
    ProviderRegistryBase,
    ProviderRegistryConfig,
)


pytestmark = pytest.mark.unit


class _DummyAdapter:
    def __init__(self) -> None:
        self.ok = True


def test_default_normalization_rules_are_applied() -> None:
    registry: ProviderRegistryBase[object] = ProviderRegistryBase()

    assert registry.normalize_provider_name(" Faster_Whisper ") == "faster-whisper"


def test_alias_resolution_runs_after_normalization() -> None:
    registry: ProviderRegistryBase[object] = ProviderRegistryBase()
    registry.register_adapter("faster-whisper", _DummyAdapter)
    registry.register_alias("FW", "faster_whisper")

    assert registry.resolve_provider_name("fw") == "faster-whisper"
    assert registry.resolve_provider_name("FW") == "faster-whisper"


def test_custom_normalizer_hook_is_used_for_names_and_aliases() -> None:
    registry: ProviderRegistryBase[object] = ProviderRegistryBase(
        normalize_name=lambda value: str(value).strip().upper()
    )
    registry.register_adapter("openai", _DummyAdapter)
    registry.register_alias("oai", "openai")

    assert registry.normalize_provider_name(" openai ") == "OPENAI"
    assert registry.resolve_provider_name("oai") == "OPENAI"


def test_normalization_can_be_disabled() -> None:
    registry: ProviderRegistryBase[object] = ProviderRegistryBase(
        config=ProviderRegistryConfig(normalize_names=False)
    )
    registry.register_adapter("Open_AI", _DummyAdapter)

    assert registry.normalize_provider_name("Open_AI") == "Open_AI"
    assert registry.list_providers() == ["Open_AI"]
