#!/usr/bin/env python3
"""
Generate STT golden JSON files from adapter output.

Example:
  export PYTHONPATH=.
  BASE=/srv/tldw_stt_golden

  python Helper_Scripts/Audio/generate_stt_golden.py \
    --provider faster-whisper \
    --audio "$BASE/audio/whisper/en/clip1.wav" \
    --model large-v3 \
    --language en \
    --base-dir "$BASE" \
    --output "$BASE/whisper_clip1.golden.json" \
    --max-ter 0.12 \
    --min-segments 2
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Tuple

if TYPE_CHECKING:
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.stt_provider_adapter import (
        SttProviderAdapter,
    )


SUPPORTED_PROVIDERS = ("faster-whisper", "parakeet", "canary")


def _normalize_provider(provider: str) -> str:
    """Normalize provider names for CLI handling."""
    lowered = provider.strip().lower()
    if lowered in {"faster_whisper", "whisper"}:
        return "faster-whisper"
    return lowered


def _resolve_base_dir(base_dir: Path | None) -> Path:
    """Resolve and validate the golden base directory."""
    base_value = base_dir
    if base_value is None:
        env_value = os.getenv("TLDW_STT_GOLDEN_AUDIO_DIR")
        if env_value:
            base_value = Path(env_value)
    if base_value is None:
        raise ValueError(
            "Base directory is required. Pass --base-dir or set TLDW_STT_GOLDEN_AUDIO_DIR."
        )

    resolved = base_value.expanduser().resolve()
    if not resolved.is_dir():
        raise ValueError(f"Base directory does not exist or is not a directory: {resolved}")
    return resolved


def _resolve_audio_path(audio_path: Path | str, base_dir: Path) -> Tuple[Path, str]:
    """Resolve an audio path and return (absolute_path, relative_posix_path)."""
    audio = Path(audio_path).expanduser()
    if not audio.is_absolute():
        audio = base_dir / audio
    audio = audio.resolve()
    if not audio.is_file():
        raise FileNotFoundError(f"Audio file not found: {audio}")
    try:
        rel_audio = audio.relative_to(base_dir)
    except ValueError as exc:
        raise ValueError(f"Audio file must live under base dir: {base_dir}") from exc
    return audio, rel_audio.as_posix()


def _resolve_output_path(output_path: Path | str, base_dir: Path) -> Path:
    """Resolve output path, treating relative paths as base-dir relative."""
    output = Path(output_path).expanduser()
    if not output.is_absolute():
        output = base_dir / output
    return output.resolve()


def _require_nemo(provider_label: str) -> None:
    """Ensure Nemo is importable and available for the given provider."""
    try:
        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Nemo import (  # type: ignore
            is_nemo_available,
        )
    except Exception as exc:
        raise RuntimeError(
            f"Nemo toolkit not importable; cannot run {provider_label} adapter."
        ) from exc
    if not is_nemo_available():
        raise RuntimeError(f"Nemo ASR not available; cannot run {provider_label} adapter.")


def _load_adapter(provider: str) -> "SttProviderAdapter":
    """Instantiate the adapter for the requested provider."""
    normalized = _normalize_provider(provider)
    if normalized == "faster-whisper":
        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.stt_provider_adapter import (  # type: ignore
            FasterWhisperAdapter,
        )

        return FasterWhisperAdapter()
    if normalized == "parakeet":
        _require_nemo("Parakeet")
        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.stt_provider_adapter import (  # type: ignore
            ParakeetAdapter,
        )

        return ParakeetAdapter()
    if normalized == "canary":
        _require_nemo("Canary")
        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.stt_provider_adapter import (  # type: ignore
            CanaryAdapter,
        )

        return CanaryAdapter()

    supported = ", ".join(SUPPORTED_PROVIDERS)
    raise ValueError(f"Unknown provider '{provider}'. Expected one of: {supported}")


def _generate_golden_payload(
    adapter: "SttProviderAdapter",
    audio_path: Path,
    rel_audio_path: str,
    model: str,
    language: str | None,
    max_token_error_rate: float | None,
    min_segments: int | None,
) -> Dict[str, Any]:
    """Run the adapter and build the golden JSON payload."""
    artifact = adapter.transcribe_batch(
        str(audio_path),
        model=model,
        language=language,
        task="transcribe",
        word_timestamps=False,
    )
    expected_text = artifact.get("text") or ""
    if not expected_text:
        print(
            f"WARNING: adapter returned empty transcript for {audio_path}",
            file=sys.stderr,
        )

    payload: Dict[str, Any] = {
        "audio": rel_audio_path,
        "model": model,
        "expected_text": expected_text,
    }
    if language:
        payload["language"] = language
    if max_token_error_rate is not None:
        payload["max_token_error_rate"] = max_token_error_rate
    if min_segments is not None:
        payload["min_segments"] = min_segments
    return payload


def _write_golden_json(output_path: Path, payload: Dict[str, Any]) -> None:
    """Write the golden JSON payload to disk."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Generate STT golden JSON files from adapter output.",
    )
    parser.add_argument(
        "--provider",
        required=True,
        help="STT provider: faster-whisper, parakeet, or canary.",
    )
    parser.add_argument(
        "--audio",
        required=True,
        type=Path,
        help="Path to the audio file (absolute or relative to --base-dir).",
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Adapter model identifier (e.g. large-v3, parakeet-standard).",
    )
    parser.add_argument(
        "--language",
        help="Optional language hint passed to the adapter (e.g. en).",
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        help="Base directory for golden audio and JSONs (default: $TLDW_STT_GOLDEN_AUDIO_DIR).",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Golden JSON output path (absolute or relative to --base-dir).",
    )
    parser.add_argument(
        "--max-ter",
        type=float,
        dest="max_token_error_rate",
        help="Optional max token error rate threshold to store in the JSON.",
    )
    parser.add_argument(
        "--min-segments",
        type=int,
        help="Optional minimum segments threshold to store in the JSON.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    args = parse_args(argv)

    try:
        base_dir = _resolve_base_dir(args.base_dir)
        audio_path, rel_audio = _resolve_audio_path(args.audio, base_dir)
        output_path = _resolve_output_path(args.output, base_dir)
        adapter = _load_adapter(args.provider)
        payload = _generate_golden_payload(
            adapter,
            audio_path,
            rel_audio,
            args.model,
            args.language,
            args.max_token_error_rate,
            args.min_segments,
        )
        _write_golden_json(output_path, payload)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote golden file to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
