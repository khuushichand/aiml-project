"""Audio processing adapters.

This module includes adapters for audio operations:
- tts: Text-to-speech synthesis
- stt_transcribe: Speech-to-text transcription
- audio_normalize: Audio normalization
- audio_concat: Audio concatenation
- audio_trim: Audio trimming
- audio_convert: Audio format conversion
- audio_extract: Audio extraction from video
- audio_mix: Audio mixing
- audio_diarize: Speaker diarization
"""

from tldw_Server_API.app.core.Workflows.adapters.audio.diarize import (
    run_audio_diarize_adapter,
)
from tldw_Server_API.app.core.Workflows.adapters.audio.processing import (
    run_audio_concat_adapter,
    run_audio_convert_adapter,
    run_audio_extract_adapter,
    run_audio_mix_adapter,
    run_audio_normalize_adapter,
    run_audio_trim_adapter,
)
from tldw_Server_API.app.core.Workflows.adapters.audio.stt import (
    run_stt_transcribe_adapter,
)
from tldw_Server_API.app.core.Workflows.adapters.audio.tts import (
    run_tts_adapter,
)

__all__ = [
    "run_tts_adapter",
    "run_stt_transcribe_adapter",
    "run_audio_normalize_adapter",
    "run_audio_concat_adapter",
    "run_audio_trim_adapter",
    "run_audio_convert_adapter",
    "run_audio_extract_adapter",
    "run_audio_mix_adapter",
    "run_audio_diarize_adapter",
]
