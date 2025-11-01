"""
Parakeet Core Streaming Transcriber
----------------------------------

Self-contained streaming transcriber that:
- Buffers float32 mono audio
- Emits partial results on a cadence
- Emits final results when `chunk_duration` is reached
- Computes robust segment metadata (segment_id, starts/ends, overlap)

The transcriber accepts an optional `decode_fn(audio_np, sample_rate) -> str`
so it can wrap any Parakeet decode implementation. If omitted, it will
attempt to use the local Nemo-based `transcribe_with_parakeet` function.
"""

from __future__ import annotations

import base64
import time
from dataclasses import dataclass
import asyncio
from typing import Any, Callable, Dict, Optional, Union

import numpy as np

from .buffer import AudioBuffer
from .config import StreamingConfig


DecodeFn = Callable[[np.ndarray, int], str]


def _variant_decode_fn(model: str, variant: str) -> Optional[DecodeFn]:
    """Build a decode function for the requested model/variant.

    This core supports only Parakeet variants. For:
    - standard: Nemo Parakeet TDT (greedy)
    - onnx:     ONNX session with mel features + tokenizer (chunk merge inside impl)
    - mlx:      Apple Silicon MLX path; handles ndarray or temp wav as needed
    """
    if str(model or "").lower() != "parakeet":
        return None
    v = str(variant or "standard").lower()

    if v == "onnx":
        try:
            from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Parakeet_ONNX import (
                transcribe_with_parakeet_onnx as _tx_onnx,
            )

            def _fn(audio_np: np.ndarray, sr: int) -> str:
                return _tx_onnx(audio_np, sample_rate=sr)

            return _fn
        except Exception:
            return None
    elif v == "mlx":
        try:
            from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Parakeet_MLX import (
                transcribe_with_parakeet_mlx as _tx_mlx,
            )

            def _fn(audio_np: np.ndarray, sr: int) -> str:
                return _tx_mlx(audio_np, sample_rate=sr)

            return _fn
        except Exception:
            return None
    else:
        # standard (Nemo Parakeet TDT, greedy)
        try:
            from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Nemo import (
                transcribe_with_parakeet as _tx_nemo,
            )

            def _fn(audio_np: np.ndarray, sr: int) -> str:
                return _tx_nemo(audio_np, sample_rate=sr, variant="standard")

            return _fn
        except Exception:
            return None


