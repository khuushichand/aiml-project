import pytest

from tldw_Server_API.app.core.TTS.adapters.base import AudioFormat, TTSRequest
from tldw_Server_API.app.core.TTS.adapters.qwen3_runtime_remote import RemoteQwenRuntime


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
