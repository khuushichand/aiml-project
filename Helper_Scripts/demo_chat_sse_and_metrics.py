#!/usr/bin/env python3
"""
Demo script: stream /api/v1/chat/completions (SSE) and print unified SSE metrics.

Usage examples:
  python Helper_Scripts/demo_chat_sse_and_metrics.py \
    --base-url http://127.0.0.1:8000 \
    --api-key $SINGLE_USER_API_KEY \
    --model gpt-4o-mini \
    --prompt "Say hello from unified streaming"

Notes:
  - Requires the server running with unified streams enabled (config.txt [Streaming] streams_unified=true),
    or the env STREAMS_UNIFIED=1 on the server.
  - If you don't have upstream provider keys, you can run the server in mock mode (see project benchmarks docs)
    or set appropriate provider/model in your server config.
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

_HELPERS_ROOT = Path(__file__).resolve()
for _parent in [_HELPERS_ROOT, *_HELPERS_ROOT.parents]:
    if _parent.name == "Helper_Scripts":
        _parent_str = str(_parent)
        if _parent_str not in sys.path:
            sys.path.insert(0, _parent_str)
        break

from common.repo_utils import configure_local_egress, ensure_repo_root

ensure_repo_root()

try:
    from tldw_Server_API.app.core import http_client
except Exception:
    print("tldw_Server_API not available; run from the repo root or set PYTHONPATH.", file=sys.stderr)
    raise SystemExit(1)


def _to_headers(api_key: Optional[str]) -> dict:
    h = {"Content-Type": "application/json"}
    if api_key:
        # Single-user mode uses X-API-KEY by default
        h["X-API-KEY"] = api_key
    return h


async def _iter_sse_lines(byte_iter):
    buffer = b""
    async for chunk in byte_iter:
        if not chunk:
            continue
        buffer += chunk
        while b"\n" in buffer:
            line, buffer = buffer.split(b"\n", 1)
            yield line.rstrip(b"\r").decode("utf-8", errors="replace")
    if buffer:
        yield buffer.decode("utf-8", errors="replace")


async def stream_chat_sse(base_url: str, api_key: Optional[str], model: str, prompt: str, timeout: float = 600.0) -> dict:
    url = base_url.rstrip("/") + "/api/v1/chat/completions"
    payload = {
        "model": model,
        "stream": True,
        "messages": [
            {"role": "user", "content": prompt},
        ],
    }
    headers = _to_headers(api_key)

    t0 = time.time()
    ttft = None
    total_lines = 0
    total_data_lines = 0
    total_heartbeats = 0
    last_nonempty = ""

    print("streaming...")
    try:
        byte_iter = http_client.astream_bytes(
            method="POST",
            url=url,
            headers=headers,
            json=payload,
            timeout=timeout,
        )
        async for raw in _iter_sse_lines(byte_iter):
            if raw is None or raw == "":
                continue
            s = str(raw)
            total_lines += 1
            if s.startswith(":"):
                total_heartbeats += 1
                # Uncomment to see heartbeat lines
                # print("[hb]", s)
                continue
            if not s.startswith("data:"):
                # Control/event/id lines
                continue
            total_data_lines += 1
            if ttft is None:
                ttft = (time.time() - t0) * 1000.0
            print("SSE:", s[:200])
            last_nonempty = s
            if s.strip().lower() == "data: [done]":
                break
    except Exception as exc:
        raise RuntimeError(f"Streaming failed: {exc}") from exc

    print(f"TTFT: {ttft:.1f} ms" if ttft is not None else "TTFT: n/a")
    print(f"lines: total={total_lines} data={total_data_lines} heartbeats={total_heartbeats}")

    return {
        "ttft_ms": ttft,
        "total_lines": total_lines,
        "total_data_lines": total_data_lines,
        "total_heartbeats": total_heartbeats,
        "last_line": last_nonempty,
    }


def fetch_metrics(base_url: str, api_key: Optional[str]) -> str:
    url = base_url.rstrip("/") + "/api/v1/metrics/text"
    headers = _to_headers(api_key)
    r = http_client.fetch(method="GET", url=url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.text


def print_unified_sse_metrics(metrics_text: str) -> None:
    # Show SSE enqueue->yield histogram buckets and queue HWM for chat streaming endpoint
    hist_pattern = re.compile(r"^sse_enqueue_to_yield_ms_bucket\{([^}]*)\}\s+(\d+(?:\.\d+)?)$")
    gauge_pattern = re.compile(r"^sse_queue_high_watermark\{([^}]*)\}\s+(\d+(?:\.\d+)?)$")

    def _labels_match(lbls: str) -> bool:
        # Require component="chat" and endpoint="chat_completions_stream" and transport="sse"
        need = {"component": "chat", "endpoint": "chat_completions_stream", "transport": "sse"}
        have = {}
        for kv in lbls.split(","):
            if "=" not in kv:
                continue
            k, v = kv.split("=", 1)
            have[k.strip()] = v.strip().strip('"')
        return all(have.get(k) == v for k, v in need.items())

    hist_lines = []
    hwm_val = None

    for line in metrics_text.splitlines():
        m = hist_pattern.match(line)
        if m and _labels_match(m.group(1)):
            hist_lines.append(line)
        g = gauge_pattern.match(line)
        if g and _labels_match(g.group(1)):
            try:
                hwm_val = float(g.group(2))
            except (TypeError, ValueError):
                continue

    if hist_lines:
        print("\nSSE enqueue→yield histogram (chat):")
        for l in hist_lines[:10]:  # show first few buckets to keep output short
            print(l)
        if len(hist_lines) > 10:
            print(f"... ({len(hist_lines) - 10} more buckets)")
    else:
        print("\nNo unified SSE histogram lines found for chat.")

    if hwm_val is not None:
        print(f"SSE queue high-watermark (chat): {hwm_val}")
    else:
        print("SSE queue HWM (chat): not found")


def main() -> int:
    ap = argparse.ArgumentParser(description="Stream chat SSE and print unified SSE metrics")
    ap.add_argument("--base-url", default=os.getenv("TLDW_BASE_URL", "http://127.0.0.1:8000"), help="Server base URL")
    ap.add_argument("--api-key", default=os.getenv("SINGLE_USER_API_KEY"), help="X-API-KEY for single-user mode")
    ap.add_argument("--model", default=os.getenv("TLDW_DEMO_MODEL", "gpt-4o-mini"), help="Model name")
    ap.add_argument("--prompt", default="Hello from unified streaming demo", help="User message content")
    args = ap.parse_args()

    configure_local_egress(args.base_url)

    rc = 0
    try:
        asyncio.run(stream_chat_sse(args.base_url, args.api_key, args.model, args.prompt))
    except Exception as e:
        print(f"Streaming failed: {e}")
        rc = 2
    else:
        try:
            mt = fetch_metrics(args.base_url, args.api_key)
            print_unified_sse_metrics(mt)
        except Exception as e:
            print(f"Fetching/printing metrics failed: {e}")
            rc = 3
    finally:
        try:
            asyncio.run(http_client.shutdown_http_client())
        except Exception as exc:
            print(f"HTTP client shutdown warning: {exc}", file=sys.stderr)

    return rc


if __name__ == "__main__":
    sys.exit(main())
