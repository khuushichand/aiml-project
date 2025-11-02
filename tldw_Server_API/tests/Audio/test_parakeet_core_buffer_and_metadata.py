import base64
import asyncio
import time
import types
import sys
import contextlib
import numpy as np
import pytest


@pytest.mark.unit
def test_audio_buffer_overlap_math():
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Parakeet_Core_Streaming.buffer import AudioBuffer

    sr = 10
    buf = AudioBuffer(sample_rate=sr, max_duration=10.0)

    # Add 2.0 seconds
    buf.add(np.ones(20, dtype=np.float32))
    assert abs(buf.get_duration() - 2.0) < 1e-6

    # Retrieve 1.5 seconds
    audio = buf.get_audio(1.5)
    assert isinstance(audio, np.ndarray) and len(audio) == 15

    # Consume 1.0s with 0.2s overlap -> remove 0.8s (8 samples)
    buf.consume(1.0, overlap=0.2)
    # Remaining should be ~1.2s (12 samples)
    dur = buf.get_duration()
    assert abs(dur - 1.2) < 1e-6


@pytest.mark.asyncio
async def test_transcriber_metadata_and_vocab(monkeypatch, tmp_path):
    # Monkeypatch custom vocab replacements to map 'foo' -> 'bar'
    import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Custom_Vocabulary as CV

    monkeypatch.setattr(CV, "load_replacements", lambda: {"foo": "bar"}, raising=False)

    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Parakeet_Core_Streaming.transcriber import (
        ParakeetCoreTranscriber,
    )
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Parakeet_Core_Streaming.config import (
        StreamingConfig,
    )

    # Fake decode that returns 'foo' so replacement yields 'bar'
    def _decode(audio_np, sr):
        """
        Return a placeholder transcription for the provided audio.

        Parameters:
            audio_np (ndarray): Audio samples as a 1-D NumPy array.
            sr (int): Sample rate of the audio in Hz.

        Returns:
            str: The transcription string "foo".
        """
        return "foo"

    sr = 10
    cfg = StreamingConfig(sample_rate=sr, chunk_duration=1.0, overlap_duration=0.2, enable_partial=False)
    tr = ParakeetCoreTranscriber(config=cfg, decode_fn=_decode)

    # 1.5s of audio -> should trigger one final
    audio = np.ones(int(1.5 * sr), dtype=np.float32)
    frame = await tr.process_audio_chunk(audio)
    assert frame is not None
    assert frame["type"] == "final"
    # Custom vocab applied
    assert frame["text"] == "bar"
    # Metadata correctness for first segment
    assert frame["segment_id"] == 1
    assert abs(frame["segment_start"] - 0.0) < 1e-6
    assert abs(frame["segment_end"] - 1.0) < 1e-6
    assert abs(frame["chunk_duration"] - 1.0) < 1e-6
    assert abs(frame["overlap"] - 0.0) < 1e-6
    assert abs(frame["chunk_start"] - 0.0) < 1e-6
    assert abs(frame["chunk_end"] - 1.0) < 1e-6
    assert abs(frame["new_audio_duration"] - 1.0) < 1e-6
    assert abs(frame["cumulative_audio"] - 1.0) < 1e-6

    # Add another 1.0s; second final should reflect overlap accounting
    audio2 = np.ones(int(1.0 * sr), dtype=np.float32)
    frame2 = await tr.process_audio_chunk(audio2)
    assert frame2 is not None and frame2["type"] == "final"
    assert frame2["segment_id"] == 2
    # new_audio_duration = chunk_duration - overlap = 0.8s
    assert abs(frame2["new_audio_duration"] - 0.8) < 1e-6
    # cumulative goes from 1.0 to 1.8
    assert abs(frame2["cumulative_audio"] - 1.8) < 1e-6
    # chunk window aligned: chunk_start at 0.8, end at 1.8
    assert abs(frame2["chunk_start"] - 0.8) < 1e-6
    assert abs(frame2["chunk_end"] - 1.8) < 1e-6


