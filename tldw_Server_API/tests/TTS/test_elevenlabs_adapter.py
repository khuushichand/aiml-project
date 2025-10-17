import pytest
import httpx

from tldw_Server_API.app.core.TTS.adapters.elevenlabs_adapter import ElevenLabsTTSAdapter
from tldw_Server_API.app.core.TTS.adapters.base import AudioFormat, TTSRequest
from tldw_Server_API.app.core.TTS.tts_exceptions import (
    TTSAuthenticationError,
    TTSRateLimitError,
    TTSTimeoutError,
    TTSProviderError,
)


def make_http_status_error(status_code: int, body: str = "") -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://api.elevenlabs.io/v1/text-to-speech/test")
    response = httpx.Response(status_code, request=request, text=body)
    return httpx.HTTPStatusError("error", request=request, response=response)


class TestElevenLabsAdapterBasics:
    @pytest.fixture
    def adapter(self):
        # Provide an API key to avoid NOT_CONFIGURED checks in some paths (we won't call initialize)
        return ElevenLabsTTSAdapter(config={"elevenlabs_api_key": "xi-test"})

    def test_accept_headers(self, adapter):
        assert adapter._get_accept_header(AudioFormat.MP3) == "audio/mpeg"
        assert adapter._get_accept_header(AudioFormat.WAV) == "audio/wav"
        assert adapter._get_accept_header(AudioFormat.OPUS) == "audio/opus"

    def test_capabilities_formats(self, adapter):
        import asyncio
        caps = asyncio.run(adapter.get_capabilities())
        formats = {f.value for f in caps.supported_formats}
        assert "mp3" in formats
        assert "wav" in formats
        assert "opus" in formats
        # Ensure legacy special-case formats are not advertised
        assert "ulaw" not in formats

    def test_voice_id_heuristic(self, adapter):
        # Alphanumeric long string should be treated as an ID
        vid = "A" * 24
        assert adapter._get_voice_id(vid) == vid
        # Known default name maps to default voice id
        assert adapter._get_voice_id("Rachel") == adapter.DEFAULT_VOICES["rachel"].id
        # Unknown name falls back to default
        assert adapter._get_voice_id("unknown-voice") == adapter.DEFAULT_VOICES["rachel"].id

    def test_model_selection(self, adapter):
        # Non-English defaults to multilingual v2
        req = TTSRequest(text="hola", language="es")
        assert adapter._select_model(req) == "eleven_multilingual_v2"
        # Override via extra params
        req2 = TTSRequest(text="test", language="en", extra_params={"model": "eleven_turbo_v2"})
        assert adapter._select_model(req2) == "eleven_turbo_v2"


class TestElevenLabsErrorMapping:
    @pytest.fixture
    def adapter(self):
        return ElevenLabsTTSAdapter(config={"elevenlabs_api_key": "xi-test"})

    def test_map_401_to_auth_error(self, adapter):
        with pytest.raises(TTSAuthenticationError):
            adapter._raise_mapped_http_error(make_http_status_error(401))

    def test_map_429_to_rate_limit(self, adapter):
        with pytest.raises(TTSRateLimitError):
            adapter._raise_mapped_http_error(make_http_status_error(429))

    def test_map_timeout_errors(self, adapter):
        with pytest.raises(TTSTimeoutError):
            adapter._raise_mapped_http_error(make_http_status_error(408))
        with pytest.raises(TTSTimeoutError):
            adapter._raise_mapped_http_error(make_http_status_error(504))

    def test_map_5xx_to_provider_error(self, adapter):
        with pytest.raises(TTSProviderError):
            adapter._raise_mapped_http_error(make_http_status_error(503))
