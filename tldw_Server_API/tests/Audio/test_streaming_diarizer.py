import numpy as np
import pytest

from pathlib import Path

from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Streaming_Unified import StreamingDiarizer


class _StubDiarizationService:
    def __init__(self, *args, **kwargs):
        self.is_available = True

    def diarize(self, audio_path, transcription_segments=None, num_speakers=None):
        segments = []
        for idx, seg in enumerate(transcription_segments or []):
            segments.append({
                **seg,
                "speaker_id": idx % 2,
                "speaker_label": f"SPEAKER_{idx % 2}",
            })
        return {
            "segments": segments,
            "speakers": [
                {"speaker_id": 0, "speaker_label": "SPEAKER_0"},
                {"speaker_id": 1, "speaker_label": "SPEAKER_1"},
            ],
        }


@pytest.mark.asyncio
async def test_streaming_diarizer_assigns_speakers(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Streaming_Unified.DiarizationService",
        _StubDiarizationService,
    )

    diarizer = StreamingDiarizer(
        sample_rate=16000,
        store_audio=True,
        storage_dir=str(tmp_path),
    )
    await diarizer.ensure_ready()
    assert diarizer.available

    audio = np.zeros(16000, dtype=np.float32)
    segment_meta = {
        "segment_id": 1,
        "segment_start": 0.0,
        "segment_end": 1.0,
        "chunk_start": 0.0,
        "chunk_end": 1.0,
        "text": "hello world",
    }

    info = await diarizer.label_segment(audio, segment_meta)
    assert info is not None
    assert info["speaker_id"] == 0
    assert info["speaker_label"] == "SPEAKER_0"

    mapping, audio_path, speakers = await diarizer.finalize()
    assert mapping[1]["speaker_id"] == 0
    assert audio_path is not None
    assert Path(audio_path).exists()
    assert speakers and len(speakers) == 2
