import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib import (
    parse_transcription_model,
)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("model_name", "expected_model"),
    [
        ("whisper-1", "large-v3"),
        ("whisper-large-v3", "large-v3"),
        ("whisper-large-v3-ct2", "large-v3"),
        ("whisper-base-ct2", "base"),
        ("whisper-tiny-ct2", "tiny"),
        ("whisper-large-v3-turbo", "deepdml/faster-whisper-large-v3-turbo-ct2"),
        ("whisper-large-v3-turbo-ct2", "deepdml/faster-whisper-large-v3-turbo-ct2"),
    ],
)
def test_parse_transcription_model_whisper_aliases(model_name: str, expected_model: str) -> None:
    provider, model, variant = parse_transcription_model(model_name)
    assert provider == "whisper"
    assert model == expected_model
    assert variant is None
