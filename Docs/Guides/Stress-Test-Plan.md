# Bifrost Streaming & Load Stress-Test Plan

This document outlines a concrete plan to validate how the gateway (Bifrost) and the tldw_server stack behave under real-world streaming and long-context loads, including failure conditions and high-concurrency traffic.

---

## 1. Scope & Success Criteria

### 1.1 Endpoints & Flows in Scope

- Primary: Streaming chat endpoints (e.g. OpenAI-compatible `/chat/completions`).
- Secondary (optional but recommended):
  - RAG / semantic-cache flows that combine LLM + vector search.
  - Any gateway-managed endpoints where Bifrost handles retries/backoff.

### 1.2 Metrics to Track

Per-request / per-stream:

- Time-to-first-token (TTFT): p50, p90, p95, p99.
- Per-chunk latency (inter-token gaps): p50, p90, p95, p99.
- Total response time and effective output tokens per second.
- Error rates and categories:
  - 4xx (esp. `429`), 5xx, timeouts, client disconnects.

System-level:

- CPU, memory, network utilization for:
  - Bifrost gateway.
  - tldw_server app.
  - LLM backend (vLLM / llama.cpp).
  - Vector DB (e.g. Qdrant) when semantic cache is enabled.
- Open file descriptors, TCP connections, accept queue length.
- Queue depths at the LLM backend and vector index.

### 1.3 Success Criteria (Examples)

These numbers should be refined once baseline measurements exist:

- p99 TTFT below an agreed threshold (e.g. `< 1s`) at target concurrency (e.g. `1–2k` streaming clients).
- p99 inter-chunk latency remains below a threshold (e.g. `< 250ms`) under long-context, long-output load.
- Steady-state error rate under `0.1%` for streaming flows at target load.
- No FD exhaustion, accept queue overflows, or runaway retry storms during failure scenarios.
- Semantic cache hit rate matches expectations and does not introduce a new bottleneck.

---

## 2. Testbed & Instrumentation

### 2.1 Environments

- **Test Environment A (Bifrost path)**:
  - Bifrost gateway in front of tldw_server.
  - Real LLM backend (vLLM or llama.cpp) with at least 128k context and 8k+ output capacity.
  - Vector DB (e.g. Qdrant) configured for semantic caching.
- **Environment B (Baseline/Current path)**:
  - Current production-like path (without Bifrost) for A/B and canary comparisons.

### 2.2 Configurations

- Bifrost:
  - Ability to toggle HTTP/1.1 keep-alive vs HTTP/2 for streaming endpoints.
  - Configuration for backoff with jitter, retries, hedged requests (if used), and circuit breakers.
- LLM backend:
  - Configured with models that support long context (32k–128k) and large outputs (2k–8k tokens).

### 2.3 Observability & Tracing

- Structured logs from Bifrost, tldw_server, LLM backend, and vector DB.
- Metrics:
  - Export Prometheus-style metrics (or equivalent) for:
    - Latency histograms per endpoint and per scenario.
    - Active connections, open FDs, error counts.
    - LLM backend queue depth and utilization.
    - Vector DB query latency and QPS.
- Tracing:
  - OpenTelemetry traces across gateway → tldw_server → LLM → vector DB.
  - Tag spans with:
    - `scenario` (e.g. `short_streaming`, `long_context_128k`, `failure_storm`).
    - `protocol` (`h1`, `h2`).
    - `cache_hit` / `cache_miss` where applicable.

---

## 3. Load Generation Framework

### 3.1 Tooling

Preferred tools:

- `k6` (JavaScript-based scenarios, good for streaming and custom metrics), or
- `wrk2` with Lua scripts, or
- Custom Go/Python harness if deeper control is needed.

Requirements:

- Open and maintain long-lived streaming connections over:
  - HTTP/1.1 with keep-alive.
  - HTTP/2.
- Read responses incrementally (SSE or chunked encoding), capturing:
  - Time to handshake completion.
  - Time to first data/token.
  - Time between successive chunks / SSE events.
- Emit aggregated metrics:
  - Tagged by `scenario`, `protocol`, `prompt_size`, `target_output`, and `concurrency`.

### 3.2 Harness Design

- One primary script per tool (e.g. `Helper_Scripts/load_tests/streaming_load.js` for k6) that:
  - Accepts configuration via environment variables or CLI flags:
    - Target URL.
    - Concurrency level and ramp-up time.
    - Prompt size (tokens/bytes).
    - Target output length (approximate).
    - Protocol (HTTP/1.1 vs HTTP/2).
    - Scenario label.
  - Logs:
    - Raw debug traces for a small subset of clients.
    - Aggregated metrics for analysis and dashboards.

---

## 4. Scenario A: Baseline Streaming & Protocol Comparison

### 4.1 Workload Description

