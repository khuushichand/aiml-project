# Audio_Streaming_Unified.py
#########################################
# Unified Real-time Streaming Transcription for All Nemo Models
# This module provides WebSocket-based real-time transcription using all Nemo models
# with support for Parakeet (all variants) and Canary (multilingual).
#
####################
# Function List
#
# 1. BaseStreamingTranscriber - Abstract base class for streaming transcription
# 2. ParakeetStreamingTranscriber - Parakeet-specific implementation
# 3. CanaryStreamingTranscriber - Canary-specific implementation
# 4. UnifiedStreamingTranscriber - Factory and unified interface
# 5. handle_unified_websocket - Unified WebSocket handler
#
####################

import asyncio
import base64
import json
import time
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Callable, Awaitable, Tuple
from dataclasses import dataclass, field
import numpy as np
import tempfile
from pathlib import Path
from fastapi import WebSocketDisconnect
from loguru import logger
from uuid import uuid4

# Import existing implementations
from .Audio_Streaming_Parakeet import (
    ParakeetStreamingTranscriber as OriginalParakeetTranscriber,
    StreamingConfig,
    AudioBuffer
)
from .Audio_Transcription_Nemo import (
    load_canary_model,
    transcribe_with_canary,
    load_parakeet_model,
    transcribe_with_parakeet
)
from .model_utils import normalize_model_and_variant

# Expose config loader for tests to monkeypatch at module scope
try:  # pragma: no cover - import may fail in minimal test environments
    from tldw_Server_API.app.core.config import load_comprehensive_config as load_comprehensive_config  # type: ignore
except Exception:  # pragma: no cover
    def load_comprehensive_config():  # type: ignore
        return None

# Expose get_whisper_model at module scope so tests can monkeypatch it
# (WhisperStreamingTranscriber.initialize() will prefer a module-level symbol if present.)
try:  # pragma: no cover - import availability varies in test contexts
    from .Audio_Transcription_Lib import get_whisper_model as get_whisper_model  # type: ignore
except Exception:  # Fallback when whisper deps are unavailable; tests may monkeypatch this
    get_whisper_model = None  # type: ignore[assignment]
from .Audio_Streaming_Insights import LiveInsightSettings, LiveMeetingInsights

try:
    from .Diarization_Lib import DiarizationService, DiarizationError
except Exception:  # pragma: no cover - optional dependency probing
    DiarizationService = None  # type: ignore

    class DiarizationError(Exception):  # type: ignore
        """Fallback diarization error when service is unavailable."""
        pass

# Optional: Parakeet Core adapter
try:  # pragma: no cover - optional integration path
    from .Parakeet_Core_Streaming.transcriber import ParakeetCoreTranscriber as _CoreTranscriber
    from .Parakeet_Core_Streaming.config import StreamingConfig as _CoreConfig

    class _ParakeetCoreAdapter:
        """Adapter exposing the same interface expected by handle_unified_websocket.

        Delegates to the self-contained Parakeet core streaming transcriber so this
        unified path can benefit from the improved buffering/metadata and variant handling.
        """

        def __init__(self, config: 'UnifiedStreamingConfig') -> None:
            """
            Initialize the adapter with the provided unified streaming configuration.

            Stores the given UnifiedStreamingConfig and prepares an internal placeholder for the underlying core transcriber (left as None until initialization).

            Parameters:
                config (UnifiedStreamingConfig): Configuration that drives model selection, runtime options, and behavior for the underlying transcriber.
            """
            self._uconf = config
            self._core = None  # type: ignore

        def initialize(self) -> None:
            # Map Unified config to core config
            """
            Initialize the core Parakeet transcriber adapter by mapping the unified streaming configuration to the core transcriber config and creating the core transcriber instance.

            Creates a _CoreConfig from the adapter's unified config, instantiates _CoreTranscriber with that config, and validates that the chosen model variant is available. Raises a RuntimeError with message "parakeet_variant_unavailable: <variant>" when the core transcriber does not expose the expected decode function, to trigger higher-level fallback logic.
            """
            c = _CoreConfig(
                model=self._uconf.model,
                model_variant=self._uconf.model_variant,
                sample_rate=self._uconf.sample_rate,
                chunk_duration=self._uconf.chunk_duration,
                overlap_duration=self._uconf.overlap_duration,
                max_buffer_duration=self._uconf.max_buffer_duration,
                enable_partial=self._uconf.enable_partial,
                partial_interval=self._uconf.partial_interval,
                min_partial_duration=self._uconf.min_partial_duration,
                language=self._uconf.language,
            )
            self._core = _CoreTranscriber(config=c)
            # Ensure chosen variant is available; if not, raise to trigger fallback logic
            try:
                # Prefer explicit check against the core helper so tests can monkeypatch it
                from .Parakeet_Core_Streaming import transcriber as _core_tx  # type: ignore
                _fn = getattr(_core_tx, "_variant_decode_fn", None)
                if callable(_fn):
                    available = _fn(c.model, c.model_variant)
                    if available is None:
                        raise RuntimeError(f"parakeet_variant_unavailable: {c.model_variant}")
                # Fallback: inspect instantiated core transcriber
                if getattr(self._core, "decode_fn", None) is None:
                    raise RuntimeError(f"parakeet_variant_unavailable: {c.model_variant}")
            except RuntimeError:
                # Re-raise variant unavailability to be caught by higher-level handler
                raise
            except Exception:
                # If validation fails unexpectedly, defer to runtime; do not block initialization
                # The streaming path will still handle decode failures gracefully.
                pass
            try:
                decode_fn = getattr(self._core, 'decode_fn', None)
            except Exception:
                decode_fn = None
            if decode_fn is None:
                raise RuntimeError(f"parakeet_variant_unavailable: {self._uconf.model_variant}")
        async def process_audio_chunk(self, audio_data: bytes):  # -> Optional[Dict[str, Any]]
            """
            Forward an incoming audio chunk to the underlying core transcriber and return any resulting transcription data.

            Parameters:
                audio_data (bytes): Raw audio bytes received from the client.

            Returns:
                dict: A transcription result object (partial or final) when available, or `None` if no transcription is produced.
            """
            return await self._core.process_audio_chunk(audio_data)  # type: ignore

        def get_full_transcript(self) -> str:
            """
            Retrieve the concatenated transcript produced by the underlying transcriber.

            Returns:
                full_transcript (str): The combined transcript text of all finalized segments in chronological order.
            """
            return self._core.get_full_transcript()  # type: ignore

        def reset(self) -> None:
            """
            Reset the adapter and its underlying core transcriber state.

            This clears any internal buffers and runtime state held by the adapter by delegating reset to the wrapped core transcriber.
            """
            self._core.reset()  # type: ignore

        def cleanup(self) -> None:
            """
            Reset the underlying core adapter/transcriber and ignore any errors raised.

            This calls the core object's `reset` method if present; exceptions from that call are suppressed to ensure cleanup does not raise.
            """
            try:
                self._core.reset()  # type: ignore
            except Exception:
                pass

except Exception:  # pragma: no cover - keep unified path working when core module absent
    _ParakeetCoreAdapter = None  # type: ignore


@dataclass
class UnifiedStreamingConfig(StreamingConfig):
    """Extended configuration for unified streaming."""
    model: str = 'parakeet'  # 'parakeet', 'canary', or 'whisper'
    model_variant: str = 'standard'  # For Parakeet: 'standard', 'onnx', 'mlx'
    language: Optional[str] = None  # Language code for transcription
    auto_detect_language: bool = False  # Auto-detect language
    enable_vad: bool = False  # Voice Activity Detection
    vad_threshold: float = 0.5
    min_partial_duration: float = 0.5
    # Whisper-specific options
    whisper_model_size: str = 'distil-large-v3'  # Whisper model size
    beam_size: int = 5  # Beam search size
    vad_filter: bool = False  # Use VAD filter for Whisper
    task: str = 'transcribe'  # 'transcribe' or 'translate'
    # Diarization-specific options
    diarization_enabled: bool = False
    diarization_store_audio: bool = False
    diarization_storage_dir: Optional[str] = None
    diarization_num_speakers: Optional[int] = None


