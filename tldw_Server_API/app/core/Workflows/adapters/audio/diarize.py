"""Speaker diarization adapter.

This module includes the diarization adapter for speaker identification.
"""

from __future__ import annotations

from typing import Any, Dict

from tldw_Server_API.app.core.Workflows.adapters._registry import registry
from tldw_Server_API.app.core.Workflows.adapters.audio._config import AudioDiarizeConfig


@registry.register(
    "audio_diarize",
    category="audio",
    description="Speaker diarization",
    parallelizable=False,
    config_model=AudioDiarizeConfig,
    tags=["audio"],
)
async def run_audio_diarize_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Perform speaker diarization on an audio file.

    Config:
      - file_uri: str - file:// path to audio file (required)
      - min_speakers: int (optional) - Minimum number of speakers
      - max_speakers: int (optional) - Maximum number of speakers
      - model: str (optional) - Diarization model to use
    Output:
      - {"speakers": [{"id": str, "segments": [...]}], "num_speakers": int}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_audio_diarize_adapter as _legacy
    return await _legacy(config, context)