- Prompts:
  - Short/medium prompts: 256–1k tokens.
  - Short/medium outputs: 256–1k tokens.
- Concurrency sweep:
  - Start at 50 clients, then 100, 200, 400, 800, up to 1–2k concurrent streaming clients if possible.

### 4.2 Experiments

- For each concurrency level:
  - Run with HTTP/1.1 keep-alive.
  - Run with HTTP/2.
- Duration:
  - Each run should have:
    - Ramp-up (e.g. 2–5 minutes).
    - Steady-state phase (e.g. 10–20 minutes).

### 4.3 Measurements & Outputs

- Per protocol and concurrency:
  - TTFT: p50/p90/p95/p99.
  - Inter-chunk latency: p50/p90/p95/p99.
  - Error rates by status code.
- Visualizations:
  - TTFT vs concurrency for HTTP/1.1 vs HTTP/2.
  - p99 inter-chunk latency vs concurrency.
  - Error rates vs concurrency.

### 4.4 Goals

- Identify:
  - Which protocol yields lower tail latency at target concurrency.
  - Concurrency levels where tail latency degrades sharply.

---

## 5. Scenario B: Long-Context & Large-Output Streaming

### 5.1 Workload Description

- Long prompts:
  - 32k, 64k, and 128k token prompts.
- Large outputs:
  - 2k, 4k, and 8k tokens.
- Concurrency:
  - Lower but realistic: 10, 20, 50, 100, 200 concurrent streaming clients.

### 5.2 Experiments

- For each prompt size and output target:
  - Run under HTTP/2 (preferred for long-lived streams).
  - Optional: compare against HTTP/1.1 at selected points.
- Ensure:
  - LLM backend is configured to accept the target sequence length.
  - GPU/CPU utilization and memory are monitored.

### 5.3 Measurements & Outputs

- TTFT and inter-chunk latency distributions at each prompt size.
- LLM backend:
  - GPU utilization, CPU, and memory usage.
  - Queue depth, if exposed.
- Stability indicators:
  - Any OOM events, throttling, or internal queue saturation.

### 5.4 Goals

- Determine safe operating envelope for long-context streams:
  - Maximum long-context concurrency with acceptable p99 TTFT and inter-chunk latency.
  - Whether Bifrost introduces additional overhead or mitigates backend variability.

---

## 6. Scenario C: High Concurrency & Connection Churn

### 6.1 Workload Description

- Mixed prompts:
  - Majority short/medium prompts with small/medium outputs.
  - Optional minority of long-context requests to simulate real-world skew.
- Concurrency:
  - 1k–2k concurrent clients.
  - Emphasize high churn: frequent disconnects and reconnects.

### 6.2 Experiments

- Patterns:
  - **Steady-state**:
    - Ramp up from 0 to target concurrency.
    - Maintain for 15–30 minutes.
  - **Churn**:
    - Randomly terminate a percentage of streams early.
    - Introduce reconnect behavior with random delays.
    - Combine with ramp patterns (e.g. sawtooth load).

### 6.3 Measurements & Outputs

- Bifrost:
  - CPU, memory, and goroutine/thread counts (depending on implementation).
  - Number of active connections, connection churn rate.
  - Open FDs and any FD-related errors.
- OS/kernel:
  - Accept queue length, SYN backlog, retransmits.
  - Any indications of hitting `somaxconn` or FD limits.
- Latency:
  - TTFT and inter-chunk latency under churn.

### 6.4 Goals

- Confirm:
  - Bifrost handles high concurrency and churn without leaks or runaway resource usage.
  - No crashes or degraded behavior due to rapid connection cycling.

---

## 7. Scenario D: Failure Storms & Resilience Behavior

### 7.1 Fault Injection Strategy

- Introduce fault injection between Bifrost and the providers (or within the LLM/HTTP client layer):
  - Configurable random failure rates:
    - `429` and `5xx` with tunable probabilities.
  - Burst failures:
    - E.g. 50% `5xx` for 30–60 seconds at a time.
  - Simulated timeouts:
    - Delayed responses that exceed client timeouts.

### 7.2 Client & Gateway Behaviors Under Test

- Backoff with jitter:
  - Confirm exponential (or appropriate) backoff and randomness in retry scheduling.
- Hedged requests:
  - If enabled, verify:
    - Duplicate requests are limited.
    - Slower hedges are correctly cancelled once a winner responds.
- Circuit breakers:
  - Ensure they:
    - Open quickly when backends are unhealthy.
    - Prevent retry storms.
    - Transition to half-open and closed states correctly after recovery.

### 7.3 Measurements & Outputs

- Number and rate of retries, by status code and scenario.
- Distribution of backoff delays and jitter.
- Number of hedged requests per logical request.
- End-user error rates and latency during failure storms.

### 7.4 Goals

- Demonstrate:
  - Error storms at the provider layer do not melt the gateway or upstream providers.
  - Users see controlled degradation (clear errors, bounded latency), not cascading failures.

