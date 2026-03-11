from __future__ import annotations

import platform
from typing import TYPE_CHECKING

from ..tts_exceptions import TTSGenerationError, TTSProviderInitializationError, TTSValidationError
from .base import AudioFormat, TTSCapabilities, TTSRequest, TTSResponse, VoiceInfo

if TYPE_CHECKING:
    from .qwen3_tts_adapter import Qwen3TTSAdapter


class Qwen3MlxRuntime:
    runtime_name = "mlx"

    def __init__(self, adapter: "Qwen3TTSAdapter") -> None:
        self.adapter = adapter

    async def initialize(self) -> bool:
        if platform.system() != "Darwin" or platform.machine().lower() != "arm64":
            raise TTSProviderInitializationError(
                "Qwen3-TTS MLX runtime requires macOS on Apple Silicon",
                provider=self.adapter.PROVIDER_KEY,
            )
        return True

    async def get_capabilities(self) -> TTSCapabilities:
        max_text_length = self.adapter._coerce_int(self.adapter.config.get("max_text_length")) or 5000
        voices = [VoiceInfo(id=speaker, name=speaker) for speaker in self.adapter.CUSTOMVOICE_SPEAKERS]
        return TTSCapabilities(
            provider_name=self.adapter.provider_name,
            supported_languages=set(self.adapter.SUPPORTED_LANGUAGES),
            supported_voices=voices,
            supported_formats={
                AudioFormat.MP3,
                AudioFormat.OPUS,
                AudioFormat.AAC,
                AudioFormat.WAV,
                AudioFormat.PCM,
            },
            max_text_length=max_text_length,
            supports_streaming=False,
            supports_voice_cloning=False,
            supports_emotion_control=False,
            sample_rate=self.adapter.sample_rate,
            default_format=AudioFormat.PCM,
            metadata={
                "runtime": self.runtime_name,
                "supported_modes": ["custom_voice_preset"],
                "supports_uploaded_custom_voices": False,
            },
        )

    def validate_mode(self, request: TTSRequest, mode: str) -> None:
        if isinstance(request.voice, str) and request.voice.startswith("custom:"):
            raise TTSValidationError(
                "Uploaded custom voices are not supported by the MLX runtime in v1",
                provider=self.adapter.PROVIDER_KEY,
            )
        if mode in {"voice_clone", "voice_design"}:
            raise TTSValidationError(
                f"Mode '{mode}' is not supported by the MLX runtime",
                provider=self.adapter.PROVIDER_KEY,
            )

    async def generate(self, request: TTSRequest, resolved_model: str, mode: str) -> TTSResponse:
        self.validate_mode(request, mode)
        raise TTSGenerationError(
            "Qwen3-TTS MLX runtime preset-speaker generation is not implemented yet",
            provider=self.adapter.PROVIDER_KEY,
            details={"runtime": self.runtime_name, "model": resolved_model},
        )
