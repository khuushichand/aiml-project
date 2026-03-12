import httpx
import pytest

from tldw_Server_API.app.core.TTS.adapters.base import AudioFormat, TTSRequest
from tldw_Server_API.app.core.TTS.adapters.qwen3_runtime_remote import RemoteQwenRuntime
from tldw_Server_API.app.core.TTS.tts_exceptions import TTSAuthenticationError, TTSTimeoutError
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
