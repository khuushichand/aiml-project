#!/usr/bin/env python3
"""
Simple Echo-TTS smoke test against the local API.

Usage (single-user):
  python Helper_Scripts/Testing-related/echo_tts_smoke.py --api-key "$SINGLE_USER_API_KEY"

Usage (multi-user JWT):
  python Helper_Scripts/Testing-related/echo_tts_smoke.py --bearer "$TOKEN"
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
import time
import wave
from pathlib import Path
from typing import Dict


def _default_voice_path() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "Helper_Scripts" / "Audio" / "Sample_Voices" / "Sample_Voice_1.wav"


def _resolve_headers(args: argparse.Namespace) -> Dict[str, str]:
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


def _load_voice_reference(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"voice_reference not found: {path}")
    voice_bytes = path.read_bytes()
    return base64.b64encode(voice_bytes).decode("utf-8")


def _write_audio(output_path: Path, stream: bool, response, start_time: float) -> Dict[str, float]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    chunk_sizes = []
    first_chunk_ms = None
    with output_path.open("wb") as fh:
        if stream:
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                if first_chunk_ms is None:
                    first_chunk_ms = (time.monotonic() - start_time) * 1000.0
                fh.write(chunk)
                total += len(chunk)
                chunk_sizes.append(len(chunk))
        else:
            data = response.read()
            fh.write(data)
            total = len(data)
            if total:
                chunk_sizes.append(total)
                first_chunk_ms = (time.monotonic() - start_time) * 1000.0
    stats: Dict[str, float] = {"total": float(total), "chunks": float(len(chunk_sizes))}
    if chunk_sizes:
        stats["min"] = float(min(chunk_sizes))
        stats["max"] = float(max(chunk_sizes))
        stats["avg"] = float(total) / float(len(chunk_sizes))
    if first_chunk_ms is not None:
        stats["first_chunk_ms"] = float(first_chunk_ms)
    stats["total_ms"] = float((time.monotonic() - start_time) * 1000.0)
    return stats


def _describe_wav(path: Path) -> str:
    try:
        with wave.open(str(path), "rb") as wav:
            frames = wav.getnframes()
            rate = wav.getframerate()
            channels = wav.getnchannels()
            duration = frames / float(rate) if rate else 0.0
        return f"wav: {channels} ch @ {rate} Hz, {duration:.2f}s"
    except Exception as exc:
        return f"wav: unreadable ({exc})"


def main() -> int:
    parser = argparse.ArgumentParser(description="Echo-TTS smoke test")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API base URL")
    parser.add_argument("--api-key", help="Single-user X-API-KEY")
    parser.add_argument("--bearer", help="Bearer token for multi-user auth")
    parser.add_argument("--model", default="echo-tts", help="TTS model id")
    parser.add_argument("--voice", default="clone", help="Voice name (Echo uses voice_reference)")
    parser.add_argument("--text", default="Echo TTS smoke test from tldw_server.", help="Text to synthesize")
    parser.add_argument("--response-format", default="wav", choices=["mp3", "opus", "aac", "flac", "wav", "pcm"])
    parser.add_argument("--stream", action="store_true", help="Enable streaming response")
    parser.add_argument("--timeout", type=int, default=120, help="HTTP timeout (seconds)")
    parser.add_argument(
        "--voice-path",
        type=Path,
        default=_default_voice_path(),
        help="Path to voice reference audio",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output audio file path (defaults to /tmp/echo_tts_smoke.<format>)",
    )
    args = parser.parse_args()

    if args.output is None:
        args.output = Path(f"/tmp/echo_tts_smoke.{args.response_format}")

    headers = _resolve_headers(args)
    if not headers:
        print("Warning: no auth header set (set --api-key or --bearer, or env SINGLE_USER_API_KEY/TLDW_BEARER_TOKEN).")

    try:
        voice_b64 = _load_voice_reference(args.voice_path)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    payload = {
        "model": args.model,
        "input": args.text,
        "voice": args.voice,
        "response_format": args.response_format,
        "stream": bool(args.stream),
        "voice_reference": voice_b64,
    }
    url = args.base_url.rstrip("/") + "/api/v1/audio/speech"
    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    for key, value in headers.items():
        req.add_header(key, value)

    try:
        request_start = time.monotonic()
        with urllib.request.urlopen(req, timeout=args.timeout) as resp:
            headers_ms = (time.monotonic() - request_start) * 1000.0
            stats = _write_audio(args.output, args.stream, resp, request_start)
            total = int(stats.get("total", 0))
            if total <= 0:
                print("Error: received empty audio payload", file=sys.stderr)
                return 3
            extra = ""
            if args.response_format == "wav":
                extra = f" ({_describe_wav(args.output)})"
            msg = f"OK: wrote {total} bytes to {args.output}{extra}"
            first_chunk_ms = stats.get("first_chunk_ms")
            total_ms = stats.get("total_ms")
            msg += f" | timing headers={int(headers_ms)}ms"
            if first_chunk_ms is not None:
                msg += f" first_chunk={int(first_chunk_ms)}ms"
            if total_ms is not None:
                msg += f" total={int(total_ms)}ms"
            if args.stream:
                chunks = int(stats.get("chunks", 0))
                if chunks:
                    avg = int(stats.get("avg", 0))
                    min_size = int(stats.get("min", 0))
                    max_size = int(stats.get("max", 0))
                    msg += f" | stream chunks={chunks} avg={avg} min={min_size} max={max_size}"
            print(msg)
            return 0
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code}: {body}", file=sys.stderr)
        return 4
    except Exception as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        return 5


if __name__ == "__main__":
    raise SystemExit(main())
