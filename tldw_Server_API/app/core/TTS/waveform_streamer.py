# waveform_streamer.py
# Description: Shared helpers to progressively encode and stream waveforms

from typing import AsyncGenerator, Optional

import numpy as np


async def stream_encoded_waveform(
    waveform: "np.ndarray",
    format: str,
    sample_rate: int,
    channels: int = 1,
    chunk_duration_sec: float = 0.2,
) -> AsyncGenerator[bytes, None]:
    """
    Progressively encode and stream a waveform as bytes in the requested format.

    Args:
        waveform: 1D float waveform in range [-1, 1] (or compatible)
        format: Target container/codec (e.g., "mp3", "wav", "opus", "flac", "aac", "pcm")
        sample_rate: Sample rate in Hz
        channels: Number of channels (default mono)
        chunk_duration_sec: Target duration per streamed chunk

    Yields:
        Encoded bytes suitable for immediate streaming to clients
    """
    # Lazy import to avoid heavy deps at import time
    from tldw_Server_API.app.core.TTS.streaming_audio_writer import (
        StreamingAudioWriter,
        AudioNormalizer,
    )

    # Ensure numpy float array
    if hasattr(waveform, "detach") and hasattr(waveform, "cpu"):
        waveform = waveform.squeeze(0).detach().cpu().numpy()
    elif not isinstance(waveform, np.ndarray):
        waveform = np.asarray(waveform)
    if waveform.ndim > 1:
        waveform = np.squeeze(waveform)

    normalizer = AudioNormalizer()
    writer = StreamingAudioWriter(format=format, sample_rate=sample_rate, channels=channels)

    try:
        chunk_samples = max(1, int(sample_rate * max(0.05, float(chunk_duration_sec))))
        for start in range(0, len(waveform), chunk_samples):
            part = waveform[start : start + chunk_samples]
            if part.size == 0:
                continue
            # Normalize to int16 for encoding
            normalized = normalizer.normalize(part, target_dtype=np.int16)
            encoded = writer.write_chunk(normalized)
            if encoded:
                yield encoded

        # Finalize
        final_bytes = writer.write_chunk(finalize=True)
        if final_bytes:
            yield final_bytes
    finally:
        writer.close()


async def encode_waveform_to_bytes(
    waveform: "np.ndarray", format: str, sample_rate: int, channels: int = 1
) -> bytes:
    """
    Encode a full waveform to bytes in the target format.
    """
    out = bytearray()
    async for chunk in stream_encoded_waveform(
        waveform, format=format, sample_rate=sample_rate, channels=channels
    ):
        out += chunk
    return bytes(out)
