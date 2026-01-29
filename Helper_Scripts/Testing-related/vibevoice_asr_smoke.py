#!/usr/bin/env python3
"""
Simple VibeVoice-ASR smoke test against the local API.

Usage (single-user):
  python Helper_Scripts/Testing-related/vibevoice_asr_smoke.py --api-key "$SINGLE_USER_API_KEY"

Usage (multi-user JWT):
  python Helper_Scripts/Testing-related/vibevoice_asr_smoke.py --bearer "$TOKEN"
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
import wave
from pathlib import Path
from typing import Dict, Tuple

import httpx


def _resolve_headers(args: argparse.Namespace) -> Dict[str, str]:
    """
    Resolve authentication headers from CLI arguments or environment variables.

    Priority: --bearer > --api-key > TLDW_BEARER_TOKEN/TLDW_TOKEN >
    SINGLE_USER_API_KEY/TLDW_API_KEY. Returns an empty dict if no credentials
    are found.
    """
    headers: Dict[str, str] = {}
    if args.bearer:
        headers["Authorization"] = f"Bearer {args.bearer}"
    elif args.api_key:
        headers["X-API-KEY"] = args.api_key
    else:
        env_bearer = os.getenv("TLDW_BEARER_TOKEN") or os.getenv("TLDW_TOKEN")
        env_key = os.getenv("SINGLE_USER_API_KEY") or os.getenv("TLDW_API_KEY")
        if env_bearer:
            headers["Authorization"] = f"Bearer {env_bearer}"
        elif env_key:
            headers["X-API-KEY"] = env_key
    return headers


def _generate_test_wav(path: Path, *, duration_s: float, sample_rate: int) -> None:
    """
    Generate a short sine-wave WAV using only stdlib modules.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    total_frames = max(int(duration_s * sample_rate), 1)
    freq_hz = 440.0
    amplitude = 0.2
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)  # 16-bit PCM
        wav.setframerate(sample_rate)
        frames = bytearray()
        for i in range(total_frames):
            t = float(i) / float(sample_rate)
            value = amplitude * math.sin(2.0 * math.pi * freq_hz * t)
            sample = max(min(int(value * 32767.0), 32767), -32768)
            frames.extend(sample.to_bytes(2, byteorder="little", signed=True))
        wav.writeframes(bytes(frames))


def _resolve_audio_path(args: argparse.Namespace) -> Tuple[Path, bool]:
    """
    Return (audio_path, is_temp).
    """
    if args.audio_path:
        audio_path = Path(args.audio_path).expanduser().resolve()
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio path not found: {audio_path}")
        return audio_path, False

    with tempfile.NamedTemporaryFile(prefix="vibevoice_asr_smoke_", suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    _generate_test_wav(tmp_path, duration_s=args.duration, sample_rate=args.sample_rate)
    return tmp_path, True


def main() -> int:
    parser = argparse.ArgumentParser(description="VibeVoice-ASR smoke test")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API base URL")
    parser.add_argument("--api-key", help="Single-user X-API-KEY")
    parser.add_argument("--bearer", help="Bearer token for multi-user auth")
    parser.add_argument("--model", default="vibevoice-asr", help="Transcription model id")
    parser.add_argument("--language", default="en", help="Language hint (ISO code)")
    parser.add_argument(
        "--hotwords",
        default='["VibeVoice","tldw_server"]',
        help="Hotwords as CSV or JSON list string",
    )
    parser.add_argument("--response-format", default="json", help="Response format")
    parser.add_argument("--audio-path", type=str, default=None, help="Path to input audio file")
    parser.add_argument("--duration", type=float, default=1.0, help="Generated WAV duration in seconds")
    parser.add_argument("--sample-rate", type=int, default=16000, help="Generated WAV sample rate")
    parser.add_argument("--timeout", type=float, default=600.0, help="HTTP timeout (seconds)")
    parser.add_argument("--verbose", action="store_true", help="Print full JSON response")
    args = parser.parse_args()

    headers = _resolve_headers(args)
    if not headers:
        print(
            "Warning: no auth header set (use --api-key/--bearer or set SINGLE_USER_API_KEY/TLDW_BEARER_TOKEN).",
            file=sys.stderr,
        )

    try:
        audio_path, is_temp = _resolve_audio_path(args)
    except Exception as exc:
        print(f"Error preparing audio: {exc}", file=sys.stderr)
        return 2

    url = args.base_url.rstrip("/") + "/api/v1/audio/transcriptions"
    data = {
        "model": args.model,
        "language": args.language,
        "response_format": args.response_format,
        "hotwords": args.hotwords,
    }

    try:
        with audio_path.open("rb") as fh:
            files = {"file": (audio_path.name, fh, "audio/wav")}
            with httpx.Client(timeout=args.timeout) as client:
                resp = client.post(url, headers=headers, data=data, files=files)
        if resp.status_code != 200:
            print(f"HTTP {resp.status_code}: {resp.text}", file=sys.stderr)
            return 3
        body = resp.json()
    except Exception as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        return 4
    finally:
        if is_temp:
            try:
                audio_path.unlink(missing_ok=True)
            except OSError as exc:
                print(f"Warning: failed to clean up temp file: {exc}", file=sys.stderr)

    text = str(body.get("text") or "").strip()
    segments = body.get("segments") or []
    language = body.get("language") or args.language
    preview = text[:120] + ("..." if len(text) > 120 else "")

    print(
        "OK: VibeVoice-ASR transcription succeeded | "
        f"language={language} segments={len(segments)} text_len={len(text)}"
    )
    if preview:
        print(f"Preview: {preview}")

    if args.verbose:
        print(json.dumps(body, indent=2, ensure_ascii=True))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
