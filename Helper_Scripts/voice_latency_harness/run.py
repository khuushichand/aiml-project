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
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Iterable, Sequence

import numpy as np
import requests
from loguru import logger


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
HISTOGRAM_METRIC_NAMES = {
    "stt_final_latency_seconds",
    "tts_ttfb_seconds",
    "voice_to_voice_seconds",
    "audio_chat_latency_seconds",
}

_SOUNDFILE_MISSING_MSG = (
    "The 'soundfile' package is required for the harness; `pip install soundfile`."
)

_PROMETHEUS_CLIENT_MISSING_MSG = (
    "Prometheus text parsing requires prometheus_client; install to enable fallback."
)


def _make_silence(duration_sec: float = 0.2, sr: int = 16000) -> bytes:
    """Generate a silent WAV clip for quick end-to-end harness checks."""
    buf = io.BytesIO()
    data = np.zeros(int(sr * duration_sec), dtype=np.float32)
    try:
        import soundfile as sf
    except ImportError as exc:  # pragma: no cover - optional dep guard
        raise RuntimeError(_SOUNDFILE_MISSING_MSG) from exc
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
    """Fetch metrics from /metrics, preferring JSON and falling back to Prometheus text parsing."""
    headers = {}
    if api_key:
        headers["X-API-KEY"] = api_key
    r = requests.get(f"{base_url}/metrics", headers=headers, timeout=5)
    r.raise_for_status()
    try:
        data = r.json()
        return data.get("metrics", data) if isinstance(data, dict) else data
    except ValueError:
        return _parse_prometheus_histograms(r.text, target_names=HISTOGRAM_METRIC_NAMES)


def _percentiles(values: Sequence[float], pcts: Sequence[int] = (50, 90)) -> Dict[str, float]:
    """Compute percentile map for a numeric sequence."""
    if len(values) == 0:
        return {}
    arr = np.array(values, dtype=float)
    return {f"p{p}": float(np.percentile(arr, p)) for p in pcts}


def _histogram_percentiles_from_buckets(hist: Dict[str, Any], pcts: Sequence[int] = (50, 90)) -> Dict[str, float]:
    """Approximate percentiles from Prometheus histogram buckets."""
    buckets = hist.get("buckets") or {}
    ordered = []
    for bound, cumulative in buckets.items():
        try:
            upper = float("inf") if str(bound) == "+Inf" else float(bound)
        except ValueError:
            continue
        ordered.append((upper, float(cumulative)))
    if not ordered:
        return {}
    ordered.sort(key=lambda pair: pair[0])
    total = float(hist.get("count") or max(val for _, val in ordered))
    if total <= 0:
        return {}
    results: Dict[str, float] = {}
    for p in pcts:
        target = total * (p / 100.0)
        prev_bound = 0.0
        prev_cum = 0.0
        for upper, cumulative in ordered:
            if cumulative >= target:
                if upper == float("inf"):
                    approx = prev_bound
                else:
                    bucket_count = max(cumulative - prev_cum, 0.0)
                    if bucket_count == 0:
                        approx = upper
                    else:
                        fraction = (target - prev_cum) / bucket_count
                        lower = prev_bound
                        approx = lower + (upper - lower) * min(max(fraction, 0.0), 1.0)
                results[f"p{p}"] = float(approx)
                break
            if upper != float("inf"):
                prev_bound = upper
            prev_cum = cumulative
    return results


def _parse_prometheus_histograms(prom_text: str, target_names: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    """Parse Prometheus text exposition into histogram bucket dictionaries."""
    try:
        from prometheus_client.parser import text_string_to_metric_families
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(_PROMETHEUS_CLIENT_MISSING_MSG) from exc

    targets = set(target_names) if target_names else None
    histograms: Dict[str, Dict[str, Any]] = {}

    for family in text_string_to_metric_families(prom_text):
        if family.type != "histogram":
            continue
        if targets and family.name not in targets:
            continue
        hist = histograms.setdefault(family.name, {"buckets": {}, "count": 0, "sum": 0.0})
        for sample in family.samples:
            name, labels, value, *_ = sample
            if name.endswith("_bucket"):
                le = labels.get("le")
                if le is None:
                    continue
                hist["buckets"][le] = hist["buckets"].get(le, 0.0) + float(value)
            elif name.endswith("_count"):
                hist["count"] = hist.get("count", 0.0) + float(value)
            elif name.endswith("_sum"):
                hist["sum"] = hist.get("sum", 0.0) + float(value)

    return histograms


def _extract_histogram_percentiles(metrics: Dict[str, Any], name: str) -> Dict[str, float]:
    """Extract histogram-style metrics into percentile summaries."""
    series = metrics.get(name)
    if series is None and isinstance(metrics.get("metrics"), dict):
        series = metrics["metrics"].get(name)
    if not series:
        return {}
    if isinstance(series, dict) and "values" in series:
        values = [v for v in series.get("values", []) if isinstance(v, (int, float))]
    elif isinstance(series, dict) and "buckets" in series:
        return _histogram_percentiles_from_buckets(series)
    elif isinstance(series, list):
        values = [v for v in series if isinstance(v, (int, float))]
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


def run_full_turn(
    base_url: str,
    api_key: Optional[str],
    model: str = "gpt-4o-mini",
    provider: str = "openai",
) -> HarnessResult:
    """Post a short silent clip, then scrape metrics to derive latency percentiles."""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-KEY"] = api_key

    audio_b64 = _b64_audio(_make_silence(0.2))
    payload = {
        "input_audio": audio_b64,
        "input_audio_format": "wav",
        "llm_config": {"model": model, "api_provider": provider},
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
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o-mini",
        help="Model name for the /api/v1/audio/chat LLM config",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default="openai",
        help="API provider name for the /api/v1/audio/chat LLM config",
    )
    args = parser.parse_args()

    try:
        if args.short:
            result = run_short_mode(args.base_url, args.api_key)
        else:
            result = run_full_turn(args.base_url, args.api_key, model=args.model, provider=args.provider)
    except Exception as exc:
        logger.error(f"Harness failed: {exc}")
        logger.exception("Full traceback:")
        raise SystemExit(1) from exc

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(result.to_json())
    logger.info(f"Wrote results to {args.out}")


if __name__ == "__main__":
    main()