class StreamingDiarizer:
    """Best-effort wrapper to reuse the offline DiarizationService during streaming."""

    def __init__(
        self,
        sample_rate: int,
        *,
        store_audio: bool = False,
        storage_dir: Optional[str] = None,
        num_speakers: Optional[int] = None,
    ) -> None:
        """
        Initialize the streaming diarizer used to collect audio and produce speaker-aligned segments.

        Parameters:
            sample_rate (int): Audio sample rate in Hz used for buffering and diarization. Defaults to 16000 when falsy.
            store_audio (bool): If True, persist the combined audio to disk when finalizing diarization.
            storage_dir (Optional[str]): Directory path where persisted audio will be written when store_audio is True.
            num_speakers (Optional[int]): Optional hint for the expected number of speakers; passed to the underlying diarization service when available.
        """
        self.sample_rate = int(sample_rate or 16000)
        self.store_audio = bool(store_audio)
        self.storage_dir = Path(storage_dir).expanduser() if storage_dir else None
        self.num_speakers = num_speakers
        self._audio_chunks: List[np.ndarray] = []
        self._transcript_segments: List[Dict[str, Any]] = []
        self._mapping: Dict[int, Dict[str, Any]] = {}
        self._last_result: Dict[str, Any] = {}
        self._dirty = False
        self._persist_path: Optional[Path] = None
        self._persist_method: Optional[str] = None  # 'soundfile' | 'scipy' | 'wave' | None
        self._lock = asyncio.Lock()
        self._service = None
        self.available = False
        self._service_checked = False
        self._service_error: Optional[str] = None

    async def label_segment(self, audio_np: np.ndarray, segment_meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Append audio/transcript and return the speaker for the latest segment."""
        if not await self._ensure_service():
            return None
        async with self._lock:
            self._audio_chunks.append(np.array(audio_np, copy=True))
            self._transcript_segments.append({
                "start": float(segment_meta.get("segment_start") or segment_meta.get("chunk_start") or 0.0),
                "end": float(segment_meta.get("segment_end") or segment_meta.get("chunk_end") or 0.0),
                "text": segment_meta.get("text", ""),
                "segment_id": int(segment_meta.get("segment_id", 0)),
            })
            self._dirty = True
            mapping = await self._ensure_mapping()
            segment_id = int(segment_meta.get("segment_id", 0))
            return mapping.get(segment_id)

    async def finalize(self) -> Tuple[Dict[int, Dict[str, Any]], Optional[str], Optional[List[Dict[str, Any]]]]:
        """Ensure latest mapping is available and optionally persist audio."""
        if not await self._ensure_service():
            return {}, None, None
        async with self._lock:
            self._dirty = True
            mapping = await self._ensure_mapping()
            audio_path = None
            if self.store_audio and self._audio_chunks:
                audio_path = await self._persist_audio()
            speakers = self._last_result.get("speakers")
            return mapping, audio_path, speakers

    async def reset(self) -> None:
        """
        Clear all buffered audio, transcripts, and diarization state, and reset persistence metadata.

        This empties the internal audio chunk and transcript segment buffers, clears any computed speaker mapping, resets the last result and dirty flag, and clears persistence path and method so the diarizer returns to an initial state.
        """
        async with self._lock:
            self._audio_chunks.clear()
            self._transcript_segments.clear()
            self._mapping.clear()
            self._last_result = {}
            self._dirty = False
            self._persist_path = None
            self._persist_method = None

    async def close(self) -> None:
        """
        Close the diarizer, clear buffered audio and transcripts, and release any held resources.
        """
        await self.reset()

    async def ensure_ready(self) -> bool:
        """Public helper to eagerly initialize the diarization backend."""
        return await self._ensure_service()

    async def _ensure_service(self) -> bool:
        if self._service_checked:
            return self.available and self._service is not None
        self._service_checked = True
        if DiarizationService is None:
            logger.debug("Streaming diarizer: DiarizationService import unavailable.")
            self.available = False
            self._service = None
            return False
        loop = asyncio.get_running_loop()
        try:
            service = await loop.run_in_executor(None, DiarizationService)
            is_available = bool(getattr(service, "is_available", True))
            if not is_available:
                logger.warning("Streaming diarizer dependencies missing; disabling diarization.")
                self.available = False
                self._service = None
                return False
            self._service = service
            self.available = True
            return True
        except Exception as exc:
            logger.warning(f"Streaming diarizer unavailable: {exc}")
            self.available = False
            self._service = None
            self._service_error = str(exc)
            return False

    async def _ensure_mapping(self) -> Dict[int, Dict[str, Any]]:
        if not await self._ensure_service():
            return {}
        if not self._dirty:
            return self._mapping
        loop = asyncio.get_running_loop()
        mapping = await loop.run_in_executor(None, self._run_alignment_sync)
        if mapping is not None:
            self._mapping = mapping
            self._dirty = False
        return self._mapping

    def _run_alignment_sync(self) -> Optional[Dict[int, Dict[str, Any]]]:
        if not self._service or not self._audio_chunks:
            return {}
        combined = self._combined_audio()
        if combined.size == 0:
            return {}
        tmp_path = None
        try:
            tmp_path = self._write_temp_wav(combined)
            transcripts = [
                {
                    "start": seg["start"],
                    "end": seg["end"],
                    "text": seg.get("text", ""),
                    "segment_id": seg["segment_id"],
                }
                for seg in self._transcript_segments
            ]
            result = self._service.diarize(
                str(tmp_path),
                transcription_segments=transcripts,
                num_speakers=self.num_speakers,
            )
            self._last_result = result or {}
            segments = self._last_result.get("segments", []) or transcripts
            mapping: Dict[int, Dict[str, Any]] = {}
            for seg in segments:
                seg_id = seg.get("segment_id") or seg.get("id")
                if seg_id is None:
                    continue
                mapping[int(seg_id)] = {
                    "speaker_id": seg.get("speaker_id"),
                    "speaker_label": seg.get("speaker_label"),
            }
            return mapping
        except DiarizationError as err:
            logger.error(f"Streaming diarizer failed: {err}")
            self.available = False
            return {}
        except Exception as exc:
            logger.error(f"Streaming diarizer unexpected error: {exc}", exc_info=True)
            return {}
        finally:
            if tmp_path:
                try:
                    Path(tmp_path).unlink(missing_ok=True)
                except Exception:
                    pass

    def _combined_audio(self) -> np.ndarray:
        if not self._audio_chunks:
            return np.zeros(0, dtype=np.float32)
        if len(self._audio_chunks) == 1:
            return np.array(self._audio_chunks[0], copy=True)
        return np.concatenate(self._audio_chunks)

    def _write_temp_wav(self, audio_np: np.ndarray) -> Path:
        """
        Write a temporary WAV file from a mono audio NumPy array and return its filesystem path.

        Parameters:
            audio_np (np.ndarray): 1-D NumPy array of audio samples, expected in float32 range [-1.0, 1.0]; the method will convert to an appropriate PCM format if needed.

        Returns:
            Path: Filesystem path to the created temporary WAV file.
        """
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_path = Path(tmp.name)
        tmp.close()
        # Prefer soundfile; fall back to scipy.io.wavfile or wave if unavailable
        try:
            import soundfile as sf  # type: ignore
            sf.write(str(tmp_path), audio_np, self.sample_rate)
        except Exception as sf_err:
            logger.warning(f"soundfile unavailable for temp WAV write: {sf_err}; falling back")
            # Try scipy
            try:
                from scipy.io import wavfile  # type: ignore
                # Convert float32 [-1,1] to int16 for scipy
                pcm16 = np.clip(audio_np, -1.0, 1.0)
                pcm16 = (pcm16 * 32767.0).astype(np.int16)
                wavfile.write(str(tmp_path), self.sample_rate, pcm16)
            except Exception as scipy_err:
                logger.warning(f"scipy.io.wavfile write failed: {scipy_err}; using wave module")
                # Fallback to wave module (int16 PCM)
                import wave
                pcm16 = np.clip(audio_np, -1.0, 1.0)
                pcm16 = (pcm16 * 32767.0).astype(np.int16)
                with wave.open(str(tmp_path), 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(self.sample_rate)
                    wf.writeframes(pcm16.tobytes())
        return tmp_path

    async def _persist_audio(self) -> Optional[str]:
        """
        Run the synchronous audio persistence routine in a thread executor and return the persisted file path if any.

        Returns:
            persisted_path (Optional[str]): Path to the persisted audio file if persistence succeeded, `None` if no file was written.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._persist_audio_sync)

    def _persist_audio_sync(self) -> Optional[str]:
        """
        Persist the currently buffered audio to a WAV file using the best available backend.

        Attempts to write the concatenated buffered audio to disk (preferred backends tried in order: soundfile, scipy.io.wavfile, wave). On success sets self._persist_path to the file path and self._persist_method to the backend used and returns the file path as a string. If no audio is buffered or all backends fail, sets self._persist_method to None and returns `None`.

        Returns:
            str or None: Absolute path to the persisted WAV file on success, `None` if no audio was written.
        """
        audio_np = self._combined_audio()
        if audio_np.size == 0:
            return None
        if self.storage_dir:
            out_dir = self.storage_dir
        else:
            out_dir = Path(tempfile.gettempdir())
        out_dir.mkdir(parents=True, exist_ok=True)
        if not self._persist_path:
            filename = f"stream_{uuid4().hex}.wav"
            self._persist_path = out_dir / filename
        # Prefer soundfile; fall back to scipy.io.wavfile or wave if unavailable
        try:
            try:
                import soundfile as sf  # type: ignore
                sf.write(str(self._persist_path), audio_np, self.sample_rate)
                self._persist_method = "soundfile"
                return str(self._persist_path)
            except Exception as sf_err:
                logger.warning(f"soundfile unavailable for persistence: {sf_err}; falling back")
                try:
                    from scipy.io import wavfile  # type: ignore
                    pcm16 = np.clip(audio_np, -1.0, 1.0)
                    pcm16 = (pcm16 * 32767.0).astype(np.int16)
                    wavfile.write(str(self._persist_path), self.sample_rate, pcm16)
                    self._persist_method = "scipy"
                    return str(self._persist_path)
                except Exception as scipy_err:
                    logger.warning(f"scipy.io.wavfile persistence failed: {scipy_err}; using wave module")
                    try:
                        import wave
                        pcm16 = np.clip(audio_np, -1.0, 1.0)
                        pcm16 = (pcm16 * 32767.0).astype(np.int16)
                        with wave.open(str(self._persist_path), 'wb') as wf:
                            wf.setnchannels(1)
                            wf.setsampwidth(2)
                            wf.setframerate(self.sample_rate)
                            wf.writeframes(pcm16.tobytes())
                        self._persist_method = "wave"
                        return str(self._persist_path)
                    except Exception as wave_err:
                        logger.warning(f"wave module persistence failed: {wave_err}")
                        self._persist_method = None
                        return None
        except Exception as persist_err:
            logger.error(f"Audio persistence failed: {persist_err}")
            self._persist_method = None
            return None

    @property
    def persistence_method(self) -> Optional[str]:
        """
        Name of the audio persistence backend selected for writing WAV files.

        Returns:
            persistence_backend (Optional[str]): The backend identifier (`'soundfile'`, `'scipy'`, or `'wave'`) if a persistence writer was selected, or `None` if no persistence backend is available.
        """
        return self._persist_method


