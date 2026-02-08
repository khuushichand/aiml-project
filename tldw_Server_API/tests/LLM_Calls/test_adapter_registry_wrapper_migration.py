from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pytest

from tldw_Server_API.app.core.LLM_Calls.adapter_registry import ChatProviderRegistry
from tldw_Server_API.app.core.LLM_Calls.providers.base import ChatProvider


pytestmark = pytest.mark.unit


class _GoodProvider(ChatProvider):
    name = "good"

    def capabilities(self) -> dict[str, Any]:
        return {"supports_streaming": True}

    def chat(self, request: dict[str, Any], *, timeout: float | None = None) -> dict[str, Any]:
        return {"id": "ok"}

    def stream(self, request: dict[str, Any], *, timeout: float | None = None) -> Iterable[str]:
        return iter([])


class _BadCapabilitiesProvider(ChatProvider):
    name = "bad"

    def capabilities(self) -> dict[str, Any]:
        raise RuntimeError("capability failure")

    def chat(self, request: dict[str, Any], *, timeout: float | None = None) -> dict[str, Any]:
        return {"id": "ok"}

    def stream(self, request: dict[str, Any], *, timeout: float | None = None) -> Iterable[str]:
        return iter([])


def test_registry_wraps_base_for_registration_and_caching() -> None:
    registry = ChatProviderRegistry(include_defaults=False)
    registry.register_adapter("good", _GoodProvider)

    adapter1 = registry.get_adapter("good")
    adapter2 = registry.get_adapter("good")

    assert isinstance(adapter1, ChatProvider)
    assert adapter1 is adapter2
    assert registry.list_providers() == ["good"]


def test_registry_capability_listing_isolation() -> None:
    registry = ChatProviderRegistry(include_defaults=False)
    registry.register_adapter("good", _GoodProvider)
    registry.register_adapter("bad", _BadCapabilitiesProvider)

    caps = registry.get_all_capabilities()
    assert caps["good"]["supports_streaming"] is True
    assert "bad" not in caps

    envelopes = {entry["provider"]: entry for entry in registry.list_capabilities()}
    assert envelopes["good"]["capabilities"]["supports_streaming"] is True
    assert envelopes["bad"]["capabilities"] is None


def test_registry_registers_default_aliases() -> None:
    registry = ChatProviderRegistry(include_defaults=False)
    registry.register_adapter("llama.cpp", _GoodProvider)

    adapter = registry.get_adapter("llama-cpp")
    assert isinstance(adapter, ChatProvider)
    assert registry.get_adapter("llamacpp") is adapter


def test_registry_config_callback_disables_provider_from_nested_config() -> None:
    registry = ChatProviderRegistry(
        config={"providers": {"good": {"enabled": False}}},
        include_defaults=False,
    )
    registry.register_adapter("good", _GoodProvider)

    assert registry.get_adapter("good") is None
    entries = {entry["provider"]: entry for entry in registry.list_capabilities()}
    assert entries["good"]["availability"] == "disabled"
    assert entries["good"]["capabilities"] is None


def test_registry_config_callback_reads_top_level_provider_enabled_flag() -> None:
    registry = ChatProviderRegistry(
        config={"good_enabled": "false"},
        include_defaults=False,
    )
    registry.register_adapter("good", _GoodProvider)

    assert registry.get_adapter("good") is None
