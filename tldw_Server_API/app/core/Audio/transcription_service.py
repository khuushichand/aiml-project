from functools import lru_cache
from typing import Optional


@lru_cache(maxsize=1)
def _valid_whisper_model_sizes() -> set[str]:
    """Cached lookup of known faster-whisper model sizes."""
    try:
        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib import (  # type: ignore
            WhisperModel as _WhisperModel,
        )

        return set(getattr(_WhisperModel, "valid_model_sizes", []))
    except Exception:
        # If the import fails (e.g., dependencies missing), fall back to empty set
        return set()


def _map_openai_audio_model_to_whisper(model: Optional[str]) -> str:
    """Map OpenAI-style audio model ids to a faster-whisper model name.

    - Known internal faster-whisper model ids (e.g., 'large-v3', 'distil-large-v3')
      and Hugging Face ids are passed through unchanged.
    - OpenAI aliases such as 'whisper-1' map to a configurable default
      (currently 'large-v3' to preserve prior behavior).
    - All unknown values fall back to 'large-v3'.
    """
    default_model = "large-v3"
    if not model:
        return default_model

    raw = str(model).strip()
    m = raw.lower()

    valid_sizes = _valid_whisper_model_sizes()
    valid_sizes_lower = {s.lower() for s in valid_sizes}
    if not valid_sizes_lower:
        valid_sizes_lower = {
            "tiny",
            "tiny.en",
            "base",
            "base.en",
            "small",
            "small.en",
            "medium",
            "medium.en",
            "large-v1",
            "large-v2",
            "large-v3",
            "large",
            "distil-large-v3",
            "distil-medium.en",
            "distil-small.en",
        }

    # Pass through known internal sizes and HF ids
    if raw in valid_sizes or m in valid_sizes or "/" in raw:
        return raw

    # OpenAI-compatible aliases
    if m == "whisper-1":
        return default_model
    if m in {"whisper-large-v3-turbo", "whisper-large-v3-turbo-ct2", "large-v3-turbo"}:
        return "deepdml/faster-whisper-large-v3-turbo-ct2"
    if m.startswith("whisper-") and m.endswith("-ct2"):
        ct2_tail = m[len("whisper-"):-4]
        if ct2_tail in valid_sizes_lower:
            return ct2_tail

    # Fallback to default
    return default_model