class QuotaExceeded(Exception):
    """Raised by on_audio_seconds callback to signal quota exhaustion."""
    def __init__(self, quota: str):
        super().__init__(quota)
        self.quota = quota


class BaseStreamingTranscriber(ABC):
    """
    Abstract base class for streaming transcribers.

    Defines the common interface for all streaming transcription implementations.
    """

    def __init__(self, config: UnifiedStreamingConfig):
        """Initialize base transcriber."""
        self.config = config
        self.buffer = AudioBuffer(
            sample_rate=config.sample_rate,
            max_duration=config.max_buffer_duration
        )
        self.model = None
        self.is_running = False
        self.transcription_history = []
        self.last_partial_time = 0
        self.segment_index = 0
        self.total_processed_seconds = 0.0

    @abstractmethod
    def initialize(self):
        """Load and initialize the model."""
        pass

    @abstractmethod
    async def process_audio_chunk(self, audio_data: bytes) -> Optional[Dict[str, Any]]:
        """Process a chunk of audio data."""
        pass

    def get_full_transcript(self) -> str:
        """Get the complete transcript so far."""
        return " ".join(self.transcription_history)

    def reset(self):
        """Reset the transcriber state."""
        self.buffer.clear()
        self.transcription_history.clear()
        self.last_partial_time = 0
        self.segment_index = 0
        self.total_processed_seconds = 0.0

    def cleanup(self):
        """Clean up resources."""
        self.model = None
        self.reset()

    def _prepare_partial_metadata(self, buffer_duration: float) -> Dict[str, float]:
        """Attach common metadata for partial updates."""
        buffer_duration = float(buffer_duration)
        start = float(self.total_processed_seconds)
        return {
            "segment_id": self.segment_index + 1,
            "segment_start": start,
            "segment_end": start + buffer_duration,
            "buffer_duration": buffer_duration,
            "cumulative_audio": float(self.total_processed_seconds),
        }

    def _prepare_final_metadata(self, chunk_duration: float) -> Dict[str, float]:
        """Attach metadata for finalized segments and advance the timeline cursor."""
        chunk_duration = float(chunk_duration)
        if chunk_duration < 0:
            chunk_duration = 0.0
        overlap_cfg = max(float(self.config.overlap_duration or 0.0), 0.0)
        if self.segment_index == 0:
            overlap_used = 0.0
        else:
            overlap_used = min(overlap_cfg, chunk_duration)
        new_audio_duration = chunk_duration - overlap_used
        if self.segment_index == 0:
            new_audio_duration = chunk_duration
        if new_audio_duration < 0:
            new_audio_duration = 0.0

        segment_start = float(self.total_processed_seconds)
        segment_end = segment_start + new_audio_duration
        chunk_start = max(segment_start - overlap_used, 0.0)
        chunk_end = chunk_start + chunk_duration

        self.total_processed_seconds = segment_end
        self.segment_index += 1

        return {
            "segment_id": self.segment_index,
            "segment_start": segment_start,
            "segment_end": segment_end,
            "chunk_duration": chunk_duration,
            "overlap": overlap_used,
            "chunk_start": chunk_start,
            "chunk_end": chunk_end,
            "new_audio_duration": new_audio_duration,
            "cumulative_audio": float(self.total_processed_seconds),
        }


