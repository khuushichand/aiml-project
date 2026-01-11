#!/usr/bin/env python3
"""
llm_gateway_bench.py

Purpose:
- Benchmark the tldw_server Chat API (/api/v1/chat/completions) for throughput and latency.
- Sweep concurrency, measure p50/p90/p95/p99 latency, error rate, and basic streaming timings (TTFT).
- Avoids external provider cost/limits when server runs with CHAT_FORCE_MOCK=1 (recommended).

Usage (examples):

  # Non-streaming, concurrency sweep 1,2,4,8 for 20s each (single-user API key)
  python Helper_Scripts/benchmarks/llm_gateway_bench.py \
      --base-url http://127.0.0.1:8000 \
      --path /api/v1/chat/completions \
      --api-key "$SINGLE_USER_API_KEY" \
      --concurrency 1 2 4 8 \
      --duration 20

  # Streaming benchmark with bearer token (multi-user) and fixed overlap = 16
  python Helper_Scripts/benchmarks/llm_gateway_bench.py \
      --stream \
      --concurrency 16 \
      --duration 30 \
      --bearer "$JWT_TOKEN"

  # Ramp until error-rate > 5% or p99 > 5s
  python Helper_Scripts/benchmarks/llm_gateway_bench.py \
      --concurrency 1 2 4 8 16 32 \
      --duration 20 \
      --max-error-rate 0.05 \
      --latency-p99-sla-ms 5000

Notes:
- To avoid hitting real providers, run the server with: CHAT_FORCE_MOCK=1 (and optionally TEST_MODE=1).
- Provider/model can be set via args. Defaults aim for mock OpenAI-compatible flow.
"""

from __future__ import annotations

import argparse
import contextlib
import asyncio
import json
import os
import random
import re
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

_HELPERS_ROOT = Path(__file__).resolve()
for _parent in [_HELPERS_ROOT, *_HELPERS_ROOT.parents]:
    if _parent.name == "Helper_Scripts":
        _parent_str = str(_parent)
        if _parent_str not in sys.path:
            sys.path.insert(0, _parent_str)
        break

from common.repo_utils import configure_local_egress, ensure_repo_root


def _status_from_exc(exc: Exception) -> int:
    resp = getattr(exc, "response", None)
    if resp is not None:
        try:
            return int(getattr(resp, "status_code", 0) or 0)
        except Exception:
            logger.exception(
                "Failed to read status_code from response; exc={exc!r} resp={resp!r}",
                exc=exc,
                resp=resp,
            )
    try:
        msg = str(exc)
    except Exception:
        logger.exception(
            "Failed to stringify exception for status parsing; exc={exc!r} resp={resp!r}",
            exc=exc,
            resp=resp,
        )
        return 0
    try:
        match = re.search(r"\b(\d{3})\b", msg)
        if match:
            return int(match.group(1))
    except Exception:
        logger.exception(
            "Failed to parse HTTP status from exception message; exc={exc!r} resp={resp!r} msg={msg!r}",
            exc=exc,
            resp=resp,
            msg=msg,
        )
        return 0
    logger.debug(
        "No HTTP status found in exception message; exc={exc!r} resp={resp!r} msg={msg!r}",
        exc=exc,
        resp=resp,
        msg=msg,
    )
    return 0


ensure_repo_root()

try:
    from tldw_Server_API.app.core import http_client
except Exception:
    print("tldw_Server_API not available; run from the repo root or set PYTHONPATH.", file=sys.stderr)
    raise SystemExit(1) from None


def _now_ms() -> float:
    return time.perf_counter() * 1000.0


def _percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    pct = max(0.0, min(100.0, pct))
    idx = int(round((pct / 100.0) * (len(values) - 1)))
    return sorted(values)[idx]


@dataclass
class RequestResult:
    ok: bool
    status: int
    latency_ms: float
    ttft_ms: Optional[float] = None  # time to first token (for streaming)
    error: Optional[str] = None


@dataclass
class StepMetrics:
    concurrency: int
    total: int
    successes: int
    failures: int
    rps: float
    p50_ms: float
    p90_ms: float
    p95_ms: float
    p99_ms: float
    ttft_p50_ms: Optional[float] = None
    ttft_p95_ms: Optional[float] = None
    error_rate: float = field(init=False)

    def __post_init__(self) -> None:
        self.error_rate = (self.failures / max(1, self.total)) if self.total else 0.0


