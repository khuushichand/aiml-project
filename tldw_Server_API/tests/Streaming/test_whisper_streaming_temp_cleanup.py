import sys
from pathlib import Path

import numpy as np
import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Streaming_Unified import (
    UnifiedStreamingConfig,
    WhisperStreamingTranscriber,
)


@pytest.mark.unit
def test_whisper_streaming_tempfile_cleanup_on_error(monkeypatch, tmp_path):
    config = UnifiedStreamingConfig(sample_rate=16000)
    transcriber = WhisperStreamingTranscriber(config)
    transcriber.transcribe_options = {}

    class _BoomModel:
        def transcribe(self, *args, **kwargs):
            raise RuntimeError("boom")

    transcriber.model = _BoomModel()

    temp_path = tmp_path / "streaming_temp.wav"

    def fake_tempfile(*args, **kwargs):
        class _Dummy:
            name = str(temp_path)

            def __enter__(self):
                temp_path.touch()
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        return _Dummy()

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Streaming_Unified.tempfile.NamedTemporaryFile",
        fake_tempfile,
    )
    fake_soundfile = type("SoundFileMod", (), {"write": lambda path, data, sample_rate: Path(path).write_bytes(b"wav")})
    monkeypatch.setitem(sys.modules, "soundfile", fake_soundfile)

    audio_np = np.zeros(160, dtype=np.float32)

    result = transcriber._transcribe_audio(audio_np)
    assert result == ""
    assert not temp_path.exists()
