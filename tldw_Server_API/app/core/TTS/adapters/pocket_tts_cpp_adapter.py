# pocket_tts_cpp_adapter.py
# Description: Placeholder PocketTTS.cpp adapter scaffold.
#
from __future__ import annotations

from loguru import logger

from .base import AudioFormat, TTSAdapter, TTSCapabilities, TTSRequest, TTSResponse


class PocketTTSCppAdapter(TTSAdapter):
    """Placeholder adapter for PocketTTS.cpp until the runtime lands."""

    PROVIDER_KEY = "pocket_tts_cpp"

    async def initialize(self) -> bool:
        logger.warning("PocketTTS.cpp adapter is not implemented yet")
        return False

    async def generate(self, request: TTSRequest) -> TTSResponse:
        raise RuntimeError("PocketTTS.cpp adapter is not implemented yet")

    async def get_capabilities(self) -> TTSCapabilities:
        return TTSCapabilities(
            provider_name=self.PROVIDER_KEY,
            supported_languages={"en"},
            supported_voices=[],
            supported_formats={AudioFormat.MP3, AudioFormat.WAV, AudioFormat.OPUS, AudioFormat.FLAC, AudioFormat.PCM, AudioFormat.AAC},
            max_text_length=5000,
            supports_streaming=False,
            supports_voice_cloning=False,
            sample_rate=24000,
            default_format=AudioFormat.MP3,
        )