def build_payload(
    *,
    provider: str,
    model: str,
    stream: bool,
    prompt_bytes: int,
) -> Dict[str, Any]:
    # Create a simple prompt of desired size (approximate bytes)
    base = "Please summarize the following text."  # ~36 bytes
    if prompt_bytes > 0:
        filler_len = max(0, prompt_bytes - len(base))
        filler = (" Lorem ipsum dolor sit amet." * ((filler_len // 28) + 1))[:filler_len]
        text = base + filler
    else:
        text = base

    messages = [
        {"role": "user", "content": text},
    ]
    return {
        "api_provider": provider,
        "model": model,
        "messages": messages,
        "stream": stream,
        # Keep the rest minimal; add knobs later if needed
    }


async def send_nonstream_request(
    client: Any,
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    timeout_s: float,
) -> RequestResult:
    t0 = _now_ms()
    try:
        r = await http_client.afetch(
            method="POST",
            url=url,
            headers=headers,
            json=payload,
            timeout=timeout_s,
            client=client,
        )
        latency_ms = _now_ms() - t0
        ok = r.status_code < 500 and r.status_code != 429
        return RequestResult(ok=ok, status=r.status_code, latency_ms=latency_ms, error=None if ok else r.text[:200])
    except Exception as e:
        latency_ms = _now_ms() - t0
        return RequestResult(ok=False, status=_status_from_exc(e), latency_ms=latency_ms, error=str(e))


async def send_stream_request(
    client: Any,
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    timeout_s: float,
) -> RequestResult:
    t0 = _now_ms()
    ttft_ms: Optional[float] = None
    status = 200
    try:
        # Ensure SSE accept header for consistency
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
            if ttft_ms is None:
                ttft_ms = _now_ms() - t0
            if data.lower() == "[done]":
                break
        latency_ms = _now_ms() - t0
        ok = status < 500 and status != 429
        return RequestResult(ok=ok, status=status, latency_ms=latency_ms, ttft_ms=ttft_ms)
    except Exception as e:
        latency_ms = _now_ms() - t0
        status = _status_from_exc(e)
        return RequestResult(ok=False, status=status, latency_ms=latency_ms, ttft_ms=ttft_ms, error=str(e))


def _parse_prometheus_text(text: str) -> Dict[Tuple[str, Tuple[Tuple[str, str], ...]], float]:
    """Parse a minimal subset of Prometheus text format into a dict.

    Returns mapping: (metric_name, sorted(label_items_tuple)) -> value
    Only parses simple series lines like: name{l1="v1",l2="v2"} value
    """
    series: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], float] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            if "{" in line and "}" in line:
                name, rest = line.split("{", 1)
                labels_str, value_str = rest.split("}")
                value_str = value_str.strip()
                # Some histogram lines have suffixes like _sum, _count
                metric_name = name.strip()
                labels: Dict[str, str] = {}
                if labels_str:
                    parts = [p for p in labels_str.split(",") if p]
                    for p in parts:
                        if "=" not in p:
                            continue
                        k, v = p.split("=", 1)
                        labels[k.strip()] = v.strip().strip('"')
                key = (metric_name, tuple(sorted(labels.items())))
                series[key] = float(value_str)
            else:
                # name value
                name, value_str = line.split()
                key = (name.strip(), tuple())
                series[key] = float(value_str)
        except Exception:
            # skip malformed lines
            continue
    return series


async def _scrape_metrics_once(client: Any, metrics_url: str) -> Dict[Tuple[str, Tuple[Tuple[str, str], ...]], float]:
    try:
        r = await http_client.afetch(method="GET", url=metrics_url, timeout=10.0, client=client)
        if r.status_code != 200:
            return {}
        return _parse_prometheus_text(r.text)
    except Exception:
        return {}


async def run_step(
    *,
    base_url: str,
    path: str,
    headers: Dict[str, str],
    provider: str,
    model: str,
    concurrency: int,
    duration_s: int,
    stream: bool,
    prompt_bytes: int,
    timeout_s: float,
    metrics_url: Optional[str] = None,
    metrics_endpoint_path: str = "/api/v1/chat/completions",
    metrics_interval_s: float = 2.0,
) -> Tuple[StepMetrics, List[RequestResult], Dict[str, Any]]:
    url = base_url.rstrip("/") + path
    limits = None
    hx = getattr(http_client, "httpx", None)
    if hx is not None:
        try:
            limits = hx.Limits(max_keepalive_connections=concurrency, max_connections=concurrency * 2)
        except Exception:
            limits = None
    client = http_client.create_async_client(base_url=None, limits=limits)
    stop_at = time.monotonic() + duration_s
    results: List[RequestResult] = []
    results_lock = asyncio.Lock()

    payload = build_payload(provider=provider, model=model, stream=stream, prompt_bytes=prompt_bytes)

    async def worker(idx: int) -> None:
        nonlocal results
        # Stagger start slightly to avoid bursty first second
        await asyncio.sleep((idx % concurrency) * 0.001)
        while time.monotonic() < stop_at:
            if stream:
                res = await send_stream_request(client, url, headers, payload, timeout_s)
            else:
                res = await send_nonstream_request(client, url, headers, payload, timeout_s)
            async with results_lock:
                results.append(res)

    # Optional metrics scraping loop
    metrics_client = http_client.create_async_client()
    pre_metrics = {}
    post_metrics = {}
    series_deltas: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], float] = {}

    if metrics_url:
        pre_metrics = await _scrape_metrics_once(metrics_client, metrics_url)

        async def _poll_metrics():
            # background polling to keep /metrics hot; final delta is taken after run
            while time.monotonic() < stop_at:
                await asyncio.sleep(max(0.1, metrics_interval_s))
                try:
                    await _scrape_metrics_once(metrics_client, metrics_url)
                except Exception:
                    pass

        poll_task = asyncio.create_task(_poll_metrics())
    else:
        poll_task = None

    tasks = [asyncio.create_task(worker(i)) for i in range(concurrency)]
    await asyncio.gather(*tasks, return_exceptions=True)
    await client.aclose()
    if poll_task:
        poll_task.cancel()
        with contextlib.suppress(Exception):
            await poll_task
    if metrics_url:
        post_metrics = await _scrape_metrics_once(metrics_client, metrics_url)
        await metrics_client.aclose()
        # Compute deltas for http_requests_total by endpoint + status
        for (mname, labels), val in post_metrics.items():
            if mname != "http_requests_total":
                continue
            label_dict = dict(labels)
            if label_dict.get("endpoint") != metrics_endpoint_path:
                continue
            pre_val = pre_metrics.get((mname, labels), 0.0)
            delta = max(0.0, val - pre_val)
            series_deltas[(mname, labels)] = delta

    # Aggregate
    total = len(results)
    successes = sum(1 for r in results if r.ok)
    failures = total - successes
    if total == 0:
        return StepMetrics(concurrency=concurrency, total=0, successes=0, failures=0, rps=0.0, p50_ms=0.0, p90_ms=0.0, p95_ms=0.0, p99_ms=0.0), results

    # Approx RPS = total / duration
    rps = total / max(0.001, duration_s)
    latencies = [r.latency_ms for r in results]
    p50 = _percentile(latencies, 50)
    p90 = _percentile(latencies, 90)
    p95 = _percentile(latencies, 95)
    p99 = _percentile(latencies, 99)

    ttfts = [r.ttft_ms for r in results if r.ttft_ms is not None]
    ttft_p50 = _percentile(ttfts, 50) if ttfts else None
    ttft_p95 = _percentile(ttfts, 95) if ttfts else None

    metrics = StepMetrics(
        concurrency=concurrency,
        total=total,
        successes=successes,
        failures=failures,
        rps=rps,
        p50_ms=p50,
        p90_ms=p90,
        p95_ms=p95,
        p99_ms=p99,
        ttft_p50_ms=ttft_p50,
        ttft_p95_ms=ttft_p95,
    )
    server_metrics = {}
    if series_deltas:
        # Summaries by status
        by_status: Dict[str, float] = {}
        total_server = 0.0
        for (_m, labels), d in series_deltas.items():
            status = dict(labels).get("status", "unknown")
            by_status[status] = by_status.get(status, 0.0) + d
            total_server += d
        server_metrics = {
            "http_requests_total_deltas": {
                "by_status": by_status,
                "total": total_server,
            }
        }
    return metrics, results, server_metrics


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Benchmark tldw_server LLM gateway (/chat/completions)")
    p.add_argument("--base-url", default=os.getenv("TLDW_BASE_URL", "http://127.0.0.1:8000"), help="Server base URL, e.g. http://127.0.0.1:8000")
    p.add_argument("--path", default="/api/v1/chat/completions", help="Endpoint path")
    p.add_argument("--api-key", default=os.getenv("SINGLE_USER_API_KEY"), help="Single-user API key (sent as X-API-KEY)")
    p.add_argument("--bearer", default=os.getenv("TLDW_BENCH_BEARER_TOKEN"), help="Bearer token for multi-user mode (Authorization: Bearer ...)")
    p.add_argument("--provider", default=os.getenv("TLDW_BENCH_PROVIDER", "openai"), help="api_provider to send (e.g. openai, local-llm)")
    p.add_argument("--model", default=os.getenv("TLDW_BENCH_MODEL", "gpt-4o-mini"), help="model to send (OpenAI-compatible)")
    p.add_argument("--stream", action="store_true", help="Use streaming mode (SSE)")
    p.add_argument("--concurrency", nargs="+", type=int, default=[1, 2, 4, 8], help="Concurrency levels to test")
    p.add_argument("--duration", type=int, default=20, help="Duration per step, seconds")
    p.add_argument("--prompt-bytes", type=int, default=256, help="Approximate size of the user message (bytes)")
    p.add_argument("--timeout", type=float, default=60.0, help="Per-request timeout (seconds)")
    p.add_argument("--latency-p99-sla-ms", type=float, default=5000.0, help="Stop if p99 exceeds this (ms)")
    p.add_argument("--max-error-rate", type=float, default=0.10, help="Stop if error rate exceeds this (0-1)")
    p.add_argument("--out", default=None, help="Write JSON results to this file")
    p.add_argument("--metrics-url", default=None, help="Optional Prometheus metrics URL (e.g., http://127.0.0.1:8000/metrics)")
    p.add_argument("--metrics-interval", type=float, default=2.0, help="Metrics poll interval during a step (seconds)")
    p.add_argument("--metrics-endpoint-path", default="/api/v1/chat/completions", help="Endpoint label to filter in http_requests_total")
    return p.parse_args(argv)


