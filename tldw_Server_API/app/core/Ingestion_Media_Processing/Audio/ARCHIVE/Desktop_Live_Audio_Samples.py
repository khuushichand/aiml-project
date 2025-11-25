"""
ARCHIVED SAMPLE CODE: Desktop / live audio utilities.

These helpers were originally embedded in `Audio_Transcription_Lib` as
interactive examples for microphone and system-audio recording. They are not
used by the server runtime or HTTP/WebSocket APIs and are provided here only
as reference/sample code for local experiments.

Notes:
- Dependencies such as `pyaudio`, `sounddevice`, and `wave` are optional and
  may not be installed in a typical server deployment.
- Error handling and APIs are oriented toward interactive scripts, not
  production usage.
- For production STT, prefer:
    * `speech_to_text(...)` for file/segment-based workflows
    * `transcribe_audio(...)` for NumPy waveform-based workflows
      (both defined in `Audio_Transcription_Lib`).
"""

from __future__ import annotations

import queue
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from scipy.io import wavfile

from tldw_Server_API.app.core.Utils.Utils import logging
from tldw_Server_API.app.core.Metrics.metrics_logger import log_counter, log_histogram, timeit
from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib import (
    transcribe_audio,
    is_transcription_error_message,
)

try:  # Optional desktop deps
    import pyaudio  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    pyaudio = None  # type: ignore

try:
    import sounddevice as sd  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    sd = None  # type: ignore

try:
    import wave  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    wave = None  # type: ignore


class PartialTranscriptionThread(threading.Thread):
    """
    Thread that performs partial (live) transcriptions on audio chunks.

    Originally used with microphone recording helpers to provide rolling,
    near-real-time transcription. Preserved here for local/desktop usage.
    """

    def __init__(
        self,
        audio_queue: "queue.Queue[bytes]",
        stop_event: threading.Event,
        partial_text_state: Dict[str, Any],
        sample_rate: int = 16000,
        chunk_size: int = 1024,
        max_buffer_seconds: float = 20.0,
        transcription_provider: str = "faster-whisper",
        whisper_model: str = "distil-large-v3",
        speaker_lang: Optional[str] = "en",
    ) -> None:
        super().__init__(daemon=True)
        self.audio_queue = audio_queue
        self.stop_event = stop_event
        self.partial_text_state = partial_text_state
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.max_buffer_seconds = max_buffer_seconds
        self.transcription_provider = transcription_provider
        self.whisper_model = whisper_model
        self.speaker_lang = speaker_lang

        self.exception_encountered: Optional[BaseException] = None

    def run(self) -> None:  # pragma: no cover - interactive/desktop helper
        try:
            buffer = b""
            max_bytes = int(self.max_buffer_seconds * self.sample_rate * 2)
            last_transcription_time = 0.0

            while not self.stop_event.is_set():
                try:
                    data = self.audio_queue.get(timeout=0.1)
                    buffer += data
                    if len(buffer) > max_bytes:
                        buffer = buffer[-max_bytes:]
                except queue.Empty:
                    pass

                now = time.time()
                if now - last_transcription_time > 1.5 and buffer:
                    audio_np = np.frombuffer(buffer, dtype=np.int16).astype(np.float32) / 32768.0
                    text = transcribe_audio(
                        audio_np,
                        transcription_provider=self.transcription_provider,
                        sample_rate=self.sample_rate,
                        speaker_lang=self.speaker_lang,
                        whisper_model=self.whisper_model,
                    )
                    if isinstance(text, str) and not is_transcription_error_message(text):
                        self.partial_text_state["text"] = text
                    last_transcription_time = now
        except BaseException as exc:
            self.exception_encountered = exc


