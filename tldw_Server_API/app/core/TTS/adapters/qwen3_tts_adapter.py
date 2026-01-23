# qwen3_tts_adapter.py
# Description: Adapter for Qwen3-TTS local models
#
# Imports
from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, Optional
import importlib

import numpy as np
from loguru import logger

from .base import (
    AudioFormat,
    TTSAdapter,
    TTSRequest,
    TTSResponse,
    TTSCapabilities,
    VoiceInfo,
)
from ..tts_exceptions import (
    TTSProviderInitializationError,
    TTSValidationError,
)
from ..streaming_audio_writer import AudioNormalizer, StreamingAudioWriter
from ..utils import parse_bool


class Qwen3TTSAdapter(TTSAdapter):
    """Adapter for Qwen3-TTS local models (CustomVoice/VoiceDesign/Base)."""

    PROVIDER_KEY = "qwen3_tts"

    MODEL_CUSTOMVOICE_17B = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
    MODEL_CUSTOMVOICE_06B = "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"
    MODEL_VOICEDESIGN_17B = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
    MODEL_BASE_17B = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
    MODEL_BASE_06B = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"

    SUPPORTED_LANGUAGES = {
        "auto",
        "zh",
        "en",
        "ja",
        "ko",
        "de",
        "fr",
        "ru",
        "pt",
        "es",
        "it",
    }

    CUSTOMVOICE_SPEAKERS = [
        "Vivian",
        "Serena",
        "Uncle_Fu",
        "Dylan",
        "Eric",
        "Ryan",
        "Aiden",
        "Ono_Anna",
        "Sohee",
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config=config)
        cfg = config or {}
        self.model = (cfg.get("model") or "auto").strip()
        self.model_path = cfg.get("model_path")
        self.tokenizer_model = cfg.get("tokenizer_model") or "Qwen/Qwen3-TTS-Tokenizer-12Hz"
        self.device = (cfg.get("device") or "cpu").strip().lower()
        self.dtype = (cfg.get("dtype") or "float16").strip().lower()
        self.attn_implementation = (cfg.get("attn_implementation") or "default").strip().lower()
        self.auto_download = parse_bool(cfg.get("auto_download"), default=False)
        self.auto_min_vram_gb = self._coerce_int(cfg.get("auto_min_vram_gb")) or 12
        self.stream_chunk_size_ms = self._coerce_int(cfg.get("stream_chunk_size_ms")) or 200
        self.sample_rate = self._coerce_int(cfg.get("sample_rate")) or 24000
        self._backend = None

    def _coerce_int(self, value: Any) -> Optional[int]:
        try:
            if value is None:
                return None
            return int(value)
        except Exception:
            return None

    async def initialize(self) -> bool:
        """Initialize adapter; verify dependency presence."""
        try:
            importlib.import_module("qwen_tts")
        except Exception as exc:
            raise TTSProviderInitializationError(
                "qwen-tts package is required for Qwen3-TTS adapter",
                provider=self.PROVIDER_KEY,
            ) from exc

        # Backend initialization is deferred to provider-specific integration.
        self._backend = None
        return True

    async def get_capabilities(self) -> TTSCapabilities:
        max_text_length = self._coerce_int(self.config.get("max_text_length")) or 5000
        voices = [VoiceInfo(id=speaker, name=speaker) for speaker in self.CUSTOMVOICE_SPEAKERS]
        return TTSCapabilities(
            provider_name=self.provider_name,
            supported_languages=set(self.SUPPORTED_LANGUAGES),
            supported_voices=voices,
            supported_formats={
                AudioFormat.MP3,
                AudioFormat.OPUS,
                AudioFormat.AAC,
                AudioFormat.WAV,
                AudioFormat.PCM,
            },
            max_text_length=max_text_length,
            supports_streaming=True,
            supports_voice_cloning=True,
            supports_emotion_control=True,
            sample_rate=self.sample_rate,
            default_format=AudioFormat.PCM,
        )

    def _is_voice_design_request(self, request: TTSRequest) -> bool:
        voice = request.voice
        if voice is None:
            return True
        if isinstance(voice, str) and not voice.strip():
            return True
        return False

    def _is_voice_clone_request(self, request: TTSRequest) -> bool:
        if request.voice_reference:
            return True
        extras = request.extra_params or {}
        if extras.get("reference_text") or extras.get("x_vector_only_mode"):
            return True
        if extras.get("voice_clone_prompt"):
            return True
        return False

    def _resolve_auto_model(self) -> str:
        if self.device.startswith("cuda"):
            try:
                import torch
                if torch.cuda.is_available():
                    device_idx = 0
                    if ":" in self.device:
                        try:
                            device_idx = int(self.device.split(":", 1)[1])
                        except Exception:
                            device_idx = 0
                    props = torch.cuda.get_device_properties(device_idx)
                    total_gb = props.total_memory / (1024 ** 3)
                    if total_gb >= float(self.auto_min_vram_gb):
                        return self.MODEL_CUSTOMVOICE_17B
            except Exception:
                logger.debug("Qwen3-TTS auto model selection could not read CUDA VRAM; falling back")
            return self.MODEL_CUSTOMVOICE_06B
        if self.device == "mps":
            return self.MODEL_CUSTOMVOICE_06B
        return self.MODEL_CUSTOMVOICE_06B

    def _resolve_model(self, request: TTSRequest) -> str:
        requested = (getattr(request, "model", None) or self.model or "auto").strip()
        if requested.lower() == "auto":
            if self._is_voice_design_request(request) or self._is_voice_clone_request(request):
                raise TTSValidationError(
                    "model='auto' is only valid for CustomVoice requests; specify a VoiceDesign/Base model",
                    provider=self.PROVIDER_KEY,
                )
            return self._resolve_auto_model()
        return requested

    async def _stream_transcoded_pcm(
        self,
        pcm_stream: AsyncGenerator[np.ndarray, None],
        request_format: AudioFormat,
    ) -> AsyncGenerator[bytes, None]:
        audio_normalizer = AudioNormalizer()
        writer = StreamingAudioWriter(
            format=request_format.value,
            sample_rate=self.sample_rate,
            channels=1,
        )
        try:
            async for chunk in pcm_stream:
                if chunk is None:
                    continue
                if isinstance(chunk, (bytes, bytearray)):
                    pcm = np.frombuffer(chunk, dtype=np.int16)
                else:
                    pcm = np.asarray(chunk)
                if pcm.dtype != np.int16:
                    pcm = audio_normalizer.normalize(pcm, target_dtype=np.int16)
                data = writer.write_chunk(pcm)
                if data:
                    yield data
            tail = writer.write_chunk(finalize=True)
            if tail:
                yield tail
        finally:
            writer.close()

    def _generate_pcm_stream(
        self,
        request: TTSRequest,
        model_id: str,
    ) -> AsyncGenerator[np.ndarray, None]:
        async def _raise_stream():
            raise TTSProviderInitializationError(
                "Qwen3-TTS streaming backend not wired",
                provider=self.PROVIDER_KEY,
            )
            if False:
                yield np.zeros(0, dtype=np.int16)
        return _raise_stream()

    async def _generate_pcm(
        self,
        request: TTSRequest,
        model_id: str,
    ) -> np.ndarray:
        raise TTSProviderInitializationError(
            "Qwen3-TTS backend not wired",
            provider=self.PROVIDER_KEY,
        )

    async def generate(self, request: TTSRequest) -> TTSResponse:
        """Generate speech from text (backend integration required)."""
        if not await self.ensure_initialized():
            raise TTSProviderInitializationError(
                "Qwen3-TTS adapter not initialized",
                provider=self.PROVIDER_KEY,
            )
        resolved_model = self._resolve_model(request)
        if self._backend is None:
            raise TTSProviderInitializationError(
                "Qwen3-TTS backend is not configured in this build",
                provider=self.PROVIDER_KEY,
            )
        if request.stream:
            pcm_stream = self._generate_pcm_stream(request, resolved_model)
            if request.format == AudioFormat.PCM:
                async def _pcm_bytes() -> AsyncGenerator[bytes, None]:
                    async for chunk in pcm_stream:
                        if chunk is None:
                            continue
                        if isinstance(chunk, (bytes, bytearray)):
                            yield bytes(chunk)
                        else:
                            yield np.asarray(chunk, dtype=np.int16).tobytes()
                audio_stream = _pcm_bytes()
            else:
                audio_stream = self._stream_transcoded_pcm(pcm_stream, request.format)
            return TTSResponse(
                audio_stream=audio_stream,
                format=request.format,
                sample_rate=self.sample_rate,
                provider=self.PROVIDER_KEY,
                model=resolved_model,
            )

        pcm_audio = await self._generate_pcm(request, resolved_model)
        audio_bytes = await self.convert_audio_format(
            pcm_audio,
            source_format=AudioFormat.PCM,
            target_format=request.format,
            sample_rate=self.sample_rate,
        )
        return TTSResponse(
            audio_content=audio_bytes,
            format=request.format,
            sample_rate=self.sample_rate,
            provider=self.PROVIDER_KEY,
            model=resolved_model,
        )
