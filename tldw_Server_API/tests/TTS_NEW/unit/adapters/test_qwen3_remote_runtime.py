import httpx
import pytest

from tldw_Server_API.app.core.TTS.adapters.base import AudioFormat, TTSRequest
from tldw_Server_API.app.core.TTS.adapters.qwen3_runtime_remote import RemoteQwenRuntime
from tldw_Server_API.app.core.TTS.tts_exceptions import (
    TTSAuthenticationError,
    TTSRateLimitError,
    TTSTimeoutError,
)
import tldw_Server_API.app.core.TTS.adapters.qwen3_runtime_remote as remote_runtime_mod


@pytest.mark.asyncio
async def test_remote_runtime_maps_qwen_clone_fields_into_extended_payload():
    runtime = RemoteQwenRuntime(
        {"base_url": "http://127.0.0.1:8001/v1/audio/speech", "api_key": "test-key"}
    )
    request = TTSRequest(
        text="hello",
        format=AudioFormat.PCM,
        voice_reference=b"VOICE_BYTES",
        extra_params={"reference_text": "ref", "voice_clone_prompt": "UFJPTVBU"},
    )

    payload = runtime._build_payload(
        request,
        resolved_model="Qwen/Qwen3-TTS-12Hz-0.6B-Base",
        mode="voice_clone",
    )

    assert payload["extra_body"]["ref_text"] == "ref"
    assert payload["extra_body"]["voice_clone_prompt"] == "UFJPTVBU"


@pytest.mark.asyncio
async def test_remote_runtime_capabilities_default_to_conservative_values():
    runtime = RemoteQwenRuntime(
        {"base_url": "http://127.0.0.1:8001/v1/audio/speech", "api_key": "test-key"}
    )

    caps = await runtime.get_capabilities()

    assert caps.supports_streaming is False
    assert caps.supports_voice_cloning is False
    assert caps.supports_emotion_control is False
    assert caps.metadata["supported_modes"] == ["custom_voice_preset"]
    assert caps.metadata["supports_uploaded_custom_voices"] is False


@pytest.mark.asyncio
async def test_remote_runtime_capabilities_allow_override():
    runtime = RemoteQwenRuntime(
        {
            "base_url": "http://127.0.0.1:8001/v1/audio/speech",
            "api_key": "test-key",
            "capability_override": {
                "supports_streaming": True,
                "supports_voice_cloning": True,
                "supports_emotion_control": True,
                "supported_modes": ["custom_voice_preset", "uploaded_custom_voice"],
                "supports_uploaded_custom_voices": True,
            },
        }
    )

    caps = await runtime.get_capabilities()

    assert caps.supports_streaming is True
    assert caps.supports_voice_cloning is True
    assert caps.supports_emotion_control is True
    assert caps.metadata["supported_modes"] == ["custom_voice_preset", "uploaded_custom_voice"]
    assert caps.metadata["supports_uploaded_custom_voices"] is True


@pytest.mark.asyncio
async def test_remote_runtime_maps_http_401_to_auth_error(monkeypatch):
    runtime = RemoteQwenRuntime(
        {"base_url": "http://127.0.0.1:8001/v1/audio/speech", "api_key": "test-key"}
    )
    request = TTSRequest(text="hello", format=AudioFormat.PCM, stream=False)

    async def fake_apost(**_kwargs):
        req = httpx.Request("POST", "http://127.0.0.1:8001/v1/audio/speech")
        return httpx.Response(401, request=req, content=b'{"error":"bad key"}')

    monkeypatch.setattr(remote_runtime_mod, "apost", fake_apost)

    with pytest.raises(TTSAuthenticationError):
        await runtime.generate(request, resolved_model="Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice", mode="custom_voice")


@pytest.mark.asyncio
async def test_remote_runtime_maps_timeout_to_tts_timeout_error(monkeypatch):
    runtime = RemoteQwenRuntime(
        {"base_url": "http://127.0.0.1:8001/v1/audio/speech", "api_key": "test-key"}
    )
    request = TTSRequest(text="hello", format=AudioFormat.PCM, stream=False)

    async def fake_apost(**_kwargs):
        raise httpx.ReadTimeout("timed out")

    monkeypatch.setattr(remote_runtime_mod, "apost", fake_apost)

    with pytest.raises(TTSTimeoutError):
        await runtime.generate(request, resolved_model="Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice", mode="custom_voice")


@pytest.mark.asyncio
async def test_remote_runtime_stream_maps_http_401_to_auth_error(monkeypatch):
    runtime = RemoteQwenRuntime(
        {"base_url": "http://127.0.0.1:8001/v1/audio/speech", "api_key": "test-key"}
    )
    request = TTSRequest(text="hello", format=AudioFormat.PCM, stream=True)

    async def fake_apost(**_kwargs):
        req = httpx.Request("POST", "http://127.0.0.1:8001/v1/audio/speech")
        return httpx.Response(401, request=req, content=b'{"error":"bad key"}')

    monkeypatch.setattr(remote_runtime_mod, "apost", fake_apost)

    response = await runtime.generate(
        request,
        resolved_model="Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
        mode="custom_voice",
    )

    with pytest.raises(TTSAuthenticationError):
        [chunk async for chunk in response.audio_stream]


@pytest.mark.asyncio
async def test_remote_runtime_stream_maps_iterator_timeout_to_tts_timeout_error(monkeypatch):
    runtime = RemoteQwenRuntime(
        {"base_url": "http://127.0.0.1:8001/v1/audio/speech", "api_key": "test-key"}
    )
    request = TTSRequest(text="hello", format=AudioFormat.PCM, stream=True)

    class _FakeStreamResponse:
        status_code = 200
        headers = {}

        def raise_for_status(self):
            return None

        async def aiter_bytes(self, chunk_size=1024):
            _ = chunk_size
            raise httpx.ReadTimeout("timed out during stream")
            yield b""  # pragma: no cover

        async def aclose(self):
            return None

    async def fake_apost(**_kwargs):
        return _FakeStreamResponse()

    monkeypatch.setattr(remote_runtime_mod, "apost", fake_apost)

    response = await runtime.generate(
        request,
        resolved_model="Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
        mode="custom_voice",
    )

    with pytest.raises(TTSTimeoutError):
        [chunk async for chunk in response.audio_stream]


@pytest.mark.asyncio
async def test_remote_runtime_maps_http_429_date_retry_after_to_rate_limit_error(monkeypatch):
    runtime = RemoteQwenRuntime(
        {"base_url": "http://127.0.0.1:8001/v1/audio/speech", "api_key": "test-key"}
    )
    request = TTSRequest(text="hello", format=AudioFormat.PCM, stream=False)

    async def fake_apost(**_kwargs):
        req = httpx.Request("POST", "http://127.0.0.1:8001/v1/audio/speech")
        return httpx.Response(
            429,
            request=req,
            headers={"retry-after": "Wed, 21 Oct 2015 07:28:00 GMT"},
            content=b'{"error":"rate limited"}',
        )

    monkeypatch.setattr(remote_runtime_mod, "apost", fake_apost)

    with pytest.raises(TTSRateLimitError) as exc:
        await runtime.generate(
            request,
            resolved_model="Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
            mode="custom_voice",
        )

    assert exc.value.retry_after is None


def test_remote_runtime_retry_after_parser_ignores_http_date():
    runtime = RemoteQwenRuntime(
        {"base_url": "http://127.0.0.1:8001/v1/audio/speech", "api_key": "test-key"}
    )

    assert runtime._parse_retry_after("120") == 120
    assert runtime._parse_retry_after(" Wed, 21 Oct 2015 07:28:00 GMT ") is None