def record_audio_to_disk(device_id: int, output_file_path: str, stop_event: threading.Event, audio_queue: "queue.Queue[bytes]") -> None:
    """
    Record audio from a PyAudio device to disk while feeding a queue.

    This helper is intended for desktop usage and depends on PyAudio.
    """
    if pyaudio is None:  # pragma: no cover - optional dependency
        raise RuntimeError("PyAudio is not available; install it to use record_audio_to_disk.")

    p = pyaudio.PyAudio()
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 2
    RATE = 44100

    try:
        device_count = p.get_device_count()
        if device_id is None or device_id < 0 or device_id >= device_count:
            err_msg = f"Invalid device ID: {device_id}. Valid range is 0-{device_count - 1}"
            logging.error(err_msg)
            raise ValueError(err_msg)

        device_info = p.get_device_info_by_index(device_id)
        logging.info(f"Using device: {device_info['name']}")

        if device_info["maxInputChannels"] < 1:
            err_msg = f"Device {device_id} ({device_info['name']}) doesn't support audio input"
            logging.error(err_msg)
            raise ValueError(err_msg)

        actual_channels = min(CHANNELS, int(device_info["maxInputChannels"]))
        if actual_channels != CHANNELS:
            logging.info(f"Adjusted channels from {CHANNELS} to {actual_channels} for device limitations")

        stream = p.open(
            format=FORMAT,
            channels=actual_channels,
            rate=RATE,
            input=True,
            input_device_index=device_id,
            frames_per_buffer=CHUNK,
        )

        wf = wave.open(output_file_path, "wb")  # type: ignore[arg-type]
        wf.setnchannels(actual_channels)
        wf.setsampwidth(2)
        wf.setframerate(RATE)

        while not stop_event.is_set():
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)
                wf.writeframes(data)
                audio_queue.put(data)
            except Exception as e:
                logging.error(f"Recording error: {e}")
                break
    finally:
        if "stream" in locals():
            try:
                stream.stop_stream()
                stream.close()
            except Exception as e:  # pragma: no cover - best-effort cleanup
                logging.debug(f"Failed to stop/close audio stream during cleanup: error={e}")
        if "wf" in locals():
            try:
                wf.close()
            except Exception as e:  # pragma: no cover
                logging.debug(f"Failed to close wav file during cleanup: error={e}")
        p.terminate()


def stop_recording_short(record_state: Dict[str, Any]):
    """
    Stop active recording threads and return partial transcription results.

    Expects a state dict created by desktop helpers using PartialTranscriptionThread.
    """
    if not record_state:
        return None, "[No active recording to stop]", None

    stop_event = record_state["stop_event"]
    rec_thread = record_state["record_thread"]
    partial_thread = record_state["partial_thread"]
    output_file_path = record_state["wav_path"]

    stop_event.set()
    rec_thread.join(timeout=5)
    if rec_thread.is_alive():
        logging.warning("record_thread didn't stop in time.")

    partial_thread.join(timeout=5)
    if partial_thread.is_alive():
        logging.warning("partial_thread didn't stop in time.")

    if getattr(partial_thread, "exception_encountered", None):
        return None, f"[Partial transcription error: {partial_thread.exception_encountered}]", output_file_path

    return partial_thread.partial_text_state.get("text"), "", output_file_path


def parse_device_id(selected_device_text: str) -> Optional[int]:
    """
    Parse device ID integer from a string like \"0: Microphone (Realtek Audio)\".
    """
    if not selected_device_text:
        return None
    try:
        parts = selected_device_text.split(":", 1)
        return int(parts[0].strip())
    except Exception as e:
        logging.error(f"Could not parse device from '{selected_device_text}': {e}")
        return None


