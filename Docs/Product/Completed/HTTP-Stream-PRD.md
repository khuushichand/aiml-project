PRD: HTTP Client Consolidation

  - Owner: Platform / Core
  - Version: 1.0
  - Status: Completed (Stage 7)

  Summary of Outcomes

  - Centralization: 100% of outbound HTTP in app/core and app/services now uses centralized helpers/factories (documented exceptions appear only in documentation examples).
  - Security: Egress enforced per hop and on proxies (deny-by-default allowlist). Optional TLS minimum version and env-driven leaf-cert pinning supported and tested.
  - Reliability: Unified retries with decorrelated jitter and Retry-After support; no auto-retry after first body byte for streaming.
  - Streaming: Standardized SSE helper with deterministic cancellation and final [DONE] ordering; added stress tests for high-chunk scenarios.
  - Downloads: Atomic rename, checksum and Content-Length validation, resume support; strict Content-Type enabled at call sites where required (audio path enabled).
  - Observability: Structured outbound logs; metrics exposed (http_client_requests_total, http_client_request_duration_seconds_bucket, http_client_retries_total, http_client_egress_denials_total); optional traceparent injection for OTel.
  - Monitoring: Grafana dashboard JSON and Prometheus alert rules added (Docs/Monitoring/http_client_grafana_dashboard.json, Docs/Monitoring/http_client_alerts_prometheus.yaml).
  - Developer experience: Config and .env examples updated (PROXY_ALLOWLIST, TLS flags, HTTP_CERT_PINS); comprehensive MockTransport-based tests for JSON helpers, redirects, proxies, downloads, SSE parsing, TLS, and perf microbenches (PERF=1).
  - CI enforcement: HTTP usage guard is blocking and passing; prevents direct httpx/requests usage outside approved core files.

  How to Monitor

  - Prometheus metrics endpoints (gated by route toggles):
      - Prometheus text: GET `/metrics`
      - JSON metrics: GET `/api/v1/metrics`
      - Quick checks:
        - `curl -s http://127.0.0.1:8000/metrics | head`
        - `curl -s http://127.0.0.1:8000/api/v1/metrics`
  - OpenTelemetry (optional):
      - Install exporters (see `tldw_Server_API/app/core/Metrics/README.md`).
      - Example env:
        - `OTEL_SERVICE_NAME=tldw_server`
        - `OTEL_SERVICE_VERSION=1.0.0`
        - `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317`
        - `OTEL_EXPORTER_OTLP_PROTOCOL=grpc`
        - `OTEL_METRICS_EXPORTER=prometheus,otlp`
        - `OTEL_TRACES_EXPORTER=otlp`
      - Server logs indicate OTEL availability on startup.
  - Dashboards & Alerts:
      - Grafana: import `Docs/Monitoring/http_client_grafana_dashboard.json`.
      - Prometheus: load alert rules from `Docs/Monitoring/http_client_alerts_prometheus.yaml`.

  Troubleshooting

  - Egress denials (NetworkError/EgressPolicyError):
      - Confirm host and scheme are allowed by the server’s egress policy and allowlists.
      - Redirects are re‑validated per hop; check each `Location` host in the chain.
      - Proxies are deny‑by‑default; set `PROXY_ALLOWLIST` (hosts or URLs) if a proxy is required.
      - Metrics: `http_client_egress_denials_total{reason}` increments with the reason label.
  - Proxy blocked or ignored:
      - Central client validates proxies against `PROXY_ALLOWLIST`. Dict form (`{"http": "...", "https": "..."}`) is supported.
      - When `HTTP_TRUST_ENV=false` (default), system proxies are ignored.
  - Redirect loops or missing Location:
      - Loops surface as `RetryExhaustedError` or `NetworkError("Invalid/without Location")` depending on hop.
      - Cap is `HTTP_MAX_REDIRECTS` (default 5). Validate final URL/content‑type matches expectations.
  - HTTP/2 disabled unexpectedly:
      - If `h2` is not installed, factories automatically downgrade to HTTP/1.1.
      - Install `httpx[h2]` to re‑enable HTTP/2; no code change needed.
  - JSON decode errors:
      - Helpers validate `Content-Type: application/json`. Pass `require_json_ct=False` (or `accept_mismatch=True` at call sites that permit it) to allow decoding regardless of header.
      - Large payloads: enforce or raise `HTTP_JSON_MAX_BYTES` at call sites using `max_bytes`.
  - Streaming stalls/DONE ordering:
      - SSE helper never retries after first body byte; cancellation propagates via `CancelledError`.
      - Unified path emits a single final `[DONE]`; for issues check provider adapters and heartbeat intervals.
  - TLS pinning/min-version failures:
      - Pinning uses leaf cert SHA‑256 hashes from `HTTP_CERT_PINS` (`host=pinA|pinB,...`).
      - Enforce min version via `TLS_ENFORCE_MIN_VERSION=true` and `TLS_MIN_VERSION=1.2|1.3`.
  - Downloads resume anomalies:
      - If server ignores `Range` and returns 200, downloader overwrites the partial file with full content.
      - Use `checksum`/`Content-Length` validation and optional `require_content_type` for strictness.

  Overview

  - Unifying principle: Every outbound call is the same thing — an egress-validated HTTP request with retries.
  - Objective: Consolidate all outbound HTTP across the codebase onto a single, secure, configurable client layer with consistent retry/backoff, timeouts, and egress enforcement.

  Problem

  - Duplication and inconsistency:
      - Central client underused: tldw_Server_API/app/core/http_client.py:1
      - Local LLM utils async client + custom retries: tldw_Server_API/app/core/Local_LLM/http_utils.py:41
      - TTS allocates raw httpx.AsyncClient pools: tldw_Server_API/app/core/TTS/tts_resource_manager.py:200
      - Summarization uses requests + urllib3.Retry: tldw_Server_API/app/core/LLM_Calls/Summarization_General_Lib.py:629
      - Streaming helpers mix requests and httpx directly: tldw_Server_API/app/core/LLM_Calls/streaming.py:18
  - Impact:
      - Inconsistent timeouts, retries, proxy handling.
      - Partial/uneven enforcement of egress/SSRF policy (policy engine exists at tldw_Server_API/app/core/Security/egress.py:146).
      - Hard to audit and monitor egress uniformly.

  Goals

  - One canonical way to:
      - Create HTTP clients (create_client / create_async_client)
      - Perform requests (fetch/afetch, JSON helpers, streaming, downloads)
  - Always enforce egress policy for every outbound call.
  - Centralize retry/backoff with sensible defaults and per-call overrides.
  - Standardize timeouts, proxy handling (trust_env=False by default), HTTP/2 preference.
  - Preserve or improve performance (keep-alive, pooling).
  - Provide minimal, consistent logging and metrics for egress.

  Non‑Goals

  - Rewriting provider-specific business logic.
  - Changing public API contracts beyond consistent network behavior.
  - Introducing new network dependencies by default (curl backend remains optional).
  - Global concurrency/rate limiting helper; tracked separately and out of scope for this PRD.

  Stakeholders

  - Platform/Core, Security, LLM Integrations, Media Ingestion, TTS, RAG/Search.

  Current State

  - Central client fully implemented with egress enforcement, retries, SSE/bytes streaming, and downloads: tldw_Server_API/app/core/http_client.py
  - Egress policy engine: tldw_Server_API/app/core/Security/egress.py
  - Broad migration complete across core/services:
      - LLM providers (non‑streaming + streaming): OpenAI, Anthropic, Cohere, Groq, OpenRouter, HuggingFace, DeepSeek, Mistral, Google.
      - WebSearch, Third_Party sources, Evaluations loaders, and OCR backends centralized to helpers.
      - Audio/document downloads consolidated via download/adownload with checksum/length validation; audio path enforces MIME.
  - Observability:
      - Per‑request structured logs; http_client_* metrics registered (requests_total, duration histogram, retries_total, egress_denials_total).
      - Optional OpenTelemetry spans and traceparent injection in place.
      - Grafana dashboard and Prometheus alerts provided under Docs/Monitoring/.
  - Security:
      - TLS minimum version enforcement (optional) and env‑driven leaf‑cert pinning map (HTTP_CERT_PINS) supported and tested.
  - CI enforcement:
      - HTTP usage guard is blocking; direct requests/httpx usage outside approved core files is prevented.

  Proposed Solution

  - Expand http_client with unified, secure primitives and require all modules to use them:
      - Factories: create_client(...), create_async_client(...) (timeouts, limits, base_url, proxies, trust_env default false)
      - Request helpers:
          - Sync: fetch(...), fetch_json(...), stream(...)
          - Async: afetch(...), afetch_json(...), astream(...)
          - Download: download(...), adownload(...) (streaming, atomic rename)
      - Retry/backoff: centralized policy with exponential backoff + jitter, Retry-After support, idempotency-aware retry by default.
      - Egress: mandatory evaluate_url_policy(url) check inside all helpers prior to network I/O.
      - Observability: log retries with redacted headers; optional metrics hooks.

  Functional Requirements

  - Client factories
      - Accept: timeout, limits (httpx.Limits), base_url, trust_env (default false), proxies, http2=True, http3=False.
      - Return httpx.Client / httpx.AsyncClient (or optional curl backend for sync fetch path already supported by fetch).
      - Defaults:
          - Timeout: connect=5s, read=30s, write=30s, pool=30s.
          - Limits: max_connections=100, max_keepalive_connections=20.
  - Requests
      - fetch/afetch: method, url, headers, params, json, data, files, timeout, allow_redirects, proxies, retry.
      - fetch_json/afetch_json: JSON parse with clear errors on non-JSON or invalid payloads; validate Content-Type is application/json unless accept_mismatch=True; optional max_bytes guard.
      - Streaming helpers:
          - astream_bytes(...): async iterator of raw bytes/chunks.
          - astream_sse(...): async iterator of parsed SSE events with fields (event, data, id, retry).
      - download/adownload: stream to temp path and atomic rename, clean partial on failure.
      - Headers/UA: standardize User-Agent as "tldw_server/<version> (<component>)" with per-call override; auto-inject X-Request-Id when present in context.
      - Cookies: no first-class cookie jar helpers; callers may attach cookies via client configuration if needed.
  - Egress policy
      - Call evaluate_url_policy(url) first; deny with clear error when disallowed.
      - Honor env-based allow/deny lists, scheme/port rules, and private/reserved IP blocking.
      - Enforce at all phases: evaluate original URL, each redirect hop (see redirect policy), and the resolved IP post-DNS; deny on scheme/host/IP violations.
      - Apply policy to proxies as well; only allow explicitly allowlisted proxies.
  - Redirect policy
      - Limit redirects to 5; re-check egress policy for each hop and validate the final URL and (optionally) expected Content-Type.
  - Retry/backoff
      - Defaults: attempts=3, exponential backoff with decorrelated jitter; base 250ms, cap 30s.
      - Retry on: 408, 429, 500, 502, 503, 504, and connect/read timeouts.
      - Respect Retry-After and provider-specific backoff headers; do not retry unsafe methods unless retry_on_unsafe=True.
      - Streams: never auto-retry once any response body bytes have been consumed; allow optional user callback to opt in for segmented protocols.
  - Observability
      - Structured logs: request_id, method, scheme, host, path, status_code, duration_ms, attempt, retry_delay_ms, exception_class; redact sensitive headers and query params by default.
      - Metrics (Prometheus style): http_client_requests_total{method,host,status}, http_client_request_duration_seconds_bucket, http_client_retries_total{reason}, http_client_egress_denials_total{reason}.
      - Optional OpenTelemetry: inject/extract trace context (traceparent) and emit spans for requests and retries.
  - JSON helpers
      - Enforce Content-Type validation by default; configurable via accept_mismatch flag; optional max_bytes limit for decode.
  - Download safety
      - Optional checksum validation (sha256, configurable algorithm), Content-Length validation, and disk quota guard.
      - Optional Range-resume capability behind a feature flag when server supports Range requests.

  Non‑Functional Requirements

  - Security by default: fail closed on egress evaluation errors; trust_env=False default.
  - Performance: reuse pooled connections; support HTTP/2; ensure no regression in TTS/LLM throughput.
  - Testability: functions accept injected clients and are easily mockable.
  - Lifecycle: document safe client usage patterns (e.g., one AsyncClient per event loop for long‑lived services); provide context managers and a shared‑pool accessor for high‑QPS modules (TTS/LLM).
  - Transport/TLS:
      - HTTP/2 enabled by default; HTTP/3 (QUIC) supported behind a flag and only where the stack supports it.
      - TLS minimum version enforcement is optional (disabled by default) and configurable (e.g., TLS 1.2+).
      - Optional certificate pinning (SPKI SHA‑256 fingerprints) supported but off by default.

  API Additions (in http_client)

  - Types
      - RetryPolicy: attempts, backoff_base_ms, backoff_cap_s, retry_on_status, retry_on_methods, respect_retry_after.
      - TLSOptions (optional): enforce_min_version: bool, min_version: {"1.2","1.3"}, cert_pins_spki_sha256: Optional[Set[str]].
  - Sync
      - def fetch(..., retry: Optional[RetryPolicy] = None) -> HttpResponse
      - def fetch_json(..., retry: Optional[RetryPolicy] = None, *, require_json_ct: bool = True, max_bytes: Optional[int] = None) -> Dict[str, Any]
      - def stream_bytes(..., retry: Optional[RetryPolicy] = None) -> Iterator[bytes]
      - def download(..., *, checksum: Optional[str] = None, checksum_alg: str = "sha256", resume: bool = False, retry: Optional[RetryPolicy] = None) -> Path
  - Async
      - async def afetch(..., retry: Optional[RetryPolicy] = None) -> HttpResponse
      - async def afetch_json(..., retry: Optional[RetryPolicy] = None, *, require_json_ct: bool = True, max_bytes: Optional[int] = None) -> Dict[str, Any]
      - async def astream_bytes(..., retry: Optional[RetryPolicy] = None) -> AsyncIterator[bytes]
      - async def astream_sse(..., retry: Optional[RetryPolicy] = None) -> AsyncIterator[SSEEvent]
      - async def adownload(..., *, checksum: Optional[str] = None, checksum_alg: str = "sha256", resume: bool = False, retry: Optional[RetryPolicy] = None) -> Path
  - Exceptions
      - EgressPolicyError, NetworkError, RetryExhaustedError, JSONDecodeError, StreamingProtocolError, DownloadError. Wrap underlying httpx errors while preserving safe context (no secrets).

  Configuration

  - Env defaults (override per-call)
      - HTTP_CONNECT_TIMEOUT (float, default 5.0)
      - HTTP_READ_TIMEOUT (float, default 30.0)
      - HTTP_WRITE_TIMEOUT (float, default 30.0)
      - HTTP_POOL_TIMEOUT (float, default 30.0)
      - HTTP_MAX_CONNECTIONS (int, default 100)
      - HTTP_MAX_KEEPALIVE_CONNECTIONS (int, default 20)
      - HTTP_RETRY_ATTEMPTS (int, default 3)
      - HTTP_BACKOFF_BASE_MS (int, default 250)
      - HTTP_BACKOFF_CAP_S (int, default 30)
      - HTTP_MAX_REDIRECTS (int, default 5)
      - PROXY_ALLOWLIST (comma-separated URLs/hosts)
      - HTTP_JSON_MAX_BYTES (int, optional; disable by default)
      - HTTP_TRUST_ENV (bool, default false)
      - HTTP_DEFAULT_USER_AGENT (string, default “tldw_server/<version> httpx”)
      - HTTP3_ENABLED (bool, default false)
      - TLS_ENFORCE_MIN_VERSION (bool, default false)
      - TLS_MIN_VERSION (str, default "1.2")
      - TLS_CERT_PINS_SPKI_SHA256 (comma-separated pins; optional)

  Security & Egress

  - Centralized guard: evaluate_url_policy in every helper prior to I/O (tldw_Server_API/app/core/Security/egress.py:146).
  - Deny unsupported schemes, disallowed ports, denylisted hosts, and private/reserved IPs unless env allows.
  - Maintain SSRF-safe defaults; proxies only when explicitly configured.

  Observability & Metrics

  - Metrics (labels include method, status, backend):
      - egress_requests_total
      - egress_request_duration_ms
      - egress_retries_total
      - egress_policy_denied_total
  - Logging: INFO on final failure, DEBUG on retries, with redacted headers.

  Migration Plan

  - Phase 1: Foundations
      - Implement afetch/astream/fetch_json and retry policy in http_client.
      - Add env/config plumbing; unit tests (retry matrix, egress deny, JSON errors, streaming close, downloads).
  - Phase 2: Early Adopters
      - Local LLM: replace request_json and client factory with create_async_client + afetch_json (tldw_Server_API/app/core/Local_LLM/http_utils.py:41).
      - TTS: construct clients via create_async_client(limits=...) in pool (tldw_Server_API/app/core/TTS/tts_resource_manager.py:200).
      - HuggingFace local API calls: move to afetch (tldw_Server_API/app/core/LLM_Calls/huggingface_api.py:105).
  - Phase 3: Broad Replacement
      - Summarization lib: replace requests.Session + Retry usages with fetch/afetch (tldw_Server_API/app/core/LLM_Calls/Summarization_General_Lib.py:629).
      - Ingestion/OCR/Audio downloads: use download/adownload (tldw_Server_API/app/core/Ingestion_Media_Processing/Audio/Audio_Files.py:222, OCR/backends/*).
      - Streaming: standardize on astream + existing SSE normalizers (tldw_Server_API/app/core/LLM_Calls/streaming.py:18).
  - Phase 4: Cleanup
      - Remove deprecated helpers and ad‑hoc clients.
      - Update docs; add integration tests for rate limits and egress denials.

  What Will Be Removed

  - Local retry/backoff and session code (non-exhaustive):
      - tldw_Server_API/app/core/Local_LLM/http_utils.py:47
      - tldw_Server_API/app/core/TTS/tts_resource_manager.py:200
      - tldw_Server_API/app/core/LLM_Calls/Summarization_General_Lib.py:629
      - Other scattered HTTPAdapter(Retry(...)) blocks and raw httpx instantiations in core/services.

  Testing Strategy

  - Unit tests
      - Egress: allowed/denied schemes, ports, hosts, private/reserved IP; DNS resolution IP checks; per-redirect hop enforcement; proxy allowlist.
      - Retry/backoff: attempts, decorrelated jitter bounds, Retry-After (delta-seconds and HTTP-date) behavior, status code matrix, idempotency.

  Status Update (current)

  - Summarization providers migrated to centralized helpers:
      - OpenAI, Anthropic (previously), now Cohere, Groq, OpenRouter, HuggingFace, DeepSeek, Mistral, Google.
      - Streaming paths use centralized client streams with no auto-retry after first byte.
  - Workflows + notifications:
      - Webhook DLQ and replay paths now use create_client/create_async_client and afetch/fetch for egress enforcement and retries.
      - Notification webhook sender switched to fetch.
  - Ingestion/audio:
      - External transcription provider now uses afetch with create_async_client; downloads previously consolidated to download/adownload.
      - Audio downloads now enforce strict content‑type; document handlers keep HEAD‑time MIME checks.
  - Docs updated:
      - README and Config_Files/README document streaming (astream_sse) and download (download/adownload) usage examples.
      - JSON: success, bad JSON, wrong content-type, max_bytes enforcement.
      - Streaming: normal end, mid-stream error surfaced, cancellation propagation (CancelledError), proper close; SSE parsing.
      - Download: atomic rename, partial cleanup, checksum and Content-Length validation, basic Range-resume (when enabled).
      - Observability: metrics counters/labels update; structured logs redact secrets; optional OTel spans emitted when enabled.
      - Monitoring: Grafana dashboard JSON and Prometheus alert rules for http_client_* metrics added.
  - What Changed (recent):
      - Added TLS minimum-version enforcement in client factories with unit tests; optional leaf-cert pinning map via HTTP_CERT_PINS and tests.
      - Added SSE stress test to validate final [DONE] ordering and cancellation under high-chunk conditions; improved unified SSE stability.
      - Added performance checks (optional, PERF=1) for non‑streaming, streaming, and download hot paths using httpx MockTransport.
      - Provided Grafana dashboard JSON and Prometheus alert rules for http_client_* metrics (requests_total, duration histogram, retries_total, egress_denials_total).
  - Integration tests
      - Swap target modules to central helpers; validate same behavior via mock servers and test markers already used in repo.
      - Redirect chains with mixed hosts; ensure egress rechecks and final content-type validation.

  Risks & Mitigations

  - Behavior drift on retries for non-idempotent methods
      - Default: do not retry unsafe methods; require explicit opt-in.
  - Throughput regressions (TTS/LLM)
      - Preserve Limits and keep-alive; validate with benchmarks.
  - Over-enforcement blocking legitimate calls
      - Ensure env allowlists; provide clear error messages and tests.

  Dependencies

  - httpx (existing), optional curl_cffi for sync impersonation path.
  - Loguru and metrics registry for observability (already present).
  - Optional cryptography for SPKI SHA‑256 certificate pinning utilities (only when pinning is enabled).

  Acceptance Criteria

  - 100% of outbound HTTP in app/core and app/services uses http_client helpers or factories (documented exceptions only).
  - All requests evaluate egress policy prior to I/O and fail closed when denied.
  - Consistent retry/backoff observed across modules; tests cover 429/5xx and network failures.
  - TTS/Local LLM throughput and latency not degraded.
  - Duplicated retry/session code removed or shimmed with deprecation warnings.

  Milestones & Timeline

  - Week 1: Implement APIs + unit tests in http_client; land without consumers.
  - Weeks 2–3: Early adopters and broad replacement (module-by-module PRs).
  - Week 4: Cleanup, docs, final integration tests.

  Open Questions

  - Circuit breaker per host? Config hints exist; defer unless needed by SLOs.
  - Dev ergonomics: rely on egress.py profile selection (permissive vs strict) or add a dedicated dev override?
  - curl_cffi impersonation defaults: remain opt-in at call sites?

  Appendix: Code References

  - Central client (to expand): tldw_Server_API/app/core/http_client.py:1
  - Egress policy: tldw_Server_API/app/core/Security/egress.py:146
  - Duplicates to consolidate:
      - tldw_Server_API/app/core/Local_LLM/http_utils.py:41
      - tldw_Server_API/app/core/TTS/tts_resource_manager.py:200
      - tldw_Server_API/app/core/LLM_Calls/Summarization_General_Lib.py:629
      - tldw_Server_API/app/core/LLM_Calls/streaming.py:18

  Implementation Plan (Detailed)

  - Stage 0: Spec Finalization
      - Confirm PRD decisions for TLS min version (optional), HTTP/3 flag, proxy allowlist, streaming contracts, and exception taxonomy.
      - Document configuration keys and defaults; align README and Config_Files/README.md.
      - Success: PRD updated; config keys listed; stakeholders sign-off.

  - Stage 1: Core API Foundations
      - Implement unified helpers in http_client:
          - Factories: create_client, create_async_client (timeouts, limits, headers, http2, trust_env, proxies validation).
          - Requests: fetch/afetch with manual redirect handling; egress enforced per hop and on proxies.
          - JSON: fetch_json/afetch_json with content-type validation and max_bytes guard.
          - Streaming: astream_bytes and astream_sse with cancellation propagation; no auto-retry post-first byte.
          - Downloads: download/adownload with atomic rename, checksum/length validation, optional resume.
          - Exceptions: EgressPolicyError, NetworkError, RetryExhaustedError, JSONDecodeError, StreamingProtocolError, DownloadError.
      - Observability:
          - Structured retry logs (redacted headers) and basic request duration metrics.
          - Optional traceparent injection from active span.
      - Security:
          - Enforce egress on original URL, redirect hops, and post-DNS IP; proxy allowlist (deny-by-default).
      - Success: Helpers compile with tests; metrics registered; defaults respected via env.

  - Stage 2: Unit Tests and Validation
      - Add httpx.MockTransport tests covering: retry/backoff, egress deny, JSON validation, streaming SSE parse, download checksum/length, cancellation propagation.
      - Add negative cases: redirect loops, redirect without Location, private/reserved IPs, proxy not allowlisted.
      - Add metrics smoke tests to ensure counters/histograms increment and redact secrets in logs.
      - Success: >90% coverage of http_client; green in CI across supported Python/httpx versions.

  - Stage 3: Early Adopters Integration
      - Replace direct HTTP calls in:
          - Local LLM utilities: `tldw_Server_API/app/core/Local_LLM/http_utils.py` → create_async_client + afetch_json.
          - TTS resource manager: `tldw_Server_API/app/core/TTS/tts_resource_manager.py` → pooled create_async_client with limits.
          - HuggingFace/local API callers: `tldw_Server_API/app/core/LLM_Calls/huggingface_api.py` → afetch.
      - Add adapters/shims where needed; keep behavior parity for timeouts and headers.
      - Success: Modules work under new helpers; basic perf checks show no regressions.

  - Stage 4: Broad Migration
      - Summarization: migrate `tldw_Server_API/app/core/LLM_Calls/Summarization_General_Lib.py` from requests+Retry to fetch/afetch.
      - Ingestion/Audio/OCR downloads: consolidate on download/adownload across ingestion backends and audio pipelines.
      - Streaming call sites: standardize on astream_sse + existing SSE normalizers in `tldw_Server_API/app/core/LLM_Calls/streaming.py`.
      - Success: Majority (>80%) of outbound HTTP uses helpers; regression tests pass.

  - Stage 5: Observability & Security Hardening — Completed
      - Ensure per-request structured logs include request_id, method, host, status, duration.
      - Wire optional OpenTelemetry spans for client calls and retries; confirm traceparent propagation to providers that support it.
      - Verify egress denials produce clear errors and increment `http_client_egress_denials_total` with reason.
      - Success: Dashboards reflect client metrics; SLO alerts (if any) unaffected.

  What Changed (Stage 5)

  - Added per-request outbound log lines in `http_client` on success and terminal failures with fields: `request_id`, `method`, `scheme`, `host`, `path`, `status_code`, `duration_ms`, `attempt`, `retry_delay_ms`, `exception_class`.
  - Trace context: `traceparent` injection already present; retry events (`http.retry`) annotated on spans.
  - Egress denials: now increment `http_client_egress_denials_total` with a reason label; tests assert message clarity and counter increments.
  - TLS security: optional minimum TLS version enforcement and per-host leaf-cert SHA-256 pinning supported by factories and enforced pre-I/O when configured.

  - Stage 6: Documentation & Examples — Completed
      - Update developer docs with examples for fetch_json, SSE streaming, and downloads with checksum.
      - Document configuration keys in Config_Files/README.md and .env templates; add migration tips for requests→httpx.
      - Success: Docs merged; example snippets validated.

  - Stage 7: Cleanup & Enforcement — Completed
      - Deprecated local retry/session code and ad‑hoc clients removed or refactored to use centralized helpers.
      - CI guard to block direct `requests`/`httpx` usage outside approved core files is active and passing in CI.
      - Success: 100% of outbound HTTP in app/core and app/services uses centralized helpers/factories (documented exceptions are examples in docs only).

  - Rollout & Risk Mitigation
      - Canary: enable helpers per-module behind lightweight toggles if needed; default to safe timeouts and trust_env=False.
      - Fallback: ability to reduce http2 to http1 automatically if `h2` unavailable; keep curl backend opt-in.
      - Rollback: revert module migrations individually (PR-by-PR) if regressions observed.

  - Deliverables
      - Code: unified http_client helpers + exceptions; module migrations; metrics wiring.
      - Tests: unit tests for helpers; integration tests for migrated modules using mock servers.
      - Docs: PRD updated; developer docs; migration notes.

  - Acceptance Gates (per stage)
      - Stage 1–2: Unit tests green; helpers stable across py/httpx versions; no secret leakage in logs.
      - Stage 3–4: Early adopters and summarization/ingestion migrated with parity; perf smoke OK.
      - Stage 5: Metrics visible and accurate; egress denials clear and tested.
      - Stage 7: CI guard active; legacy code removed or wrapped with deprecation warnings.
