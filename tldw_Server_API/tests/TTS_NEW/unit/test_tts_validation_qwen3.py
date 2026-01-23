import base64

import pytest

from tldw_Server_API.app.core.TTS.adapters.base import TTSRequest, AudioFormat
from tldw_Server_API.app.core.TTS.tts_exceptions import TTSValidationError
from tldw_Server_API.app.core.TTS.tts_validation import validate_tts_request


@pytest.mark.unit
def test_voice_clone_prompt_size_limit():
    payload = base64.b64encode(b"a" * 2048).decode("utf-8")
    request = TTSRequest(
        text="hello",
        format=AudioFormat.MP3,
        extra_params={"voice_clone_prompt": payload},
    )
    cfg = {
        "providers": {"qwen3_tts": {"voice_clone_prompt_max_kb": 1}},
        "strict_validation": True,
    }
    with pytest.raises(TTSValidationError) as exc:
        validate_tts_request(request, provider="qwen3_tts", config=cfg)
    assert "voice_clone_prompt" in str(exc.value)


@pytest.mark.unit
def test_voice_clone_prompt_payload_object_valid():
    payload = {
        "format": "qwen3_tts_prompt_v1",
        "data_b64": base64.b64encode(b"abc").decode("utf-8"),
    }
    request = TTSRequest(
        text="hello",
        format=AudioFormat.MP3,
        extra_params={"voice_clone_prompt": payload},
    )
    cfg = {
        "providers": {"qwen3_tts": {"voice_clone_prompt_max_kb": 1}},
        "strict_validation": True,
    }
    # Should not raise
    validate_tts_request(request, provider="qwen3_tts", config=cfg)


@pytest.mark.unit
def test_voice_clone_prompt_payload_object_invalid_format():
    payload = {
        "format": "unknown",
        "data_b64": base64.b64encode(b"abc").decode("utf-8"),
    }
    request = TTSRequest(
        text="hello",
        format=AudioFormat.MP3,
        extra_params={"voice_clone_prompt": payload},
    )
    cfg = {
        "providers": {"qwen3_tts": {"voice_clone_prompt_max_kb": 1}},
        "strict_validation": True,
    }
    with pytest.raises(TTSValidationError) as exc:
        validate_tts_request(request, provider="qwen3_tts", config=cfg)
    assert "voice_clone_prompt" in str(exc.value)