---

## 8. Scenario E: Semantic Cache & Vector Index Behavior

### 8.1 Workload Description

- Semantic cache enabled with a vector DB (e.g. Qdrant).
- Generated test data:
  - Prompts arranged to achieve predictable cache hit rates:
    - ~0% (cold cache).
    - ~50% (mixed).
    - ~90% (hot cache).

### 8.2 Experiments

- For each target hit rate:
  - Run a streaming workload at moderate concurrency (e.g. 100–500 clients).
  - Ensure:
    - Requests are tagged with cache hit/miss outcomes.
    - LLM is invoked only when expected (miss path).

### 8.3 Measurements & Outputs

- True cache hit rate vs expected.
- Latency breakdown:
  - Embedding generation time.
  - Vector index query time (Qdrant).
  - Miss path latency (full LLM call).
  - Overall TTFT and streaming latency for hits vs misses.
- Vector DB metrics:
  - Query QPS, p99 latency.
  - CPU, memory utilization.

### 8.4 Goals

- Confirm:
  - Semantic caching improves effective latency and/or cost.
  - Vector index does not become the new bottleneck under realistic load.

---

## 9. OS, Kernel, and Infrastructure Tuning

### 9.1 OS-Level Tuning

- File descriptors:
  - Increase `ulimit -n` and `fs.file-max` to support target concurrent connections.
- TCP and backlog:
  - Tune `net.core.somaxconn`, `net.ipv4.tcp_max_syn_backlog`.
  - Consider TIME-WAIT and keepalive settings appropriate to load profile.
- Socket options:
  - Enable `SO_REUSEPORT` where applicable to allow multiple workers to share the same port.

### 9.2 Infrastructure Choices

- Instance types:
  - Avoid underpowered “t-class” instances (credit-based bursting) for sustained load.
  - Choose instances with sufficient CPU, memory, and NIC bandwidth for target concurrency.
- Network:
  - Verify available bandwidth and RTT; ensure no network bottlenecks at load generator or gateway.

### 9.3 Re-Validation

- After applying OS/infra tuning:
  - Re-run the heaviest scenarios:
    - Long-context (Scenario B).
    - High concurrency & churn (Scenario C).
    - Failure storms (Scenario D).
  - Confirm:
    - Improved tail latency and stability.
    - No resource exhaustion or kernel errors in logs.

---

## 10. Canary Rollout with Real Traffic

### 10.1 Traffic Mirroring

- Use the API gateway (e.g. Kong) to:
  - Mirror a small percentage of real traffic (e.g. 5%) to the Bifrost path.
  - Maintain the existing path as the primary user-facing route.
  - Discard mirrored responses so users are unaffected.

### 10.2 Monitoring & Comparison

- Compare between current path and Bifrost path:
  - Tail latency (p95/p99) per endpoint.
  - Error codes and rates.
  - Provider cost / token usage if available.
- Use OpenTelemetry:
  - Correlate mirrored requests via trace IDs.
  - Measure end-to-end spans and identify any additional overhead.

### 10.3 Ramp-Up & Decision

- If metrics remain healthy at 5%:
  - Increase to 10–20% and repeat monitoring.
- Decision:
  - Determine whether Bifrost meets or exceeds the success criteria defined in Section 1.
  - If yes, plan a controlled swap to make Bifrost the primary path.

---

## 11. Artifacts, Automation & Maintenance

### 11.1 Artifacts

- Store all load-test scripts and configurations under:
  - `Helper_Scripts/load_tests/` (or a similar dedicated directory).
- Document:
  - Exact versions of tools (k6/wrk2/etc.).
  - Model names and configurations used for LLM backends.
  - Key system and OS configuration values during tests.

### 11.2 Automation

- Provide simple commands to rerun key scenarios:
  - e.g. `make load-test-scenario-a`, `make load-test-scenario-b`, etc. (if using `make`).
- Integrate critical, lightweight scenarios into CI/CD where feasible:
  - Smoke-level load tests on new gateway or LLM configurations.

### 11.3 Baselines & Regression Detection

- Capture and store baseline results:
  - TTFT and p99 latency curves.
  - Error rates and resource usage profiles.
- On significant changes (gateway, model, config):
  - Re-run a subset of scenarios and compare against baselines.
  - Investigate any regressions in tail latency, error rates, or resource footprint.

---

## 12. Next Steps

Immediate next actions to start implementation:

1. Choose the primary load tool (k6, wrk2, or custom harness) and create a minimal streaming test against the current `/chat/completions` endpoint.
2. Stand up the Bifrost + tldw_server + LLM backend environment with basic observability enabled.
3. Implement Scenario A (baseline streaming & protocol comparison) and record initial results.
4. Iterate on OS and configuration tuning before moving to long-context and failure scenarios.
