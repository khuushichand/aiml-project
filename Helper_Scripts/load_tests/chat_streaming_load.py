#!/usr/bin/env python3
"""
chat_streaming_load.py

Scenario A-style streaming load harness for /api/v1/chat/completions.

Focus:
    - Time-to-first-token (TTFT) distribution (p50/p95/p99).
    - Inter-chunk latency distribution across all streams.
    - Simple success/failure stats under a given concurrency level.

Usage (example, single-user, local):

    export SINGLE_USER_API_KEY=your-key
    # Start server (ideally with STREAMS_UNIFIED=1, and optionally CHAT_FORCE_MOCK=1)
    python Helper_Scripts/load_tests/chat_streaming_load.py \\
        --base-url http://127.0.0.1:8000 \\
        --api-key "$SINGLE_USER_API_KEY" \\
        --model gpt-4o-mini \\
        --concurrency 100 \\
        --streams-per-client 2 \\
        --prompt-bytes 512 \\
        --http2

Notes:
    - This harness is intentionally focused and lightweight: it runs a fixed
      number of streams at a given concurrency and reports TTFT and per-chunk
      latency distributions.
    - For broader sweep benchmarks (multiple concurrencies, RPS, etc.), see
      Helper_Scripts/benchmarks/llm_gateway_bench.py and the Makefile targets
      `bench-sweep` / `bench-stream`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
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


def _status_from_exc(exc: Exception) -> int:
    resp = getattr(exc, "response", None)
    if resp is not None:
        try:
            return int(getattr(resp, "status_code", 0) or 0)
        except Exception:
            pass
    msg = str(exc)
    for token in msg.split():
        if token.isdigit() and len(token) == 3:
            try:
                return int(token)
            except Exception:
                continue
    return 0


_ensure_repo_root()

try:
    from tldw_Server_API.app.core import http_client
except Exception:
    print("tldw_Server_API not available; run from the repo root or set PYTHONPATH.", file=sys.stderr)
    raise SystemExit(1)


def _now_ms() -> float:
    return time.perf_counter() * 1000.0


def _percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    pct = max(0.0, min(100.0, pct))
    idx = int(round((pct / 100.0) * (len(values) - 1)))
    return sorted(values)[idx]


@dataclass
class StreamResult:
    ok: bool
    status: int
    latency_ms: float
    ttft_ms: Optional[float]
    chunk_latencies_ms: List[float] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class AggregateMetrics:
    concurrency: int
    total_streams: int
    successes: int
    failures: int
    ttft_p50_ms: Optional[float]
    ttft_p95_ms: Optional[float]
    ttft_p99_ms: Optional[float]
    chunk_p50_ms: Optional[float]
    chunk_p95_ms: Optional[float]
    chunk_p99_ms: Optional[float]
    error_rate: float


def _build_headers(api_key: Optional[str], bearer: Optional[str]) -> Dict[str, str]:
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    elif api_key:
        headers["X-API-KEY"] = api_key
    return headers


def _build_prompt(prompt_bytes: int) -> str:
    base = "Please summarize the following text."
    if prompt_bytes <= 0:
        return base
    filler_len = max(0, prompt_bytes - len(base))
    filler = (" Lorem ipsum dolor sit amet." * ((filler_len // 28) + 1))[:filler_len]
    return base + filler


def _build_payload(model: str, prompt_bytes: int) -> Dict[str, Any]:
    messages = [{"role": "user", "content": _build_prompt(prompt_bytes)}]
    return {
        "model": model,
        "stream": True,
        "messages": messages,
    }


async def _run_single_stream(
    client: Any,
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    timeout_s: float,
) -> StreamResult:
    t0 = _now_ms()
    ttft_ms: Optional[float] = None
    chunk_latencies: List[float] = []
    last_chunk_ts: Optional[float] = None

    try:
        stream_headers = dict(headers)
        stream_headers.setdefault("Accept", "text/event-stream")
        async for event in http_client.astream_sse(
            method="POST",
            url=url,
            headers=stream_headers,
            json=payload,
            timeout=timeout_s,
            client=client,
        ):
            data = (event.data or "").strip()
            if not data:
                continue
            now = _now_ms()
            if data.lower() == "[done]":
                break
            if ttft_ms is None:
                ttft_ms = now - t0
            if last_chunk_ts is not None:
                chunk_latencies.append(now - last_chunk_ts)
            last_chunk_ts = now

        latency_ms = _now_ms() - t0
        return StreamResult(
            ok=True,
            status=200,
            latency_ms=latency_ms,
            ttft_ms=ttft_ms,
            chunk_latencies_ms=chunk_latencies,
        )
    except Exception as exc:
        latency_ms = _now_ms() - t0
        return StreamResult(
            ok=False,
            status=_status_from_exc(exc),
            latency_ms=latency_ms,
            ttft_ms=ttft_ms,
            chunk_latencies_ms=chunk_latencies,
            error=str(exc),
        )


async def _run_load(
    *,
    base_url: str,
    api_key: Optional[str],
    bearer: Optional[str],
    model: str,
    concurrency: int,
    streams_per_client: int,
    prompt_bytes: int,
    timeout_s: float,
    http2: bool,
) -> Tuple[AggregateMetrics, List[StreamResult]]:
    url = base_url.rstrip("/") + "/api/v1/chat/completions"
    headers = _build_headers(api_key, bearer)
    payload = _build_payload(model, prompt_bytes)

    limits = None
    hx = getattr(http_client, "httpx", None)
    if hx is not None:
        try:
            limits = hx.Limits(
                max_keepalive_connections=max(concurrency, 1),
                max_connections=max(concurrency * 2, 10),
            )
        except Exception:
            limits = None
    client = http_client.create_async_client(http2=http2, limits=limits)

    results: List[StreamResult] = []
    results_lock = asyncio.Lock()

    async def worker(worker_id: int) -> None:
        # Stagger start slightly to avoid a sharp burst
        await asyncio.sleep((worker_id % max(concurrency, 1)) * 0.001)
        for _ in range(streams_per_client):
            res = await _run_single_stream(client, url, headers, payload, timeout_s)
            async with results_lock:
                results.append(res)

    tasks = [asyncio.create_task(worker(i)) for i in range(concurrency)]
    await asyncio.gather(*tasks, return_exceptions=True)
    await client.aclose()

    total_streams = len(results)
    successes = sum(1 for r in results if r.ok)
    failures = total_streams - successes
    error_rate = failures / total_streams if total_streams else 0.0

    ttfts = [r.ttft_ms for r in results if r.ttft_ms is not None]
    all_chunk_latencies: List[float] = []
    for r in results:
        all_chunk_latencies.extend(r.chunk_latencies_ms)

    ttft_p50 = _percentile(ttfts, 50) if ttfts else None
    ttft_p95 = _percentile(ttfts, 95) if ttfts else None
    ttft_p99 = _percentile(ttfts, 99) if ttfts else None

    chunk_p50 = _percentile(all_chunk_latencies, 50) if all_chunk_latencies else None
    chunk_p95 = _percentile(all_chunk_latencies, 95) if all_chunk_latencies else None
    chunk_p99 = _percentile(all_chunk_latencies, 99) if all_chunk_latencies else None

    agg = AggregateMetrics(
        concurrency=concurrency,
        total_streams=total_streams,
        successes=successes,
        failures=failures,
        ttft_p50_ms=ttft_p50,
        ttft_p95_ms=ttft_p95,
        ttft_p99_ms=ttft_p99,
        chunk_p50_ms=chunk_p50,
        chunk_p95_ms=chunk_p95,
        chunk_p99_ms=chunk_p99,
        error_rate=error_rate,
    )
    return agg, results


async def run_load(
    *,
    base_url: str,
    api_key: Optional[str],
    bearer: Optional[str],
    model: str,
    concurrency: int,
    streams_per_client: int,
    prompt_bytes: int,
    timeout_s: float,
    http2: bool,
) -> Tuple[AggregateMetrics, List[StreamResult]]:
    """
    Public helper to run a single streaming load step.

    This is a thin wrapper around the internal _run_load used by the CLI entrypoint.
    """
    return await _run_load(
        base_url=base_url,
        api_key=api_key,
        bearer=bearer,
        model=model,
        concurrency=concurrency,
        streams_per_client=streams_per_client,
        prompt_bytes=prompt_bytes,
        timeout_s=timeout_s,
        http2=http2,
    )


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Streaming load harness for /api/v1/chat/completions (TTFT + per-chunk latency)."
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
        "--concurrency",
        type=int,
        default=int(os.getenv("TLDW_LOAD_CONCURRENCY", "50")),
        help="Number of concurrent streaming clients (default: %(default)s).",
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
        "--json-out",
        default=None,
        help="Optional path to write JSON summary (AggregateMetrics + basic stats).",
    )
    parser.add_argument(
        "--print-error-samples",
        type=int,
        default=3,
        help="Max number of error samples to print (default: %(default)s).",
    )
    return parser.parse_args(argv)


def _print_summary(metrics: AggregateMetrics, results: List[StreamResult], print_error_samples: int) -> None:
    print("\n=== Chat Streaming Load Summary ===")
    print(f"Concurrency           : {metrics.concurrency}")
    print(f"Total streams         : {metrics.total_streams}")
    print(f"Successes             : {metrics.successes}")
    print(f"Failures              : {metrics.failures}")
    print(f"Error rate            : {metrics.error_rate * 100:.2f}%")

    if metrics.ttft_p50_ms is not None:
        print(
            f"TTFT p50/p95/p99 (ms) : "
            f"{metrics.ttft_p50_ms:.1f} / {metrics.ttft_p95_ms:.1f} / {metrics.ttft_p99_ms:.1f}"
        )
    else:
        print("TTFT stats            : n/a")

    if metrics.chunk_p50_ms is not None:
        print(
            f"Chunk p50/p95/p99 (ms): "
            f"{metrics.chunk_p50_ms:.1f} / {metrics.chunk_p95_ms:.1f} / {metrics.chunk_p99_ms:.1f}"
        )
    else:
        print("Chunk latency stats   : n/a (no token chunks observed)")

    if print_error_samples > 0:
        failed = [r for r in results if not r.ok]
        if failed:
            print(f"\nSample errors (showing up to {print_error_samples}):")
            for r in failed[:print_error_samples]:
                print(f"  status={r.status} error={r.error!r}")


def _to_serializable(metrics: AggregateMetrics) -> Dict[str, Any]:
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


async def _main_async(args: argparse.Namespace) -> int:
    if not args.api_key and not args.bearer:
        print("Warning: no API key or bearer token provided; requests may fail if auth is enabled.", file=sys.stderr)

    _configure_local_egress(args.base_url)

    print("Chat streaming load harness")
    print(f"  Base URL           : {args.base_url}")
    print(f"  Model              : {args.model}")
    print(f"  Concurrency        : {args.concurrency}")
    print(f"  Streams per client : {args.streams_per_client}")
    print(f"  Prompt bytes       : {args.prompt_bytes}")
    print(f"  HTTP/2             : {'enabled' if args.http2 else 'disabled'}")
    print("")

    metrics, results = await _run_load(
        base_url=args.base_url,
        api_key=args.api_key,
        bearer=args.bearer,
        model=args.model,
        concurrency=args.concurrency,
        streams_per_client=args.streams_per_client,
        prompt_bytes=args.prompt_bytes,
        timeout_s=args.timeout,
        http2=args.http2,
    )

    _print_summary(metrics, results, args.print_error_samples)

    if args.json_out:
        data = {
            "base_url": args.base_url,
            "model": args.model,
            "concurrency": args.concurrency,
            "streams_per_client": args.streams_per_client,
            "prompt_bytes": args.prompt_bytes,
            "http2": args.http2,
            "metrics": _to_serializable(metrics),
            "generated_at": time.time(),
        }
        try:
            with open(args.json_out, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            print(f"\nWrote JSON summary to {args.json_out}")
        except Exception as exc:
            print(f"\nFailed to write JSON summary to {args.json_out}: {exc}", file=sys.stderr)

    return 0


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        return asyncio.run(_main_async(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
