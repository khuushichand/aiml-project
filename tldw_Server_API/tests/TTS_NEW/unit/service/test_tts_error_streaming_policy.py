import pytest
from unittest.mock import AsyncMock, MagicMock

from tldw_Server_API.app.api.v1.schemas.audio_schemas import OpenAISpeechRequest
from tldw_Server_API.app.core.TTS.tts_service_v2 import TTSServiceV2
from tldw_Server_API.app.core.TTS.adapters.base import TTSAdapter, TTSRequest, TTSResponse, AudioFormat, ProviderStatus, TTSCapabilities
from tldw_Server_API.app.core.TTS.tts_exceptions import (
    TTSProviderError,
    TTSNetworkError,
    TTSTimeoutError,
)
from tldw_Server_API.app.core.TTS.adapter_registry import TTSProvider


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
    def __init__(self):
             self.registered = []
        self.gauges = []
        self.increments = []
        self.observations = []

    def register_metric(self, *args, **kwargs):

             self.registered.append((args, kwargs))

    def set_gauge(self, *args, **kwargs):

             self.gauges.append((args, kwargs))

    def increment(self, *args, **kwargs):

             self.increments.append((args, kwargs))

    def observe(self, *args, **kwargs):

             self.observations.append((args, kwargs))


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


def test_tts_service_default_stream_errors_as_audio_false(monkeypatch):


     """
    When no environment override or registry config is present,
    TTSServiceV2 should default to _stream_errors_as_audio == False so
    errors propagate as HTTP errors instead of embedded audio bytes.
    """
    # Ensure no env override is present
    monkeypatch.delenv("TTS_STREAM_ERRORS_AS_AUDIO", raising=False)

    # Factory without a registry/config so the service falls back to defaults
    factory = MagicMock()

    svc = TTSServiceV2(factory)
    assert svc._stream_errors_as_audio is False


class NetworkFailingAdapter(TTSAdapter):
    """Adapter that always fails with a retryable network-style error."""

    def __init__(self, provider_name: str = "openai"):
        super().__init__({})
        self._status = ProviderStatus.AVAILABLE
        self._initialized = True
        self.provider_id = provider_name

    async def initialize(self) -> bool:
        self._initialized = True
        self._status = ProviderStatus.AVAILABLE
        return True

    async def generate(self, request: TTSRequest) -> TTSResponse:
        raise TTSNetworkError("simulated network failure", provider=self.provider_id)

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


class TimeoutFailingAdapter(NetworkFailingAdapter):
    """Adapter that always fails with a retryable timeout error."""

    async def generate(self, request: TTSRequest) -> TTSResponse:
        raise TTSTimeoutError("simulated timeout", provider=self.provider_id)


class FallbackSuccessAdapter(TTSAdapter):
    """Fallback adapter that returns successful audio."""

    def __init__(self, provider_name: str = "elevenlabs"):
        super().__init__({})
        self._status = ProviderStatus.AVAILABLE
        self._initialized = True
        self.provider_id = provider_name

    async def initialize(self) -> bool:
        self._initialized = True
        self._status = ProviderStatus.AVAILABLE
        return True

    async def generate(self, request: TTSRequest) -> TTSResponse:
        return TTSResponse(audio_data=b"fallback-audio", format=request.format)

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


@pytest.mark.asyncio
async def test_network_error_triggers_fallback_and_metrics_increment():
    """TTSError subclasses like TTSNetworkError should trigger fallback and increment metrics."""

    primary_adapter = NetworkFailingAdapter("openai")
    fallback_adapter = FallbackSuccessAdapter("elevenlabs")

    class DummyRegistry:
        def __init__(self):
                     # Minimal adapter specs mapping so _get_fallback_adapter can see these providers
            self._adapter_specs = {
                TTSProvider.OPENAI: object(),
                TTSProvider.ELEVENLABS: object(),
            }

        async def get_adapter(self, provider_enum: TTSProvider) -> TTSAdapter:
            if provider_enum == TTSProvider.OPENAI:
                return primary_adapter
            if provider_enum == TTSProvider.ELEVENLABS:
                return fallback_adapter
            raise TTSProviderError("provider not configured", provider=str(provider_enum.value))

    class DummyFactory:
        def __init__(self):
                     self.registry = DummyRegistry()

        async def get_adapter_by_model(self, model: str) -> TTSAdapter:
            # Always return primary adapter for the initial model
            return primary_adapter

        async def get_best_adapter(self, *_, **__) -> TTSAdapter:
            # Fallback adapter chosen by _get_fallback_adapter
            return fallback_adapter

    factory = DummyFactory()
    svc = TTSServiceV2(factory)
    metrics = MetricsStub()
    svc.metrics = metrics

    req = OpenAISpeechRequest(
        input="Hello",
        model="tts-1",
        voice="alloy",
        response_format="mp3",
        stream=False,
    )

    chunks = []
    async for c in svc.generate_speech(req, fallback=True):
        chunks.append(c)

    joined = b"".join(chunks)
    assert b"fallback-audio" in joined

    # Ensure at least one fallback attempt metric was recorded
    fallback_metrics = [
        (args, kwargs)
        for args, kwargs in metrics.increments
        if args and args[0] == "tts_fallback_attempts"
    ]
    assert fallback_metrics, "Expected tts_fallback_attempts to be incremented on network error"


@pytest.mark.asyncio
async def test_timeout_error_triggers_fallback_and_metrics_increment():
    """TTSTimeoutError should also trigger fallback and increment metrics."""

    primary_adapter = TimeoutFailingAdapter("openai")
    fallback_adapter = FallbackSuccessAdapter("elevenlabs")

    class DummyRegistry:
        def __init__(self):
                     self._adapter_specs = {
                TTSProvider.OPENAI: object(),
                TTSProvider.ELEVENLABS: object(),
            }

        async def get_adapter(self, provider_enum: TTSProvider) -> TTSAdapter:
            if provider_enum == TTSProvider.OPENAI:
                return primary_adapter
            if provider_enum == TTSProvider.ELEVENLABS:
                return fallback_adapter
            raise TTSProviderError("provider not configured", provider=str(provider_enum.value))

    class DummyFactory:
        def __init__(self):
                     self.registry = DummyRegistry()

        async def get_adapter_by_model(self, model: str) -> TTSAdapter:
            return primary_adapter

        async def get_best_adapter(self, *_, **__) -> TTSAdapter:
            return fallback_adapter

    factory = DummyFactory()
    svc = TTSServiceV2(factory)
    metrics = MetricsStub()
    svc.metrics = metrics

    req = OpenAISpeechRequest(
        input="Hello",
        model="tts-1",
        voice="alloy",
        response_format="mp3",
        stream=False,
    )

    chunks = []
    async for c in svc.generate_speech(req, fallback=True):
        chunks.append(c)

    joined = b"".join(chunks)
    assert b"fallback-audio" in joined

    fallback_metrics = [
        (args, kwargs)
        for args, kwargs in metrics.increments
        if args and args[0] == "tts_fallback_attempts"
    ]
    assert fallback_metrics, "Expected tts_fallback_attempts to be incremented on timeout error"
