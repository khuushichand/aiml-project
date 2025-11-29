#!/usr/bin/env python3
"""
chat_streaming_sweep.py

Run a Scenario A-style sweep over multiple concurrency levels for
/api/v1/chat/completions using the chat_streaming_load harness.

For each concurrency value, the script:
    - Runs N sequential streams per client.
    - Measures TTFT p50/p95/p99.
    - Measures inter-chunk latency p50/p95/p99 across all streams.
    - Prints a compact table row per concurrency step.

Usage (HTTP/1.1 example):

    export SINGLE_USER_API_KEY=your-key
    python Helper_Scripts/load_tests/chat_streaming_sweep.py \\
        --base-url http://127.0.0.1:8000 \\
        --api-key "$SINGLE_USER_API_KEY" \\
        --model gpt-4o-mini \\
        --concurrency-steps 50 100 200 \\
        --streams-per-client 2 \\
        --prompt-bytes 512

Usage (HTTP/2 example):

    python Helper_Scripts/load_tests/chat_streaming_sweep.py \\
        --base-url http://127.0.0.1:8000 \\
        --api-key "$SINGLE_USER_API_KEY" \\
        --model gpt-4o-mini \\
        --concurrency-steps 50 100 200 \\
        --streams-per-client 2 \\
        --prompt-bytes 512 \\
        --http2
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

from .chat_streaming_load import AggregateMetrics, run_load


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sweep chat streaming load over multiple concurrency levels."
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("TLDW_BASE_URL", "http://127.0.0.1:8000"),
        help="Server base URL (default: %(default)s).",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("TLDW_API_KEY") or os.getenv("SINGLE_USER_API_KEY"),
        help="Single-user API key (sent as X-API-KEY).",
    )
    parser.add_argument(
        "--bearer",
        default=os.getenv("TLDW_BENCH_BEARER_TOKEN"),
        help="Bearer token for multi-user mode (Authorization: Bearer ...).",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("TLDW_LOAD_MODEL", "gpt-4o-mini"),
        help="Model name for /chat/completions (default: %(default)s).",
    )
    parser.add_argument(
        "--concurrency-steps",
        nargs="+",
        type=int,
        required=True,
        help="List of concurrency levels to run (e.g. 50 100 200).",
    )
    parser.add_argument(
        "--streams-per-client",
        type=int,
        default=int(os.getenv("TLDW_LOAD_STREAMS_PER_CLIENT", "1")),
        help="Number of sequential streams per client (default: %(default)s).",
    )
    parser.add_argument(
        "--prompt-bytes",
        type=int,
        default=int(os.getenv("TLDW_LOAD_PROMPT_BYTES", "256")),
        help="Approximate size of the user message in bytes (default: %(default)s).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.getenv("TLDW_LOAD_TIMEOUT", "600")),
        help="Per-stream timeout in seconds (default: %(default)s).",
    )
    parser.add_argument(
        "--http2",
        action="store_true",
        help="Enable HTTP/2 on the client (default: HTTP/1.1).",
    )
    parser.add_argument(
        "--sleep-between",
        type=float,
        default=5.0,
        help="Seconds to sleep between concurrency steps (default: %(default)s).",
    )
    parser.add_argument(
        "--json-out",
        default=None,
        help="Optional path to write JSON summary for all steps.",
    )
    return parser.parse_args(argv)


def _metrics_to_dict(metrics: AggregateMetrics) -> Dict[str, Any]:
    return {
        "concurrency": metrics.concurrency,
        "total_streams": metrics.total_streams,
        "successes": metrics.successes,
        "failures": metrics.failures,
        "error_rate": metrics.error_rate,
        "ttft_p50_ms": metrics.ttft_p50_ms,
        "ttft_p95_ms": metrics.ttft_p95_ms,
        "ttft_p99_ms": metrics.ttft_p99_ms,
        "chunk_p50_ms": metrics.chunk_p50_ms,
        "chunk_p95_ms": metrics.chunk_p95_ms,
        "chunk_p99_ms": metrics.chunk_p99_ms,
    }


def _print_header() -> None:
    print(
        "conc  total  ok    err   err%   "
        "ttft_p50  ttft_p95  ttft_p99  "
        "chunk_p50  chunk_p95  chunk_p99"
    )


def _print_row(m: AggregateMetrics) -> None:
    err_pct = m.error_rate * 100.0

    def fmt(v: Optional[float]) -> str:
        return f"{v:8.1f}" if v is not None else f"{'n/a':>8}"

    print(
        f"{m.concurrency:4d}  "
        f"{m.total_streams:5d}  "
        f"{m.successes:5d}  "
        f"{m.failures:5d}  "
        f"{err_pct:5.1f}  "
        f"{fmt(m.ttft_p50_ms)}  "
        f"{fmt(m.ttft_p95_ms)}  "
        f"{fmt(m.ttft_p99_ms)}  "
        f"{fmt(m.chunk_p50_ms)}  "
        f"{fmt(m.chunk_p95_ms)}  "
        f"{fmt(m.chunk_p99_ms)}"
    )


async def _run_sweep(args: argparse.Namespace) -> int:
    if not args.api_key and not args.bearer:
        print("Warning: no API key or bearer token provided; requests may fail if auth is enabled.", file=sys.stderr)

    print("Chat streaming sweep")
    print(f"  Base URL           : {args.base_url}")
    print(f"  Model              : {args.model}")
    print(f"  Concurrency steps  : {args.concurrency_steps}")
    print(f"  Streams per client : {args.streams_per_client}")
    print(f"  Prompt bytes       : {args.prompt_bytes}")
    print(f"  HTTP/2             : {'enabled' if args.http2 else 'disabled'}")
    print("")

    all_steps: List[Dict[str, Any]] = []
    _print_header()

    for idx, conc in enumerate(args.concurrency_steps):
        metrics, _ = await run_load(
            base_url=args.base_url,
            api_key=args.api_key,
            bearer=args.bearer,
            model=args.model,
            concurrency=conc,
            streams_per_client=args.streams_per_client,
            prompt_bytes=args.prompt_bytes,
            timeout_s=args.timeout,
            http2=args.http2,
        )
        _print_row(metrics)
        all_steps.append(_metrics_to_dict(metrics))

        if idx != len(args.concurrency_steps) - 1 and args.sleep_between > 0:
            await asyncio.sleep(args.sleep_between)

    if args.json_out:
        payload = {
            "base_url": args.base_url,
            "model": args.model,
            "concurrency_steps": args.concurrency_steps,
            "streams_per_client": args.streams_per_client,
            "prompt_bytes": args.prompt_bytes,
            "http2": args.http2,
            "steps": all_steps,
            "generated_at": time.time(),
        }
        try:
            with open(args.json_out, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            print(f"\nWrote sweep summary JSON to {args.json_out}")
        except Exception as exc:  # pragma: no cover - defensive
            print(f"\nFailed to write JSON summary to {args.json_out}: {exc}", file=sys.stderr)

    return 0


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        import asyncio

        return asyncio.run(_run_sweep(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

