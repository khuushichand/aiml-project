"""
Audio capture from microphone using sounddevice.
"""

import asyncio
import threading
from typing import Callable, Optional

import numpy as np
import sounddevice as sd


class AudioCapture:
    """
    Real-time audio capture from microphone.

    Usage:
        capture = AudioCapture(sample_rate=16000)

        @capture.on_data
        def handle_audio(audio_data: np.ndarray):
            # Process audio data
            pass

        @capture.on_level
        def handle_level(level: float):
            # Update level meter
            pass

        capture.start()
        # ... later
        capture.stop()
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        blocksize: int = 4096,
        device: Optional[int] = None,
    ):
        """
        Initialize audio capture.

        Args:
            sample_rate: Sample rate in Hz
            channels: Number of channels (1 for mono)
            blocksize: Audio block size
            device: Audio device index (None for default)
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.blocksize = blocksize
        self.device = device

        self._stream: Optional[sd.InputStream] = None
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # Callbacks
        self._on_data: list[Callable[[np.ndarray], None]] = []
        self._on_level: list[Callable[[float], None]] = []
        self._on_start: list[Callable[[], None]] = []
        self._on_stop: list[Callable[[], None]] = []
        self._on_error: list[Callable[[Exception], None]] = []

    def on_data(self, callback: Callable[[np.ndarray], None]) -> Callable[[np.ndarray], None]:
        """Register callback for audio data."""
        self._on_data.append(callback)
        return callback

    def on_level(self, callback: Callable[[float], None]) -> Callable[[float], None]:
        """Register callback for audio level."""
        self._on_level.append(callback)
        return callback

    def on_start(self, callback: Callable[[], None]) -> Callable[[], None]:
        """Register callback for capture start."""
        self._on_start.append(callback)
        return callback

    def on_stop(self, callback: Callable[[], None]) -> Callable[[], None]:
        """Register callback for capture stop."""
        self._on_stop.append(callback)
        return callback

    def on_error(self, callback: Callable[[Exception], None]) -> Callable[[Exception], None]:
        """Register callback for errors."""
        self._on_error.append(callback)
        return callback

    def start(self) -> None:
        """Start audio capture."""
        if self._running:
            return

        try:
            self._loop = asyncio.get_event_loop()
        except RuntimeError:
            self._loop = None

        def audio_callback(
            indata: np.ndarray,
            frames: int,
            time_info: dict,
            status: sd.CallbackFlags,
        ) -> None:
            """Audio stream callback."""
            if status:
                for callback in self._on_error:
                    callback(RuntimeError(f"Audio stream error: {status}"))

            # Convert to float32 mono
            audio_data = indata[:, 0].astype(np.float32)

            # Calculate RMS level
            rms = np.sqrt(np.mean(audio_data**2))
            level = min(1.0, rms * 10)  # Scale for better visibility

            # Dispatch callbacks
            for callback in self._on_data:
                if self._loop:
                    self._loop.call_soon_threadsafe(callback, audio_data.copy())
                else:
                    callback(audio_data.copy())

            for callback in self._on_level:
                if self._loop:
                    self._loop.call_soon_threadsafe(callback, level)
                else:
                    callback(level)

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            blocksize=self.blocksize,
            device=self.device,
            dtype=np.float32,
            callback=audio_callback,
        )

        self._stream.start()
        self._running = True

        for callback in self._on_start:
            callback()

    def stop(self) -> None:
        """Stop audio capture."""
        if not self._running:
            return

        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        self._running = False

        for callback in self._on_stop:
            callback()

    def is_active(self) -> bool:
        """Check if capture is active."""
        return self._running

    @staticmethod
    def list_devices() -> list[dict]:
        """List available audio input devices."""
        devices = []
        for i, device in enumerate(sd.query_devices()):
            if device["max_input_channels"] > 0:
                devices.append(
                    {
                        "index": i,
                        "name": device["name"],
                        "channels": device["max_input_channels"],
                        "sample_rate": device["default_samplerate"],
                    }
                )
        return devices
