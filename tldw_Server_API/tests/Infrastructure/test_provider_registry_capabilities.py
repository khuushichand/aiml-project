from __future__ import annotations

import pytest

from tldw_Server_API.app.core.Infrastructure.provider_registry import (
    ProviderRegistryBase,
    ProviderStatus,
)


pytestmark = pytest.mark.unit


class _GoodAdapter:
    def capabilities(self) -> dict[str, bool]:
        return {"supports_streaming": True}


class _BadCapabilitiesAdapter:
    def capabilities(self) -> dict[str, bool]:
        raise RuntimeError("capability lookup failed")


class _NoCapabilitiesMethodAdapter:
    def __init__(self) -> None:
        self.meta = {"provider": "custom"}


def _by_provider(entries: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {str(entry["provider"]): entry for entry in entries}


def test_list_capabilities_returns_standard_envelope() -> None:
    registry: ProviderRegistryBase[object] = ProviderRegistryBase()
    registry.register_adapter("good", _GoodAdapter)

    entries = registry.list_capabilities()
    assert len(entries) == 1

    entry = entries[0]
    assert entry["provider"] == "good"
    assert entry["availability"] == ProviderStatus.ENABLED.value
    assert entry["capabilities"] == {"supports_streaming": True}


def test_list_capabilities_isolates_per_provider_errors() -> None:
    registry: ProviderRegistryBase[object] = ProviderRegistryBase()
    registry.register_adapter("good", _GoodAdapter)
    registry.register_adapter("bad", _BadCapabilitiesAdapter)

    entries = _by_provider(registry.list_capabilities())
    assert set(entries.keys()) == {"good", "bad"}

    assert entries["good"]["availability"] == ProviderStatus.ENABLED.value
    assert entries["good"]["capabilities"] == {"supports_streaming": True}

    # Capability errors are isolated to this provider only.
    assert entries["bad"]["availability"] == ProviderStatus.ENABLED.value
    assert entries["bad"]["capabilities"] is None


def test_list_capabilities_includes_disabled_entries_when_requested() -> None:
    registry: ProviderRegistryBase[object] = ProviderRegistryBase()
    registry.register_adapter("disabled-provider", _GoodAdapter, enabled=False)

    include_disabled = _by_provider(registry.list_capabilities(include_disabled=True))
    assert include_disabled["disabled-provider"]["availability"] == ProviderStatus.DISABLED.value
    assert include_disabled["disabled-provider"]["capabilities"] is None

    excluded = registry.list_capabilities(include_disabled=False)
    assert excluded == []


def test_list_capabilities_supports_custom_capability_getter() -> None:
    registry: ProviderRegistryBase[object] = ProviderRegistryBase()
    registry.register_adapter("custom", _NoCapabilitiesMethodAdapter)

    entries = registry.list_capabilities(
        capability_getter=lambda adapter: getattr(adapter, "meta", None)
    )
    assert entries[0]["capabilities"] == {"provider": "custom"}


def test_list_capabilities_marks_failed_provider_on_init_error() -> None:
    class _FailsInit:
        def __init__(self) -> None:
            raise RuntimeError("boom")

    registry: ProviderRegistryBase[object] = ProviderRegistryBase()
    registry.register_adapter("failing", _FailsInit)
    registry.register_adapter("good", _GoodAdapter)

    entries = _by_provider(registry.list_capabilities())
    assert entries["failing"]["availability"] == ProviderStatus.FAILED.value
    assert entries["failing"]["capabilities"] is None
    assert entries["good"]["availability"] == ProviderStatus.ENABLED.value
