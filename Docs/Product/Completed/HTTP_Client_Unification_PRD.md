# HTTP Client Unification PRD

Status: Completed (implemented)
Owner: Core Maintainers
Target Release: 0.2.x

## 1. Summary
Standardize all outbound HTTP traffic on a single policy and observability layer
(`tldw_Server_API/app/core/http_client.py`) while allowing multiple transports
under a shared interface (async + streaming; sync only during migration). aiohttp
is the default transport; httpx is transitional for legacy sync callers and is
removed once sync callers migrate. This removes duplicated retry, egress checks,
and logging logic spread across modules and simplifies tests.

## 2. Problem Statement
Outbound HTTP currently uses requests, httpx, and aiohttp directly in multiple
modules. Each path re-implements retry and error handling, and not all paths
consistently enforce the egress policy or emit metrics.

Examples:
- tldw_Server_API/app/core/LLM_Calls/chat_calls.py
- tldw_Server_API/app/core/Embeddings/connection_pool.py
- tldw_Server_API/app/core/Web_Scraping/enhanced_web_scraping.py
- tldw_Server_API/app/core/External_Sources/google_drive.py
- tldw_Server_API/app/core/Sync/Sync_Client.py
- tldw_Server_API/app/core/Ingestion_Media_Processing/Audio/Audio_Transcription_External_Provider.py

## 3. Goals & Success Criteria
- All outbound HTTP goes through http_client for policy, retries, and metrics.
- Support async and streaming with consistent behavior; keep legacy sync support
  only during migration.
- Reduce direct requests/httpx/aiohttp usage to transport adapters only.
- Simplify tests: patch a single client factory.

Success Metrics:
- Migration checkpoints (acceptable interim state):
  - End of Phase 2: >= 80% of in-scope modules migrated; remaining modules listed in a short-lived allowlist.
  - End of Phase 3: 100% of in-scope modules migrated; direct usage only inside adapters/vendor SDKs.
- No direct requests/httpx/aiohttp usage in business logic modules (vendor SDKs exempt).
- Egress policy is enforced on all outbound requests.
- Consistent metrics and logging for outbound traffic.

## 4. In Scope
- Define a transport adapter interface used by http_client.
- Provide adapters for aiohttp (default) and httpx (transitional).
- Migrate modules listed in the problem statement to use http_client.
- Update tests to patch transport adapters instead of raw libraries.
- Support proxies and client certificates via the shared interface.

## 5. Out of Scope
- Changing external API contracts.
- Removing any dependency entirely beyond planned sync deprecation (httpx remains
  only while legacy sync paths exist; requests usage is vendor-SDK-only).
- Rewriting provider-specific logic unrelated to HTTP transport.
- Wrapping or replacing third-party vendor SDKs that encapsulate their own HTTP.
- HTTP/2 support (future item).

## 6. Functional Requirements
### 6.1 Shared Interface
- http_client exposes:
  - request(method, url, params, headers, json, data, files, auth, timeout, retry, stream,
            proxies, verify, cert, cookies, http2)
  - `files` follows httpx/requests multipart conventions: mapping or sequence of
    (field, (filename, file-like or bytes, content_type)). Adapters do not accept
    file paths or open files; callers supply file-like objects. When `files` are
    provided and RetryPolicy enables retries, seekability is validated once
    synchronously at call time (before the first send) for each file-like object.
    Validation error: "file-like object for field '<field>' is not seekable; required
    when retries are enabled". Adapters/transports do not re-check per retry because
    callers must supply seekable objects when retries are configured. Non-seekable
    objects are permitted only when retries are disabled; request helpers like
    request_json(...), stream_bytes(...), and stream_sse(...) surface the same
    validation error when retries are enabled. Upload buffering/streaming is
    delegated to the transport.
  - RequestOptions object for request options (preferred to limit signature growth)
  - RetryPolicy object for retries (defaults sourced from [HTTP] config / HTTP_* env vars)
  - request_json(...) with content-type validation; allow override for mismatched or missing
    content-type (e.g., require_json_ct=False). RequestOptions includes
    require_json_ct (default true) to keep sync/async helpers consistent.
  - stream_bytes(...) and stream_sse(...) helpers
