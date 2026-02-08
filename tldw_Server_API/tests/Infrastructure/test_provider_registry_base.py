from __future__ import annotations

import time

import pytest

from tldw_Server_API.app.core.Infrastructure.provider_registry import (
    ProviderRegistryBase,
    ProviderRegistryConfig,
    ProviderStatus,
)


pytestmark = pytest.mark.unit


class _DummyAdapter:
    def __init__(self) -> None:
        self.ready = True


def test_register_and_cache_class_adapter() -> None:
    registry: ProviderRegistryBase[_DummyAdapter] = ProviderRegistryBase()
    registry.register_adapter("dummy", _DummyAdapter)

    adapter1 = registry.get_adapter("dummy")
    adapter2 = registry.get_adapter("dummy")

    assert adapter1 is not None
    assert adapter1 is adapter2
    assert registry.get_status("dummy") == ProviderStatus.ENABLED


def test_register_dotted_path_adapter() -> None:
    registry: ProviderRegistryBase[object] = ProviderRegistryBase()
    registry.register_adapter("counter", "collections.Counter")

    adapter = registry.get_adapter("counter")

    assert adapter is not None
    assert adapter.__class__.__name__ == "Counter"


def test_register_instance_adapter_reuses_instance() -> None:
    instance = _DummyAdapter()
    registry: ProviderRegistryBase[_DummyAdapter] = ProviderRegistryBase()
    registry.register_adapter("dummy", instance)

    assert registry.get_adapter("dummy") is instance


def test_name_normalization_and_alias_resolution() -> None:
    registry: ProviderRegistryBase[_DummyAdapter] = ProviderRegistryBase()
    registry.register_adapter("faster-whisper", _DummyAdapter, aliases=["fw"])

    assert registry.resolve_provider_name("faster_whisper") == "faster-whisper"
    assert registry.resolve_provider_name("FW") == "faster-whisper"
    assert registry.get_adapter("FW") is not None


def test_disabled_provider_returns_none_and_disabled_status() -> None:
    registry: ProviderRegistryBase[_DummyAdapter] = ProviderRegistryBase()
    registry.register_adapter("dummy", _DummyAdapter, enabled=False)

    assert registry.get_adapter("dummy") is None
    assert registry.get_status("dummy") == ProviderStatus.DISABLED


def test_unknown_provider_status_is_unknown() -> None:
    registry: ProviderRegistryBase[_DummyAdapter] = ProviderRegistryBase()

    assert registry.get_adapter("missing") is None
    assert registry.get_status("missing") == ProviderStatus.UNKNOWN


def test_failed_provider_without_retry_stays_failed() -> None:
    class _AlwaysFail:
        def __init__(self) -> None:
            raise RuntimeError("boom")

    registry: ProviderRegistryBase[object] = ProviderRegistryBase()
    registry.register_adapter("broken", _AlwaysFail)

    assert registry.get_adapter("broken") is None
    assert registry.get_status("broken") == ProviderStatus.FAILED
    assert registry.get_adapter("broken") is None
    assert registry.get_status("broken") == ProviderStatus.FAILED


def test_failed_provider_can_retry_after_window() -> None:
    state = {"attempts": 0}

    class _Flaky:
        def __init__(self) -> None:
            state["attempts"] += 1
            if state["attempts"] == 1:
                raise RuntimeError("first attempt fails")
            self.ok = True

    registry: ProviderRegistryBase[object] = ProviderRegistryBase(
        config=ProviderRegistryConfig(failure_retry_seconds=0.02)
    )
    registry.register_adapter("flaky", _Flaky)

    assert registry.get_adapter("flaky") is None
    assert registry.get_status("flaky") == ProviderStatus.FAILED

    time.sleep(0.03)

    adapter = registry.get_adapter("flaky")
    assert adapter is not None
    assert state["attempts"] == 2
    assert registry.get_status("flaky") == ProviderStatus.ENABLED
