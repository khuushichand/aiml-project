#!/usr/bin/env python3
"""
Minimal voice latency harness stub.

Currently measures TTS time-to-first-byte (TTFB) for the REST endpoint
`/api/v1/audio/speech` with `response_format=pcm` using streaming.

Extend with WS STT commit/final timing once VAD/commit is in place to compute
`stt_final_latency_seconds` and end-to-end `voice_to_voice_seconds`.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from typing import Dict, Any, List
from pathlib import Path
from urllib.parse import urlparse


def _ensure_repo_root() -> None:
    here = Path(__file__).resolve()
    for parent in [here] + list(here.parents):
        if (parent / "tldw_Server_API").is_dir():
            sys.path.insert(0, str(parent))
            return


def _configure_local_egress(url: str) -> None:
    try:
        parsed = urlparse(url)
    except Exception:
        return
    host = (parsed.hostname or "").lower()
    if host in {"localhost", "0.0.0.0"} or host.startswith("127.") or host == "::1":
        os.environ.setdefault("WORKFLOWS_EGRESS_BLOCK_PRIVATE", "false")
        if "WORKFLOWS_EGRESS_ALLOWED_PORTS" not in os.environ:
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            os.environ["WORKFLOWS_EGRESS_ALLOWED_PORTS"] = f"{port},80,443"


_ensure_repo_root()

try:
    from tldw_Server_API.app.core import http_client
except Exception:
    print("tldw_Server_API not available; run from the repo root or set PYTHONPATH.", file=sys.stderr)
    raise SystemExit(1)


def _now() -> float:
    return time.time()


def _p50(values: List[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    mid = (len(s) - 1) * 0.5
    i = int(mid)
    if i == mid:
        return s[i]
    return (s[i] + s[i + 1]) / 2


def _p90(values: List[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = max(0, int(round(0.9 * (len(s) - 1))))
    return s[k]


async def measure_tts_ttfb(base: str, token: str | None, text: str, runs: int = 5) -> Dict[str, Any]:
    url = f"{base.rstrip('/')}/api/v1/audio/speech"
    headers = {"Accept": "application/octet-stream", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    ttfb_runs: List[float] = []
    per_run: List[Dict[str, Any]] = []

    for i in range(max(1, runs)):
        req_id = str(uuid.uuid4())
        headers["X-Request-Id"] = req_id
        payload = {
            "model": "tts-1",
            "input": text,
            "voice": "alloy",
            "response_format": "pcm",
            "stream": True,
        }
        start = _now()
        first = None
        total_bytes = 0
        try:
            async for chunk in http_client.astream_bytes(
                method="POST",
                url=url,
                headers=headers,
                json=payload,
                timeout=60.0,
            ):
                if not chunk:
                    continue
                total_bytes += len(chunk)
                if first is None:
                    first = _now()
                    ttfb = max(0.0, first - start)
                    ttfb_runs.append(ttfb)
                    # Continue consuming to validate stream is healthy
        except Exception as e:
            per_run.append({"run": i + 1, "ok": False, "error": str(e)})
            continue
        per_run.append({"run": i + 1, "ok": True, "ttfb_s": ttfb_runs[-1] if ttfb_runs else None, "bytes": total_bytes, "request_id": req_id})

    summary = {
        "mode": "tts",
        "runs": len(per_run),
        "p50_ttfb_s": round(_p50(ttfb_runs), 4) if ttfb_runs else None,
        "p90_ttfb_s": round(_p90(ttfb_runs), 4) if ttfb_runs else None,
        "per_run": per_run,
    }
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description="Voice Latency Harness (stub)")
    ap.add_argument("--mode", choices=["tts"], default="tts", help="Measurement mode")
    ap.add_argument("--base", default="http://127.0.0.1:8000", help="Server base URL")
    ap.add_argument("--token", default=None, help="Auth token (Bearer)")
    ap.add_argument("--text", default="Hello from TLDW", help="TTS input text")
    ap.add_argument("--runs", type=int, default=5, help="Number of runs")
    args = ap.parse_args()

    if args.mode == "tts":
        _configure_local_egress(args.base)
        try:
            result = asyncio.run(measure_tts_ttfb(args.base, args.token, args.text, args.runs))
        finally:
            try:
                asyncio.run(http_client.shutdown_http_client())
            except Exception:
                pass
        print(json.dumps(result, indent=2))
        return

    print("Unsupported mode", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
