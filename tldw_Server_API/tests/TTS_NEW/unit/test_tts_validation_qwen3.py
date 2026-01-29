import base64
import io

import numpy as np
import pytest
import soundfile as sf

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


@pytest.mark.unit
def test_qwen3_customvoice_speaker_validation():
    request = TTSRequest(
        text="hello",
        format=AudioFormat.MP3,
        voice="NotARealSpeaker",
    )
    request.model = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
    with pytest.raises(TTSValidationError) as exc:
        validate_tts_request(request, provider="qwen3_tts")
    assert "speaker" in str(exc.value).lower()


@pytest.mark.unit
def test_qwen3_base_requires_reference_audio():
    request = TTSRequest(
        text="hello",
        format=AudioFormat.MP3,
        voice="custom:voice-1",
        extra_params={},
    )
    request.model = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
    with pytest.raises(TTSValidationError) as exc:
        validate_tts_request(request, provider="qwen3_tts")
    assert "reference" in str(exc.value).lower()


@pytest.mark.unit
def test_qwen3_base_requires_reference_audio_even_with_x_vector_only():
    request = TTSRequest(
        text="hello",
        format=AudioFormat.MP3,
        voice="custom:voice-1",
        extra_params={"x_vector_only_mode": True},
    )
    request.model = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"
    with pytest.raises(TTSValidationError) as exc:
        validate_tts_request(request, provider="qwen3_tts")
    assert "reference" in str(exc.value).lower()


@pytest.mark.unit
def test_qwen3_base_requires_reference_text_unless_x_vector_only():
    request = TTSRequest(
        text="hello",
        format=AudioFormat.MP3,
        voice="custom:voice-1",
        voice_reference=b"RIFF" + b"\x00" * 1000,
        extra_params={},
    )
    request.model = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
    with pytest.raises(TTSValidationError) as exc:
        validate_tts_request(request, provider="qwen3_tts")
    assert "reference_text" in str(exc.value).lower()


@pytest.mark.unit
def test_reference_duration_min_enforced():
    buf = io.BytesIO()
    audio = np.zeros(240, dtype=np.float32)
    sf.write(buf, audio, 24000, format="WAV", subtype="PCM_16")
    request = TTSRequest(
        text="hello",
        format=AudioFormat.MP3,
        voice="custom:voice-1",
        voice_reference=buf.getvalue(),
        extra_params={
            "reference_text": "ref transcript",
            "reference_duration_min": 1.0,
        },
    )
    request.model = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"
    with pytest.raises(TTSValidationError) as exc:
        validate_tts_request(request, provider="qwen3_tts")
    assert "too short" in str(exc.value).lower()


@pytest.mark.unit
def test_qwen3_base_default_reference_min_duration():
    buf = io.BytesIO()
    audio = np.zeros(240, dtype=np.float32)
    sf.write(buf, audio, 24000, format="WAV", subtype="PCM_16")
    request = TTSRequest(
        text="hello",
        format=AudioFormat.MP3,
        voice="custom:voice-1",
        voice_reference=buf.getvalue(),
        extra_params={
            "reference_text": "ref transcript",
        },
    )
    request.model = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
    with pytest.raises(TTSValidationError) as exc:
        validate_tts_request(request, provider="qwen3_tts")
    assert "too short" in str(exc.value).lower()
