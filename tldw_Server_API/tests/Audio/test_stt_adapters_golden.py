"""
Golden real-audio tests for STT adapters.

These tests are intentionally opt-in and are designed to run on a GPU-enabled
machine that has the heavy STT dependencies installed. They:

  - Read golden configuration JSON files from a directory specified by
    TLDW_STT_GOLDEN_AUDIO_DIR.
  - Run the real adapters (faster-whisper, Parakeet, Canary) on real audio.
  - Compare the produced transcript against a known-good reference using a
    simple token-level error rate.

Golden JSON schema (example):

{
  "audio": "whisper/en/clip1.wav",            # Path relative to TLDW_STT_GOLDEN_AUDIO_DIR
  "model": "large-v3",                        # Adapter model name
  "language": "en",                           # Optional language hint
  "expected_text": "Reference transcript...", # Reference transcript
  "max_token_error_rate": 0.15,               # Allowed token error rate
  "min_segments": 1                           # Minimum expected segments
}

To run:

  export TLDW_STT_GOLDEN_ENABLE=1
  export TLDW_STT_GOLDEN_AUDIO_DIR=/path/to/golden/audio
  pytest -m "stt_golden" -v
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List

import pytest
from tldw_Server_API.app.core.Utils.Utils import logging


TOLERANCE_DEFAULT = 0.20  # Conservative default token error rate


def _bool_env(name: str) -> bool:
    raw = os.getenv(name, "")
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def _require_golden_env() -> Path:
    if not _bool_env("TLDW_STT_GOLDEN_ENABLE"):
        pytest.skip("TLDW_STT_GOLDEN_ENABLE not set; skipping STT golden tests")
    base = os.getenv("TLDW_STT_GOLDEN_AUDIO_DIR")
    if not base:
        pytest.skip("TLDW_STT_GOLDEN_AUDIO_DIR not set; skipping STT golden tests")
    base_path = Path(base)
    if not base_path.is_dir():
        pytest.skip(f"TLDW_STT_GOLDEN_AUDIO_DIR={base_path} does not exist or is not a directory")
    return base_path


def _normalize_text(text: str) -> List[str]:
    import re

    if not text:
        return []
    lowered = text.strip().lower()
    # Keep letters, digits, and spaces; drop punctuation.
    cleaned = re.sub(r"[^a-z0-9\s]+", " ", lowered)
    tokens = [t for t in cleaned.split() if t]
    return tokens


def _levenshtein(a: List[str], b: List[str]) -> int:
    """Compute Levenshtein edit distance between two token sequences."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    prev = list(range(len(b) + 1))
    curr = [0] * (len(b) + 1)

    for i, ca in enumerate(a, start=1):
        curr[0] = i
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            curr[j] = min(
                curr[j - 1] + 1,      # insertion
                prev[j] + 1,          # deletion
                prev[j - 1] + cost,   # substitution
            )
        prev, curr = curr, prev

    return prev[-1]


def _token_error_rate(ref: str, hyp: str) -> float:
    ref_tokens = _normalize_text(ref)
    hyp_tokens = _normalize_text(hyp)
    if not ref_tokens:
        return 0.0 if not hyp_tokens else 1.0
    dist = _levenshtein(ref_tokens, hyp_tokens)
    return float(dist) / float(len(ref_tokens))


@dataclass
class GoldenCase:
    audio_path: Path
    model: str
    language: str | None
    expected_text: str
    max_token_error_rate: float
    min_segments: int


def _load_golden_cases(base: Path, pattern: str) -> List[GoldenCase]:
    cases: List[GoldenCase] = []
    for golden_path in base.rglob(pattern):
        try:
            cfg = json.loads(golden_path.read_text(encoding="utf-8"))
        except Exception as e:
            logging.warning(f"Skipping malformed golden case file {golden_path}: {e}")
            continue
        rel_audio = cfg.get("audio")
        if not rel_audio:
            continue
        audio_path = base / rel_audio
        if not audio_path.is_file():
            continue
        model = cfg.get("model") or ""
        expected_text = cfg.get("expected_text") or ""
        if not model or not expected_text:
            continue
        case = GoldenCase(
            audio_path=audio_path,
            model=model,
            language=cfg.get("language"),
            expected_text=expected_text,
            max_token_error_rate=float(cfg.get("max_token_error_rate") or TOLERANCE_DEFAULT),
            min_segments=int(cfg.get("min_segments") or 1),
        )
        cases.append(case)
    return cases


