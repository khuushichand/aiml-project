"""
Streaming configuration for the Parakeet Core Streaming module.

This module is intentionally self-contained so it can be copied into
another server (e.g., a standalone Parakeet streaming API).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class StreamingConfig:
    """Configuration for streaming transcription.

    - sample_rate: input audio rate (Hz), float32 mono expected
    - chunk_duration: seconds of audio to trigger a final segment
    - overlap_duration: seconds to keep (context) when advancing the buffer
    - max_buffer_duration: cap the buffer size (prevents runaway memory)
    - enable_partial: whether to emit partials between finals
    - partial_interval: minimum seconds between partial frames
    - min_partial_duration: minimum buffered seconds before emitting partials
    - language: optional language hint (not required for Parakeet)
    """

    # Model selection
    model: str = "parakeet"                 # currently only 'parakeet' is supported in this core
    model_variant: str = "standard"          # 'standard' | 'onnx' | 'mlx'
    # Audio & segmentation
    sample_rate: int = 16000
    chunk_duration: float = 2.0
    overlap_duration: float = 0.5
    max_buffer_duration: float = 30.0
    enable_partial: bool = True
    partial_interval: float = 0.5
    min_partial_duration: float = 0.5
    language: Optional[str] = None


__all__ = ["StreamingConfig"]