@pytest.mark.unit
def test_variant_decode_selection(monkeypatch):
    # Create dummy modules for each variant path
    mod_nemo = types.ModuleType("Audio_Transcription_Nemo")
    def _tx_parakeet(audio_np, sample_rate, variant="standard"):
        """
        Create a placeholder transcription label that encodes the Parakeet variant.

        Parameters:
        	audio_np (numpy.ndarray): Array of audio samples.
        	sample_rate (int): Sample rate of the audio in Hz.
        	variant (str): Variant identifier to include in the label (default: "standard").

        Returns:
        	transcription (str): String in the form `nemo:{variant}`.
        """
        return f"nemo:{variant}"
    mod_nemo.transcribe_with_parakeet = _tx_parakeet
    monkeypatch.setitem(
        sys.modules,
        "tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Nemo",
        mod_nemo,
    )

    mod_onnx = types.ModuleType("Audio_Transcription_Parakeet_ONNX")
    mod_onnx.transcribe_with_parakeet_onnx = lambda audio_np, sample_rate: "onnx:ok"
    monkeypatch.setitem(
        sys.modules,
        "tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Parakeet_ONNX",
        mod_onnx,
    )

    mod_mlx = types.ModuleType("Audio_Transcription_Parakeet_MLX")
    mod_mlx.transcribe_with_parakeet_mlx = lambda audio_np, sample_rate: "mlx:ok"
    monkeypatch.setitem(
        sys.modules,
        "tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Parakeet_MLX",
        mod_mlx,
    )

    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Parakeet_Core_Streaming.transcriber import (
        ParakeetCoreTranscriber,
    )
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Parakeet_Core_Streaming.config import (
        StreamingConfig,
    )

    sr = 10
    audio = np.zeros(5, dtype=np.float32)

    # Standard (nemo)
    tr_std = ParakeetCoreTranscriber(config=StreamingConfig(sample_rate=sr, model_variant="standard"))
    assert tr_std.decode_fn is not None
    assert tr_std._decode(audio) == "nemo:standard"

    # ONNX
    tr_onnx = ParakeetCoreTranscriber(config=StreamingConfig(sample_rate=sr, model_variant="onnx"))
    assert tr_onnx.decode_fn is not None
    assert tr_onnx._decode(audio) == "onnx:ok"

    # MLX
    tr_mlx = ParakeetCoreTranscriber(config=StreamingConfig(sample_rate=sr, model_variant="mlx"))
    assert tr_mlx.decode_fn is not None
    assert tr_mlx._decode(audio) == "mlx:ok"


@pytest.mark.asyncio
async def test_decode_offloaded_to_thread():
    # Decode function that blocks the thread briefly
    def _slow_decode(audio_np, sr):
        """
        Simulates a slow synchronous decode operation for an audio buffer.

        Parameters:
            audio_np (ndarray): Array of audio samples to decode.
            sr (int): Sample rate of the audio in Hz.

        Returns:
            str: The decoded text `"ok"`.
        """
        time.sleep(0.1)
        return "ok"

    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Parakeet_Core_Streaming.transcriber import (
        ParakeetCoreTranscriber,
    )
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Parakeet_Core_Streaming.config import (
        StreamingConfig,
    )

    sr = 10
    tr = ParakeetCoreTranscriber(config=StreamingConfig(sample_rate=sr, chunk_duration=1.0, enable_partial=False), decode_fn=_slow_decode)

    # Heartbeat task that runs while decode executes; if event loop is blocked, counter stays ~0
    ticks = {"n": 0, "stop": False}

    async def _ticker():
        """
        Continuously increments the shared ticks counter until the stop flag is set.

        This coroutine repeatedly increments ticks["n"] and yields control to the event loop on each iteration by awaiting asyncio.sleep(0), stopping when ticks["stop"] becomes truthy.
        """
        while not ticks["stop"]:
            ticks["n"] += 1
            await asyncio.sleep(0)  # yield control

    task = asyncio.create_task(_ticker())
    try:
        audio = np.ones(int(1.1 * sr), dtype=np.float32)
        frame = await tr.process_audio_chunk(audio)
        assert frame is not None and frame["type"] == "final"
    finally:
        ticks["stop"] = True
        await asyncio.sleep(0)
        task.cancel()
        with contextlib.suppress(Exception):
            await task

    # We expect the ticker to have run several times while decode ran in a thread
    assert ticks["n"] > 1
