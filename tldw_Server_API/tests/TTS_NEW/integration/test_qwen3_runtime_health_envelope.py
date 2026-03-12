from unittest.mock import MagicMock

import pytest

import tldw_Server_API.app.api.v1.endpoints.audio.audio_health as audio_health
import tldw_Server_API.app.core.TTS.adapter_registry as adapter_registry
from tldw_Server_API.app.core.TTS.adapters.base import AudioFormat, TTSCapabilities
from tldw_Server_API.app.core.TTS.tts_service_v2 import TTSServiceV2


class _FakeRegistry:
    def list_capabilities(self, include_disabled=True):
        assert include_disabled is True
        return [
            {
                "provider": "qwen3_tts",
                "availability": "enabled",
                "capabilities": TTSCapabilities(
                    provider_name="Qwen3-TTS",
                    supported_languages={"en"},
                    supported_voices=[],
                    supported_formats={AudioFormat.PCM},
                    max_text_length=5000,
                    supports_streaming=False,
                    metadata={"runtime": "mlx", "supported_modes": ["custom_voice_preset"]},
                ),
            }
        ]


class _FakeFactory:
    def __init__(self):
        self.registry = _FakeRegistry()


class _FakeTTSService:
    def __init__(self):
        self._serializer = TTSServiceV2()._serialize_capabilities

    def get_status(self):
        return {
            "providers": {
                "qwen3_tts": {
                    "status": "enabled",
                    "availability": "enabled",
                    "initialized": True,
                    "failed": False,
                }
            },
            "available": 1,
            "total_providers": 1,
            "circuit_breakers": {"qwen3_tts:mlx": {"state": "closed"}},
        }

    async def get_capabilities(self):
        return {}

    def _serialize_capabilities(self, caps):
        return self._serializer(caps)


@pytest.mark.asyncio
async def test_qwen3_runtime_health_envelope_includes_breaker_key(monkeypatch):
    async def _fake_get_tts_factory():
        return _FakeFactory()

    monkeypatch.setattr(adapter_registry, "get_tts_factory", _fake_get_tts_factory)

    health = await audio_health.get_tts_health(
        request=MagicMock(),
        tts_service=_FakeTTSService(),
    )

    envelope = health["capabilities_envelope"][0]
    assert envelope["runtime"] == "mlx"
    assert envelope["breaker_key"] == "qwen3_tts:mlx"
    assert health["providers"]["details"]["qwen3_tts"]["breaker_key"] == "qwen3_tts:mlx"