class ParakeetStreamingTranscriber(BaseStreamingTranscriber):
    """
    Parakeet-specific streaming transcriber.

    Supports all Parakeet variants: standard, ONNX, MLX.
    """

    def initialize(self):
        """Load the Parakeet model based on configuration."""
        variant = self.config.model_variant
        logger.info(f"Loading Parakeet model (variant: {variant})")

        if variant == 'mlx':
            # MLX model is loaded on-demand in transcribe function
            # First check if MLX dependencies are available
            try:
                from .Audio_Transcription_Parakeet_MLX import transcribe_with_parakeet_mlx
                logger.info("Using Parakeet MLX variant (lazy loading)")
                self.model = "mlx"  # Placeholder to indicate MLX is ready
                return  # Success
            except ImportError as e:
                logger.error(f"Failed to import Parakeet MLX: {e}")
                raise RuntimeError(f"Parakeet MLX dependencies not available. Install with: pip install mlx mlx-lm")
        else:
            # Load standard or ONNX variant (requires Nemo)
            try:
                self.model = load_parakeet_model(variant)
                if self.model is None:
                    raise RuntimeError(f"Failed to load Parakeet {variant} model")
                logger.info(f"Loaded Parakeet {variant} model")
            except ImportError as e:
                if "nemo" in str(e).lower():
                    logger.warning(f"Nemo toolkit not installed, attempting to fallback to MLX variant")
                    # Try to fallback to MLX variant
                    try:
                        from .Audio_Transcription_Parakeet_MLX import transcribe_with_parakeet_mlx
                        logger.info("Falling back to Parakeet MLX variant due to missing Nemo")
                        self.config.model_variant = 'mlx'
                        self.model = "mlx"  # Placeholder to indicate MLX is ready
                        return  # Success with fallback
                    except ImportError:
                        logger.error("MLX fallback failed - MLX dependencies not available")
                        raise RuntimeError(f"Nemo toolkit not installed for {variant} variant and MLX fallback unavailable. "
                                         f"Install Nemo with: pip install nemo_toolkit[asr] "
                                         f"OR install MLX with: pip install mlx mlx-lm")
                raise

    async def process_audio_chunk(self, audio_data: bytes) -> Optional[Dict[str, Any]]:
        """
        Process audio chunk with Parakeet.

        Args:
            audio_data: Raw audio bytes

        Returns:
            Transcription result or None
        """
        # Convert bytes to numpy array
        audio_np = np.frombuffer(audio_data, dtype=np.float32)

        # Add to buffer
        self.buffer.add(audio_np)

        current_time = time.time()
        buffer_duration = self.buffer.get_duration()

        # Check if we should send a partial result
        if (self.config.enable_partial and
            current_time - self.last_partial_time > self.config.partial_interval and
            buffer_duration > 0.5):

            # Get audio for partial transcription
            audio_for_partial = self.buffer.get_audio()
            if audio_for_partial is not None and len(audio_for_partial) > 0:
                # Transcribe partial audio
                if self.config.model_variant == 'mlx':
                    # Use MLX implementation
                    from .Audio_Transcription_Parakeet_MLX import transcribe_with_parakeet_mlx
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                        import soundfile as sf
                        sf.write(tmp_file.name, audio_for_partial, self.config.sample_rate)
                        text = transcribe_with_parakeet_mlx(tmp_file.name)
                        Path(tmp_file.name).unlink()
                else:
                    # Use standard/ONNX implementation
                    text = transcribe_with_parakeet(
                        audio_for_partial,
                        self.config.sample_rate,
                        self.config.model_variant
                    )

                self.last_partial_time = current_time

                if text:
                    # Apply custom vocabulary post-replacements if enabled
                    try:
                        from .Audio_Custom_Vocabulary import postprocess_text_if_enabled
                        text = postprocess_text_if_enabled(text)
                    except Exception:
                        pass
                    metadata = self._prepare_partial_metadata(buffer_duration)
                    result = {
                        "type": "partial",
                        "text": text,
                        "timestamp": current_time,
                        "is_final": False,
                        "model": f"parakeet-{self.config.model_variant}"
                    }
                    result.update(metadata)
                    return result

        # Check if we have enough audio for a final chunk
        if buffer_duration >= self.config.chunk_duration:
            # Get chunk for transcription
            audio_chunk = self.buffer.get_audio(self.config.chunk_duration)

            if audio_chunk is not None:
                # Transcribe the chunk
                if self.config.model_variant == 'mlx':
                    from .Audio_Transcription_Parakeet_MLX import transcribe_with_parakeet_mlx
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                        import soundfile as sf
                        sf.write(tmp_file.name, audio_chunk, self.config.sample_rate)
                        text = transcribe_with_parakeet_mlx(tmp_file.name)
                        Path(tmp_file.name).unlink()
                else:
                    text = transcribe_with_parakeet(
                        audio_chunk,
                        self.config.sample_rate,
                        self.config.model_variant
                    )

                # Consume the buffer, keeping overlap
                self.buffer.consume(
                    self.config.chunk_duration,
                    self.config.overlap_duration
                )

                if text:
                    # Apply custom vocabulary post-replacements if enabled
                    try:
                        from .Audio_Custom_Vocabulary import postprocess_text_if_enabled
                        text = postprocess_text_if_enabled(text)
                    except Exception:
                        pass
                    self.transcription_history.append(text)
                    chunk_duration = float(len(audio_chunk)) / float(self.config.sample_rate or 1)
                    metadata = self._prepare_final_metadata(chunk_duration)
                    result = {
                        "type": "final",
                        "text": text,
                        "timestamp": current_time,
                        "is_final": True,
                        "model": f"parakeet-{self.config.model_variant}"
                    }
                    result.update(metadata)
                    result["_audio_chunk"] = np.array(audio_chunk, copy=True)
                    return result

        return None


class CanaryStreamingTranscriber(BaseStreamingTranscriber):
    """
    Canary-specific streaming transcriber.

    Supports multilingual transcription with language detection.
    """

    def initialize(self):
        """Load the Canary model."""
        logger.info("Loading Canary multilingual model")
        self.model = load_canary_model()
        if self.model is None:
            raise RuntimeError("Failed to load Canary model")
        logger.info("Loaded Canary model")

        # Set default language if not specified
        if not self.config.language:
            self.config.language = 'en'  # Default to English

    async def process_audio_chunk(self, audio_data: bytes) -> Optional[Dict[str, Any]]:
        """
        Process audio chunk with Canary.

        Args:
            audio_data: Raw audio bytes

        Returns:
            Transcription result or None
        """
        # Convert bytes to numpy array
        audio_np = np.frombuffer(audio_data, dtype=np.float32)

        # Add to buffer
        self.buffer.add(audio_np)

        current_time = time.time()
        buffer_duration = self.buffer.get_duration()

        # Check if we should send a partial result
        if (self.config.enable_partial and
            current_time - self.last_partial_time > self.config.partial_interval and
            buffer_duration > 0.5):

            # Get audio for partial transcription
            audio_for_partial = self.buffer.get_audio()
            if audio_for_partial is not None and len(audio_for_partial) > 0:
                # Transcribe partial audio
                text = transcribe_with_canary(
                    audio_for_partial,
                    self.config.sample_rate,
                    self.config.language
                )

                self.last_partial_time = current_time

                if text:
                    # Apply custom vocabulary post-replacements if enabled
                    try:
                        from .Audio_Custom_Vocabulary import postprocess_text_if_enabled
                        text = postprocess_text_if_enabled(text)
                    except Exception:
                        pass
                    # Detect language if auto-detection is enabled
                    detected_language = self.config.language
                    if self.config.auto_detect_language:
                        # Simple heuristic - could be improved with actual language detection
                        detected_language = self._detect_language(text)

                    metadata = self._prepare_partial_metadata(buffer_duration)
                    result = {
                        "type": "partial",
                        "text": text,
                        "timestamp": current_time,
                        "is_final": False,
                        "language": detected_language,
                        "model": "canary-1b"
                    }
                    result.update(metadata)
                    return result

        # Check if we have enough audio for a final chunk
        if buffer_duration >= self.config.chunk_duration:
            # Get chunk for transcription
            audio_chunk = self.buffer.get_audio(self.config.chunk_duration)

            if audio_chunk is not None:
                # Transcribe the chunk
                text = transcribe_with_canary(
                    audio_chunk,
                    self.config.sample_rate,
                    self.config.language
                )

                # Consume the buffer, keeping overlap
                self.buffer.consume(
                    self.config.chunk_duration,
                    self.config.overlap_duration
                )

                if text:
                    # Apply custom vocabulary post-replacements if enabled
                    try:
                        from .Audio_Custom_Vocabulary import postprocess_text_if_enabled
                        text = postprocess_text_if_enabled(text)
                    except Exception:
                        pass
                    # Detect language if auto-detection is enabled
                    detected_language = self.config.language
                    if self.config.auto_detect_language:
                        detected_language = self._detect_language(text)

                    self.transcription_history.append(text)
                    chunk_duration = float(len(audio_chunk)) / float(self.config.sample_rate or 1)
                    metadata = self._prepare_final_metadata(chunk_duration)
                    result = {
                        "type": "final",
                        "text": text,
                        "timestamp": current_time,
                        "is_final": True,
                        "language": detected_language,
                        "model": "canary-1b"
                    }
                    result.update(metadata)
                    result["_audio_chunk"] = np.array(audio_chunk, copy=True)
                    return result

        return None

    def _detect_language(self, text: str) -> str:
        """
        Simple language detection heuristic.

        In production, this should use a proper language detection library.
        """
        # This is a placeholder - in reality, you'd use langdetect or similar
        # For now, just return the configured language
        return self.config.language


