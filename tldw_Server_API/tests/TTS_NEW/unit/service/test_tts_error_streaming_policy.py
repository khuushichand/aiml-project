import pytest
from unittest.mock import AsyncMock, MagicMock

from tldw_Server_API.app.api.v1.schemas.audio_schemas import OpenAISpeechRequest
from tldw_Server_API.app.core.TTS.tts_service_v2 import TTSServiceV2
from tldw_Server_API.app.core.TTS.adapters.base import TTSAdapter, TTSRequest, TTSResponse, AudioFormat, ProviderStatus, TTSCapabilities
from tldw_Server_API.app.core.TTS.tts_exceptions import TTSProviderError


class FailingAdapter(TTSAdapter):
    def __init__(self, provider_name: str = "failing"):
        super().__init__({})
        self._status = ProviderStatus.AVAILABLE
        self._initialized = True
        self.provider_id = provider_name

    async def initialize(self) -> bool:
        self._initialized = True
        self._status = ProviderStatus.AVAILABLE
        return True

    async def generate(self, request: TTSRequest) -> TTSResponse:
        raise TTSProviderError("simulated failure", provider=self.provider_id)

    async def get_capabilities(self) -> TTSCapabilities:
        from tldw_Server_API.app.core.TTS.adapters.base import VoiceInfo
        return TTSCapabilities(
            provider_name=self.provider_id,
            supports_streaming=True,
            supports_voice_cloning=False,
            supported_languages={"en"},
            supported_formats={AudioFormat.MP3},
            max_text_length=5000,
            supported_voices=[VoiceInfo(id="v1", name="V1")],
        )


class MetricsStub:
    def register_metric(self, *args, **kwargs):
        return None

    def set_gauge(self, *args, **kwargs):
        return None

    def increment(self, *args, **kwargs):
        return None

    def observe(self, *args, **kwargs):
        return None


@pytest.mark.asyncio
async def test_stream_errors_as_audio_true_yields_error_bytes():
    # Factory/registry mock with compat flag enabled
    factory = MagicMock()
    factory.get_adapter_by_model = AsyncMock(return_value=FailingAdapter("mock"))
    registry = MagicMock()
    registry.config = {"performance": {"max_concurrent_generations": 1, "stream_errors_as_audio": True}}
    factory.registry = registry

    svc = TTSServiceV2(factory)
    svc.metrics = MetricsStub()

    req = OpenAISpeechRequest(input="Hello", model="mock", voice="v1", response_format="mp3")
    # Disable fallback so we hit direct error path
    chunks = []
    async for chunk in svc.generate_speech(req, fallback=False):
        chunks.append(chunk)

    assert len(chunks) >= 1
    joined = b"".join(chunks)
    assert joined.startswith(b"ERROR:")


@pytest.mark.asyncio
async def test_stream_errors_as_audio_false_raises_exception():
    factory = MagicMock()
    factory.get_adapter_by_model = AsyncMock(return_value=FailingAdapter("mock"))
    registry = MagicMock()
    registry.config = {"performance": {"max_concurrent_generations": 1, "stream_errors_as_audio": False}}
    factory.registry = registry

    svc = TTSServiceV2(factory)
    svc.metrics = MetricsStub()

    req = OpenAISpeechRequest(input="Hello", model="mock", voice="v1", response_format="mp3")

    with pytest.raises(Exception):
        # Consume the async generator to trigger exception
        async for _ in svc.generate_speech(req, fallback=False):
            pass
