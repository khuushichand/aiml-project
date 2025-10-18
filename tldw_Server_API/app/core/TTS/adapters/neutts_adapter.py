"""NeuTTS Air adapter

Integrates the NeuTTS Air text-to-speech model (on-device, voice cloning)
into the unified TTS adapter framework. Supports:
- Non-streaming generation (all backends)
- Streaming generation when using a GGUF backbone (llama-cpp)

Requirements (install as needed):
- neucodec>=0.0.4
- librosa, phonemizer, transformers
- optional: llama-cpp-python (for GGUF streaming), onnxruntime (if using ONNX codec)

Reference upstream: https://github.com/neuphonic/neutts-air
"""
from __future__ import annotations

import asyncio
import base64
import os
import tempfile
from typing import AsyncGenerator, Dict, Optional, Any

import numpy as np
from loguru import logger

from .base import (
    TTSAdapter,
    TTSCapabilities,
    TTSResponse,
    TTSRequest,
    AudioFormat,
    ProviderStatus,
)
from ..tts_exceptions import (
    TTSGenerationError,
    TTSModelLoadError,
    TTSModelNotFoundError,
    TTSProviderNotConfiguredError,
    TTSValidationError,
)
from ..tts_validation import validate_tts_request


class NeuTTSAdapter(TTSAdapter):
    """Adapter for NeuTTS Air provider."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config=config)
        self.sample_rate: int = int(self.config.get("sample_rate", 24000))

        # NeuTTS backbone/codec configuration
        self.backbone_repo: str = str(
            self.config.get("backbone_repo", "neuphonic/neutts-air")
        )
        self.backbone_device: str = str(self.config.get("backbone_device", "cpu"))
        self.codec_repo: str = str(
            self.config.get("codec_repo", "neuphonic/neucodec")
        )
        self.codec_device: str = str(self.config.get("codec_device", "cpu"))

        # Will be set after init
        self._engine = None
        self._is_quantized_model = False
        self._supports_streaming = False
        self.audio_normalizer = None

    async def initialize(self) -> bool:
        """Initialize NeuTTS Air engine and dependencies."""
        try:
            # Lazy import of vendored engine to avoid global import failures
            from tldw_Server_API.app.core.TTS.vendors.neuttsair.neutts import NeuTTSAir as _NeuTTSAir

            # Create engine instance
            logger.info(
                f"NeuTTS: loading backbone={self.backbone_repo} codec={self.codec_repo}"
            )
            # Respect auto_download toggle from provider config (default True)
            auto_download = bool(self.config.get("auto_download", True))
            self._engine = _NeuTTSAir(
                backbone_repo=self.backbone_repo,
                backbone_device=self.backbone_device,
                codec_repo=self.codec_repo,
                codec_device=self.codec_device,
                auto_download=auto_download,
            )

            # Detect capabilities from engine flags
            self._is_quantized_model = getattr(self._engine, "_is_quantized_model", False)
            self._supports_streaming = bool(self._is_quantized_model)

            # Utilities
            from tldw_Server_API.app.core.TTS.streaming_audio_writer import AudioNormalizer
            self.audio_normalizer = AudioNormalizer()

            self._status = ProviderStatus.AVAILABLE
            logger.info(
                f"NeuTTS initialized (streaming={'yes' if self._supports_streaming else 'no'})"
            )
            return True

        except ImportError as e:
            logger.error(f"NeuTTS import error: {e}")
            raise TTSModelLoadError(
                "NeuTTS dependencies missing",
                provider=self.provider_name,
                details={
                    "error": str(e),
                    "suggestion": "Install: neucodec>=0.0.4, librosa, phonemizer, transformers; optional llama-cpp-python for GGUF",
                },
            )
        except Exception as e:
            logger.error(f"NeuTTS initialization failed: {e}")
            raise TTSModelLoadError(
                "Failed to initialize NeuTTS",
                provider=self.provider_name,
                details={"error": str(e)},
            )

    async def get_capabilities(self) -> TTSCapabilities:
        return TTSCapabilities(
            provider_name="NeuTTS",
            supported_languages={"en", "en-us", "en-gb"},
            supported_voices=[],  # voice is driven by reference cloning
            supported_formats={
                AudioFormat.MP3,
                AudioFormat.WAV,
                AudioFormat.OPUS,
                AudioFormat.FLAC,
                AudioFormat.PCM,
            },
            max_text_length=1000,
            supports_streaming=self._supports_streaming,
            supports_voice_cloning=True,
            supports_emotion_control=False,
            supports_speech_rate=True,
            supports_pitch_control=False,
            supports_volume_control=False,
            supports_ssml=False,
            supports_phonemes=True,
            supports_multi_speaker=False,
            supports_background_audio=False,
            latency_ms=400 if self._supports_streaming else 3500,
            sample_rate=self.sample_rate,
            default_format=AudioFormat.WAV,
        )

    async def generate(self, request: TTSRequest) -> TTSResponse:
        if not await self.ensure_initialized():
            raise TTSProviderNotConfiguredError(
                "NeuTTS not initialized",
                provider=self.provider_name,
            )

        # Validate request
        try:
            validate_tts_request(request, provider="neutts")
        except Exception as e:
            logger.error(f"NeuTTS request validation failed: {e}")
            raise

        # Resolve reference inputs
        ref_text = None
        extras = request.extra_params or {}
        # Accept `reference_text` or `ref_text` in extra_params
        ref_text = (
            extras.get("reference_text")
            or extras.get("ref_text")
            or extras.get("voice_reference_text")
        )

        # Optionally override engine repos/devices per request
        self._maybe_override_engine(extras)

        # Ref codes may be provided directly (list of ints)
        ref_codes = extras.get("ref_codes")
        if ref_codes is not None and not isinstance(ref_codes, (list, tuple)):
            raise TTSValidationError(
                "ref_codes must be a list of integers",
                details={"type": type(ref_codes).__name__},
            )

        # If ref codes not provided, use voice_reference audio to encode
        temp_path = None
        try:
            if ref_codes is None:
                if not request.voice_reference:
                    raise TTSValidationError(
                        "NeuTTS requires voice_reference audio or pre-encoded ref_codes",
                        details={"hint": "pass base64 voice_reference or extra_params.ref_codes"},
                    )
                # Write bytes to a temporary file (librosa can auto-detect format)
                temp_fd, temp_path = tempfile.mkstemp(suffix=".wav")
                os.close(temp_fd)
                with open(temp_path, "wb") as f:
                    f.write(request.voice_reference)
                # Encode reference
                logger.info("NeuTTS: encoding reference audio")
                ref_codes = self._engine.encode_reference(temp_path)  # type: ignore

            if not ref_text or not isinstance(ref_text, str) or not ref_text.strip():
                raise TTSValidationError(
                    "NeuTTS requires reference_text corresponding to the reference audio",
                    details={"param": "extra_params.reference_text"},
                )

            # Generate waveform
            logger.info("NeuTTS: generating waveform")
            wav = self._engine.infer(request.text, ref_codes, ref_text)  # type: ignore
            # Normalize to int16
            from tldw_Server_API.app.core.TTS.streaming_audio_writer import AudioNormalizer
            normalizer = self.audio_normalizer or AudioNormalizer()
            audio_i16 = normalizer.normalize(wav, target_dtype=np.int16)

            # Convert to requested format (single shot)
            audio_bytes = await self.convert_audio_format(
                audio_i16, source_format=AudioFormat.PCM, target_format=request.format, sample_rate=self.sample_rate
            )
            return TTSResponse(
                audio_data=audio_bytes,
                format=request.format,
                sample_rate=self.sample_rate,
                text_processed=request.text,
                provider=self.provider_name,
                model=self.backbone_repo,
            )
        except TTSValidationError:
            raise
        except Exception as e:
            logger.error(f"NeuTTS generation error: {e}")
            raise TTSGenerationError(
                "NeuTTS generation failed",
                provider=self.provider_name,
                details={"error": str(e)},
            )
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    async def generate_stream(self, request: TTSRequest) -> AsyncGenerator[bytes, None]:
        if not await self.ensure_initialized():
            raise TTSProviderNotConfiguredError(
                "NeuTTS not initialized",
                provider=self.provider_name,
            )
        if not self._supports_streaming:
            raise TTSGenerationError(
                "NeuTTS streaming requires a GGUF backbone (llama-cpp)",
                provider=self.provider_name,
            )

        # Validate request
        try:
            validate_tts_request(request, provider="neutts")
        except Exception as e:
            logger.error(f"NeuTTS request validation failed: {e}")
            raise

        # Resolve reference inputs
        extras = request.extra_params or {}
        ref_text = (
            extras.get("reference_text")
            or extras.get("ref_text")
            or extras.get("voice_reference_text")
        )
        ref_codes = extras.get("ref_codes")

        temp_path = None
        try:
            if ref_codes is None:
                if not request.voice_reference:
                    raise TTSValidationError(
                        "NeuTTS streaming requires voice_reference audio or pre-encoded ref_codes",
                        details={"hint": "pass base64 voice_reference or extra_params.ref_codes"},
                    )
                temp_fd, temp_path = tempfile.mkstemp(suffix=".wav")
                os.close(temp_fd)
                with open(temp_path, "wb") as f:
                    f.write(request.voice_reference)
                ref_codes = self._engine.encode_reference(temp_path)  # type: ignore

            if not ref_text or not isinstance(ref_text, str) or not ref_text.strip():
                raise TTSValidationError(
                    "NeuTTS requires reference_text corresponding to the reference audio",
                    details={"param": "extra_params.reference_text"},
                )

            # Set up streaming writer for target format
            from tldw_Server_API.app.core.TTS.streaming_audio_writer import StreamingAudioWriter
            writer = StreamingAudioWriter(
                format=request.format.value,
                sample_rate=self.sample_rate,
                channels=1,
            )
            chunk_idx = 0
            try:
                for chunk in self._engine.infer_stream(request.text, ref_codes, ref_text):  # type: ignore
                    if chunk is None or len(chunk) == 0:
                        continue
                    chunk_idx += 1
                    # Normalize float32 -> int16, then encode
                    normalized = self.audio_normalizer.normalize(chunk, target_dtype=np.int16)
                    encoded = writer.write_chunk(normalized)
                    if encoded:
                        yield encoded
                # Finalize
                final_bytes = writer.write_chunk(finalize=True)
                if final_bytes:
                    yield final_bytes
                logger.info(f"NeuTTS streamed {chunk_idx} chunks")
            finally:
                writer.close()

        except TTSValidationError:
            raise
        except Exception as e:
            logger.error(f"NeuTTS streaming error: {e}")
            raise TTSGenerationError(
                "NeuTTS streaming failed",
                provider=self.provider_name,
                details={"error": str(e)},
            )
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    def _maybe_override_engine(self, extras: Dict[str, Any]):
        """Allow per-request override of model repos/devices via extra_params."""
        # No hot-reload to different repos; only accept if same repos to avoid reinit
        bb = extras.get("backbone_repo")
        cr = extras.get("codec_repo")
        if (bb and bb != self.backbone_repo) or (cr and cr != self.codec_repo):
            logger.warning(
                "NeuTTS per-request repo override ignored (engine already initialized)."
            )
        # Device overrides are safe to ignore at runtime; could be used in future