class WhisperStreamingTranscriber(BaseStreamingTranscriber):
    """
    Whisper-specific streaming transcriber using faster-whisper.

    Optimized for accuracy with configurable model sizes and features.
    """

    def initialize(self):
        """Load the Whisper model based on configuration."""
        logger.info(f"WhisperStreamingTranscriber.initialize() called with config: "
                   f"whisper_model_size={self.config.whisper_model_size}, "
                   f"language={self.config.language}, task={self.config.task}")

        try:
            # Prefer a module-level override (tests may monkeypatch this symbol on
            # Audio_Streaming_Unified) and fall back to the library import.
            get_whisper_model = globals().get('get_whisper_model')  # type: ignore[assignment]
            if get_whisper_model is None:
                logger.debug("Importing get_whisper_model from Audio_Transcription_Lib")
                from .Audio_Transcription_Lib import get_whisper_model  # type: ignore[no-redef]
                logger.debug("Successfully imported get_whisper_model")

            # Determine device and compute type
            import torch
            device = 'cuda' if torch.cuda.is_available() else 'cpu'

            # Compute type is determined by the device, not a config parameter
            compute_type = 'float16' if device == 'cuda' else 'int8'

            logger.info(f"Loading Whisper model: {self.config.whisper_model_size} on {device} with compute_type: {compute_type}")

            # Load the model using existing function
            self.model = get_whisper_model(self.config.whisper_model_size, device)  # type: ignore[misc]

            if self.model is None:
                raise RuntimeError(f"Failed to load Whisper model: {self.config.whisper_model_size}")

            logger.info(f"Successfully loaded Whisper model: {self.config.whisper_model_size}, model object: {type(self.model)}")

            # Set transcription options
            self.transcribe_options = {
                'beam_size': self.config.beam_size,
                'best_of': self.config.beam_size,
                'vad_filter': self.config.vad_filter,
                'task': self.config.task
            }

            if self.config.language and not self.config.auto_detect_language:
                self.transcribe_options['language'] = self.config.language
            # Inject custom vocabulary initial prompt if configured
            try:
                from .Audio_Custom_Vocabulary import initial_prompt_if_enabled
                _init_prompt = initial_prompt_if_enabled()
                if _init_prompt:
                    self.transcribe_options['initial_prompt'] = _init_prompt
                    logger.info("Applied custom vocabulary initial_prompt for Whisper streaming")
            except Exception as _cv_err:
                logger.debug(f"Whisper streaming initial_prompt skipped: {_cv_err}")

            # Whisper works better with longer audio chunks
            self.min_chunk_duration = 1.0  # Minimum 1 second of audio
            self.optimal_chunk_duration = 5.0  # Optimal chunk size for Whisper

        except ImportError as e:
            logger.error(f"Failed to import Whisper dependencies: {e}")
            raise RuntimeError("Whisper dependencies not available")
        except Exception as e:
            logger.error(f"Failed to initialize Whisper model: {e}")
            raise

    async def process_audio_chunk(self, audio_data: bytes) -> Optional[Dict[str, Any]]:
        """
        Process audio chunk with Whisper.

        Args:
            audio_data: Raw audio bytes

        Returns:
            Transcription result or None
        """
        # Convert bytes to numpy array
        audio_np = np.frombuffer(audio_data, dtype=np.float32)

        # Add to buffer
        self.buffer.add(audio_np)

        current_time = time.time()
        buffer_duration = self.buffer.get_duration()

        # Check if we should send a partial result
        # Whisper needs more audio for good results, so we wait for more data
        if (self.config.enable_partial and
            current_time - self.last_partial_time > self.config.partial_interval and
            buffer_duration >= self.min_chunk_duration):

            # Get audio for partial transcription
            audio_for_partial = self.buffer.get_audio()
            if audio_for_partial is not None and len(audio_for_partial) > 0:
                # Transcribe partial audio
                text = self._transcribe_audio(audio_for_partial)

                self.last_partial_time = current_time

                if text:
                    metadata = self._prepare_partial_metadata(buffer_duration)
                    result = {
                        "type": "partial",
                        "text": text,
                        "timestamp": current_time,
                        "is_final": False,
                        "model": f"whisper-{self.config.whisper_model_size}"
                    }
                    result.update(metadata)
                    return result

        # Check if we have enough audio for a final chunk
        # Use optimal chunk duration for better accuracy
        if buffer_duration >= self.optimal_chunk_duration:
            # Get chunk for transcription
            audio_chunk = self.buffer.get_audio(self.optimal_chunk_duration)

            if audio_chunk is not None:
                # Transcribe the chunk
                text = self._transcribe_audio(audio_chunk)

                # Consume the buffer, keeping overlap for context
                self.buffer.consume(
                    self.optimal_chunk_duration,
                    self.config.overlap_duration
                )

                if text:
                    self.transcription_history.append(text)
                    chunk_duration = float(len(audio_chunk)) / float(self.config.sample_rate or 1)
                    metadata = self._prepare_final_metadata(chunk_duration)
                    result = {
                        "type": "final",
                        "text": text,
                        "timestamp": current_time,
                        "is_final": True,
                        "model": f"whisper-{self.config.whisper_model_size}",
                        "language": self.config.language if self.config.language else "auto"
                    }
                    result.update(metadata)
                    result["_audio_chunk"] = np.array(audio_chunk, copy=True)
                    return result

        return None

    def _transcribe_audio(self, audio_np: np.ndarray) -> str:
        """
        Transcribe audio using Whisper model.

        Args:
            audio_np: Audio data as numpy array

        Returns:
            Transcribed text
        """
        try:
            # Save audio to temporary file (Whisper needs file input)
            import tempfile
            import soundfile as sf

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                sf.write(tmp_file.name, audio_np, self.config.sample_rate)

                # Transcribe using Whisper
                segments_raw, info = self.model.transcribe(
                    tmp_file.name,
                    **self.transcribe_options
                )

                # Collect all text from segments
                text_parts = []
                for segment in segments_raw:
                    text_parts.append(segment.text.strip())

                # Clean up temp file
                Path(tmp_file.name).unlink()

                # Join all text parts
                text = " ".join(text_parts)
                # Apply custom vocabulary post-replacements if enabled
                try:
                    from .Audio_Custom_Vocabulary import postprocess_text_if_enabled
                    text = postprocess_text_if_enabled(text)
                except Exception:
                    pass

                # Log detected language if auto-detecting
                if self.config.auto_detect_language and hasattr(info, 'language'):
                    logger.debug(f"Detected language: {info.language} (confidence: {info.language_probability:.2f})")

                return text

        except Exception as e:
            logger.error(f"Error during Whisper transcription: {e}")
            return ""


