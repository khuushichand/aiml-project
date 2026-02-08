from __future__ import annotations

from typing import Any

import pytest

from tldw_Server_API.app.core.TTS.adapter_registry import TTSAdapterRegistry, TTSProvider
from tldw_Server_API.app.core.TTS.adapters.base import (
    AudioFormat,
    TTSCapabilities,
    TTSAdapter,
    TTSRequest,
    TTSResponse,
)


pytestmark = pytest.mark.unit


class _MockAdapterV1(TTSAdapter):
    async def initialize(self) -> bool:
        return True

    async def generate(self, request: TTSRequest) -> TTSResponse:
        return TTSResponse(audio_data=b"v1", format=AudioFormat.MP3, provider="mock")

    async def get_capabilities(self) -> TTSCapabilities:
        return TTSCapabilities(
            provider_name="mock",
            supported_languages={"en"},
            supported_voices=[],
            supported_formats={AudioFormat.MP3},
            max_text_length=500,
            supports_streaming=False,
        )


class _MockAdapterV2(TTSAdapter):
    async def initialize(self) -> bool:
        return True

    async def generate(self, request: TTSRequest) -> TTSResponse:
        return TTSResponse(audio_data=b"v2", format=AudioFormat.MP3, provider="mock")

    async def get_capabilities(self) -> TTSCapabilities:
        return TTSCapabilities(
            provider_name="mock",
            supported_languages={"en"},
            supported_voices=[],
            supported_formats={AudioFormat.MP3},
            max_text_length=500,
            supports_streaming=False,
        )


@pytest.mark.asyncio
async def test_registry_uses_shared_base_for_caching() -> None:
    registry = TTSAdapterRegistry(config={"mock_enabled": True}, include_defaults=False)
    registry.register_adapter(TTSProvider.MOCK, _MockAdapterV1)

    adapter1 = await registry.get_adapter(TTSProvider.MOCK)
    adapter2 = await registry.get_adapter("mock")

    assert isinstance(adapter1, TTSAdapter)
    assert adapter2 is adapter1


@pytest.mark.asyncio
async def test_registry_reregister_invalidates_cached_adapter() -> None:
    registry = TTSAdapterRegistry(config={"mock_enabled": True}, include_defaults=False)
    registry.register_adapter(TTSProvider.MOCK, _MockAdapterV1)

    first = await registry.get_adapter(TTSProvider.MOCK)
    assert isinstance(first, _MockAdapterV1)

    registry.register_adapter(TTSProvider.MOCK, _MockAdapterV2)
    second = await registry.get_adapter(TTSProvider.MOCK)

    assert isinstance(second, _MockAdapterV2)
    assert second is not first


@pytest.mark.asyncio
async def test_registry_config_callback_marks_explicitly_disabled_provider() -> None:
    registry = TTSAdapterRegistry(config={"mock_enabled": False}, include_defaults=False)
    registry.register_adapter(TTSProvider.MOCK, _MockAdapterV1)

    adapter = await registry.get_adapter(TTSProvider.MOCK)

    assert adapter is None
    assert registry._base.get_status(TTSProvider.MOCK.value).value == "disabled"


@pytest.mark.asyncio
async def test_registry_list_capabilities_returns_standard_envelope() -> None:
    registry = TTSAdapterRegistry(config={"mock_enabled": True}, include_defaults=False)
    registry.register_adapter(TTSProvider.MOCK, _MockAdapterV1)

    entries = await registry.list_capabilities()
    assert len(entries) == 1

    entry = entries[0]
    assert entry["provider"] == "mock"
    assert entry["availability"] == "enabled"
    capabilities = entry["capabilities"]
    assert isinstance(capabilities, TTSCapabilities)
    assert capabilities.provider_name == "mock"


@pytest.mark.asyncio
async def test_registry_list_capabilities_excludes_disabled_when_requested() -> None:
    registry = TTSAdapterRegistry(config={"mock_enabled": False}, include_defaults=False)
    registry.register_adapter(TTSProvider.MOCK, _MockAdapterV1)

    all_entries = await registry.list_capabilities(include_disabled=True)
    assert all_entries[0]["provider"] == "mock"
    assert all_entries[0]["availability"] == "disabled"
    assert all_entries[0]["capabilities"] is None

    enabled_entries = await registry.list_capabilities(include_disabled=False)
    assert enabled_entries == []
