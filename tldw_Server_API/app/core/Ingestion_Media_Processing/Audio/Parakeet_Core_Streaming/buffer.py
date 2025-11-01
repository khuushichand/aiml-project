"""
Audio buffer utilities for Parakeet Core Streaming.

The buffer stores float32 mono audio samples and provides:
- add(): append new samples
- get_duration(): seconds accumulated
- get_audio(): retrieve full or windowed slice
- consume(): advance buffer, keeping an overlap window
- clear(): reset buffer
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional
import numpy as np


@dataclass
class AudioBuffer:
    sample_rate: int
    max_duration: float
    data: List[np.ndarray] = field(default_factory=list)

    def add(self, audio_chunk: np.ndarray) -> None:
        if audio_chunk is None or audio_chunk.size == 0:
            return
        # Ensure float32 mono
        if audio_chunk.dtype != np.float32:
            audio_chunk = audio_chunk.astype(np.float32)
        if audio_chunk.ndim > 1:
            audio_chunk = np.mean(audio_chunk, axis=1).astype(np.float32)
        self.data.append(audio_chunk)

        # Trim to max duration by keeping the most recent tail
        total_samples = sum(len(chunk) for chunk in self.data)
        max_samples = int(self.sample_rate * float(self.max_duration or 0.0))
        if max_samples > 0 and total_samples > max_samples:
            combined = np.concatenate(self.data) if len(self.data) > 1 else self.data[0]
            self.data = [combined[-max_samples:]]

    def get_duration(self) -> float:
        if not self.data:
            return 0.0
        total_samples = sum(len(chunk) for chunk in self.data)
        return float(total_samples) / float(self.sample_rate or 1)

    def get_audio(self, duration: Optional[float] = None) -> Optional[np.ndarray]:
        if not self.data:
            return None
        if duration is None:
            return np.concatenate(self.data) if len(self.data) > 1 else np.array(self.data[0], copy=True)

        samples_needed = int(float(duration) * float(self.sample_rate or 1))
        combined = np.concatenate(self.data) if len(self.data) > 1 else self.data[0]
        if len(combined) >= samples_needed:
            return np.array(combined[:samples_needed], copy=True)
        return None

    def consume(self, duration: float, overlap: float = 0.0) -> None:
        if not self.data:
            return
        duration = max(float(duration), 0.0)
        overlap = max(float(overlap), 0.0)
        combined = np.concatenate(self.data) if len(self.data) > 1 else self.data[0]
        samples_to_consume = int(max(duration - overlap, 0.0) * float(self.sample_rate or 1))
        if samples_to_consume > 0 and len(combined) > samples_to_consume:
            remaining = combined[samples_to_consume:]
            self.data = [remaining]
        else:
            self.data.clear()

    def clear(self) -> None:
        self.data.clear()


__all__ = ["AudioBuffer"]

