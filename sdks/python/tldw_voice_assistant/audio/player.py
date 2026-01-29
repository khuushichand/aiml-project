"""
Audio playback for TTS responses.
"""

import io
import queue
import threading
from typing import Callable, Optional

import numpy as np
import sounddevice as sd


class AudioPlayer:
    """
    Audio playback with queue support for streaming TTS.

    Usage:
        player = AudioPlayer()

        @player.on_start
        def handle_start():
            print("Started playing")

        @player.on_end
        def handle_end():
            print("Finished playing")

        # Add chunks as they arrive
        player.add_chunk(audio_bytes, format="mp3")

        # Or play complete audio
        player.play(audio_bytes, format="mp3")
    """

    def __init__(
        self,
        sample_rate: int = 22050,
        device: Optional[int] = None,
    ):
        """
        Initialize audio player.

        Args:
            sample_rate: Output sample rate in Hz
            device: Audio device index (None for default)
        """
        self.sample_rate = sample_rate
        self.device = device

        self._queue: queue.Queue[Optional[np.ndarray]] = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._playing = False
        self._volume = 1.0

        # Callbacks
        self._on_start: list[Callable[[], None]] = []
        self._on_end: list[Callable[[], None]] = []
        self._on_error: list[Callable[[Exception], None]] = []

    def on_start(self, callback: Callable[[], None]) -> Callable[[], None]:
        """Register callback for playback start."""
        self._on_start.append(callback)
        return callback

    def on_end(self, callback: Callable[[], None]) -> Callable[[], None]:
        """Register callback for playback end."""
        self._on_end.append(callback)
        return callback

    def on_error(self, callback: Callable[[Exception], None]) -> Callable[[Exception], None]:
        """Register callback for errors."""
        self._on_error.append(callback)
        return callback

    def add_chunk(self, audio_data: bytes, format: str = "mp3") -> None:
        """
        Add an audio chunk to the playback queue.

        Args:
            audio_data: Audio bytes
            format: Audio format (mp3, wav, pcm)
        """
        try:
            samples = self._decode_audio(audio_data, format)
            self._queue.put(samples)

            # Start playback thread if not running
            if not self._running:
                self._start_playback_thread()

        except Exception as e:
            for callback in self._on_error:
                callback(e)

    def play(self, audio_data: bytes, format: str = "mp3", blocking: bool = False) -> None:
        """
        Play audio data.

        Args:
            audio_data: Audio bytes
            format: Audio format (mp3, wav, pcm)
            blocking: Wait for playback to complete
        """
        try:
            samples = self._decode_audio(audio_data, format)

            if blocking:
                sd.play(samples * self._volume, self.sample_rate, device=self.device)
                sd.wait()
            else:
                self._queue.put(samples)
                if not self._running:
                    self._start_playback_thread()

        except Exception as e:
            for callback in self._on_error:
                callback(e)

    def stop(self) -> None:
        """Stop playback and clear queue."""
        # Clear queue
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

        # Stop current playback
        sd.stop()

        # Signal thread to stop
        self._queue.put(None)
        self._running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
            self._thread = None

    def set_volume(self, volume: float) -> None:
        """
        Set playback volume.

        Args:
            volume: Volume level (0.0 - 1.0)
        """
        self._volume = max(0.0, min(1.0, volume))

    def get_volume(self) -> float:
        """Get current volume."""
        return self._volume

    def is_playing(self) -> bool:
        """Check if currently playing."""
        return self._playing

    def _start_playback_thread(self) -> None:
        """Start the playback thread."""
        self._running = True
        self._thread = threading.Thread(target=self._playback_loop, daemon=True)
        self._thread.start()

    def _playback_loop(self) -> None:
        """Main playback loop."""
        first_chunk = True

        while self._running:
            try:
                # Get next chunk (with timeout to allow stopping)
                samples = self._queue.get(timeout=0.1)

                if samples is None:
                    break

                if first_chunk:
                    first_chunk = False
                    self._playing = True
                    for callback in self._on_start:
                        callback()

                # Play audio
                sd.play(samples * self._volume, self.sample_rate, device=self.device)
                sd.wait()

            except queue.Empty:
                if self._playing and self._queue.empty():
                    self._playing = False
                    for callback in self._on_end:
                        callback()
                    first_chunk = True
                continue
            except Exception as e:
                for callback in self._on_error:
                    callback(e)

        self._playing = False

    def _decode_audio(self, audio_data: bytes, format: str) -> np.ndarray:
        """
        Decode audio bytes to numpy array.

        Args:
            audio_data: Audio bytes
            format: Audio format

        Returns:
            numpy array of float32 samples
        """
        if format == "pcm":
            # Assume float32 PCM
            return np.frombuffer(audio_data, dtype=np.float32)

        elif format == "wav":
            # Use soundfile if available, otherwise scipy
            try:
                import soundfile as sf

                samples, _ = sf.read(io.BytesIO(audio_data), dtype="float32")
                return samples
            except ImportError:
                from scipy.io import wavfile

                rate, samples = wavfile.read(io.BytesIO(audio_data))
                return samples.astype(np.float32) / 32768.0

        elif format in ("mp3", "opus"):
            # Use pydub for compressed formats
            try:
                from pydub import AudioSegment

                audio = AudioSegment.from_file(io.BytesIO(audio_data), format=format)
                samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
                samples = samples / 32768.0  # Normalize

                # Convert to mono if stereo
                if audio.channels == 2:
                    samples = samples.reshape(-1, 2).mean(axis=1)

                return samples

            except ImportError:
                raise ImportError(
                    f"Decoding {format} requires pydub. Install with: pip install pydub"
                )

        else:
            raise ValueError(f"Unsupported audio format: {format}")
