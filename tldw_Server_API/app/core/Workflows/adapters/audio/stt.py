"""Speech-to-text adapter.

This module includes the STT adapter for audio transcription.
"""

from __future__ import annotations

from typing import Any, Dict

from tldw_Server_API.app.core.Workflows.adapters._registry import registry
from tldw_Server_API.app.core.Workflows.adapters.audio._config import STTConfig


@registry.register(
    "stt_transcribe",
    category="audio",
    description="Speech-to-text transcription",
    parallelizable=False,
    config_model=STTConfig,
    tags=["audio", "speech"],
)
async def run_stt_transcribe_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Transcribe audio file locally with optional diarization.

    Config:
      - file_uri: str - file:// path to audio/video file (required)
      - model: str = "large-v3" - Whisper model name
      - language: str (optional) - Source language code
      - hotwords: list[str] | str (optional) - Hotwords for improved recognition
      - diarize: bool = False - Enable speaker diarization
      - word_timestamps: bool = False - Include word-level timestamps
    Output:
      - {"text": str, "segments": [...], "language": str}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_stt_transcribe_adapter as _legacy
    return await _legacy(config, context)
