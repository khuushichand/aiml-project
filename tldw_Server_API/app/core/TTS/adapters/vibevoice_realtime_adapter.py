# vibevoice_realtime_adapter.py
# Description: VibeVoice Realtime TTS adapter skeleton (streaming text -> audio)
#
# Imports
import asyncio
from typing import Any, Dict, Optional, Set
#
# Third-party Imports
from loguru import logger
#
# Local Imports
from .base import (
    AudioFormat,
    ProviderStatus,
    TTSCapabilities,
    TTSAdapter,
    TTSRequest,
    TTSResponse,
)
from ..tts_exceptions import (
    TTSProviderUnavailableError,
)
from ..tts_validation import validate_tts_request
from ..utils import parse_bool
#
#######################################################################################################################
#
# VibeVoice Realtime Adapter (Skeleton)


class VibeVoiceRealtimeAdapter(TTSAdapter):
    """
    Adapter skeleton for Microsoft VibeVoice-Realtime (0.5B).

    This adapter is intentionally minimal; it provides configuration wiring and
    capability metadata, while returning "unavailable" until a realtime backend
    is integrated (local or remote).
    """

    PROVIDER_KEY = "vibevoice_realtime"
    SUPPORTED_FORMATS: Set[AudioFormat] = {
        AudioFormat.PCM,
        AudioFormat.WAV,
        AudioFormat.MP3,
        AudioFormat.OPUS,
        AudioFormat.FLAC,
    }
    SUPPORTED_LANGUAGES = {"en"}
    MAX_TEXT_LENGTH = 8192
    DEFAULT_SAMPLE_RATE = 24000

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        cfg = config or {}
        extra_cfg = cfg.get("extra_params") if isinstance(cfg.get("extra_params"), dict) else {}

        self.model_path = (
            cfg.get("vibevoice_realtime_model_path")
            or cfg.get("model_path")
            or extra_cfg.get("model_path")
            or "microsoft/VibeVoice-Realtime-0.5B"
        )
        self.device = (
            cfg.get("vibevoice_realtime_device")
            or cfg.get("device")
            or extra_cfg.get("device")
            or "cpu"
        )
        self.sample_rate = int(
            cfg.get("vibevoice_realtime_sample_rate")
            or cfg.get("sample_rate")
            or extra_cfg.get("sample_rate")
            or self.DEFAULT_SAMPLE_RATE
        )
        self.auto_download = parse_bool(
            cfg.get("vibevoice_realtime_auto_download")
            or cfg.get("auto_download")
            or extra_cfg.get("auto_download"),
            default=False,
        )
        self.stream_chunk_ms = int(
            cfg.get("vibevoice_realtime_stream_chunk_ms")
            or cfg.get("stream_chunk_size_ms")
            or extra_cfg.get("stream_chunk_size_ms")
            or 40
        )
        self._init_lock = asyncio.Lock()

    async def initialize(self) -> bool:
        """Skeleton initializer; returns unavailable until implementation is wired."""
        logger.warning(
            "VibeVoice Realtime adapter is a stub. Configure a realtime backend to enable."
        )
        self._status = ProviderStatus.ERROR
        return False

    async def get_capabilities(self) -> TTSCapabilities:
        return TTSCapabilities(
            provider_name="VibeVoice-Realtime",
            supported_languages=self.SUPPORTED_LANGUAGES,
            supported_voices=[],
            supported_formats=self.SUPPORTED_FORMATS,
            max_text_length=self.MAX_TEXT_LENGTH,
            supports_streaming=True,
            supports_voice_cloning=False,
            supports_emotion_control=False,
            supports_speech_rate=True,
            supports_pitch_control=False,
            supports_volume_control=False,
            supports_ssml=False,
            supports_phonemes=False,
            supports_multi_speaker=False,
            supports_background_audio=False,
            latency_ms=200,
            sample_rate=self.sample_rate,
            default_format=AudioFormat.PCM,
        )

    async def generate(self, request: TTSRequest) -> TTSResponse:
        """Realtime adapter does not yet support non-session generation."""
        # Validate input for consistent error handling.
        validate_tts_request(request, provider=self.PROVIDER_KEY)
        raise TTSProviderUnavailableError(
            "VibeVoice Realtime adapter is not yet implemented",
            provider=self.PROVIDER_KEY,
        )

