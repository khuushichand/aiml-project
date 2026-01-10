import numpy as np
import pytest


@pytest.mark.unit
def test_nemo_streaming_suppresses_error_sentinel(monkeypatch):
    """
    NemoStreamingTranscriber should not treat STT error sentinel strings as real user text.

    When the underlying transcriber returns a sentinel like "[Transcription error] ...",
    the streaming transcriber should ignore it (and log) rather than appending it to
    the accumulated transcript.
    """
    import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Live_Transcription_Nemo as nemo_mod

    def fake_transcribe_with_nemo(audio_data, sample_rate=16000, model="parakeet", variant="standard", language=None, chunk_duration=None, overlap_duration=15.0, chunk_callback=None):  # noqa: D401,E501
        return "[Transcription error] Nemo backend unavailable"

    monkeypatch.setattr(nemo_mod, "transcribe_with_nemo", fake_transcribe_with_nemo)

    tx = nemo_mod.NemoStreamingTranscriber(
        model="parakeet",
        variant="standard",
        language=None,
        chunk_duration=0.1,
        overlap_duration=0.0,
    )

    # Provide enough audio to trigger a chunk transcription
    samples = int(tx.sample_rate * tx.chunk_duration)
    audio_chunk = np.zeros(samples, dtype=np.float32)

    result = tx.process_chunk(audio_chunk)

    # Error sentinel should be filtered out and not returned/accumulated
    assert result is None
    assert tx.get_full_transcription() == ""


@pytest.mark.unit
def test_parakeet_rnnt_eou_token_stripped():
    """
    The helper used by the Parakeet RNNT streaming path should strip the
    literal `<EOU>` token emitted by Parakeet-Realtime-EOU style models.
    """
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Streaming_Unified import (
        _strip_parakeet_eou_token,
    )

    assert _strip_parakeet_eou_token("hello<EOU>") == "hello"
    assert _strip_parakeet_eou_token(" hi <EOU> ") == "hi"
    assert _strip_parakeet_eou_token("<EOU>") == ""
    # Non-EOU text should be unchanged aside from surrounding whitespace
    assert _strip_parakeet_eou_token("  just text  ") == "just text"
