from __future__ import annotations

from enum import Enum

import pytest

from tldw_Server_API.app.core.Infrastructure.provider_registry import (
    ProviderRegistryBase,
    ProviderStatus,
)


pytestmark = pytest.mark.unit


def test_provider_status_from_value_handles_canonical_strings() -> None:
    assert ProviderStatus.from_value("enabled") == ProviderStatus.ENABLED
    assert ProviderStatus.from_value("failed") == ProviderStatus.FAILED
    assert ProviderStatus.from_value("disabled") == ProviderStatus.DISABLED
    assert ProviderStatus.from_value("unknown") == ProviderStatus.UNKNOWN


def test_provider_status_from_value_handles_domain_aliases() -> None:
    assert ProviderStatus.from_value("available") == ProviderStatus.ENABLED
    assert ProviderStatus.from_value("error") == ProviderStatus.FAILED
    assert ProviderStatus.from_value("not_configured") == ProviderStatus.DISABLED
    assert ProviderStatus.from_value("initializing") == ProviderStatus.UNKNOWN


def test_provider_status_from_value_handles_enum_instances() -> None:
    class ForeignStatus(Enum):
        READY = "available"
        BROKEN = "error"

    assert ProviderStatus.from_value(ForeignStatus.READY) == ProviderStatus.ENABLED
    assert ProviderStatus.from_value(ForeignStatus.BROKEN) == ProviderStatus.FAILED


def test_provider_status_from_value_unknown_inputs_default_to_unknown() -> None:
    assert ProviderStatus.from_value(None) == ProviderStatus.UNKNOWN
    assert ProviderStatus.from_value("") == ProviderStatus.UNKNOWN
    assert ProviderStatus.from_value("something-else") == ProviderStatus.UNKNOWN


def test_registry_map_status_uses_custom_mapper() -> None:
    class ExternalStatus(Enum):
        AVAILABLE = "available"
        ERROR = "error"
        DISABLED = "not_configured"

    registry: ProviderRegistryBase[object] = ProviderRegistryBase(
        status_mapper=lambda raw: raw.value if isinstance(raw, ExternalStatus) else raw
    )

    assert registry.map_status(ExternalStatus.AVAILABLE) == ProviderStatus.ENABLED
    assert registry.map_status(ExternalStatus.ERROR) == ProviderStatus.FAILED
    assert registry.map_status(ExternalStatus.DISABLED) == ProviderStatus.DISABLED


def test_registry_map_status_returns_unknown_when_mapper_raises() -> None:
    registry: ProviderRegistryBase[object] = ProviderRegistryBase(
        status_mapper=lambda _: (_ for _ in ()).throw(RuntimeError("bad mapper"))
    )

    assert registry.map_status("enabled") == ProviderStatus.UNKNOWN
