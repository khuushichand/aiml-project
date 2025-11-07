"""
Locust load test for tldw_server Chat API (/api/v1/chat/completions)

Supports closed-loop and an approximate open-loop RPS plan via LoadTestShape.

Environment variables (override defaults):
  - HOST                          : e.g., http://127.0.0.1:8000 (use --host CLI too)
  - TLDW_BENCH_PATH               : default "/api/v1/chat/completions"
  - TLDW_BENCH_PROVIDER           : default "openai"
  - TLDW_BENCH_MODEL              : default "gpt-4o-mini"
  - TLDW_BENCH_STREAM             : "1|true|yes|on" to enable streaming
  - TLDW_BENCH_PROMPT_BYTES       : integer payload size for user message (default 256)
  - SINGLE_USER_API_KEY           : for single-user mode (sent as X-API-KEY)
  - TLDW_BENCH_BEARER_TOKEN       : for multi-user mode (Authorization: Bearer ...)
  - TLDW_TASKS_PER_USER_PER_SEC   : default 1 (used with RPS plan)
  - TLDW_RPS_PLAN                 : comma list of "rps:seconds", e.g. "10:30,20:30,40:60,20:30,10:30"

Run (headless examples):
  locust -f Helper_Scripts/benchmarks/locustfile.py \
    --host http://127.0.0.1:8000 --headless -u 50 -r 10 -t 2m

  # RPS plan (approximate open-loop): 10 rps for 30s, 20 rps for 30s, 40 rps for 60s, 20 rps for 30s, 10 rps for 30s
  TLDW_RPS_PLAN="10:30,20:30,40:60,20:30,10:30" \
  TLDW_TASKS_PER_USER_PER_SEC=1 \
  locust -f Helper_Scripts/benchmarks/locustfile.py --host http://127.0.0.1:8000 --headless -t 3m
"""

from __future__ import annotations

import math
import os
import time
from typing import Any, Dict, Tuple

from locust import HttpUser, task, between, constant_pacing, events, LoadTestShape


BASE_PATH = os.getenv("TLDW_BENCH_PATH", "/api/v1/chat/completions")
PROVIDER = os.getenv("TLDW_BENCH_PROVIDER", "openai")
MODEL = os.getenv("TLDW_BENCH_MODEL", "gpt-4o-mini")
STREAM = os.getenv("TLDW_BENCH_STREAM", "0").strip().lower() in {"1", "true", "yes", "on"}
PROMPT_BYTES = int(os.getenv("TLDW_BENCH_PROMPT_BYTES", "256") or 256)
TASKS_PER_USER_PER_SEC = float(os.getenv("TLDW_TASKS_PER_USER_PER_SEC", "1") or 1)

API_KEY = os.getenv("SINGLE_USER_API_KEY")
BEARER = os.getenv("TLDW_BENCH_BEARER_TOKEN")


def build_headers() -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if BEARER:
        headers["Authorization"] = f"Bearer {BEARER}"
    elif API_KEY:
        headers["X-API-KEY"] = API_KEY
    return headers


def build_payload(prompt_bytes: int = PROMPT_BYTES) -> Dict[str, Any]:
    base = "Please summarize the following text."
    filler_len = max(0, prompt_bytes - len(base))
    filler = (" Lorem ipsum dolor sit amet." * ((filler_len // 28) + 1))[:filler_len]
    content = base + filler
    return {
        "api_provider": PROVIDER,
        "model": MODEL,
        "stream": STREAM,
        "messages": [{"role": "user", "content": content}],
    }


class ChatUser(HttpUser):
    # Constant pacing for predictability; combined with user count gives approximate RPS
    wait_time = constant_pacing(1.0 / max(0.0001, TASKS_PER_USER_PER_SEC))

    @task
    def chat(self):
        headers = build_headers()
        payload = build_payload()

        if not STREAM:
            # Regular non-stream request; Locust captures timing automatically
            self.client.post(BASE_PATH, headers=headers, json=payload, name="chat:nonstream")
            return

        # Streaming: measure TTFT and total time
        start = time.perf_counter()
        ttft_ms = None
        try:
            with self.client.post(
                BASE_PATH,
                headers=headers,
                json=payload,
                stream=True,
                name="chat:stream",
                catch_response=True,
            ) as resp:
                # Iterate SSE lines; first non-empty line marks TTFT
                for line in resp.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    if ttft_ms is None:
                        ttft_ms = (time.perf_counter() - start) * 1000.0
                    # Stop when provider DONE seen
                    s = str(line).strip().lower()
                    if s == "data: [done]" or s == "[done]":
                        break
                # Mark success
                resp.success()
        except Exception as e:
            # Emit a failed request event
            events.request.fire(
                request_type="STREAM",
                name="chat:stream",
                response_time=(time.perf_counter() - start) * 1000.0,
                response_length=0,
                exception=e,
                context={},
            )
            return

        # Emit a synthetic TTFT metric (as separate request type for visibility)
        if ttft_ms is not None:
            events.request.fire(
                request_type="TTFT",
                name="chat:stream_ttft",
                response_time=ttft_ms,
                response_length=0,
                exception=None,
                context={},
            )


def _parse_rps_plan(plan: str) -> Tuple[Tuple[float, int], ...]:
    steps = []
    for part in plan.split(","):
        if not part:
            continue
        if ":" not in part:
            continue
        rps_s, dur_s = part.split(":", 1)
        try:
            rps = float(rps_s)
            dur = int(dur_s)
            steps.append((rps, dur))
        except Exception:
            continue
    return tuple(steps)


class RPSShape(LoadTestShape):
    """Approximate target RPS by adjusting user count over time.

    - Define plan via TLDW_RPS_PLAN="rps:seconds,..."
    - Effective RPS ~= users * TASKS_PER_USER_PER_SEC
    """

    plan = _parse_rps_plan(os.getenv("TLDW_RPS_PLAN", ""))
    start_time = time.time()

    def tick(self):  # type: ignore[override]
        if not self.plan:
            return None
        elapsed = time.time() - self.start_time
        t = 0.0
        for rps, dur in self.plan:
            if elapsed < t + dur:
                # compute desired users to approximate this RPS
                users = int(math.ceil(rps / max(0.0001, TASKS_PER_USER_PER_SEC)))
                spawn_rate = max(1, users)  # spawn quickly to target
                return (users, spawn_rate)
            t += dur
        return None

