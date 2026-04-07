import pytest
import wave
from io import BytesIO

from tldw_Server_API.app.core.TTS.adapters.base import AudioFormat, TTSRequest
from tldw_Server_API.app.core.TTS.tts_exceptions import TTSValidationError
from tldw_Server_API.app.core.TTS.tts_validation import validate_tts_request


def _make_wav_bytes(*, seconds: int, sample_rate: int = 8000) -> bytes:
    buffer = BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * (seconds * sample_rate))
    return buffer.getvalue()


@pytest.mark.unit
def test_pocket_tts_cpp_accepts_custom_voice_without_raw_reference():
    request = TTSRequest(text="hello", voice="custom:voice-1", format=AudioFormat.MP3)

    validate_tts_request(request, provider="pocket_tts_cpp")


@pytest.mark.unit
def test_pocket_tts_cpp_rejects_requests_without_reference_or_custom_voice():
    request = TTSRequest(text="hello", voice="narrator", format=AudioFormat.MP3)

    with pytest.raises(TTSValidationError) as exc:
        validate_tts_request(request, provider="pocket_tts_cpp")

    message = str(exc.value).lower()
    assert "voice_reference" in message or "custom" in message


@pytest.mark.unit
def test_pocket_tts_cpp_rejects_voice_reference_longer_than_provider_limit():
    request = TTSRequest(
        text="hello",
        voice="alloy",
        format=AudioFormat.MP3,
        voice_reference=_make_wav_bytes(seconds=61),
    )

    with pytest.raises(TTSValidationError) as exc:
        validate_tts_request(request, provider="pocket_tts_cpp")

    assert "too long" in str(exc.value).lower() or "max" in str(exc.value).lower()
