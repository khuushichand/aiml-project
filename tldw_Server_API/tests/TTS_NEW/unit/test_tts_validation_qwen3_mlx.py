import pytest

from tldw_Server_API.app.core.TTS.adapters.base import AudioFormat, TTSRequest
from tldw_Server_API.app.core.TTS.tts_exceptions import TTSValidationError
import tldw_Server_API.app.core.TTS.utils as tts_utils
from tldw_Server_API.app.core.TTS.tts_validation import validate_tts_request


@pytest.mark.unit
def test_mlx_runtime_rejects_uploaded_custom_voice_request():
    request = TTSRequest(
        text="hello",
        voice="custom:voice-1",
        format=AudioFormat.MP3,
    )
    request.model = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"

    with pytest.raises(TTSValidationError) as exc:
        validate_tts_request(
            request,
            provider="qwen3_tts",
            config={"providers": {"qwen3_tts": {"runtime": "mlx"}}},
        )

    assert "uploaded custom voices" in str(exc.value).lower()


@pytest.mark.unit
def test_runtime_auto_on_apple_silicon_rejects_uploaded_custom_voice_request(monkeypatch):
    monkeypatch.setattr(tts_utils.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(tts_utils.platform, "machine", lambda: "arm64")

    request = TTSRequest(
        text="hello",
        voice="custom:voice-1",
        format=AudioFormat.MP3,
    )
    request.model = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"

    with pytest.raises(TTSValidationError) as exc:
        validate_tts_request(
            request,
            provider="qwen3_tts",
            config={"providers": {"qwen3_tts": {"runtime": "auto"}}},
        )

    assert "uploaded custom voices" in str(exc.value).lower()