- `http2` remains a forward-compatible parameter in public signatures and is
  currently a no-op (ignored) until HTTP/2 support is implemented.
- All functions enforce egress policy, timeouts, and metrics.

### 6.1.1 RequestOptions Structure
RequestOptions is a dataclass or TypedDict with the following fields:

- `timeout: Timeout | float | None` (default: per-request timeout defaults)
- `retry: RetryPolicy | None` (default: config defaults)
- `allow_unsafe_methods: bool` (default: false; overrides RetryPolicy for POST/PUT/PATCH/DELETE retries)
- `max_attempts: int | None` (default: RetryPolicy.attempts or config default)
- `require_json_ct: bool` (default: true; applies only to request_json helpers)
- `headers: Dict[str, str] | None` (default: None)
- `params: Dict[str, Any] | None` (default: None)
- `json: Any | None` (default: None)
- `data: Any | None` (default: None)
- `files: FileSpec | None` (default: None; multipart mapping or sequence)
- `auth: Tuple[str, str] | None` (default: None)
- `allow_redirects: bool` (default: true)
- `proxies: str | Dict[str, str] | None` (default: None)
- `verify: bool | str | SSLContext | None` (default: None; transport-specific)
- `cert: str | Tuple[str, str] | None` (default: None; transport-specific)
- `cookies: Dict[str, str] | None` (default: None)
- `http2: bool` (default: false; ignored until HTTP/2 is in-scope)

Example usage:
```python
opts = RequestOptions(
    timeout=Timeout(connect=5, read=60),
    retry=RetryPolicy(attempts=2, retry_on_unsafe=True),
    require_json_ct=True,
)
```

### 6.2 Transport Adapters
- Default transport uses aiohttp for async and streaming.
- httpx adapter is transitional for legacy sync paths only; end state is async-only
  once legacy sync callers migrate.
- Adapters must not bypass egress policy or metrics.
- Adapter selection is not configurable in production; aiohttp is the default and
  httpx is limited to legacy sync paths.
- Adapters must support proxies and client certs when configured.

### 6.3 Retry and Backoff
- Retry policy centralized in http_client.
- No module implements custom retries outside the adapter layer.
- Defaults:
  - Retriable methods: GET, HEAD, OPTIONS by default; unsafe methods require explicit opt-in.
  - Retriable statuses: 408, 429, 500, 502, 503, 504; retry on connect/read timeouts.
  - Timeout defaults per request: connect=5s, read=30s, write=30s, pool=30s.
  - Backoff: decorrelated jitter, base 250ms, cap 30s; max attempts=3 (includes initial request).
  - Honor Retry-After where provided.
- RetryPolicy includes `allow_unsafe_methods` (default false) to opt into retries for
  POST/PUT/PATCH/DELETE when explicitly enabled.
- Per-request overrides allowed for timeouts, retry enablement, allow_unsafe_methods,
  and max attempts.
- Streaming requests are never retried after the first byte is received.
- Config alignment:
  - Timeouts map to `[HTTP]` `connect_timeout|read_timeout|write_timeout|pool_timeout`
    (env: `HTTP_CONNECT_TIMEOUT|HTTP_READ_TIMEOUT|HTTP_WRITE_TIMEOUT|HTTP_POOL_TIMEOUT`).
  - Retries map to `[HTTP]` `retry_attempts|backoff_base_ms|backoff_cap_s`
    (env: `HTTP_RETRY_ATTEMPTS|HTTP_BACKOFF_BASE_MS|HTTP_BACKOFF_CAP_S`).
  - Pool sizing maps to `[HTTP]` `max_connections|max_keepalive_connections`
    (env: `HTTP_MAX_CONNECTIONS|HTTP_MAX_KEEPALIVE_CONNECTIONS`).
  - Rationale: connect=5s fails fast on dead endpoints, 30s read/write/pool
    reflects conservative provider latency envelopes; per-provider overrides
    remain available and are documented in the config reference.