class LiveAudioStreamer:
    """
    Sample helper for live microphone transcription on the desktop.

    This class was originally included as a \"FIXME/sample\" in the main STT
    library. It remains available here for local experiments but is not part
    of the supported server feature set.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        chunk_size: int = 1024,
        silence_threshold: float = 0.01,
        silence_duration: float = 1.6,
        transcription_provider: str = "faster-whisper",
        whisper_model: str = "distil-large-v3",
        speaker_lang: str = "en",
        nemo_variant: str = "standard",
    ) -> None:
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.silence_threshold = silence_threshold
        self.silence_duration = silence_duration
        self.transcription_provider = transcription_provider
        self.whisper_model = whisper_model
        self.speaker_lang = speaker_lang
        self.nemo_variant = nemo_variant

        self.audio_queue: "queue.Queue[np.ndarray]" = queue.Queue()
        self.is_recording = False
        self.stop_event = threading.Event()

        self.last_audio_chunk_time = time.time()
        self.silence_start_time: Optional[float] = None

        if pyaudio is None:  # pragma: no cover - optional dependency
            raise RuntimeError("PyAudio is not available; install it to use LiveAudioStreamer.")
        self.pa = pyaudio.PyAudio()
        self.stream = None
        self.listener_thread: Optional[threading.Thread] = None

    def audio_callback(self, in_data, frame_count, time_info, status):
        if status:
            print(f"Stream status: {status}")
        if not self.is_recording:
            return (in_data, pyaudio.paContinue)

        audio_data = np.frombuffer(in_data, dtype=np.float32)
        self.audio_queue.put(audio_data.copy())
        return (in_data, pyaudio.paContinue)

    def start(self) -> None:  # pragma: no cover - interactive helper
        self.is_recording = True
        self.stream = self.pa.open(
            format=pyaudio.paFloat32,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size,
            stream_callback=self.audio_callback,
        )
        self.stream.start_stream()
        self.listener_thread = threading.Thread(target=self.listen_loop, daemon=True)
        self.listener_thread.start()

    def stop(self) -> None:  # pragma: no cover - interactive helper
        self.is_recording = False
        self.stop_event.set()
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        if self.listener_thread:
            self.listener_thread.join()
        self.pa.terminate()

    def listen_loop(self) -> None:  # pragma: no cover - interactive helper
        audio_buffer: List[np.ndarray] = []

        while not self.stop_event.is_set():
            try:
                chunk = self.audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            audio_buffer.append(chunk)

            amplitude = np.abs(chunk).mean()
            if amplitude < self.silence_threshold:
                if self.silence_start_time is None:
                    self.silence_start_time = time.time()
                else:
                    elapsed = time.time() - self.silence_start_time
                    if elapsed >= self.silence_duration:
                        print("Silence detected. Finalizing the chunk.")
                        final_audio = np.concatenate(audio_buffer, axis=0).flatten()
                        audio_buffer.clear()
                        user_text = transcribe_audio(
                            final_audio,
                            sample_rate=self.sample_rate,
                            whisper_model=self.whisper_model,
                            speaker_lang=self.speaker_lang,
                            transcription_provider=self.transcription_provider,
                        )

                        try:
                            if isinstance(user_text, str) and is_transcription_error_message(user_text):
                                logging.error(f"LiveAudioStreamer STT error sentinel: {user_text}")
                            else:
                                self.handle_transcribed_text(user_text)
                        except Exception as _cb_exc:
                            logging.error(f"LiveAudioStreamer handle_transcribed_text error: {_cb_exc}")
                        self.silence_start_time = None
            else:
                self.silence_start_time = None

    def handle_transcribed_text(self, text: str) -> None:
        """
        Hook/callback for handling transcribed text.
        Override this in your script to process user speech.
        """
        print(f"USER SAID: {text}")


def test_device_availability(device_id: Optional[int]) -> bool:
    """
    Test if a specific PyAudio input device is available for recording.
    """
    if pyaudio is None or device_id is None:  # pragma: no cover
        return False

    p = pyaudio.PyAudio()
    try:
        device_info = p.get_device_info_by_index(device_id)
        if not device_info or device_info["maxInputChannels"] < 1:
            return False

        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=44100,
            input=True,
            input_device_index=device_id,
            frames_per_buffer=1024,
            start=False,
        )
        stream.close()
        return True
    except Exception as e:
        logging.debug(f"Device {device_id} not available: {e}")
        return False
    finally:
        p.terminate()


@timeit
def record_audio(duration: float, sample_rate: int = 16000, chunk_size: int = 1024):
    """
    Start recording audio from the default input device for a fixed duration.

    Desktop helper that returns PyAudio handles and a queue of recorded chunks.
    """
    if pyaudio is None:  # pragma: no cover
        raise RuntimeError("PyAudio is not available; install it to use record_audio.")

    log_counter("record_audio_attempt", labels={"duration": duration})
    p = pyaudio.PyAudio()
    stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=sample_rate,
        input=True,
        frames_per_buffer=chunk_size,
    )

    print("Recording...")
    stop_recording = threading.Event()
    audio_queue: "queue.Queue[bytes]" = queue.Queue()

    def audio_callback():
        for _ in range(0, int(sample_rate / chunk_size * duration)):
            if stop_recording.is_set():
                break
            data = stream.read(chunk_size)
            audio_queue.put(data)

    audio_thread = threading.Thread(target=audio_callback, daemon=True)
    audio_thread.start()

    return p, stream, audio_queue, stop_recording, audio_thread


@timeit
def stop_recording_infinite(p, stream, audio_queue: "queue.Queue[bytes]", stop_recording_event: threading.Event, audio_thread: threading.Thread) -> bytes:
    """
    Stop an ongoing \"infinite\" audio recording and return concatenated frames.
    """
    log_counter("stop_recording_attempt")
    start_time = time.time()
    stop_recording_event.set()
    audio_thread.join()

    frames: List[bytes] = []
    while not audio_queue.empty():
        frames.append(audio_queue.get())

    print("Recording finished.")

    stream.stop_stream()
    stream.close()
    p.terminate()

    stop_time = time.time() - start_time
    log_histogram("stop_recording_duration", stop_time)
    log_counter("stop_recording_success")
    return b"".join(frames)


@timeit
def save_audio_temp(audio_data: Any, sample_rate: int = 16000) -> Optional[str]:
    """
    Save audio data (NumPy array or Tensor) to a temporary WAV file and return its path.
    """
    log_counter("save_audio_temp_attempt")

    try:
        import torch  # Local import to avoid hard dependency when unused
    except Exception:  # pragma: no cover
        torch = None  # type: ignore

    try:
        if "torch" in locals() and torch is not None and isinstance(audio_data, torch.Tensor):  # type: ignore[name-defined]
            audio_data = audio_data.cpu().numpy()

        audio_np = np.asarray(audio_data, dtype=np.float32).copy()
        max_amp = np.max(np.abs(audio_np))
        if max_amp > 1.0:
            audio_np /= max_amp

        audio_int16 = np.int16(audio_np * 32767)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            wavfile.write(temp_file.name, sample_rate, audio_int16)
            log_counter("save_audio_temp_success")
            return temp_file.name
    except Exception as e:
        logging.error(f"Error saving temp audio: {str(e)}")
        log_counter("save_audio_temp_error")
        return None


def get_system_audio_devices() -> List[Dict[str, Any]]:
    """
    Return available audio devices for system audio recording, highlighting loopback devices.
    """
    if sd is None:  # pragma: no cover
        raise RuntimeError("sounddevice is not available; install it to use get_system_audio_devices.")

    loopback_keywords = [
        "loopback",
        "stereo mix",
        "monitor",
        "blackhole",
        "soundflower",
        "what u hear",
        "output",
        "mix",
    ]

    devices: List[Dict[str, Any]] = []
    try:
        host_apis = sd.query_hostapis()
        all_devs = sd.query_devices()

        for device_index, device in enumerate(all_devs):
            if device["max_input_channels"] > 0:
                name_lower = device["name"].lower()
                api_name = host_apis[device["hostapi"]]["name"]

                is_likely_loopback = any(keyword in name_lower for keyword in loopback_keywords)

                devices.append(
                    {
                        "id": device_index,
                        "name": f"{device['name']} ({api_name})"
                        + (" [SYSTEM AUDIO]" if is_likely_loopback else ""),
                        "hostapi": device["hostapi"],
                        "max_input_channels": device["max_input_channels"],
                        "max_output_channels": device["max_output_channels"],
                        "rate": device["default_samplerate"],
                        "is_loopback": is_likely_loopback,
                    }
                )

        devices.sort(key=lambda x: (not x.get("is_loopback"), x["name"]))
    except Exception as e:
        logging.error(f"Error enumerating audio devices: {e}")

    return devices


def record_system_audio(
    duration: float,
    device_id: int,
    sample_rate: int = 44100,
    channels: int = 2,
) -> str:
    """
    Record system audio output to a temporary WAV file and return its path.
    """
    if sd is None or wave is None:  # pragma: no cover
        raise RuntimeError("sounddevice/wave are not available; install them to use record_system_audio.")

    temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)

    try:
        device_info = sd.query_devices(device_id)
        actual_sample_rate = int(
            device_info["default_samplerate"] if device_info["default_samplerate"] > 0 else sample_rate
        )

        logging.info(
            f"Starting system audio recording (Duration: {duration}s, "
            f"Device: {device_info['name']}, SR: {actual_sample_rate})"
        )

        audio_data = sd.rec(
            int(duration * actual_sample_rate),
            samplerate=actual_sample_rate,
            channels=min(channels, device_info["max_input_channels"]),
            device=device_id,
            dtype=np.int16,
            blocking=True,
        )

        with wave.open(temp_file.name, "wb") as wav_file:  # type: ignore[arg-type]
            wav_file.setnchannels(min(channels, device_info["max_input_channels"]))
            wav_file.setsampwidth(2)
            wav_file.setframerate(actual_sample_rate)
            wav_file.writeframes(audio_data.tobytes())

        logging.info(f"Recording saved to {temp_file.name}")
        return temp_file.name
    except Exception as e:
        temp_file.close()
        Path(temp_file.name).unlink(missing_ok=True)
        raise RuntimeError(f"Recording failed: {str(e)}")

