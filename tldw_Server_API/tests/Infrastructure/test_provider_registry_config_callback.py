from __future__ import annotations

import pytest

from tldw_Server_API.app.core.Infrastructure.provider_registry import (
    ProviderRegistryBase,
    ProviderStatus,
)


pytestmark = pytest.mark.unit


def test_provider_enabled_callback_can_disable_and_reenable_provider() -> None:
    state = {"enabled": False, "init_count": 0}

    class _Adapter:
        def __init__(self) -> None:
            state["init_count"] += 1

    registry: ProviderRegistryBase[object] = ProviderRegistryBase(
        provider_enabled_callback=lambda _: state["enabled"]
    )
    registry.register_adapter("provider", _Adapter)

    assert registry.get_status("provider") == ProviderStatus.DISABLED
    assert registry.get_adapter("provider") is None
    assert state["init_count"] == 0

    state["enabled"] = True
    adapter = registry.get_adapter("provider")
    assert adapter is not None
    assert state["init_count"] == 1
    assert registry.get_status("provider") == ProviderStatus.ENABLED


def test_provider_enabled_callback_none_defers_to_registered_state() -> None:
    registry: ProviderRegistryBase[object] = ProviderRegistryBase(
        provider_enabled_callback=lambda _: None
    )
    registry.register_adapter("provider", list)

    assert registry.get_status("provider") == ProviderStatus.ENABLED
    assert isinstance(registry.get_adapter("provider"), list)


def test_registered_disabled_state_takes_precedence_over_callback() -> None:
    registry: ProviderRegistryBase[object] = ProviderRegistryBase(
        provider_enabled_callback=lambda _: True
    )
    registry.register_adapter("provider", list, enabled=False)

    assert registry.get_status("provider") == ProviderStatus.DISABLED
    assert registry.get_adapter("provider") is None


def test_list_providers_respects_callback_for_include_disabled_false() -> None:
    registry: ProviderRegistryBase[object] = ProviderRegistryBase(
        provider_enabled_callback=lambda name: False if name == "disabled-by-config" else None
    )
    registry.register_adapter("disabled-by-config", list)
    registry.register_adapter("enabled-provider", list)

    assert registry.list_providers(include_disabled=False) == ["enabled-provider"]
    assert registry.list_providers(include_disabled=True) == [
        "disabled-by-config",
        "enabled-provider",
    ]


def test_callback_exceptions_do_not_break_registry_behavior() -> None:
    registry: ProviderRegistryBase[object] = ProviderRegistryBase(
        provider_enabled_callback=lambda _: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    registry.register_adapter("provider", list)

    assert registry.get_status("provider") == ProviderStatus.ENABLED
    assert isinstance(registry.get_adapter("provider"), list)


def test_set_provider_enabled_callback_updates_runtime_behavior() -> None:
    state = {"enabled": True}
    registry: ProviderRegistryBase[object] = ProviderRegistryBase()
    registry.register_adapter("provider", list)

    assert registry.get_status("provider") == ProviderStatus.ENABLED

    registry.set_provider_enabled_callback(lambda _: state["enabled"])
    state["enabled"] = False

    assert registry.get_status("provider") == ProviderStatus.DISABLED
    assert registry.get_adapter("provider") is None