def build_auth_headers(api_key: Optional[str], bearer: Optional[str]) -> Dict[str, str]:
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    elif api_key:
        headers["X-API-KEY"] = api_key
    return headers


async def main_async(args: argparse.Namespace) -> int:
    headers = build_auth_headers(args.api_key, args.bearer)
    configure_local_egress(args.base_url)
    if args.metrics_url:
        configure_local_egress(args.metrics_url)
    all_results: List[Dict[str, Any]] = []
    print("Benchmarking", flush=True)
    print(f"  Base URL: {args.base_url}")
    print(f"  Path    : {args.path}")
    print(f"  Provider: {args.provider}")
    print(f"  Model   : {args.model}")
    print(f"  Stream  : {args.stream}")
    print(f"  Duration: {args.duration}s per step")
    print(f"  PromptB : {args.prompt_bytes} bytes")
    print(f"  Cnc List: {args.concurrency}\n")

    for c in args.concurrency:
        metrics, results, server_metrics = await run_step(
            base_url=args.base_url,
            path=args.path,
            headers=headers,
            provider=args.provider,
            model=args.model,
            concurrency=c,
            duration_s=args.duration,
            stream=args.stream,
            prompt_bytes=args.prompt_bytes,
            timeout_s=args.timeout,
            metrics_url=(args.metrics_url or (args.base_url.rstrip("/") + "/metrics")),
            metrics_endpoint_path=args.metrics_endpoint_path,
            metrics_interval_s=args.metrics_interval,
        )
        all_results.append({
            "concurrency": metrics.concurrency,
            "total": metrics.total,
            "successes": metrics.successes,
            "failures": metrics.failures,
            "rps": metrics.rps,
            "p50_ms": metrics.p50_ms,
            "p90_ms": metrics.p90_ms,
            "p95_ms": metrics.p95_ms,
            "p99_ms": metrics.p99_ms,
            "ttft_p50_ms": metrics.ttft_p50_ms,
            "ttft_p95_ms": metrics.ttft_p95_ms,
            "error_rate": metrics.error_rate,
            "server_metrics": server_metrics,
        })

        print(f"Concurrency {c} => total={metrics.total} ok={metrics.successes} err={metrics.failures} rps={metrics.rps:.1f}")
        print(f"  p50={metrics.p50_ms:.0f}ms  p90={metrics.p90_ms:.0f}ms  p95={metrics.p95_ms:.0f}ms  p99={metrics.p99_ms:.0f}ms  err={metrics.error_rate*100:.1f}%")
        if args.stream and metrics.ttft_p50_ms is not None:
            print(f"  ttft_p50={metrics.ttft_p50_ms:.0f}ms  ttft_p95={metrics.ttft_p95_ms:.0f}ms")
        if all_results[-1].get("server_metrics"):
            by_status = all_results[-1]["server_metrics"].get("http_requests_total_deltas", {}).get("by_status", {})
            if by_status:
                summary = ", ".join(f"{k}={int(v)}" for k, v in sorted(by_status.items()))
                print(f"  server http_requests_total (delta): {summary}")

        # Stop criteria
        if metrics.error_rate > args.max_error_rate:
            print(f"Stopping: error rate {metrics.error_rate:.2f} > {args.max_error_rate}")
            break
        if metrics.p99_ms > args.latency_p99_sla_ms:
            print(f"Stopping: p99 {metrics.p99_ms:.0f}ms > {args.latency_p99_sla_ms:.0f}ms")
            break

    if args.out:
        try:
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump({
                    "base_url": args.base_url,
                    "path": args.path,
                    "provider": args.provider,
                    "model": args.model,
                    "stream": args.stream,
                    "duration": args.duration,
                    "prompt_bytes": args.prompt_bytes,
                    "steps": all_results,
                    "generated_at": time.time(),
                }, f, indent=2)
            print(f"Saved results to {args.out}")
        except Exception as e:
            print(f"Failed to save results: {e}")

    return 0


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    try:
        return asyncio.run(main_async(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
