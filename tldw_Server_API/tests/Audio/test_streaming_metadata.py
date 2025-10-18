import numpy as np
import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Streaming_Unified import (
    ParakeetStreamingTranscriber,
    StreamingConfig,
)


@pytest.mark.asyncio
async def test_transcriber_emits_segment_metadata(monkeypatch):
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Streaming_Unified.load_parakeet_model",
        lambda variant: object(),
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Streaming_Unified.transcribe_with_parakeet",
        lambda audio, sr, variant: "test segment",
    )

    config = StreamingConfig(
        model_variant="standard",
        sample_rate=16000,
        chunk_duration=1.0,
        overlap_duration=0.25,
        enable_partial=False,
    )
    transcriber = ParakeetStreamingTranscriber(config)
    transcriber.initialize()

    chunk_samples = int(config.sample_rate * config.chunk_duration)
    audio_chunk = np.zeros(chunk_samples, dtype=np.float32).tobytes()

    result1 = await transcriber.process_audio_chunk(audio_chunk)
    assert result1 is not None
    assert "_audio_chunk" in result1
    result1.pop("_audio_chunk", None)
    assert result1["type"] == "final"
    assert result1["segment_id"] == 1
    assert result1["segment_start"] == pytest.approx(0.0, abs=1e-6)
    assert result1["segment_end"] == pytest.approx(config.chunk_duration, abs=1e-6)
    assert result1["chunk_start"] == pytest.approx(0.0, abs=1e-6)
    assert result1["chunk_end"] == pytest.approx(config.chunk_duration, abs=1e-6)

    # Feed a second chunk to verify overlap accounting
    result2 = await transcriber.process_audio_chunk(audio_chunk)
    assert result2 is not None
    assert "_audio_chunk" in result2
    result2.pop("_audio_chunk", None)
    assert result2["segment_id"] == 2
    expected_start = config.chunk_duration
    expected_end = config.chunk_duration + (config.chunk_duration - config.overlap_duration)
    assert result2["segment_start"] == pytest.approx(expected_start, abs=1e-6)
    assert result2["segment_end"] == pytest.approx(expected_end, abs=1e-6)
    assert result2["overlap"] == pytest.approx(config.overlap_duration, abs=1e-6)