### 6.4 Streaming Semantics
- Streaming returns SSE events or raw bytes with explicit no-retry after first byte.
- SSE parsing rules:
  - Only `data:` lines form event payloads (joined by "\n"); comment lines (starting with
    `:`) are ignored.
  - `event:`, `id:`, and `retry:` fields are surfaced when present.
  - A blank line terminates the current event; emit only if at least one `data:` line
    was seen since the previous terminator.
  - Event-only frames (no `data:`) are treated as heartbeat signals; they reset the
    idle timer but do not emit a payload. If `heartbeat_event_names` is set, only those
    event names count as heartbeats.
  - Optional `stop_on_done`/`done_sentinels` allow callers to end streams on provider
    sentinels (default disabled; helpers emit raw events).
  - Non-2xx responses raise before streaming starts.
  - Mid-stream disconnects surface a streaming error to the caller (no silent swallow).
- Streaming behavior matches current SSE semantics for provider endpoints.
- Streaming timeout policy:
  - Transport read timeout is disabled for streaming.
  - Connect/write/pool timeouts still apply for streaming requests.
  - `stream_first_byte_timeout_s` (default 10s) fails fast before first byte.
  - `stream_idle_timeout_s` (default 60s) resets on any bytes/SSE event.
  - Optional `stream_max_duration_s` caps total stream runtime.
  - Optional `expected_heartbeat_s` or `heartbeat_event_names` define keepalive; if not
    observed within the idle window, raise a streaming timeout.
- Backpressure and resource limits:
  - Cap buffered SSE data per event and per stream; abort with a clear error on overflow.
  - Idle-timeout tracking should update on chunk boundaries, not per-byte, to avoid overhead.
  - Heartbeats reset idle timers until a done sentinel is emitted; after done, the stream ends.

### 6.5 Testing and Mocking
- Provide a single injection point for tests (transport adapter or client factory).
- Remove reliance on patching requests.Session, httpx.Client, or aiohttp.ClientSession directly.

### 6.6 Egress Policy Enforcement
- Validate scheme/host/port before dispatch.
- Follow redirects only after re-validating target URLs against egress policy.
- Resolve DNS for each direct request and each redirect target, block private/reserved ranges.
- Proxy usage is gated by `PROXY_ALLOWLIST`, and `HTTP_TRUST_ENV` defaults to false.
- When a proxy is configured and allowed, validate the proxy endpoint; target hostnames
  must still be allowlisted, and the proxy is expected to enforce URL access control.
  Local DNS resolution is not performed for proxied targets; IP-literal targets are
  denied unless explicitly allowlisted.

### 6.7 Client Lifecycle and Pooling
- http_client owns client instances; adapters do not create ad-hoc clients.
- Clients are reused across requests and closed on app shutdown.
- Pool limits and keep-alive settings are configured centrally in http_client.
- Async clients are created and used within the running event loop only.
- Maintain a per-event-loop async client cache; do not reuse clients across loops.
- Close async clients on app shutdown and when a test event loop is torn down.
- Pool defaults align to `[HTTP]` `max_connections=100` and `max_keepalive_connections=20`.

## 7. Migration Phases
1) Introduce transport adapter interface and aiohttp/httpx adapters.
2) Migrate web scraping, embeddings connection pool, external sources, sync client.
3) Migrate remaining modules with direct requests usage.
4) Remove legacy retry helpers and direct HTTP usage from business logic.

### 7.1 Migration Checklist
- Replace direct requests/httpx/aiohttp calls with http_client (or RequestOptions).
- Confirm timeouts/retry overrides for non-idempotent calls and streaming endpoints.
- Map per-provider `*_api_timeout|*_api_retry|*_api_retry_delay` settings to RetryPolicy overrides where still needed. Post-migration, provider settings live under `[Providers.<ProviderName>]` (env: `PROVIDER_<NAME>_*`). Discovery: search for `*_api_timeout|*_api_retry|*_api_retry_delay` via `rg -n "_api_(timeout|retry|retry_delay)" tldw_Server_API/ Config_Files/` or a small helper script that enumerates matches. Fallback: if a provider-specific backoff algorithm cannot be expressed by RetryPolicy, document the custom strategy in the provider config and add a hook to translate/wrap it where possible. Example: `stripe_api_retry_delay` -> `Providers.Stripe.retry.delay` (env `PROVIDER_STRIPE_RETRY_DELAY`); if Stripe's SDK backoff is custom, document `Providers.Stripe.retry.backoff_strategy="stripe_sdk"` and wrap the delay calculation while still using RetryPolicy for attempts/statuses.
- Update provider docs and config examples to point at the unified HTTP settings.
- Ensure streaming callers handle SSE events per defined parsing rules.
- Verify adapters use shared clients and are closed via app lifecycle hooks.