class UnifiedStreamingTranscriber:
    """
    Factory and unified interface for streaming transcribers.

    Automatically selects the appropriate transcriber based on configuration.
    """

    def __init__(self, config: UnifiedStreamingConfig):
        """Initialize unified transcriber."""
        self.config = config
        self.transcriber = None

    def initialize(self):
        """
        Selects and initializes the model-specific streaming transcriber based on this instance's configuration.

        For the Parakeet model, prefers the Parakeet Core adapter when available and falls back to the legacy Parakeet transcriber otherwise. After selection, the chosen transcriber is instantiated, its initialize method is called, and the transcriber instance is stored on self.transcriber.
        """
        model_lower = self.config.model.lower()

        if model_lower == 'canary':
            self.transcriber = CanaryStreamingTranscriber(self.config)
        elif model_lower == 'whisper':
            self.transcriber = WhisperStreamingTranscriber(self.config)
        else:  # Parakeet
            # Prefer the core adapter when available; fall back to legacy transcriber
            if _ParakeetCoreAdapter is not None:
                self.transcriber = _ParakeetCoreAdapter(self.config)  # type: ignore
            else:
                self.transcriber = ParakeetStreamingTranscriber(self.config)

        self.transcriber.initialize()
        logger.info(f"Initialized {self.config.model} transcriber")

    async def process_audio_chunk(self, audio_data: bytes) -> Optional[Dict[str, Any]]:
        """Process audio chunk with selected transcriber."""
        if not self.transcriber:
            raise RuntimeError("Transcriber not initialized")
        return await self.transcriber.process_audio_chunk(audio_data)

    def get_full_transcript(self) -> str:
        """Get complete transcript."""
        if not self.transcriber:
            return ""
        return self.transcriber.get_full_transcript()

    def reset(self):
        """Reset transcriber state."""
        if self.transcriber:
            self.transcriber.reset()

    def cleanup(self):
        """Clean up resources."""
        if self.transcriber:
            self.transcriber.cleanup()
        self.transcriber = None

# Explicit export list to aid test imports and static analyzers
__all__ = [
    'UnifiedStreamingConfig',
    'BaseStreamingTranscriber',
    'WhisperStreamingTranscriber',
    'CanaryStreamingTranscriber',
    'ParakeetStreamingTranscriber',
    'UnifiedStreamingTranscriber',
]


