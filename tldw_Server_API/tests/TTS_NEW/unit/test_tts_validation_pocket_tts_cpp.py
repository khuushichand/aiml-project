import pytest

from tldw_Server_API.app.core.TTS.adapters.base import AudioFormat, TTSRequest
from tldw_Server_API.app.core.TTS.tts_exceptions import TTSValidationError
from tldw_Server_API.app.core.TTS.tts_validation import validate_tts_request


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
