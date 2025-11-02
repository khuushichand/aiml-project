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
        """
        Add a numpy audio chunk to the buffer, normalizing it to mono float32 and trimming the buffer to the configured maximum duration.

        Parameters:
            audio_chunk (np.ndarray | None): Audio samples to add. Accepts a 1-D array of samples or a 2-D array (frames x channels); multi-channel input is converted to mono by averaging channels. If `None` or an empty array is provided, the call is ignored.

        Detailed behavior:
            - Converts input to dtype `float32` if necessary.
            - Converts multi-dimensional audio to mono by averaging across channels.
            - Appends the resulting chunk to the internal buffer.
            - If the total buffered samples exceed `sample_rate * max_duration`, keeps only the most recent samples up to that maximum duration.
        """
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
        """
        Get the total duration of audio currently buffered.

        Returns:
            float: Total duration of the buffered audio in seconds; returns 0.0 when the buffer is empty.
        """
        if not self.data:
            return 0.0
        total_samples = sum(len(chunk) for chunk in self.data)
        return float(total_samples) / float(self.sample_rate or 1)

    def get_audio(self, duration: Optional[float] = None) -> Optional[np.ndarray]:
        """
        Return buffered mono audio as a contiguous float32 array, optionally limited to a requested duration.

        If duration is omitted, returns all buffered samples concatenated. If duration is provided, returns the first samples corresponding to that duration when the buffer contains at least that many samples; returns `None` if the buffer is empty or does not contain enough samples. Returned arrays are mono float32 and are copies of the buffered data.

        Parameters:
            duration (Optional[float]): Desired length in seconds of the returned audio. If `None`, the entire buffer is returned.

        Returns:
            Optional[np.ndarray]: A contiguous 1-D numpy array of mono float32 samples of the requested length, or `None` if the buffer is empty or does not contain enough samples.
        """
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
        """
        Advance the buffer by a given duration while optionally retaining an overlap window.

        Parameters:
            duration (float): Number of seconds to remove from the start of the buffered audio. Values less than 0 are treated as 0.
            overlap (float): Number of seconds to keep from the start of the remaining audio after consuming `duration`; values less than 0 are treated as 0.

        Behavior:
            - If the buffer is empty, does nothing.
            - If the buffer contains more samples than the requested consume amount minus overlap, the buffer is replaced with the remaining tail (keeping the overlap).
            - If there are not enough samples to satisfy the consume request, the buffer is cleared.
        """
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
        """
        Clear all buffered audio chunks.

        Removes all stored audio data so the buffer becomes empty.
        """
        self.data.clear()


__all__ = ["AudioBuffer"]