## 8. Risks & Mitigations
- Risk: performance regressions for high-concurrency paths after consolidation.
  - Mitigation: benchmark aiohttp against current usage, track perf regressions with
    metrics, and keep a rollback plan to the prior release if regressions appear.
- Risk: streaming differences across transports.
  - Mitigation: add regression tests for SSE formatting and chunk timing.

## 9. Testing Plan
- Unit tests for transport adapter enforcement of egress policy and retries.
- Integration tests for streaming endpoints and web scraping flows.
- Regression tests for known provider behaviors.
- Observability tests: metrics emitted on request/retry/failure with stable label sets across adapters.
- Streaming timeout tests for first-byte timeout, idle timeout reset, and heartbeat
  enforcement.
- Proxy allowlist enforcement tests, including IP-literal blocking for direct and
  proxied requests.

## 10. Acceptance Criteria
- All outbound HTTP routes through http_client in production modules (vendor SDKs exempt).
- Egress policy, retries, and metrics are consistent everywhere.
- Redirects and DNS resolution are re-validated for egress policy enforcement.
- Tests do not patch raw requests/httpx/aiohttp directly.

## 11. Decisions & Clarifications
- Adapter selection is not configurable; aiohttp is the default and httpx is limited
  to legacy sync paths during migration.
- End state is async-only; legacy sync support is removed after migrations complete.
- Vendor SDKs that encapsulate HTTP are exempt from unification.
- Proxies and client certificates are in-scope for the shared interface.
- requests usage is vendor-SDK-only; no requests adapter is planned.
- RetryPolicy includes `allow_unsafe_methods` (default false), and retry attempts include
  the initial request.
- stream_sse is neutral by default; optional `stop_on_done`/`done_sentinels` are opt-in.

## 12. Monitoring & Alerting (Resolved)
Outbound HTTP monitoring rolls into the existing Metrics + logging stack:
- Metrics: use `http_client_*` counters/histograms already emitted by `http_client`
  and exported by the existing metrics pipeline (Prometheus/OTel).
  - `http_client_requests_total{method,host,status}`
  - `http_client_request_duration_seconds{method,host}`
  - `http_client_retries_total{method,host}`
  - `http_client_egress_denials_total{host,reason}`
- Logs: loguru error logs already include provider + request context; alerting
  can rely on error-rate metrics plus log aggregation for triage.
- Suggested alerts (tune thresholds per env):
  - Egress denials: any `http_client_egress_denials_total` > 0 in 5m (security).
  - Retry storms: `http_client_retries_total / http_client_requests_total` > 0.2 in 10m.
  - Error rate: 5xx/transport errors > 2% in 5m.
  - Latency regression: p95 `http_client_request_duration_seconds` over baseline.

## 13. Config Reference
- HTTP client defaults and environment variable mappings live in `tldw_Server_API/Config_Files/README.md`.
- Transport selection is not configurable; aiohttp is the default and httpx is limited
  to legacy sync paths.
- Streaming timeout defaults map to `[HTTP]` keys:
  - `stream_first_byte_timeout_s` (env: `HTTP_STREAM_FIRST_BYTE_TIMEOUT_S`)
  - `stream_idle_timeout_s` (env: `HTTP_STREAM_IDLE_TIMEOUT_S`)
  - `stream_max_duration_s` (env: `HTTP_STREAM_MAX_DURATION_S`)
  - `expected_heartbeat_s` (env: `HTTP_STREAM_EXPECTED_HEARTBEAT_S`)
  - `heartbeat_event_names` (env: `HTTP_STREAM_HEARTBEAT_EVENT_NAMES`, comma-separated)
- Pool sizing defaults map to `[HTTP]` keys:
  - `max_connections` (env: `HTTP_MAX_CONNECTIONS`)
  - `max_keepalive_connections` (env: `HTTP_MAX_KEEPALIVE_CONNECTIONS`)
- Proxy defaults map to `[HTTP]` keys:
  - `trust_env` (env: `HTTP_TRUST_ENV`)
  - `proxy_allowlist` (env: `PROXY_ALLOWLIST`)