@dataclass
class ParakeetCoreTranscriber:
    config: StreamingConfig
    decode_fn: Optional[DecodeFn] = None

    def __post_init__(self) -> None:
        self.buffer = AudioBuffer(sample_rate=self.config.sample_rate, max_duration=self.config.max_buffer_duration)
        self._last_partial_time = 0.0
        self._total_processed_seconds = 0.0
        self._segment_index = 0
        self._history: list[str] = []
        if self.decode_fn is None:
            self.decode_fn = _variant_decode_fn(self.config.model, self.config.model_variant)

    # --- Public API ---
    def reset(self) -> None:
        self.buffer.clear()
        self._history.clear()
        self._last_partial_time = 0.0
        self._total_processed_seconds = 0.0
        self._segment_index = 0

    def get_full_transcript(self) -> str:
        return " ".join(self._history)

    async def process_audio_chunk(self, audio: Union[bytes, str, np.ndarray]) -> Optional[Dict[str, Any]]:
        """Ingest an audio chunk and possibly emit a partial or final frame.

        Accepts:
        - raw float32 bytes
        - base64 string (float32 bytes)
        - numpy float32 array
        """
        audio_np = self._coerce_to_np(audio)
        if audio_np is None or audio_np.size == 0:
            return None
        self.buffer.add(audio_np)

        now = time.time()
        buf_dur = self.buffer.get_duration()

        # Partials
        if (
            self.config.enable_partial
            and (now - self._last_partial_time) >= float(self.config.partial_interval)
            and buf_dur > 0.5
        ):
            audio_for_partial = self.buffer.get_audio()
            if audio_for_partial is not None and audio_for_partial.size > 0:
                # Offload potentially blocking decode to a worker thread
                text = await self._decode_async(audio_for_partial)
                # Apply custom vocabulary post-replacements if enabled
                if text:
                    try:  # lazy import to keep core lightweight
                        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Custom_Vocabulary import (
                            postprocess_text_if_enabled as _cv_post,
                        )
                        text = _cv_post(text) or text
                    except Exception:
                        pass
                self._last_partial_time = now
                if text:
                    frame = {
                        "type": "partial",
                        "text": text,
                        "timestamp": now,
                        "is_final": False,
                    }
                    frame.update(self._prepare_partial_metadata(buf_dur))
                    return frame

        # Finals
        if buf_dur >= float(self.config.chunk_duration):
            audio_chunk = self.buffer.get_audio(self.config.chunk_duration)
            if audio_chunk is not None and audio_chunk.size > 0:
                # Offload potentially blocking decode to a worker thread
                text = await self._decode_async(audio_chunk)
                # Apply custom vocabulary post-replacements if enabled
                if text:
                    try:  # lazy import to keep core lightweight
                        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Custom_Vocabulary import (
                            postprocess_text_if_enabled as _cv_post,
                        )
                        text = _cv_post(text) or text
                    except Exception:
                        pass
                self.buffer.consume(self.config.chunk_duration, self.config.overlap_duration)
                if text:
                    self._history.append(text)
                    chunk_seconds = float(len(audio_chunk)) / float(self.config.sample_rate or 1)
                    frame = {
                        "type": "final",
                        "text": text,
                        "timestamp": now,
                        "is_final": True,
                    }
                    frame.update(self._prepare_final_metadata(chunk_seconds))
                    # include optional audio reference for downstream (e.g., diarization)
                    frame["_audio_chunk"] = np.array(audio_chunk, copy=True)
                    return frame

        return None

    async def flush(self) -> Optional[Dict[str, Any]]:
        if self.buffer.get_duration() <= 0:
            return None
        audio_np = self.buffer.get_audio()
        self.buffer.clear()
        if audio_np is None or audio_np.size == 0:
            return None
        # Offload potentially blocking decode to a worker thread
        text = await self._decode_async(audio_np)
        # Apply custom vocabulary post-replacements if enabled
        if text:
            try:  # lazy import to keep core lightweight
                from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Custom_Vocabulary import (
                    postprocess_text_if_enabled as _cv_post,
                )
                text = _cv_post(text) or text
            except Exception:
                pass
        if text:
            self._history.append(text)
            now = time.time()
            chunk_seconds = float(len(audio_np)) / float(self.config.sample_rate or 1)
            frame = {
                "type": "final",
                "text": text,
                "timestamp": now,
                "is_final": True,
            }
            frame.update(self._prepare_final_metadata(chunk_seconds))
            return frame
        return None

    # --- Internals ---
    def _coerce_to_np(self, audio: Union[bytes, str, np.ndarray]) -> Optional[np.ndarray]:
        if isinstance(audio, np.ndarray):
            arr = audio
        elif isinstance(audio, str):
            try:
                raw = base64.b64decode(audio)
            except Exception:
                return None
            # align to float32 sample size
            if (len(raw) % 4) != 0:
                raw = raw[: len(raw) - (len(raw) % 4)]
            arr = np.frombuffer(raw, dtype=np.float32)
        elif isinstance(audio, (bytes, bytearray)):
            raw = bytes(audio)
            # detect if base64-ish ASCII; if so, decode
            try:
                sample = raw[:16]
                if all(32 <= b <= 126 or b in (10, 13) for b in sample):
                    raw = base64.b64decode(raw)
            except Exception:
                pass
            if (len(raw) % 4) != 0:
                raw = raw[: len(raw) - (len(raw) % 4)]
            arr = np.frombuffer(raw, dtype=np.float32)
        else:
            return None

        # ensure mono float32
        if arr.dtype != np.float32:
            arr = arr.astype(np.float32)
        if arr.ndim > 1:
            arr = np.mean(arr, axis=1).astype(np.float32)
        return arr

    def _decode(self, audio_np: np.ndarray) -> str:
        # (Re)select decoder if needed (model/variant may have been updated externally)
        if not self.decode_fn:
            self.decode_fn = _variant_decode_fn(self.config.model, self.config.model_variant)
        if not self.decode_fn:
            return ""
        try:
            return str(self.decode_fn(audio_np, int(self.config.sample_rate)))
        except Exception:
            return ""

    async def _decode_async(self, audio_np: np.ndarray) -> str:
        """Run decode in a thread to avoid blocking the event loop."""
        if not self.decode_fn:
            self.decode_fn = _variant_decode_fn(self.config.model, self.config.model_variant)
        if not self.decode_fn:
            return ""
        try:
            return str(await asyncio.to_thread(self.decode_fn, audio_np, int(self.config.sample_rate)))
        except Exception:
            return ""

    def _prepare_partial_metadata(self, buffer_duration: float) -> Dict[str, float]:
        start = float(self._total_processed_seconds)
        return {
            "segment_id": self._segment_index + 1,
            "segment_start": start,
            "segment_end": start + float(buffer_duration),
            "buffer_duration": float(buffer_duration),
            "cumulative_audio": float(self._total_processed_seconds),
        }

    def _prepare_final_metadata(self, chunk_duration: float) -> Dict[str, float]:
        chunk_duration = max(float(chunk_duration), 0.0)
        overlap_cfg = max(float(self.config.overlap_duration or 0.0), 0.0)
        if self._segment_index == 0:
            overlap_used = 0.0
        else:
            overlap_used = min(overlap_cfg, chunk_duration)

        new_audio_duration = chunk_duration - overlap_used
        if self._segment_index == 0:
            new_audio_duration = chunk_duration
        if new_audio_duration < 0:
            new_audio_duration = 0.0

        segment_start = float(self._total_processed_seconds)
        segment_end = segment_start + new_audio_duration
        chunk_start = max(segment_start - overlap_used, 0.0)
        chunk_end = chunk_start + chunk_duration

        self._total_processed_seconds = segment_end
        self._segment_index += 1

        return {
            "segment_id": self._segment_index,
            "segment_start": segment_start,
            "segment_end": segment_end,
            "chunk_duration": chunk_duration,
            "overlap": overlap_used,
            "chunk_start": chunk_start,
            "chunk_end": chunk_end,
            "new_audio_duration": new_audio_duration,
            "cumulative_audio": float(self._total_processed_seconds),
        }


__all__ = ["ParakeetCoreTranscriber", "DecodeFn"]