@pytest.mark.stt_golden
def test_faster_whisper_golden_clips():
    """
    Validate faster-whisper adapter on golden audio clips.

    Looks for JSON files matching `whisper_*.golden.json` under
    TLDW_STT_GOLDEN_AUDIO_DIR and runs FasterWhisperAdapter on the referenced
    audio files.
    """
    base = _require_golden_env()
    cases = _load_golden_cases(base, "whisper_*.golden.json")
    if not cases:
        pytest.skip("No Whisper golden cases found under TLDW_STT_GOLDEN_AUDIO_DIR")

    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.stt_provider_adapter import (  # type: ignore
        FasterWhisperAdapter,
    )

    adapter = FasterWhisperAdapter()
    for case in cases:
        artifact = adapter.transcribe_batch(
            str(case.audio_path),
            model=case.model,
            language=case.language,
            task="transcribe",
            word_timestamps=False,
        )
        hyp_text = artifact.get("text") or ""
        ter = _token_error_rate(case.expected_text, hyp_text)
        assert ter <= case.max_token_error_rate, (
            f"Whisper golden mismatch for {case.audio_path}: "
            f"TER={ter:.3f} > max={case.max_token_error_rate:.3f}"
        )
        segments = artifact.get("segments") or []
        assert isinstance(segments, list)
        assert len(segments) >= case.min_segments


@pytest.mark.stt_golden
def test_parakeet_golden_clips():
    """
    Validate Parakeet adapter on golden audio clips when Nemo is available.
    """
    base = _require_golden_env()
    cases = _load_golden_cases(base, "parakeet_*.golden.json")
    if not cases:
        pytest.skip("No Parakeet golden cases found under TLDW_STT_GOLDEN_AUDIO_DIR")

    # Skip gracefully when Nemo toolkit is not available.
    try:
        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Nemo import (  # type: ignore
            is_nemo_available,
        )
    except Exception:
        pytest.skip("Nemo toolkit not importable; skipping Parakeet golden tests")

    if not is_nemo_available():
        pytest.skip("Nemo ASR not available; skipping Parakeet golden tests")

    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.stt_provider_adapter import (  # type: ignore
        ParakeetAdapter,
    )

    adapter = ParakeetAdapter()
    for case in cases:
        artifact = adapter.transcribe_batch(
            str(case.audio_path),
            model=case.model,
            language=case.language,
            task="transcribe",
        )
        hyp_text = artifact.get("text") or ""
        ter = _token_error_rate(case.expected_text, hyp_text)
        assert ter <= case.max_token_error_rate, (
            f"Parakeet golden mismatch for {case.audio_path}: "
            f"TER={ter:.3f} > max={case.max_token_error_rate:.3f}"
        )
        segments = artifact.get("segments") or []
        assert isinstance(segments, list)
        assert len(segments) >= case.min_segments


@pytest.mark.stt_golden
def test_canary_golden_clips():
    """
    Validate Canary adapter on golden audio clips when Nemo is available.
    """
    base = _require_golden_env()
    cases = _load_golden_cases(base, "canary_*.golden.json")
    if not cases:
        pytest.skip("No Canary golden cases found under TLDW_STT_GOLDEN_AUDIO_DIR")

    # Skip gracefully when Nemo toolkit is not available.
    try:
        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Nemo import (  # type: ignore
            is_nemo_available,
        )
    except Exception:
        pytest.skip("Nemo toolkit not importable; skipping Canary golden tests")

    if not is_nemo_available():
        pytest.skip("Nemo ASR not available; skipping Canary golden tests")

    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.stt_provider_adapter import (  # type: ignore
        CanaryAdapter,
    )

    adapter = CanaryAdapter()
    for case in cases:
        artifact = adapter.transcribe_batch(
            str(case.audio_path),
            model=case.model,
            language=case.language,
            task="transcribe",
        )
        hyp_text = artifact.get("text") or ""
        ter = _token_error_rate(case.expected_text, hyp_text)
        assert ter <= case.max_token_error_rate, (
            f"Canary golden mismatch for {case.audio_path}: "
            f"TER={ter:.3f} > max={case.max_token_error_rate:.3f}"
        )
        segments = artifact.get("segments") or []
        assert isinstance(segments, list)
        assert len(segments) >= case.min_segments
