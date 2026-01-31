"""Text-to-speech adapter.

This module includes the TTS adapter for speech synthesis.
"""

from __future__ import annotations

from typing import Any, Dict

from tldw_Server_API.app.core.Workflows.adapters._registry import registry
from tldw_Server_API.app.core.Workflows.adapters.audio._config import TTSConfig


@registry.register(
    "tts",
    category="audio",
    description="Text-to-speech synthesis",
    parallelizable=True,
    config_model=TTSConfig,
    tags=["audio", "speech"],
)
async def run_tts_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Synthesize speech from text using the internal TTS service.

    Config:
      - input: str (templated) - Text to synthesize; defaults to last.text
      - model: str = "kokoro" - TTS model (kokoro, tts-1, etc.)
      - voice: str = "af_heart" - Voice to use
      - response_format: Literal["mp3", "wav", "opus", "flac", "aac", "pcm"] = "mp3"
      - speed: float = 1.0 - Speech speed multiplier
      - provider: str (optional) - Provider hint
    Output:
      - {"audio_uri": "file://...", "format": str, "model": str,
         "voice": str, "size_bytes": int}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_tts_adapter as _legacy
    return await _legacy(config, context)
