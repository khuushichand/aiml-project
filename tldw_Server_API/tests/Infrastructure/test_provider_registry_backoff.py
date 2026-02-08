from __future__ import annotations

import time

import pytest

from tldw_Server_API.app.core.Infrastructure.provider_registry import (
    ProviderRegistryBase,
    ProviderRegistryConfig,
    ProviderStatus,
)


pytestmark = pytest.mark.unit


def test_retry_disabled_uses_infinite_backoff() -> None:
    state = {"attempts": 0}

    class _AlwaysFail:
        def __init__(self) -> None:
            state["attempts"] += 1
            raise RuntimeError("boom")

    registry: ProviderRegistryBase[object] = ProviderRegistryBase()
    registry.register_adapter("broken", _AlwaysFail)

    assert registry.get_adapter("broken") is None
    assert state["attempts"] == 1
    assert registry.get_status("broken") == ProviderStatus.FAILED

    # Retry disabled: no additional init attempts.
    assert registry.get_adapter("broken") is None
    assert state["attempts"] == 1
    time.sleep(0.03)
    assert registry.get_adapter("broken") is None
    assert state["attempts"] == 1


def test_retry_window_blocks_attempts_until_expiration() -> None:
    state = {"attempts": 0}

    class _FailOnce:
        def __init__(self) -> None:
            state["attempts"] += 1
            if state["attempts"] == 1:
                raise RuntimeError("first attempt fails")
            self.ok = True

    registry: ProviderRegistryBase[object] = ProviderRegistryBase(
        config=ProviderRegistryConfig(failure_retry_seconds=0.05)
    )
    registry.register_adapter("flaky", _FailOnce)

    assert registry.get_adapter("flaky") is None
    assert state["attempts"] == 1
    assert registry.get_status("flaky") == ProviderStatus.FAILED

    # Still in backoff window; should not retry.
    assert registry.get_adapter("flaky") is None
    assert state["attempts"] == 1

    time.sleep(0.06)
    adapter = registry.get_adapter("flaky")
    assert adapter is not None
    assert state["attempts"] == 2
    assert registry.get_status("flaky") == ProviderStatus.ENABLED

    # Cached adapter: no additional construction.
    assert registry.get_adapter("flaky") is adapter
    assert state["attempts"] == 2


@pytest.mark.parametrize("retry_seconds", [0.0, -1.0])
def test_non_positive_retry_seconds_disable_retries(retry_seconds: float) -> None:
    state = {"attempts": 0}

    class _AlwaysFail:
        def __init__(self) -> None:
            state["attempts"] += 1
            raise RuntimeError("boom")

    registry: ProviderRegistryBase[object] = ProviderRegistryBase(
        config=ProviderRegistryConfig(failure_retry_seconds=retry_seconds)
    )
    registry.register_adapter("broken", _AlwaysFail)

    assert registry.get_adapter("broken") is None
    assert state["attempts"] == 1
    time.sleep(0.03)
    assert registry.get_adapter("broken") is None
    assert state["attempts"] == 1


def test_reset_failures_allows_immediate_retry() -> None:
    state = {"attempts": 0}

    class _FailOnce:
        def __init__(self) -> None:
            state["attempts"] += 1
            if state["attempts"] == 1:
                raise RuntimeError("first attempt fails")
            self.ok = True

    registry: ProviderRegistryBase[object] = ProviderRegistryBase(
        config=ProviderRegistryConfig(failure_retry_seconds=60.0)
    )
    registry.register_adapter("provider", _FailOnce)

    assert registry.get_adapter("provider") is None
    assert state["attempts"] == 1
    assert registry.get_adapter("provider") is None
    assert state["attempts"] == 1

    registry.reset_failures()
    adapter = registry.get_adapter("provider")
    assert adapter is not None
    assert state["attempts"] == 2
    assert registry.get_status("provider") == ProviderStatus.ENABLED


def test_adapter_validation_failure_enters_backoff() -> None:
    state = {"attempts": 0}

    class _ConstructsFine:
        def __init__(self) -> None:
            state["attempts"] += 1
            self.ok = True

    registry: ProviderRegistryBase[object] = ProviderRegistryBase(
        config=ProviderRegistryConfig(failure_retry_seconds=0.05),
        adapter_validator=lambda _: False,
    )
    registry.register_adapter("provider", _ConstructsFine)

    assert registry.get_adapter("provider") is None
    assert state["attempts"] == 1
    assert registry.get_status("provider") == ProviderStatus.FAILED

    # Backoff suppresses repeated constructions.
    assert registry.get_adapter("provider") is None
    assert state["attempts"] == 1

    time.sleep(0.06)
    assert registry.get_adapter("provider") is None
    assert state["attempts"] == 2
