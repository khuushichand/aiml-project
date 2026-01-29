# Tests for Echo-TTS specific validation rules

import pytest

from tldw_Server_API.app.core.TTS.adapters.base import AudioFormat, TTSRequest
from tldw_Server_API.app.core.TTS.tts_exceptions import TTSTextTooLongError
from tldw_Server_API.app.core.TTS.tts_validation import TTSInputValidator


def test_echo_tts_requires_voice_reference():
    request = TTSRequest(text="Hello", format=AudioFormat.WAV)
    validator = TTSInputValidator({"strict_validation": True})
    is_valid, error_message = validator.validate_request(request, provider="echo_tts")
    assert not is_valid
    assert "Voice reference" in error_message


def test_echo_tts_utf8_byte_cap():
    # Each "\u00e1" is two bytes in UTF-8; 768 chars -> 1536 bytes > 767 byte cap.
    text = "\u00e1" * 768
    validator = TTSInputValidator({"strict_validation": True})
    with pytest.raises(TTSTextTooLongError):
        validator.validate_text_length(text, provider="echo_tts")
