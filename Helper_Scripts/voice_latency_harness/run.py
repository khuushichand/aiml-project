"""
voice_latency_harness/run.py

A lightweight harness to measure end-to-end voice latency using existing APIs/metrics.

- Short mode (default): uses mock providers and a short synthetic clip to avoid downloads.
- Full mode: optional, requires real providers and a running server at BASE_URL.

Outputs a JSON summary with p50/p90 for:
  - stt_final_latency_seconds
  - tts_ttfb_seconds
  - voice_to_voice_seconds
  - audio_chat_latency_seconds (when available)

Usage:
  python Helper_Scripts/voice_latency_harness/run.py --out out.json --short
  python Helper_Scripts/voice_latency_harness/run.py --out out.json --base-url http://127.0.0.1:8000 --api-key $KEY
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import traceback
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence

import numpy as np
import requests


DEFAULT_BASE_URL = "http://127.0.0.1:8000"


def _make_silence(duration_sec: float = 0.2, sr: int = 16000) -> bytes:
    """Generate a silent WAV clip for quick end-to-end harness checks."""
    buf = io.BytesIO()
    data = np.zeros(int(sr * duration_sec), dtype=np.float32)
    try:
        import soundfile as sf
    except ImportError as exc:  # pragma: no cover - optional dep guard
        raise RuntimeError("The 'soundfile' package is required for the harness; `pip install soundfile`.") from exc
    sf.write(buf, data, sr, format="WAV")
    return buf.getvalue()


def _b64_audio(audio_bytes: bytes) -> str:
    """Base64-encode audio bytes for API submission."""
    return base64.b64encode(audio_bytes).decode("ascii")


@dataclass
class HarnessResult:
    """Aggregated latency percentiles plus raw metrics payload from the server."""

    stt_final_latency_seconds: Dict[str, float]
    tts_ttfb_seconds: Dict[str, float]
    voice_to_voice_seconds: Dict[str, float]
    audio_chat_latency_seconds: Dict[str, float]
    raw_metrics: Dict[str, Any]

    def to_json(self) -> str:
        """Serialize the harness result to formatted JSON."""
        return json.dumps(
            {
                "stt_final_latency_seconds": self.stt_final_latency_seconds,
                "tts_ttfb_seconds": self.tts_ttfb_seconds,
                "voice_to_voice_seconds": self.voice_to_voice_seconds,
                "audio_chat_latency_seconds": self.audio_chat_latency_seconds,
                "raw_metrics": self.raw_metrics,
            },
            indent=2,
        )


def _fetch_metrics(base_url: str, api_key: Optional[str]) -> Dict[str, Any]:
    """Fetch metrics from /metrics, preferring JSON but falling back to Prom text."""
    headers = {}
    if api_key:
        headers["X-API-KEY"] = api_key
    r = requests.get(f"{base_url}/metrics", headers=headers, timeout=5)
    r.raise_for_status()
    # Prefer JSON metrics endpoint if exposed; fall back to Prom text.
    try:
        return r.json()
    except ValueError:
        text = r.text
        parsed: Dict[str, Any] = {}
        for line in text.splitlines():
            if line.startswith("#") or not line.strip():
                continue
            if " " in line:
                name = line.split(" ", 1)[0]
                parsed.setdefault(name, 0)
                parsed[name] += 1
        return parsed


def _percentiles(values: Sequence[float], pcts: Sequence[int] = (50, 90)) -> Dict[str, float]:
    """Compute percentile map for a numeric sequence."""
    if len(values) == 0:
        return {}
    arr = np.array(values, dtype=float)
    return {f"p{p}": float(np.percentile(arr, p)) for p in pcts}


def _extract_histogram_percentiles(metrics: Dict[str, Any], name: str) -> Dict[str, float]:
    """Extract histogram-style metrics into percentile summaries."""
    series = metrics.get(name)
    if not series:
        return {}
    if isinstance(series, dict) and "values" in series:
        values = [v for v in series.get("values", []) if isinstance(v, (int, float))]
    elif isinstance(series, list):
        values = series
    else:
        values = []
    return _percentiles(values)


def run_short_mode(base_url: str, api_key: Optional[str]) -> HarnessResult:
    """Scrape /metrics and derive latency percentiles without issuing new requests."""
    metrics = _fetch_metrics(base_url, api_key)
    return HarnessResult(
        stt_final_latency_seconds=_extract_histogram_percentiles(metrics, "stt_final_latency_seconds"),
        tts_ttfb_seconds=_extract_histogram_percentiles(metrics, "tts_ttfb_seconds"),
        voice_to_voice_seconds=_extract_histogram_percentiles(metrics, "voice_to_voice_seconds"),
        audio_chat_latency_seconds=_extract_histogram_percentiles(metrics, "audio_chat_latency_seconds"),
        raw_metrics=metrics,
    )


def run_full_turn(base_url: str, api_key: Optional[str]) -> HarnessResult:
    """Post a short silent clip, then scrape metrics to derive latency percentiles."""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-KEY"] = api_key

    audio_b64 = _b64_audio(_make_silence(0.2))
    payload = {
        "input_audio": audio_b64,
        "input_audio_format": "wav",
        "llm_config": {"model": "gpt-4o-mini", "api_provider": "openai"},
        # Default harness target; override via server/env config as needed.
    }
    start = time.time()
    r = requests.post(f"{base_url}/api/v1/audio/chat", headers=headers, json=payload, timeout=30)
    latency = time.time() - start
    r.raise_for_status()

    metrics = _fetch_metrics(base_url, api_key)
    audio_chat_p = _extract_histogram_percentiles(metrics, "audio_chat_latency_seconds")
    if not audio_chat_p:
        audio_chat_p = {"p50": latency, "p90": latency}
    return HarnessResult(
        stt_final_latency_seconds=_extract_histogram_percentiles(metrics, "stt_final_latency_seconds"),
        tts_ttfb_seconds=_extract_histogram_percentiles(metrics, "tts_ttfb_seconds"),
        voice_to_voice_seconds=_extract_histogram_percentiles(metrics, "voice_to_voice_seconds"),
        audio_chat_latency_seconds=audio_chat_p,
        raw_metrics=metrics,
    )


def main():
    """CLI entrypoint for the voice latency harness."""
    parser = argparse.ArgumentParser(description="Voice latency harness")
    parser.add_argument("--out", type=str, default="out.json", help="Path to write JSON results")
    parser.add_argument("--base-url", type=str, default=DEFAULT_BASE_URL, help="Server base URL")
    parser.add_argument("--api-key", type=str, default=None, help="API key (if required)")
    parser.add_argument("--short", action="store_true", help="Short mode: no calls, just scrape metrics")
    args = parser.parse_args()

    try:
        if args.short:
            result = run_short_mode(args.base_url, args.api_key)
        else:
            result = run_full_turn(args.base_url, args.api_key)
    except Exception as exc:
        sys.stderr.write(f"[harness] failed: {exc}\n")
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(result.to_json())
    print(f"[harness] wrote results to {args.out}")


if __name__ == "__main__":
    main()