async def handle_unified_websocket(
    websocket,
    config: Optional[UnifiedStreamingConfig] = None,
    on_audio_seconds: Optional[Callable[[float, int], Awaitable[None]]] = None,
    on_heartbeat: Optional[Callable[[], Awaitable[None]]] = None,
):
    """
    Handle a WebSocket connection to perform unified real-time transcription across Parakeet, Canary, and Whisper models.

    This handler waits for an optional client configuration message, initializes a model-specific transcriber (with runtime fallback logic), and processes incoming base64-encoded audio messages into partial and final transcription results sent to the client as JSON frames. It optionally integrates streaming diarization and live insights, emits structured status/warning/error frames, supports a commit/reset/stop control messages, and ensures proper cleanup of transcriber, diarizer, and insights resources on exit.

    Parameters:
        websocket: The WebSocket connection object used to receive client messages and send JSON frames.
        config (Optional[UnifiedStreamingConfig]): Optional initial streaming configuration; updated if a client config message is received.
        on_audio_seconds (Optional[Callable[[float, int], Awaitable[None]]]): Optional callback invoked before processing each audio chunk with two arguments: computed audio duration in seconds and the sample rate in Hz.
        on_heartbeat (Optional[Callable[[], Awaitable[None]]]): Optional callback invoked on each received audio message to refresh external TTLs (e.g., Redis-based heartbeats).
    """
    logger.info("=== handle_unified_websocket STARTED ===")

    if not config:
        config = UnifiedStreamingConfig()
        logger.info("Created default config")
    else:
        logger.info(f"Received config from caller: model={config.model}, variant={config.model_variant}")

    logger.info(f"Initial config: model={config.model}, variant={config.model_variant}")
    transcriber = None  # Initialize transcriber after config is set
    insights_settings: Optional[LiveInsightSettings] = None
    insights_engine: Optional[LiveMeetingInsights] = None
    diarizer: Optional[StreamingDiarizer] = None

    try:
        # Always wait for configuration message from client
        config_received = False
        try:
            logger.info("Waiting for configuration message from client...")
            config_message = await asyncio.wait_for(websocket.receive_text(), timeout=15.0)  # Increased timeout
            # Do not log raw payload contents (may include base64 audio); log metadata only
            logger.info(f"Received message (length={len(config_message)})")
            config_data = json.loads(config_message)
            logger.info(f"Parsed config data type: {config_data.get('type')}")

            if config_data.get("type") == "config":
                # Update configuration
                old_variant = config.model_variant
                raw_model = config_data.get("model", "parakeet")
                variant_override = config_data.get("variant") or config_data.get("model_variant")
                new_model, new_variant = normalize_model_and_variant(
                    raw_model,
                    current_model=config.model,
                    current_variant=config.model_variant,
                    variant_override=variant_override,
                )
                config.model = new_model
                config.model_variant = new_variant
                config.language = config_data.get("language", "en")
                config.sample_rate = config_data.get("sample_rate", 16000)
                config.auto_detect_language = config_data.get("auto_detect_language", False)
                config.chunk_duration = config_data.get("chunk_duration", 2.0)
                config.enable_partial = config_data.get("enable_partial", True)
                config.enable_vad = config_data.get("enable_vad", False)
                config.vad_threshold = config_data.get("vad_threshold", 0.5)
                # Optional partial emission tuning
                try:
                    if "min_partial_duration" in config_data:
                        config.min_partial_duration = max(0.0, float(config_data.get("min_partial_duration")))
                except (TypeError, ValueError):
                    logger.warning("Invalid min_partial_duration in config; keeping previous value")

                # Whisper-specific configuration
                if config.model.lower() == "whisper":
                    config.whisper_model_size = config_data.get("whisper_model_size", "distil-large-v3")
                    config.beam_size = config_data.get("beam_size", 5)
                    config.vad_filter = config_data.get("vad_filter", False)
                    config.task = config_data.get("task", "transcribe")

                insights_payload = config_data.get("insights") or config_data.get("meeting_insights")
                if insights_payload is not None:
                    try:
                        insights_settings = LiveInsightSettings.from_client_payload(insights_payload)
                    except Exception as insight_err:
                        logger.error(f"Failed to parse live insights config: {insight_err}")
                        insights_settings = LiveInsightSettings(enabled=False)
                elif config_data.get("insights_enabled") is True and insights_settings is None:
                    insights_settings = LiveInsightSettings(enabled=True)
                elif config_data.get("insights_enabled") is False:
                    insights_settings = LiveInsightSettings(enabled=False)

                diarization_payload = config_data.get("diarization")
                if diarization_payload is not None:
                    enabled_field = diarization_payload.get("enabled")
                    config.diarization_enabled = bool(enabled_field) if enabled_field is not None else True
                    if "store_audio" in diarization_payload:
                        config.diarization_store_audio = bool(diarization_payload.get("store_audio"))
                    storage_dir = diarization_payload.get("storage_dir")
                    if storage_dir:
                        config.diarization_storage_dir = str(storage_dir)
                    if "num_speakers" in diarization_payload:
                        try:
                            config.diarization_num_speakers = int(diarization_payload.get("num_speakers") or 0) or None
                        except (TypeError, ValueError):
                            logger.warning("Invalid diarization.num_speakers value; ignoring.")
                elif "diarization_enabled" in config_data:
                    config.diarization_enabled = bool(config_data.get("diarization_enabled"))
                if "diarization_store_audio" in config_data:
                    config.diarization_store_audio = bool(config_data.get("diarization_store_audio"))

                logger.info(f"Config updated: model={config.model}, variant changed from {old_variant} to {config.model_variant}, "
                           f"sample_rate={config.sample_rate}, chunk_duration={config.chunk_duration}")
                config_received = True

                # Prepare acknowledgment (do not send to keep protocol noise-free for tests)
                status_msg = {
                    "type": "status",
                    "state": "configured",
                    "model": config.model
                }

                if config.model.lower() == "parakeet":
                    status_msg["variant"] = config.model_variant
                elif config.model.lower() == "canary":
                    status_msg["language"] = config.language
                elif config.model.lower() == "whisper":
                    status_msg["whisper_model"] = config.whisper_model_size
                    status_msg["task"] = config.task
                    status_msg["language"] = config.language if config.language else "auto"

                # Intentionally not sending status frame; log only
                logger.info(f"Config acknowledged (not sent to client): {status_msg}")
            else:
                # Do not log full payload to avoid dumping base64 audio
                msg_type = config_data.get('type')
                data_len = len(config_data.get('data', '')) if isinstance(config_data.get('data'), str) else 0
                logger.warning(f"Received non-config message type: {msg_type} (payload length ~{data_len})")
        except asyncio.TimeoutError:
            logger.warning(f"Config message timeout after 15s. Using default configuration: model={config.model}, variant={config.model_variant}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse config message as JSON: {e}")
            logger.warning("Using default configuration due to JSON parse error")
        except Exception as e:
            logger.error(f"Unexpected error receiving config message: {e}", exc_info=True)
            logger.warning("Using default configuration due to error")

        if not config_received:
            logger.warning(f"No valid config received. Proceeding with: model={config.model}, variant={config.model_variant}")

        # Create transcriber with config
        if transcriber is None:
            logger.info(f"Creating UnifiedStreamingTranscriber for model: {config.model}")
            transcriber = UnifiedStreamingTranscriber(config)

        try:
            logger.info(f"Initializing transcriber for model: {config.model}")
            logger.info(f"Configuration details: model_variant={config.model_variant}, "
                       f"whisper_model_size={getattr(config, 'whisper_model_size', 'N/A')}, "
                       f"sample_rate={config.sample_rate}, language={config.language}")
            transcriber.initialize()
            logger.info(f"Transcriber initialized successfully for model: {config.model}")
        except Exception as e:
            error_msg = f"Failed to initialize {config.model} model: {str(e)}"
            logger.error(error_msg, exc_info=True)
            # Emit structured warning about model/variant unavailability before fallback attempts
            try:
                await websocket.send_json({
                    "type": "warning",
                    "state": "model_unavailable",
                    "error_type": "model_unavailable",
                    "message": "Requested model/variant unavailable; attempting fallback if enabled",
                    "details": {
                        "model": config.model,
                        "variant": getattr(config, 'model_variant', None),
                        "error": str(e),
                    },
                })
            except Exception:
                pass

            # Check if fallback to Whisper is enabled in config (module-level alias for test monkeypatching)
            comprehensive_config = load_comprehensive_config()

            # ConfigParser returns a ConfigParser object, not a dict
            fallback_enabled = False
            try:
                if comprehensive_config.has_section('STT-Settings'):
                    fallback_value = comprehensive_config.get('STT-Settings', 'streaming_fallback_to_whisper', fallback='false')
                    fallback_enabled = str(fallback_value).lower() == 'true'
                    logger.info(f"Streaming fallback to Whisper enabled: {fallback_enabled}")
            except Exception as config_error:
                logger.warning(f"Could not read streaming_fallback_to_whisper from config: {config_error}")
                # Defer Whisper fallback unless explicitly configured
                fallback_enabled = False

            # Try to fall back to Whisper if enabled and not already using Whisper
            if fallback_enabled and config.model.lower() != 'whisper':
                logger.info("Fallback to Whisper is enabled in config. Attempting to fall back...")
                try:
                    original_model = config.model
                    config.model = 'whisper'
                    config.whisper_model_size = 'distil-large-v3'
                    transcriber = UnifiedStreamingTranscriber(config)
                    transcriber.initialize()
                    logger.info("Successfully fell back to Whisper model")

                    # Notify client about fallback
                    await websocket.send_json({
                        "type": "warning",
                        "message": f"{original_model} model unavailable, using Whisper instead",
                        "fallback": True,
                        "original_model": original_model,
                        "active_model": "whisper"
                    })
                except Exception as fallback_error:
                    logger.error(f"Fallback to Whisper also failed: {fallback_error}")
                    # Send error with more details
                    await websocket.send_json({
                        "type": "error",
                        "error_type": "model_unavailable",
                        "message": "No transcription models available. Please install required dependencies.",
                        "details": {
                            "model": config.model,
                            "variant": getattr(config, 'model_variant', None),
                            "original_error": str(e),
                            "fallback_error": str(fallback_error),
                            "suggestion": "Install nemo_toolkit[asr] for Parakeet/Canary or ensure faster-whisper is installed"
                        }
                    })

                    # Close with error code
                    await websocket.close(code=1011, reason="No models available")
                    return
            else:
                # Fallback disabled or already using Whisper
                suggestion = ""
                if config.model.lower() in ['parakeet', 'canary']:
                    suggestion = "Install nemo_toolkit[asr]: pip install nemo_toolkit[asr]"
                elif config.model.lower() == 'whisper':
                    suggestion = "Ensure faster-whisper is installed: pip install faster-whisper"

                # Send error with more details
                await websocket.send_json({
                    "type": "error",
                    "error_type": "model_unavailable",
                    "message": error_msg,
                    "details": {
                        "model": config.model,
                        "error_type": type(e).__name__,
                        "error_details": str(e),
                        "fallback_enabled": fallback_enabled,
                        "suggestion": suggestion
                    }
                })

                # Close with error code
                await websocket.close(code=1011, reason=error_msg[:120])  # 1011 = Internal Error
                return

        if diarizer is None and config.diarization_enabled:
            try:
                diarizer = StreamingDiarizer(
                    sample_rate=config.sample_rate,
                    store_audio=config.diarization_store_audio,
                    storage_dir=config.diarization_storage_dir,
                    num_speakers=config.diarization_num_speakers,
                )
                ready = await diarizer.ensure_ready()
                if not ready:
                    logger.warning("Streaming diarizer unavailable during initialization; disabling diarization.")
                    await websocket.send_json({
                        "type": "warning",
                        "state": "diarization_unavailable",
                        "message": "Diarization disabled: dependencies missing or initialization failed",
                        "details": getattr(diarizer, "_service_error", None),
                    })
                    diarizer = None
                else:
                    await websocket.send_json({
                        "type": "status",
                        "state": "diarization_enabled",
                        "diarization": {
                            "store_audio": config.diarization_store_audio,
                            "storage_dir": config.diarization_storage_dir,
                            "num_speakers": config.diarization_num_speakers,
                        },
                    })
            except Exception as diar_err:
                logger.error(f"Failed to initialize streaming diarizer: {diar_err}", exc_info=True)
                await websocket.send_json({
                    "type": "warning",
                    "state": "diarization_unavailable",
                    "message": "Diarization disabled: initialization failed",
                    "details": str(diar_err),
                })
                diarizer = None

        if insights_engine is None and insights_settings and insights_settings.enabled:
            try:
                insights_engine = LiveMeetingInsights(websocket, insights_settings)
                logger.info(
                    f"Live insights enabled (provider={insights_engine.provider}, model={insights_engine.model})"
                )
                await websocket.send_json({
                    "type": "status",
                    "state": "insights_enabled",
                    "insights": insights_engine.describe()
                })
            except Exception as insight_err:
                logger.error(f"Failed to initialize live insights engine: {insight_err}", exc_info=True)
                await websocket.send_json({
                    "type": "warning",
                    "state": "insights_unavailable",
                    "message": "Live insights disabled: initialization failed",
                    "details": str(insight_err)
                })
                insights_engine = None
        elif insights_settings and not insights_settings.enabled:
            logger.info("Live insights explicitly disabled for this session.")

        # Do not send a ready status frame to minimize protocol chatter

        # Process messages
        while True:
            try:
                message = await websocket.receive_text()
                data = json.loads(message)

                if data.get("type") == "audio":
                    # Decode audio data
                    audio_base64 = data.get("data", "")
                    audio_bytes = base64.b64decode(audio_base64)
                    # Optional callback to account for usage seconds before processing
                    if on_audio_seconds is not None:
                        # Compute seconds from byte length and configured sample rate
                        try:
                            from tldw_Server_API.app.core.Usage.audio_quota import bytes_to_seconds as _bytes_to_seconds
                            seconds = _bytes_to_seconds(len(audio_bytes), int(config.sample_rate or 16000))
                        except Exception:
                            seconds = float(len(audio_bytes)) / float(4 * max(1, int(config.sample_rate or 16000)))
                        await on_audio_seconds(seconds, int(config.sample_rate or 16000))
                    # Optional heartbeat to refresh stream TTL when using Redis counters
                    if on_heartbeat is not None:
                        try:
                            await on_heartbeat()
                        except Exception:
                            pass

                    # Process audio chunk
                    result = await transcriber.process_audio_chunk(audio_bytes)

                    if result:
                        audio_np = result.pop("_audio_chunk", None)
                        if audio_np is not None and diarizer:
                            try:
                                speaker_info = await diarizer.label_segment(
                                    audio_np,
                                    {
                                        "segment_id": result.get("segment_id"),
                                        "segment_start": result.get("segment_start"),
                                        "segment_end": result.get("segment_end"),
                                        "chunk_start": result.get("chunk_start"),
                                        "chunk_end": result.get("chunk_end"),
                                        "text": result.get("text"),
                                    },
                                )
                                if speaker_info:
                                    if speaker_info.get("speaker_id") is not None:
                                        result.setdefault("speaker_id", speaker_info["speaker_id"])
                                    if speaker_info.get("speaker_label"):
                                        result.setdefault("speaker_label", speaker_info["speaker_label"])
                            except Exception as diar_err:
                                logger.error(f"Diarization update failed: {diar_err}", exc_info=True)

                        await websocket.send_json(result)
                        if insights_engine and result.get("is_final"):
                            try:
                                await insights_engine.on_transcript(result)
                            except Exception as insight_err:
                                logger.error(f"Live insights failed to ingest segment: {insight_err}", exc_info=True)

                elif data.get("type") == "commit":
                    # Get final transcript
                    full_transcript = transcriber.get_full_transcript()
                    await websocket.send_json({
                        "type": "full_transcript",
                        "text": full_transcript,
                        "timestamp": time.time()
                    })
                    if insights_engine:
                        try:
                            await insights_engine.on_commit(full_transcript)
                        except Exception as insight_err:
                            logger.error(f"Live insights final summary failed: {insight_err}", exc_info=True)
                    if diarizer:
                        try:
                            mapping, audio_path, speakers = await diarizer.finalize()
                            if mapping or audio_path or speakers:
                                speaker_map = [
                                    {
                                        "segment_id": seg_id,
                                        "speaker_id": info.get("speaker_id"),
                                        "speaker_label": info.get("speaker_label"),
                                    }
                                    for seg_id, info in sorted(mapping.items())
                                ]
                                await websocket.send_json({
                                    "type": "diarization_summary",
                                    "speaker_map": speaker_map,
                                    "audio_path": audio_path,
                                    "speakers": speakers,
                                    "persistence_method": getattr(diarizer, "persistence_method", None),
                                })
                                # Emit structured warning when persistence requested but unavailable
                                try:
                                    if (
                                        config.diarization_store_audio
                                        and (audio_path is None or not audio_path)
                                    ):
                                        await websocket.send_json({
                                            "type": "warning",
                                            "warning_type": "audio_persistence_unavailable",
                                            "message": "Audio persistence was requested but is unavailable; continuing without persisted WAV",
                                        })
                                except Exception:
                                    pass
                        except Exception as diar_err:
                            logger.error(f"Diarization finalize failed: {diar_err}", exc_info=True)

                elif data.get("type") == "reset":
                    # Reset transcriber
                    transcriber.reset()
                    if insights_engine:
                        try:
                            await insights_engine.reset()
                        except Exception as insight_err:
                            logger.error(f"Live insights reset failed: {insight_err}", exc_info=True)
                    if diarizer:
                        try:
                            await diarizer.reset()
                        except Exception as diar_err:
                            logger.error(f"Diarization reset failed: {diar_err}", exc_info=True)
                    await websocket.send_json({
                        "type": "status",
                        "state": "reset"
                    })

                elif data.get("type") == "stop":
                    # Stop transcription
                    break

            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON message"
                })
            except QuotaExceeded as qe:
                # Send structured quota error and close with application-defined code
                try:
                    await websocket.send_json({
                        "type": "error",
                        "error_type": "quota_exceeded",
                        "quota": getattr(qe, "quota", "unknown"),
                        "message": "Streaming transcription quota exceeded"
                    })
                finally:
                    try:
                        await websocket.close(code=4003, reason="quota_exceeded")
                    except Exception:
                        pass
                return
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": f"Processing error: {str(e)}"
                })

    except asyncio.TimeoutError:
        await websocket.send_json({
            "type": "error",
            "message": "Configuration timeout"
        })
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected by client")
    except Exception as e:
        logger.error(f"WebSocket handler error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Server error: {str(e)}"
            })
        except Exception as send_err:
            logger.debug(f"Failed to send error frame on websocket: error={send_err}")
    finally:
        # Clean up
        if transcriber:
            transcriber.cleanup()
        if insights_engine:
            try:
                await insights_engine.close()
            except Exception as insight_err:
                logger.error(f"Failed to close live insights engine: {insight_err}")
        if diarizer:
            try:
                await diarizer.close()
            except Exception as diar_err:
                logger.error(f"Failed to close diarizer: {diar_err}")


# Export main components
__all__ = [
    'UnifiedStreamingConfig',
    'BaseStreamingTranscriber',
    'ParakeetStreamingTranscriber',
    'CanaryStreamingTranscriber',
    'WhisperStreamingTranscriber',
    'UnifiedStreamingTranscriber',
    'handle_unified_websocket'
]
