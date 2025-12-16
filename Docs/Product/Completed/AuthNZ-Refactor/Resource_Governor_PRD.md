# Resource Governance PRD (v1)

## Summary

Multiple independent rate limiters and quota mechanisms exist across the codebase with overlapping logic and inconsistent semantics (burst behavior, refunding, test bypass, metrics, persistence). This PRD proposes a unified ResourceGovernor capable of governing per-entity resource limits for requests, tokens, streams, jobs, and minutes using a shared interface and pluggable backends (in-memory and Redis) with consistent test-mode behavior, metrics tags, and refund semantics.

**Current Status (v1.1)**:
- Core `ResourceGovernor` library (memory + Redis backends), policy loader/store (file + AuthNZ DB), and ingress middleware are implemented and exercised in tests and in production surfaces.
- High-impact modules (MCP, Chat, Embeddings API/server, Audio concurrency, AuthNZ, Evaluations, Character Chat, Web scraping) consult the governor under the global `RG_ENABLED`/config toggle (no per-module enable flags), with legacy limiters retained as fallback-only shims where needed.
- Durable daily caps are implemented via `ResourceDailyLedger` for audio minutes plus additional categories (for example, tokens-per-day and workflows runs-per-day), with parity tests covering both deny semantics and headers.
- Remaining work is primarily long-tail cleanup (retiring compatibility shims, policy tuning, and observability hardening) tracked as v1.2+ follow-ups rather than undocumented gaps.

## Problem & Symptoms

- Fragmented rate limiting/quota implementations per feature lead to duplication, drift, and inconsistent outcomes:
  - Chat token bucket + per-conversation limits: `tldw_Server_API/app/core/Chat/rate_limiter.py:1`
  - MCP in-memory/Redis limiter + category limiters: `tldw_Server_API/app/core/MCP_unified/auth/rate_limiter.py:1`
  - Embeddings sliding window limiter: `tldw_Server_API/app/core/Embeddings/rate_limiter.py:1`
  - Global SlowAPI limiter: `tldw_Server_API/app/api/v1/API_Deps/rate_limiting.py:1`
  - Audio quotas (daily minutes, concurrent streams/jobs): `tldw_Server_API/app/core/Usage/audio_quota.py:1`
- Additional duplications not originally listed but present:
  - AuthNZ DB/Redis limiter: `tldw_Server_API/app/core/AuthNZ/rate_limiter.py:1`
  - Evaluations per-user limiter and usage ledger: `tldw_Server_API/app/core/Evaluations/user_rate_limiter.py:1`
  - Character Chat limiter (Redis + memory): `tldw_Server_API/app/core/Character_Chat/character_rate_limiter.py:1`
  - Web scraping rate limiters: `tldw_Server_API/app/core/Web_Scraping/enhanced_web_scraping.py:125`
  - Embeddings server token-bucket decorator: `tldw_Server_API/app/core/Embeddings/Embeddings_Server/Embeddings_Create.py:1030`

Symptoms:
- Inconsistent burst multipliers and windows; different interpretations of “per minute”.
- Hard-to-reason interactions between limiters (e.g., SlowAPI + per-module meters).
- Divergent test bypass logic (varied env flags, ad-hoc behavior).
- Inconsistent metrics (names, labels, presence) and poor cross-feature visibility.
- Code complexity and maintenance overhead; bugs from drift and duplicated env parsing.

## Goals

- One unified ResourceGovernor module to manage “per-entity resource limits” across categories:
  - Categories: `requests`, `tokens`, `streams`, `jobs`, `minutes`.
- Pluggable backends: in-memory (single-instance) and Redis (multi-instance), chosen by configuration.
- Consistent API supporting reserve/commit/refund and query, with atomic composite reservations across categories when possible.
- First-class test-mode behavior (deterministic bypass or fixed limits) without per-feature custom parsing.
- Standardized metrics and tracing for allow/deny/wait/refund with consistent label sets.
- Compatibility shims for existing modules; incremental migration plan.

Non-goals (v1):
- Redesigning pricing/billing or tier models.
- Replacing durable ledgers where they make sense (e.g., daily minutes table for audio).
- Removing SlowAPI entirely; it can remain as an ingress façade backed by the governor.

For scope management, v1.0 focused on delivering the core governor, policy layer, and initial high-impact integrations (MCP, Chat, Embeddings, Audio, SlowAPI). v1.1 extends this with DB-backed policy management, a shared `ResourceDailyLedger` for additional daily caps, and early cost-unit/analytics wiring; further follow-ups remain under “Post v1.1”.

## Personas & Entities

- Persona: API user (API key/JWT user id), service client (MCP client id), conversation id (Chat), IP address (ingress fallback), system services.
- Entity key format: `scope:value` where scope ∈ {`user`, `api_key`, `client`, `ip`, `conversation`, `tenant`, `service`}.
- Effective entity: per endpoint determines which entity keys apply. Examples:
  - Chat: `user:{id}`, optionally `conversation:{id}`; tokens reserved under `tokens` and request under `requests`.
  - Audio stream: `user:{id}` governing `streams` semaphore and `minutes` ledger.
  - MCP: `client:{id}` or `user:{id}` with `requests` in categories `ingestion` or `read` via tags.

## Functional Requirements

- Core interface:
  - check(spec) → decision: Read-only evaluation that returns allow/deny with retry_after and metadata without mutating counters. Intended for diagnostics, UI, and tests; enforcement paths use `reserve`.
  - reserve(spec, op_id) → handle: Reserves resources atomically across categories (best-effort rollback on partial failures). `op_id` is an idempotency key and is required on all mutating calls.
  - commit(handle, actual_usage, op_id) → None: Finalizes reservation and records usage (e.g., minutes consumed, tokens used). Idempotent per `op_id`.
  - refund(handle or delta, op_id) → None: Returns unused capacity (e.g., estimated vs actual tokens; failure paths). Idempotent per `op_id`.
  - renew(handle, ttl_s) → None: Renews concurrency leases (streams/jobs) heartbeat before TTL expiry.
  - release(handle) → None: Explicitly releases concurrency leases (streams/jobs) when finished.
  - peek(query) → usage: Returns current usage and remaining headroom per category/entity.
  - reset(entity/category) → None: Administrative reset.

- Categories & semantics:
  - `requests`: token-bucket or sliding-window RPM/RPS limits; burst configured.
  - `tokens`: token-bucket for budgeted tokens per window (e.g., per minute).
  - `streams`: semaphore-like concurrency limit (bounded integer counter) with lease TTL/heartbeat.
  - `jobs`: semaphore-like concurrency limit with queue-aware labeling; optional per-queue limits.
  - `minutes`: durable, per-day (UTC) ledger; supports add on commit and check before reserve.

- Default algorithms and formulas:
  - `requests`: token-bucket by default. Capacity `C = burst * rate * window`; refill at `rate` per second. Sliding-window may be selected per policy for very small-window accuracy.
  - `tokens`: token-bucket by default. Units are model tokens when available; otherwise generic estimated tokens as a stand-in.
  - `streams/jobs`: bounded counters with per-lease TTL; requires `renew` heartbeat to keep leases alive.
  - `minutes`: durable daily cap; see Minutes Ledger Semantics.

### Canonical flows

- Non-streaming HTTP request (e.g., chat completion):
  - `reserve` for the relevant `requests` (and optionally `tokens`) categories → call handler → `commit(actual_usage)` on success or `refund` on failure/short-circuit.
- Streaming call (e.g., audio or long-running chat stream):
  - `reserve` for `streams` plus any estimated `tokens`/`minutes` → start stream → periodically `renew` leases while active → `commit(actual_usage)` and `release` on completion; `refund` unused estimates on early termination.
- Background job / async worker:
  - `reserve` for `jobs` (and any other relevant categories) when enqueuing or dequeuing based on module needs → process work → `commit` or `refund` and `release` when the job completes or is abandoned.

## Time Sources

- All time calculations for windows, TTLs, and expirations use monotonic clocks via a `TimeSource` abstraction to avoid wall-clock jumps.
- `ResourceGovernor` accepts a `time_source` parameter (defaults to a monotonic provider). Tests inject a fake time source for deterministic control.

- Composite reservation: Reserve in deterministic order to minimize deadlock; on failure, release prior reserves.

- Test mode:
  - Prefer a single project-wide flag `TLDW_TEST_MODE=true`; `RG_TEST_BYPASS` may override governor behavior for tests.
  - In test mode: no burst (`burst=1.0`), deterministic timing, optional fixed limits via `RG_TEST_*` envs.
  - Zero reliance on request headers for bypass.

- Metrics & tracing:
  - Metrics emitted on every decision: allow/deny, reserve/commit/refund, with labels: `category`, `scope`, `backend`, `result`, `reason`, `endpoint`, `service`, `policy_id`. Entity is excluded by default; optionally include a hashed entity label when `RG_METRICS_ENTITY_LABEL=true`.
  - Gauges for concurrency (`streams_active`, `jobs_active`); counters for denials and refunds.
  - Optional exemplars and trace IDs if tracing enabled.

- Configuration:
  - Policy source of truth:
    - Production precedence (high→low): AuthNZ DB policy store → env overrides → YAML policy file → defaults.
    - Development/Test precedence (high→low): env overrides → YAML policy file → defaults.
  - Shared env var prefix `RG_*` (examples below) with legacy alias mapping for backward compatibility.

## Non-Functional Requirements

- Correctness under concurrency; atomicity across categories best-effort with rollback.
- Performance suitable for hot paths; constant-time checks and minimal allocations.
- Minimal lock contention; per-entity locks, monotonic time usage.
- Clean resource cleanup (idle entry GC) and Redis TTLs to prevent leaks.
- Backwards compatible rollout with shims and metrics parity.

## Architecture & API

- Module location: `tldw_Server_API/app/core/Resource_Governance/`
  - `ResourceGovernor` (facade) — processes rules, composes category managers, handles composite reservations.
- Backends:
  - `InMemoryBackend` — dicts + locks; token buckets, sliding windows, semaphores.
  - `RedisBackend` — ZSET sliding windows, token buckets, and robust semaphore leases with TTL.
  - Categories:
    - `RequestsLimiter` (token bucket or sliding window per rule).
    - `TokensLimiter` (token bucket with refund support).
  - `ConcurrencyLimiter` (streams/jobs using counters with TTL + heartbeat).
    - `MinutesLedger` (durable DB-backed; reuses audio minutes schema for v1 with abstract interface).
  - Types:
    - `EntityKey(scope: str, value: str)`
    - `Category(str)`; `LimitSpec` (rate, window, burst, max_concurrent, daily_cap, etc.)
    - `ReservationHandle(id, items, metadata, ttl, expires_at)` with implicit expiry tracking.
    - `TimeSource` interface providing monotonic `now()`; default binds to `time.monotonic()`; tests can inject a fake time source.

- Proposed Python signature (simplified):

```python
@dataclass
class RGRequest:
    entity: EntityKey
    # Units: requests → 1 per HTTP call; tokens → model tokens (preferred) or estimated generic tokens.
    categories: Dict[str, Dict[str, int]]  # e.g., {"requests": {"units": 1}, "tokens": {"units": 1200}}
    tags: Dict[str, str] = field(default_factory=dict)  # endpoint, service, policy_id, etc.

@dataclass
class RGDecision:
    allowed: bool
    retry_after: int | None
    # details contains: {
    #   "policy_id": str,
    #   "categories": {
    #       "requests": {"allowed": bool, "limit": int, "used": int, "remaining": int, "retry_after": int | None},
    #       "tokens":   {"allowed": bool, "limit": int, "used": int, "remaining": int, "retry_after": int | None},
    #       ...
    #   }
    # }
    details: Dict[str, Any]

class ResourceGovernor:
    async def check(self, req: RGRequest) -> RGDecision: ...
    async def reserve(self, req: RGRequest, op_id: str | None = None) -> tuple[RGDecision, str]: ...  # returns (decision, handle_id)
    async def commit(self, handle_id: str, actuals: Dict[str, int] | None = None, op_id: str | None = None) -> None: ...
    async def refund(self, handle_id: str, deltas: Dict[str, int] | None = None, op_id: str | None = None) -> None: ...
    async def renew(self, handle_id: str, ttl_s: int) -> None: ...  # concurrency lease heartbeat
    async def release(self, handle_id: str) -> None: ...  # explicit release for concurrency leases
    async def peek(self, entity: EntityKey, categories: list[str]) -> Dict[str, Any]: ...
    async def query(self, entity: EntityKey, category: str) -> Dict[str, Any]: ...  # normalized diagnostics view
    async def reset(self, entity: EntityKey, category: str | None = None) -> None: ...
```

- Atomicity strategy:
  - For Redis: use Lua scripts or MULTI/EXEC to reserve multiple categories; on partial failure, rollback prior reservations.
  - For memory: acquire category locks in stable order; on failure, release acquired reservations.

- Redis concurrency lease design:
  - Use a ZSET per entity/category (e.g., `rg:lease:<category>:<scope>:<entity>`) containing `member=lease_id`, `score=expiry_ts`.
  - Acquire via Lua: purge expired (ZREMRANGEBYSCORE), check `ZCARD < limit`, `ZADD` new lease with expiry. Return `lease_id` as handle.
  - Renew via `ZADD` with updated expiry for `lease_id`. Release via `ZREM` on `lease_id`.
  - Periodic GC sweeps ensure eventual cleanup; avoid pure INCR/DECR to eliminate race hazards.

- Refund semantics:
  - Chat: reserve estimated tokens; on completion, commit actual tokens used and refund the difference.
  - Failures: refund all prior reservations; log reason and emit refund metrics.
  - Time-bounded reservations: auto-expire stale handles; periodic cleanup task.
  - Safety: cap refunds by prior reservation per category to avoid negative usage; validate `actuals <= reserved` unless policy explicitly enables overage handling.

- Handle lifecycle:
  - `ReservationHandle` includes `expires_at` and `op_id`. Background sweeper reclaims expired handles across backends.
  - All state transitions (reserve, commit, refund, renew, release, expire) include a `reason` for audit and metrics.

- Policy composition semantics:
  - Strictest-wins semantics and `retry_after` aggregation are defined in “Policy Composition & Retry‑After”; implementations must follow that behavior for all categories.

## Configuration

- New standardized env vars (legacy aliases maintained via mapping during migration):
  - `RG_BACKEND`: `memory` | `redis`
  - `RG_REDIS_URL`: Redis URL
  - `REDIS_URL`: Redis URL (alias; used across infrastructure helpers)
  - `RG_TEST_BYPASS`: `true|false` (defaults to honoring `TEST_MODE`)
  - `RG_REDIS_FAIL_MODE`: `fail_closed` | `fail_open` | `fallback_memory` (defaults to `fallback_memory`). Controls behavior on Redis outages:
    - `fail_closed`: on Redis errors, deny requests and emit metrics/logs indicating `backend=redis_error`.
    - `fail_open`: on Redis errors, allow without mutating usage while emitting `backend=fail_open` metrics.
    - `fallback_memory`: on Redis errors, route operations to the in-process memory backend; if the memory path also fails, treat it as `fail_open`.
    - Per-policy `fail_mode` in policy payloads overrides `RG_REDIS_FAIL_MODE` for that policy/category.
    - Default `fallback_memory` favors availability for non-critical categories; consider `fail_closed` for strict write paths or global-coordination categories.
  - `RG_CLIENT_IP_HEADER`: Header to trust for client IP when behind trusted proxies (e.g., `X-Forwarded-For`, `CF-Connecting-IP`).
  - `RG_TRUSTED_PROXIES`: Comma-separated CIDRs for trusted reverse proxies; when unset, IP scope uses the direct remote address only.
  - `RG_METRICS_ENTITY_LABEL`: `true|false` (default `false`). If true, include hashed entity label in metrics; otherwise exclude to avoid high cardinality.
  - `RG_POLICY_STORE`: `file` | `db` (default `file`). In production, prefer `db` and use AuthNZ DB as SoT; in dev, `file` + env overrides.
  - Test‑harness flags (diagnostics only):
    - `RG_TEST_FORCE_STUB_RATE`: `true|false` forces in‑process sliding‑window logic for requests/tokens in Redis backend. Useful to make burst/steady tests deterministic when real Redis timing or clock skew affects retry_after near window boundaries.
    - `RG_TEST_PURGE_LEASES_BEFORE_RESERVE`: `true|false` best‑effort purge of expired leases before reserve in tests to reduce flakiness.

### Flag overview (operator-facing)

- Day-to-day configuration focuses on: `RG_ENABLED`, `RG_BACKEND`, `RG_REDIS_URL`, `RG_REDIS_FAIL_MODE`, and `RG_POLICY_STORE`.
- Test/CI flows primarily use: `TLDW_TEST_MODE` and (optionally) `RG_TEST_BYPASS`; advanced diagnostics flags such as `RG_TEST_FORCE_STUB_RATE`, `RG_TEST_PURGE_LEASES_BEFORE_RESERVE`, and `RG_REAL_REDIS_URL` should be confined to test harnesses.
- Integrations are controlled by the global `RG_ENABLED`/config toggle; per-module `RG_ENABLE_*` flags are removed. Module-specific tuning is expressed via policies + route-map and (where present) policy-id override envs (for example `RG_CHAT_POLICY_ID`).

### Acceptance‑Window Fallback (Requests)

Real Redis can occasionally report window counts near boundaries that admit a request even when a prior denial suggested a small retry_after. To keep behavior deterministic (especially in CI), the Redis backend maintains a per‑(policy, entity) “acceptance‑window” tracker for requests:

- When the tracker observes that `limit` requests were accepted within the current window, further requests are denied until the window end (floor). This is an additive guard over ZSET counts, not a replacement.
- On denial, the guard sets a deny‑until floor to the end of the window to avoid early admits caused by rounding/drift.
- In test contexts, you can prefer the acceptance‑window path by setting `RG_TEST_FORCE_STUB_RATE=1`.

### Policy Composition & Retry‑After

- Composition (strictest wins): for each category, compute headroom per applicable scope (global, tenant, user, conversation); the effective headroom is the minimum across scopes.
- Deny when effective headroom < requested units.
- Retry‑After aggregation: per category, compute the maximum retry_after across denying scopes; the overall decision retry_after is the maximum across denied categories. This prevents premature retries when multiple scopes deny with different windows.
- For concurrency categories (`streams`, `jobs`), `retry_after` is best-effort and may be derived from lease TTLs or a conservative backoff; implementations may omit or cap `Retry-After` when no reliable estimate is available.

### Metrics Labels & Cardinality

- Counters/gauges:
  - `rg_decisions_total{category,scope,backend,result,policy_id}`
  - `rg_denials_total{category,scope,reason,policy_id}`
  - `rg_refunds_total{category,scope,reason,policy_id}`
  - `rg_concurrency_active{category,scope,policy_id}`
- Entity labels are excluded by default to avoid high cardinality; enable only for targeted debugging with `RG_METRICS_ENTITY_LABEL=true` and prefer sampled logs for per‑entity traces.
  - `RG_POLICY_DB_CACHE_TTL_SEC`: TTL for DB policy cache (default 10s) when `RG_POLICY_STORE=db`.

### Middleware Options (default-on)

- `RGSimpleMiddleware` is attached automatically whenever `RG_ENABLED=true` and performs a minimal pre-check for the `requests` category using `route_map` resolution.
- Middleware enablement is controlled by the global `RG_ENABLED` flag.
- Middleware options apply only when `RG_ENABLED=true`; otherwise they are inert.
- Note: earlier experimental flags `RG_MIDDLEWARE_ENFORCE_TOKENS` / `RG_MIDDLEWARE_ENFORCE_STREAMS` were removed; the middleware enforces `requests` only and other categories are enforced at endpoint level (reserve/commit).

### Testing (integration)

- `RG_REAL_REDIS_URL`: optional real Redis URL used by integration tests to validate multi-key Lua path; if absent or unreachable, those tests are skipped. `REDIS_URL` is also honored.
  - Category defaults (fallbacks applied per module if unspecified):
    - `RG_REQUESTS_RPM_DEFAULT`, `RG_REQUESTS_BURST`
    - `RG_TOKENS_PER_MIN_DEFAULT`, `RG_TOKENS_BURST`
    - `RG_STREAMS_MAX_CONCURRENT_DEFAULT`, `RG_STREAMS_TTL_SEC`
    - `RG_JOBS_MAX_CONCURRENT_DEFAULT`
    - `RG_MINUTES_DAILY_CAP_DEFAULT` (still enforced via durable ledger)

- Back-compat mapping examples:
  - `MCP_RATE_LIMIT_*` → requests-category policy rules for service `mcp`.
  - Chat `TEST_CHAT_*` → test-mode overrides for chat-specific rules.
  - Audio quotas envs (`AUDIO_*`) remain for `minutes` and concurrency defaults.

- Test mode semantics:
  - Prefer a single project-wide flag `TLDW_TEST_MODE=true`.
  - `RG_TEST_BYPASS` overrides only the governor’s behavior; precedence: `RG_TEST_BYPASS` if set, else `TLDW_TEST_MODE`.
  - In test mode, defaults: no burst (`burst=1.0`), deterministic timing, and optional fixed limits via `RG_TEST_*` envs.

## Ingress Scoping & IP Derivation

- Derive the effective entity for ingress using auth scopes when available (`user`, `api_key`, `client`).
- For `ip` scope behind proxies, require explicit configuration:
  - Only trust `RG_CLIENT_IP_HEADER` when the immediate peer IP is within `RG_TRUSTED_PROXIES`.
  - Otherwise, use the direct remote address.
  - If both auth and IP are available, prefer auth scopes for rate limits; use IP as fallback.

## Policy DSL & Route Mapping

- Central policy file in YAML (hot-reloadable) declares limits per category and scope with identifiers:

```yaml
policies:
  chat.default:
    requests: { rpm: 120, burst: 2.0 }
    tokens:   { per_min: 60000, burst: 1.5 }
    scopes: [global, user, conversation]
    fail_mode: fail_closed
  mcp.ingestion:
    requests: { rpm: 60, burst: 1.0 }
    scopes: [global, client]
    fail_mode: fallback_memory
```

- Policy fields at a glance:
  - `requests.rpm` / `requests.burst` — request rate and burst multiplier.
  - `tokens.per_min` / `tokens.burst` — token-per-minute caps with burst support.
  - `streams.max_concurrent` / `streams.ttl_sec` and `jobs.max_concurrent` / `jobs.ttl_sec` — concurrency limits with lease TTLs.
  - `minutes.daily_cap` / `minutes.rounding` — daily ledger caps (in minutes) with explicit rounding semantics.
  - `scopes` — list of scopes that apply for a policy (for example, `["global", "user", "conversation"]`).
- Routes attach `policy_id` via FastAPI route tags or decorators. An ASGI middleware reads the tag and consults the governor. SlowAPI decorators remain as config carriers only.
- Policy reload: file watcher or periodic TTL check; swap policies atomically. Invalid updates are rejected with clear logs.
- Per-category overrides: policy `fail_mode` may override `RG_REDIS_FAIL_MODE` for that policy/category.
- Stub location: `tldw_Server_API/Config_Files/resource_governor_policies.yaml` provides default examples and hot-reload settings.
- Source of Truth in production: policies stored in AuthNZ DB (e.g., `rg_policies`) with JSON payloads and `updated_at` timestamps.
  - Cache layer with TTL and/or change feed; hot-reload applies atomically across workers.
  - Env vars remain as development overrides; DB wins in production when present.
- Ingress coverage checklist (internal): keep `route_map.by_path` (and/or route tags) aligned so that at minimum `/api/v1/chat/*`, `/api/v1/embeddings*`, `/api/v1/audio/*`, `/api/v1/mcp/*`, and `/api/v1/evaluations/*` resolve to the expected policies, and explicitly document any high-value ingress routes that are intentionally left outside RG governance.

### Admin API (Minimal)

- Read-only snapshot:
  - `GET /api/v1/resource-governor/policy` → metadata (version, store, count); `?include=ids|full` for IDs or full payloads.
- Admin (requires `admin` role; single-user treated as admin):
  - `GET /api/v1/resource-governor/policies` → list `{id, version, updated_at}`
  - `GET /api/v1/resource-governor/policy/{policy_id}` → `{id, version, updated_at, payload}`
  - `PUT /api/v1/resource-governor/policy/{policy_id}` → upsert JSON payload; optional explicit `version` for optimistic concurrency (auto-increments when omitted; see behavior notes below)
  - `DELETE /api/v1/resource-governor/policy/{policy_id}` → delete policy
  - Implementation note: in v0.1 these admin endpoints, and the diagnostics endpoints below, are part of the principal-governed admin surfaces described in `Docs/Product/Principal-Governance-PRD.md` (see “Admin Surfaces Governed by Principals” coverage snapshot) and are wired through the claim-first stack:
    - `get_auth_principal` to resolve identity and claims, with principal/claim semantics owned by the Principal & Governance PRD.
    - `require_roles("admin")` (or `principal.is_admin`) as the single gate for admin access, matching the principal-governance rules in that document.
    - Tests in `tldw_Server_API/tests/AuthNZ_Unit/test_resource_governor_permissions_claims.py` and `tldw_Server_API/tests/Resource_Governance/` lock in 401/403/200 semantics for JWT/API-key flows and single-user mode.
- Behavior:
  - When `RG_POLICY_STORE=db`, successful writes trigger best-effort PolicyLoader refresh; file store remains read-only.
  - All responses include `{status: ok|error}` and details on errors; avoid logging PII.
  - When a client supplies `version` on `PUT` and `RG_POLICY_STORE=db`, updates enforce optimistic concurrency:
    - If no row exists yet, the supplied `version` is used for the initial insert.
    - If a row exists and its stored `version` matches the supplied `version`, the payload is updated and `version` is incremented.
    - If a row exists and its stored `version` differs from the supplied `version`, the admin API returns HTTP `409 Conflict` with `{status: "conflict", error: "version_conflict", policy_id, detail}`; this behavior is locked in by `tldw_Server_API/tests/Resource_Governance/integration/test_policy_admin_optimistic_postgres.py`.

## Integration Plan (Phased Migration)

Phase 0 — Ship ResourceGovernor (no integrations yet)
- Implement `ResourceGovernor` module with memory + Redis backends and category primitives.
- Add metrics emission via existing registry (labels: category, scope, backend, result, policy_id).
- Provide test-mode handling in one place.

Phase 1 — MCP
- Replace `tldw_Server_API/app/core/MCP_unified/auth/rate_limiter.py` internals with a thin façade over ResourceGovernor categories `requests` with tags `category=ingestion|read`.
- Preserve public API (`get_rate_limiter`, `RateLimitExceeded`) to avoid breaking imports.

Phase 2 — Chat
- Replace `ConversationRateLimiter` with `requests` + `tokens` categories.
- Keep per-conversation policy by composing the entity key `conversation:{id}` in addition to `user:{id}`.
- Maintain `initialize_rate_limiter` signature; under the hood, use ResourceGovernor.

Phase 3 — SlowAPI façade
- Configure `API_Deps/rate_limiting.py` to use `limiter.key_func` for ingress scoping (`ip`/`user`) and delegate allow/deny to ResourceGovernor `requests` category before handlers.
- Keep decorator usage (`@limiter.limit(...)`) as a config carrier only. Map decorator strings to RG policies using route tags (e.g., `tags={"policy_id": "chat.default"}`) and an ASGI middleware that consults the governor. No in-SlowAPI counters.
- Policy resolution reads from the YAML policy file (see Policy DSL & Route Mapping) with hot-reload support.

Phase 4 — Embeddings
- Replace `UserRateLimiter` with ResourceGovernor `requests` limits; for large-cost ops, optionally also a `tokens` category if desired.
- Remove ad-hoc env parsing; map legacy envs to `RG_*`.

Phase 5 — Audio quotas
- Keep durable minutes ledger DB exactly as-is but implement limits via `minutes` category interface.
- Replace in-process concurrent `streams`/`jobs` counters with `ConcurrencyLimiter` (with Redis TTL heartbeat support).

Phase 6 — Evaluations, AuthNZ, Character Chat, Web Scraping, Embeddings Server
- Gradually replace each with governor-backed categories; preserve public APIs during deprecation window.

Phase 7 — Cleanup & removal
- Delete/retire old limiter implementations once their consumers are migrated.
- Keep minimal façade shims that import ResourceGovernor and raise deprecation warnings.

## Deletions / Consolidation Targets

- Replace and then delete (or shim):
  - `tldw_Server_API/app/core/Chat/rate_limiter.py`
  - `tldw_Server_API/app/core/MCP_unified/auth/rate_limiter.py`
  - `tldw_Server_API/app/core/Embeddings/rate_limiter.py`
  - `tldw_Server_API/app/api/v1/API_Deps/rate_limiting.py` (convert to façade)
  - `tldw_Server_API/app/core/Usage/audio_quota.py` (concurrency + check plumbing via governor; keep minutes DB ledger implementation)
  - Plus: `AuthNZ` limiter, `Evaluations` limiter, `Character_Chat` limiter, `Web_Scraping` limiters, and Embeddings server decorator limiter

- Remove custom per-file env parsing once policy merges into shared config.

## Metrics & Observability

- Counters:
  - `rg_decisions_total{category,scope,backend,result,policy_id}` (entity excluded by default; optionally include hashed entity when `RG_METRICS_ENTITY_LABEL=true`).
  - `rg_refunds_total{category,scope,reason,policy_id}`
  - `rg_denials_total{category,scope,reason,policy_id}`
  - `rg_shadow_decision_mismatch_total{route,policy_id,legacy,rg}` (shadow-mode only; counts divergences between legacy limiter and RG decisions)
- Gauges:
  - `rg_concurrency_active{category,scope,policy_id}` (for streams/jobs)
- Histograms:
  - `rg_wait_seconds{category,scope,policy_id}` when wait/retry paths are used
- Logs:
  - Structured with category, decision, retry_after, reason, policy_id; include `handle_id` and `op_id` where applicable.
  - Never log raw `api_key`; mask or include only an HMAC/hashed form for diagnostics. Do not emit PII in logs.

### HTTP Headers

- For HTTP endpoints governed by the `requests` category, emit standard headers for compatibility during migration:
  - `Retry-After: <seconds>` on 429 responses based on the overall decision’s `retry_after`.
  - `X-RateLimit-Limit: <limit>` reflects the strictest applicable limit for the `requests` category.
  - `X-RateLimit-Remaining: <remaining>` reflects the remaining headroom under that strictest scope after the decision.
  - `X-RateLimit-Reset: <epoch_seconds>` or `<seconds>` until reset, aligned to the governing window.
- For concurrency denials (e.g., `streams`), return `429` with `Retry-After` set from the category decision; do not emit misleading `X-RateLimit-*` unless the route is also governed by `requests`.
- Maintain SlowAPI-compatible behavior on migrated routes to avoid client regressions.

- Tokens and per-minute headers (when applicable):
  - When a `tokens` policy is active for a route and the middleware/enforcement layer peeks token usage, include:
  - `X-RateLimit-Tokens-Remaining: <remaining_tokens>`
  - If policy defines `tokens.per_min`, also include `X-RateLimit-PerMinute-Limit: <per_min>` and `X-RateLimit-PerMinute-Remaining: <remaining_tokens>`.
  - Success-path headers use a precise governor `peek` (strictest scope) to populate Remaining/Reset. Reset is computed as the maximum across governed categories to avoid premature retries.

### Route Governance Matrix (v0.1 snapshot)

The table below summarizes which high-value ingress routes are governed by ResourceGovernor in v0.1 and which rely on legacy per-module limiters only. It mirrors the `route_map.by_path` defaults in `tldw_Server_API/Config_Files/resource_governor_policies.yaml` and the Stage 1 notes in `AuthNZ-PRDs_IMPLEMENTATION_PLAN.md`.

| Route prefix                          | Policy id            | RG-governed? | Notes                                                    |
|---------------------------------------|----------------------|--------------|----------------------------------------------------------|
| `/api/v1/chat/*`                      | `chat.default`       | Yes          | Requests/tokens via RG; legacy chat limiter kept as shim |
| `/api/v1/embeddings*`                 | `embeddings.default` | Yes          | Requests via RG; per-user legacy limiter as shadow       |
| `/api/v1/audio/*`                     | `audio.default`      | Yes          | Streams/minutes via RG + ledger; Redis as fallback      |
| `/api/v1/mcp/*`                       | `mcp.ingestion`      | Yes          | MCP HTTP ingress governed; module limiter is façade      |
| `/api/v1/evaluations/*`               | `evals.default`      | Yes          | Evaluations limiter shims RG; headers tested end-to-end  |
| `/api/v1/auth/*`                      | (varies)             | Partially    | AuthNZ rate limits via AuthGovernor; RG ingress optional |
| `/api/v1/research/*`                  | —                    | No (v0.1)    | Uses module-specific limiters/backpressure only          |
| `/api/v1/rag/*`                       | —                    | No (v0.1)    | Guarded by LLM budgets and module-specific shims         |
| `/api/v1/media/*`                     | —                    | No (v0.1)    | Ingestion/backpressure via module limiters, not RG       |
| `/api/v1/workflows/*`                 | —                    | No (v0.1)    | Scheduler/worker limits via existing jobs/scheduler code |
| `/api/v1/prompt-studio/*`             | —                    | No (v0.1)    | Prompt Studio uses claim-first AuthNZ + LLM budgets      |

Operator guidance:
- When adding new routes under existing prefixes, keep `route_map.by_path` in sync and reuse the established policy ids.
- When introducing a new domain (new prefix), decide explicitly whether it should be RG-governed:
  - If yes, add a policy and route-map entry, and update tests to assert 402/429 + headers.
  - If no, document the rationale in this matrix and in the module’s PRD, and rely on module-specific limiters or LLM budgets instead.

### Diagnostics

- Capability probe (admin-only): `GET /api/v1/resource-governor/diag/capabilities`
  - Returns a compact diagnostic payload indicating backend and code paths in use:
    - `backend`: `memory` or `redis`
    - `real_redis`: boolean indicating whether a real Redis client is connected (vs. an in-memory stub)
    - `tokens_lua_loaded`, `multi_lua_loaded`: booleans for loaded scripts (Redis backend)
    - `last_used_tokens_lua`, `last_used_multi_lua`: booleans indicating whether those code paths were exercised recently
  - Use this endpoint to verify Lua/script capabilities and troubleshoot fallbacks in production.

## Security & Privacy

- Redaction:
  - Treat API keys, user identifiers, and IPs as sensitive; never log raw values. Use hashed/HMAC forms with a server-secret salt for correlation when necessary.
  - Metrics must not include high-cardinality PII. Do not emit raw entity values; optional hashed entity is gated behind `RG_METRICS_ENTITY_LABEL=true`.
- Tenant scope:
  - Include `tenant:{id}` as a first-class scope from the outset, even if initial policies are no-op. This avoids retrofit costs and enables future isolation. The tenant id may be derived from a trusted header or JWT claim.
- Data minimization:
  - Expose only aggregated counters/gauges/histograms. Keep detailed per-entity diagnostics in sampled logs with redaction.

## Minutes Ledger Semantics

- Daily accounting is based on UTC. When a usage period overlaps midnight UTC, split minutes across the two UTC days on `commit`.
- Retroactive commits are disallowed by default; optionally allow with an explicit `occurred_at` timestamp and policy gates. If allowed, minutes accrue to the UTC day of `occurred_at`.
- Rounding: track internal usage at sub-minute resolution; charge per policy rounding rules (e.g., ceil to nearest minute on commit) consistently.

### Generic Daily Ledger (v1.1)

- Implementation status: a generic `ResourceDailyLedger` DAL now exists in `tldw_Server_API/app/core/DB_Management/Resource_Daily_Ledger.py`, is covered by SQLite/Postgres tests, and is actively used by the audio quotas module as the canonical store for daily `minutes` usage.
- Interface: `add(LedgerEntry(...))` for idempotent inserts keyed by `(day_utc, entity_scope, entity_value, category, op_id)`, plus helpers `total_for_day(...)`, `remaining_for_day(...)`, and `peek_range(entity_scope, entity_value, category, start_day_utc, end_day_utc)`.
- Storage: reuses the AuthNZ DB via the `resource_daily_ledger` table (schema below). Existing `audio_usage_daily` tables are retained as compatibility/fallback state (for example, for pre-upgrade rows or environments where the ledger cannot be initialized) but are no longer written to for new audio minutes events.
- Semantics: UTC-based partitioning; app callers are responsible for splitting long-running usage across UTC day boundaries before calling `add`, and for applying any policy-specific rounding rules at commit time.
- Rollout: v1.0 ships the DAL, uses it for audio minutes writes and enforcement (with legacy tables backfilled into the ledger on first use), and treats the governor’s `minutes` category as a future integration point. Planned v1.1 work focuses on extending the same ledger pattern to additional daily quotas (for example, tokens-per-day or evaluations) and, if needed, wiring those quotas through a dedicated `minutes` category adapter in the ResourceGovernor.

## Database Schemas

### Policy Store (AuthNZ DB)

- PostgreSQL

```sql
CREATE TABLE IF NOT EXISTS rg_policies (
  id TEXT PRIMARY KEY,                -- policy_id, e.g., 'chat.default'
  payload JSONB NOT NULL,            -- full policy object
  version INTEGER NOT NULL DEFAULT 1,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Optional index for updated_at for fast latest reads
CREATE INDEX IF NOT EXISTS idx_rg_policies_updated_at ON rg_policies (updated_at DESC);
```

- SQLite

```sql
CREATE TABLE IF NOT EXISTS rg_policies (
  id TEXT PRIMARY KEY,
  payload TEXT NOT NULL,             -- JSON-encoded
  version INTEGER NOT NULL DEFAULT 1,
  updated_at TEXT NOT NULL           -- ISO8601 UTC
);

CREATE INDEX IF NOT EXISTS idx_rg_policies_updated_at ON rg_policies (updated_at);
```

Notes:
- The server constructs a merged snapshot from all rows keyed by `id` with the latest `updated_at`.
- In production, the AuthNZ subsystem owns read/write APIs for this table.

### Generic Daily Ledger (v1.1)

- PostgreSQL

```sql
CREATE TABLE IF NOT EXISTS resource_daily_ledger (
  id BIGSERIAL PRIMARY KEY,
  day_utc DATE NOT NULL,
  entity_scope TEXT NOT NULL,        -- e.g., 'user', 'client', 'tenant'
  entity_value TEXT NOT NULL,        -- identifier for the scope (PII handling at app layer)
  category TEXT NOT NULL,            -- e.g., 'minutes', 'tokens_per_day'
  units BIGINT NOT NULL CHECK (units >= 0),
  op_id TEXT NOT NULL,               -- idempotency key
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_ledger_op ON resource_daily_ledger (day_utc, entity_scope, entity_value, category, op_id);
CREATE INDEX IF NOT EXISTS idx_ledger_lookup ON resource_daily_ledger (entity_scope, entity_value, category, day_utc);
```

- SQLite

```sql
CREATE TABLE IF NOT EXISTS resource_daily_ledger (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  day_utc TEXT NOT NULL,             -- 'YYYY-MM-DD'
  entity_scope TEXT NOT NULL,
  entity_value TEXT NOT NULL,
  category TEXT NOT NULL,
  units INTEGER NOT NULL,
  op_id TEXT NOT NULL,
  occurred_at TEXT NOT NULL,         -- ISO8601 UTC
  created_at TEXT NOT NULL           -- ISO8601 UTC
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_ledger_op ON resource_daily_ledger (day_utc, entity_scope, entity_value, category, op_id);
CREATE INDEX IF NOT EXISTS idx_ledger_lookup ON resource_daily_ledger (entity_scope, entity_value, category, day_utc);
```

Notes:
- App layer enforces `units >= 0` and splits usage across UTC day boundaries at commit time.
- Over-aggregation (e.g., totals table) can be added later if needed for performance.

### Cross-Category Budgets (Modeling)

- Future concept: define a `cost_unit` conversion map in policy (e.g., 1 token = 0.001 CU, 1 request = 1 CU) to track budget consumption uniformly across categories without changing enforcement semantics.
- Implement later (post v1.1) to avoid scope creep; used for analytics and optional budget caps.

## Test Strategy

- Unit tests (memory backend):
  - Token bucket and sliding window correctness for `requests` and `tokens`.
  - Concurrency limiter (acquire/release/heartbeat/TTL expiry).
  - Minutes ledger adapter (mock DB) correctness across day boundaries (UTC).
  - Composite reservation rollback and idempotent refunding.
  - Test-mode bypass and deterministic burst behavior.
  - Mockable `TimeSource` injection to drive time-dependent behavior deterministically.

- Unit tests (Redis backend):
  - Lua script operations for sliding window and token bucket; atomic composite reservations.
  - Redis TTL behavior and cleanup.

- Integration tests:
  - Replace MCP limiter via façade; verify 429 and retry headers remain correct.
  - Chat path: estimated token reservation and refund with actual usage from provider responses.
  - Audio streaming: enforce `streams` concurrency and daily `minutes` cap, including heartbeat.
  - SlowAPI façade routes: verify ingress keys map to governor and rate limits apply consistently.
  - Failover modes: verify `fail_closed`, `fail_open`, and `fallback_memory` behaviors under Redis outage simulation.

- Chaos tests:
  - Induce Redis outages and network partitions; assert behavior per `RG_REDIS_FAIL_MODE`. Validate metrics emit `backend=fallback` and decisions match expectations.
  - Simulate wall-clock drift vs monotonic time; ensure window math uses monotonic source and remains stable.

- Property-based tests:
  - Verify token-bucket vs sliding-window equivalence under selected parameter sets (e.g., large windows, steady inter-arrival, low burst). Use Hypothesis to generate arrival patterns; assert admitted counts converge within tolerance.

- Concurrency stress tests:
  - High-contention acquire/release with lease TTL expiry, overlapping `renew` and `release`. Validate no leaks, no double-release, and correct ZSET membership behavior under churn.

- Shadow-mode validation:
  - Run legacy limiter and RG in parallel; emit delta metric when decisions differ; fail test on sustained mismatches. Cover requests/tokens and concurrency categories.

- Coverage targets: ≥ 80% for the new module with both backends; keep existing suites green.

## Rollout & Compatibility

- Feature flags: `RG_ENABLED=true|false` (default true in dev; off-by-default can be considered for safety in production).
- Legacy env compatibility layer logs a warning once per process on use.
- Shadow mode (optional): evaluate decisions with RG and existing limiter in parallel, emit delta metrics, and compare before cutover.

### Per-Module Feature Flags

- v1.1 removes per-module `RG_ENABLE_*` rollout flags. Integrations consult RG when global `RG_ENABLED=true` (or `[ResourceGovernor] enabled=true`) and fall back to legacy rails only when RG is disabled/unavailable.
- Module-specific tuning is expressed via policies + route-map and (where present) policy-id override envs (for example `RG_AUTHNZ_POLICY_ID`), not per-module enable toggles.

### Compat Map (Legacy → RG)

- General rules:
  - When both legacy and RG envs are set, RG envs take precedence.
  - On process start, detect legacy envs in use and log a once-per-process deprecation warning with the mapped `RG_*` equivalent and a removal target version.
  - Where applicable, legacy decorator parameters (e.g., SlowAPI) are ignored once RG integration is enabled; their presence is logged as informational with the resolved `policy_id`.

- MCP (examples):
  - `MCP_RATE_LIMIT_RPM` → policy `mcp.ingestion.requests.rpm`
  - `MCP_RATE_LIMIT_BURST` → policy `mcp.ingestion.requests.burst`
  - `MCP_REDIS_URL` → `RG_REDIS_URL` (alias)
  - `MCP_RATE_LIMIT_TEST_BYPASS` → `RG_TEST_BYPASS`

- Chat (examples):
  - `CHAT_GLOBAL_RPM` → policy `chat.default.requests.rpm` (scope `global`)
  - `CHAT_PER_USER_RPM` → policy `chat.default.requests.rpm` (scope `user`)
  - `CHAT_PER_CONVERSATION_RPM` → policy `chat.default.requests.rpm` (scope `conversation`)
  - `CHAT_PER_USER_TOKENS_PER_MINUTE` → policy `chat.default.tokens.per_min`
  - `TEST_CHAT_*` → `RG_TEST_*` or policy test overrides

- SlowAPI (examples):
  - `SLOWAPI_GLOBAL_RPM` → policy `ingress.default.requests.rpm`
  - `SLOWAPI_GLOBAL_BURST` → policy `ingress.default.requests.burst`
  - Decorator strings remain as config carriers; when `RGSimpleMiddleware` is attached (automatically when `RG_ENABLED=true`, unless forced off), the global SlowAPI limiter’s key function returns `None` so enforcement is handled by ResourceGovernor while decorators provide metadata only.

- Audio (examples):
  - `AUDIO_DAILY_MINUTES_CAP` → policy `audio.default.minutes.daily_cap`
  - `AUDIO_MAX_CONCURRENT_STREAMS` → policy `audio.default.streams.max_concurrent`
  - `AUDIO_STREAM_TTL_SEC` → `RG_STREAMS_TTL_SEC`

- Embeddings (examples):
  - `EMBEDDINGS_RPM` → policy `embeddings.default.requests.rpm`
  - `EMBEDDINGS_BURST` → policy `embeddings.default.requests.burst`

- Evaluations/AuthNZ/Character Chat/Web Scraping (examples):
  - `EVALS_RPM` → policy `evals.default.requests.rpm`
  - `AUTHNZ_RPM` → policy `authnz.default.requests.rpm`
  - `CHARACTER_CHAT_RPM` → policy `character_chat.default.requests.rpm`
  - `WEB_SCRAPING_RPM` → policy `web_scraping.default.requests.rpm`

### SlowAPI ASGI Middleware

- Provide an ASGI middleware adapter (e.g., `RGSlowAPIMiddleware`) that:
  - Extracts `policy_id` from route tags/decorators.
  - Derives the effective entity (auth scopes preferred; IP fallback with trusted-proxy rules).
  - Calls the governor’s `reserve` API before handler for enforcement; on deny, returns 429 with headers; on allow, sets `X-RateLimit-*` headers and proceeds. `check` is used only for diagnostics and shadow-mode comparisons.
  - On completion, performs `commit/refund` as applicable; handles streaming by renewing/releasing leases.
  - When `RG_ENABLED=false`, middleware is disabled and legacy SlowAPI behavior remains.

## Risks & Mitigations

- Partial failures across categories → perform deterministic order, rollback on failure, log anomalies.
- Redis outages → respect `RG_REDIS_FAIL_MODE` semantics (default `fallback_memory`); emit metrics indicating the active fail mode and any `backend=fallback` behavior.
- Behavior drift from legacy implementations → shadow mode comparisons and golden tests.
- Test flakiness with time windows → use monotonic time and deterministic burst in `TLDW_TEST_MODE`.
- Metrics cardinality → exclude `entity` from metric labels by default; optionally include hashed entity via `RG_METRICS_ENTITY_LABEL`; sample per-entity logs for diagnostics.
- Concurrency lease management → provide explicit `renew` and `release`; use per-lease IDs and TTLs; GC expired leases.
- IP scoping behind proxies → require `RG_TRUSTED_PROXIES` and `RG_CLIENT_IP_HEADER` to trust forwarded addresses; prefer auth scopes over IP when available.
- Policy composition ambiguity → adhere to the strictest-wins semantics and `retry_after` aggregation defined in “Policy Composition & Retry‑After”; cover these rules explicitly in tests.
- Fallback-to-memory over-admission → make behavior configurable via `RG_REDIS_FAIL_MODE` (default `fallback_memory`); emit metrics on failover; consider per-category overrides.
- Idempotency on retries → require `op_id` for reserve/commit/refund; operations are idempotent per `op_id` and handle.
- Minutes ledger edge cases → split usage across UTC day boundaries; define rounding rules; restrict retroactive commits or require `occurred_at`.
- Env flag drift → standardize on `TLDW_TEST_MODE`; `RG_TEST_BYPASS` only overrides governor behavior with documented precedence.

## Open Questions

- Minutes generalization: the shared `ResourceDailyLedger` DAL now acts as the source of truth for audio minutes (with `audio_usage_daily` retained only as a compatibility/fallback ledger); v1.1 work focuses on extending the same ledger patterns to other daily quotas (for example, tokens-per-day, evaluations, or watchlists).
- Cross-category budgets: do we want a global “cost units” budget that maps tokens/requests/minutes into a unified spend, and if so, which categories should feed into that budget in v1.1 (versus analytics-only usage)?
- Tier/source of truth: adopt AuthNZ DB as the policy SoT in production with cache + hot-reload; keep env+YAML as dev overrides.
- Multi-tenant isolation: do we introduce `tenant:{id}` as a first-class scope now?


## Acceptance Criteria

- New `ResourceGovernor` module with memory + Redis backends and the specified API.
- MCP, Chat, and SlowAPI ingress paths migrated to the unified governor with no regression in public API or tests.
- Audio streams concurrency enforced via the governor and daily minutes enforced via the shared `ResourceDailyLedger` when available, with the legacy `audio_usage_daily` tables retained as a compatibility/fallback ledger.
- Embeddings limiter replaced; Evaluations/AuthNZ/Character Chat/Web Scraping scheduled for follow-on.
- Consistent test-mode bypass and refund semantics demonstrated in tests.
- Metrics emitted with the standardized label set; basic dashboards updated.
- Compat map documented and implemented with deprecation warnings for legacy envs.
- Global `RG_ENABLED` is the canonical toggle (per-module `RG_ENABLE_*` rollout flags are removed).
- Roadmap captured: v1.1 generic DailyLedger plan documented; cross-category budget model noted for future.

## ResourceGovernor v1 status (implementation snapshot)

- Core library & policy loader:
  - Memory + Redis backends are implemented with `reserve/check/commit/refund/renew/release` semantics, metrics (`rg_decisions_total`, `rg_denials_total`, `rg_refunds_total`, `rg_concurrency_active`, `rg_wait_seconds`), and Redis fail modes driven by `RG_REDIS_FAIL_MODE`.
  - File and DB policy stores are wired via `rg_policy_store`/`rg_policy_path`, with the default YAML at `tldw_Server_API/Config_Files/resource_governor_policies.yaml` and AuthNZ-backed `rg_policies` support.
- Ingress middleware:
  - `RGSimpleMiddleware` is attached automatically whenever `RG_ENABLED=true`.
  - route-map-based resolution is in place for `/api/v1/chat/*`, `/api/v1/audio/*`, `/api/v1/embeddings*`, `/api/v1/mcp/*`, and `/api/v1/evaluations/*`, with standard `Retry-After` / `X-RateLimit-*` headers on deny and success.
- Chat:
  - `RGSimpleMiddleware` enforces `requests` on `/api/v1/chat/*` via route-map policy resolution.
  - `/api/v1/chat/completions` performs endpoint-level token reservation/commit (including durable `tokens.daily_cap` via `ResourceDailyLedger`) when a governor/policy loader are present on `app.state`.
  - The internal `ConversationRateLimiter.check_rate_limit` consults ResourceGovernor when global RG is enabled; legacy buckets are fallback-only.
- Audio:
  - Streams/jobs concurrency is enforced via the governor (`audio.default` policy, `streams`/`jobs` categories) when global RG is enabled, with Redis/in-process counters retained as a fallback when RG is unavailable.
  - Daily minutes are now enforced via the shared `ResourceDailyLedger` when available (primary path), with `audio_usage_daily` retained as a compatibility/fallback ledger when the generic daily ledger is unavailable; tests such as `tldw_Server_API/tests/Audio/test_audio_quota_rg_and_ledger.py` and `tldw_Server_API/tests/Usage/test_audio_rg_minutes_and_heartbeat.py` lock in this behavior.
  - The audio WebSocket transcription endpoint consumes `audio_quota` helpers, which in turn use the governor for streams concurrency when RG is enabled; legacy Redis counters are bypassed on the RG path.
- Embeddings:
  - Async embeddings paths (`async_embeddings.py` and `request_batching.py`) consult `AsyncRateLimiter`, which delegates token accounting to the ResourceGovernor when global RG is enabled (using `embeddings.default` policy and `RGRequest(entity="user:{id}", categories={"tokens": {"units": tokens_units}})` when available). Request-rate limiting is enforced at ingress via `RGSimpleMiddleware` for `/api/v1/embeddings*` to avoid double-enforcement; the per-user sliding-window `UserRateLimiter` remains as a fallback compatibility shim when RG is disabled or unavailable.
  - Route-map entries for `/api/v1/embeddings*` are wired through `RGSimpleMiddleware`, and end-to-end tests in `tldw_Server_API/tests/Resource_Governance/test_e2e_chat_audio_headers.py` exercise success and 429 deny behavior (with `Retry-After` / `X-RateLimit-*` headers) on `/api/v1/embeddings/providers-config` when RG is enabled.
- MCP & SlowAPI:
  - MCP unified `RateLimiter.check_rate_limit` enforces via the ResourceGovernor when global RG is enabled, reserving against `mcp.{category}` policies (`entity="client:{key}"`, `categories={"requests": {"units": 1}}`) and raising `RateLimitExceeded` based on RG decisions; the in-memory/Redis limiter is retained as a fallback-only compatibility path when RG is disabled or errors, with cutover behavior locked in by `tldw_Server_API/tests/Resource_Governance/test_rg_cutover_embeddings_mcp.py`.
  - SlowAPI-decorated routes now treat the global limiter as a configuration carrier when `RGSimpleMiddleware` is attached: the key function returns `None` in that case so enforcement is handled by ResourceGovernor, and end-to-end tests in `tldw_Server_API/tests/Resource_Governance/test_e2e_chat_audio_headers.py` assert RG-style headers on representative chat, MCP, audio, and embeddings routes.
- Evaluations:
  - The per-user `UserRateLimiter.check_rate_limit` in `tldw_Server_API/app/core/Evaluations/user_rate_limiter.py` consults the ResourceGovernor when global RG is enabled (via `_maybe_enforce_with_rg_evaluations`, using `entity="user:{user_id}"` and reserving `categories={"evaluations": {"units": 1}}` plus optional `tokens` against the `evals.default` policy). Ingress `requests` are enforced by `RGSimpleMiddleware` via `route_map.by_path` for `/api/v1/evaluations/*`; the legacy per-minute counters remain compatibility-only and are bypassed whenever an RG decision exists. Daily evaluations/tokens caps consult the shared `ResourceDailyLedger` when available (with `daily_usage` retained for cost and upgrade backfill).
  - Note on “cost/day” caps: unified evaluations endpoints currently pass `estimated_cost=0.0`, and cost caps are not enforced under RG-first decisions. If real cost enforcement is needed, introduce an RG category + daily ledger for cost units once a stable cost estimator exists; otherwise treat cost caps as deprecated/legacy-only.
  - End-to-end tests in `tldw_Server_API/tests/Resource_Governance/test_e2e_evals_authnz_character_headers.py` hit `/api/v1/evaluations/rate-limits` under a small `evals.*` policy and assert a first-success / second-429 (or 503 in fail modes) pattern with `Retry-After` and `X-RateLimit-*` headers driven by `RGSimpleMiddleware` and the route-map entry for `/api/v1/evaluations/*`.
- AuthNZ:
  - The AuthNZ `RateLimiter.check_rate_limit` in `tldw_Server_API/app/core/AuthNZ/rate_limiter.py` checks the ResourceGovernor first when global RG is enabled, reserving against `authnz.default` (or an override via `RG_AUTHNZ_POLICY_ID`) with `RGRequest(entity=identifier, categories={"requests": {"units": 1}})`; on RG denial it returns a `(False, meta)` result with `retry_after`, `policy_id`, and `rate_limit_source="resource_governor"`, and falls back to the legacy DB/Redis limiter only when RG is disabled or unavailable.
  - Cutover behavior is locked in by `tldw_Server_API/tests/Resource_Governance/test_rg_cutover_evals_authnz_character_web.py::test_authnz_rg_denies`, and HTTP-level behavior (200 vs 429 + headers) is exercised via the lightweight `/api/v1/authnz/debug/api-key-id` endpoint in `test_e2e_evals_authnz_character_headers.py`, which runs under a small `authnz.*` route-map policy when RG is enabled.
- Character Chat:
  - The `CharacterRateLimiter.check_rate_limit` in `tldw_Server_API/app/core/Character_Chat/character_rate_limiter.py` gates character operations through the ResourceGovernor when global RG is enabled, issuing `RGRequest(entity="user:{user_id}", categories={"requests": {"units": 1}})` against the `character_chat.default` (or overridden) policy; on RG denial it raises HTTP 429 with a `Retry-After` header and a policy-aware error message, while the existing Redis/in-memory limiter remains authoritative when RG is disabled or unavailable.
  - Unit-level RG decision shape is covered by `test_rg_cutover_evals_authnz_character_web.py::test_character_chat_rg_denies`, and end-to-end deny semantics (200 then 429/503, with `Retry-After`/`X-RateLimit-*` headers on 429) for the legacy `/api/v1/chats/{chat_id}/complete` endpoint are covered by `test_e2e_evals_authnz_character_headers.py::test_e2e_character_chat_deny_headers_retry_after` under a route-map policy for `/api/v1/chats/*`.
- Web Scraping:
  - The enhanced web scraping `RateLimiter.acquire` in `tldw_Server_API/app/core/Web_Scraping/enhanced_web_scraping.py` consults the ResourceGovernor when global RG is enabled, reserving `RGRequest(entity="service:web_scraping", categories={"requests": {"units": 1}})` against a `web_scraping.default` (or overridden) policy; RG denials are modeled as backoff sleeps (`retry_after` seconds) rather than HTTP 429s, after which the in-memory per-second/minute/hour limits continue to apply.
  - The RG integration is validated by `test_rg_cutover_evals_authnz_character_web.py::test_web_scraping_rg_denies`, which asserts correct `entity`, `categories`, and tags for RG reservations while leaving the existing HTTP semantics of the research/web scraping endpoints unchanged.

## Appendix — Mapping table (initial examples)

- Chat
  - Before: `ConversationRateLimiter` with `global_rpm`, `per_user_rpm`, `per_conversation_rpm`, `per_user_tokens_per_minute`.
  - After: `requests` for global/user/conversation via policy rules; `tokens` per user with burst; refund on completion.

- MCP
  - Before: in-memory/Redis with `ingestion` and `read` categories.
  - After: `requests` with tag `category=ingestion|read`; same RPMs, Redis kept via backend.

- Audio
  - Before: DB-backed daily minutes + in-process/Redis counters for streams/jobs.
  - After: `minutes` via durable ledger adapter; `streams`/`jobs` via `ConcurrencyLimiter` with TTL heartbeat.

- SlowAPI
  - Before: global limiter with key_func sentinel for TEST_MODE.
  - After: façade that derives entity key and delegates to `requests` governor, retaining decorators for route config.

- Embeddings
  - Before: sliding window per user.
  - After: `requests` for per-user RPM with burst support via governor rules.

- Evaluations/AuthNZ/Character Chat/Web Scraping
  - Before: bespoke.
  - After: move to governor with appropriate categories; keep per-feature knobs as policy inputs.

## Implementation Plan (v1 Roadmap)

Stage 0 — Spec Alignment & Stubs
- Goal: Lock semantics and prepare scaffolding for incremental delivery.
- Deliverables:
  - Align implementation with the “Policy Composition & Retry‑After” rules (strictest-wins per category; retry_after = max across denying scopes/categories) and default algorithms (token bucket first, sliding window where appropriate).
  - Guard metrics cardinality: exclude `entity` by default; gate hashed entity behind `RG_METRICS_ENTITY_LABEL=true`.
  - Add stub policy YAML at `tldw_Server_API/Config_Files/resource_governor_policies.yaml` with examples from “Policy DSL & Route Mapping”.
  - Finalize envs: `RG_POLICY_STORE`, `RG_REDIS_FAIL_MODE`, `RG_METRICS_ENTITY_LABEL`, `RG_CLIENT_IP_HEADER`, `RG_TRUSTED_PROXIES`.
- Success Criteria:
  - YAML stub loads; envs documented; PRD clarifications merged.
- Tests:
  - YAML schema/load test (file store) and basic validation of policy fields.

Stage 1 — Core ResourceGovernor Library
- Goal: Implement core API and in-memory backend with deterministic tests.
- Deliverables:
  - `ResourceGovernor` with `check/reserve/commit/refund/renew/release/peek/query/reset` and idempotency via `op_id`.
  - Memory backend implementations: token bucket + sliding window for `requests/tokens`; semaphore for `streams/jobs` with lease TTL; thin adapter for existing minutes ledger.
  - Handle lifecycle with `expires_at`, background sweeper, refund safety (cap by prior reservation).
  - `TimeSource` (monotonic) injectable for tests.
  - Metrics: `rg_decisions_total{category,scope,backend,result,policy_id}`, `rg_denials_total{...}`, `rg_refunds_total{...}`, gauges for `rg_concurrency_active{...}`.
- Success Criteria:
  - ≥80% coverage for core module; stable unit tests; deterministic behavior in `TLDW_TEST_MODE`.
- Tests:
  - Unit tests for token bucket/sliding window, composite reservations, idempotent commit/refund, concurrency leases (memory), and handle expiry using mock time.

Stage 2 — Redis Backend & Concurrency Leases
- Goal: Ship Redis path with safe lease management and fail modes.
- Deliverables:
  - Lua/MULTI-EXEC operations for windows and atomic multi-category reservations.
  - ZSET-based leases per entity/category with acquire/renew/release + GC; TTL heartbeat.
  - `RG_REDIS_FAIL_MODE=fail_closed|fail_open|fallback_memory` honored; per-policy overrides respected.
- Success Criteria:
  - Concurrency stress tests show no leaks/double-release; failover behavior observable via `backend=fallback` metrics.
- Tests:
  - Redis unit/integration tests for leases/TTL/renew; chaos tests simulating Redis outage and clock skew; property tests for windows under selected parameters.

Stage 3 — Policy Layer (Store/Loader) & Health
- Goal: Centralize policies and expose observability.
- Deliverables:
  - `PolicyLoader` with `file` and `db` stores; cache TTL (`RG_POLICY_DB_CACHE_TTL_SEC`); hot-reload.
  - Wire selection via `RG_POLICY_STORE` in settings/config; env overrides in dev.
  - AuthNZ-backed `PolicyStore` (read-only) reading `rg_policies` (Postgres/SQLite variants) + sample seed helper.
  - Health endpoint: `GET /api/v1/resource-governor/health` → `{store, snapshot_version, policy_count, updated_at}`.
- Success Criteria:
  - Health endpoint returns live snapshot data; DB store works with AuthNZ Postgres fixture.
- Tests:
  - SQLite unit test for `AuthNZPolicyStore` and seed helper.
  - Postgres-based test using existing Postgres fixtures (if available) for both `PolicyStore` and `DailyLedger` plumbing readiness.
  - Integration test verifying `/health` reports policy snapshot metadata.

Stage 4 — Ingress Middleware & Header Compatibility
- Goal: Replace ingress counting with a thin governor façade.
- Deliverables:
  - ASGI middleware (SlowAPI façade) reading route tags/decorators to resolve `policy_id` and derive entity (auth scopes preferred; IP fallback with trusted-proxy rules).
  - Enforce via `reserve` pre-handler; `commit/refund` post-handler; support streaming renew/release. Use `check` only for diagnostics and shadow-mode comparisons.
  - Standard headers mapping: `Retry-After`, `X-RateLimit-*` for `requests` where applicable.
  - Logging: mask/HMAC sensitive fields; include `handle_id`, `op_id`, `policy_id`, `denial_reason`.
- Success Criteria:
  - No double-counting; header compatibility verified; décor strings map to policies via tags.
- Tests:
  - Integration tests covering allowed/denied paths, header values, proxy scoping with `RG_TRUSTED_PROXIES` and `RG_CLIENT_IP_HEADER`.

Stage 5 — Module Integrations (MCP, Chat, Embeddings, Audio)
- Goal: Migrate high-impact modules with feature flags and parity tests.
- Deliverables:
  - MCP: replace limiter with RG `requests` and tags `category=ingestion|read`.
  - Chat: combine `requests` + `tokens`; idempotent reserve→commit(actuals)→refund(delta) flow.
  - Embeddings: unify to RG `requests`; property tests for window equivalence under steady load.
  - Audio: `streams` semaphore with TTL heartbeat; continue durable `minutes` via existing ledger; add minimal `DailyLedger` DAL wrapper with `remaining(daily_cap)` and `peek_range` (SQLite + Postgres paths) to prep v1.1.
  - Integrations are controlled by global `RG_ENABLED`; staged rollout is handled via policies + `route_map` (and policy-id overrides where present), not per-module enable flags.
- Success Criteria:
  - MCP/Chat/Embeddings parity (HTTP behavior, headers); audio streams enforce concurrency; minutes charging unchanged.
- Tests:
  - Module-specific integration tests; Postgres tests for `DailyLedger.peek_range` using `test_db_pool` fixture where available.

Stage 6 — Admin API, Observability & Rollout
- Goal: Manage policies safely and cut over with guardrails.
- Deliverables:
  - Admin policy endpoints (PUT/DELETE/GET) gated by admin auth; file store remains read-only.
  - Postgres seeder for `rg_policies` and example seed data.
  - Shadow-mode decision delta metric (legacy vs RG) and basic dashboards for `rg_*` metrics.
  - Compat map + deprecation warnings; staged rollout plan (enable MCP/Chat first, then Embeddings/SlowAPI, then Audio).
- Success Criteria:
  - Admin endpoints tested; dashboards populated; shadow-mode shows near-zero drift pre-cutover; policies/route-map allow safe rollback.
- Tests:
  - Admin API integration test for `/api/v1/resource-governor/policy` endpoints.
  - Shadow-mode drift alert test (delta metric non-zero on injected mismatch).

v1.1 (Shipped)
- Shared `ResourceDailyLedger` generalized beyond audio minutes (including tokens-per-day and workflows runs-per-day caps).
- Expanded ingress `route_map` coverage for additional high-value domains (see the shipped YAML defaults and policy store).
- Continued cutover of long-tail limiters to RG-first behavior with parity tests and shadow metrics.

### v1.1 Checklist (Shipped + Ongoing)

1. **Daily ledger for tokens‑per‑day (Chat + Embeddings)**
   - Decide the canonical daily category naming. Recommended: reuse `category="tokens"` in `ResourceDailyLedger` for all LLM token budgets so caps are cross‑module.
   - Add ledger shadow‑writes:
     - Chat: after a completion finishes and real token usage is known, write `LedgerEntry(scope="user", value=user_id, category="tokens", units=total_tokens, op_id="chat:{request_id}")`.
     - Embeddings: on each embeddings call, write `LedgerEntry(..., category="tokens", units=input_tokens_or_cost_units, op_id="emb:{request_id}")` (or keep as `requests` only if embeddings budgets stay request‑based).
     - Include a one‑time backfill for “today so far” from legacy per‑module usage tables during upgrade (same pattern as audio/evals).
   - Add enforcement:
     - Extend RG policy DSL with an optional `tokens.daily_cap` (or a dedicated `tokens_per_day` field) and document it.
     - In RG reserve/check for `tokens`, consult `ResourceDailyLedger.remaining_for_day(...)` when a daily cap is present; deny with `Retry‑After` until next UTC day boundary.
   - Tests:
     - Unit: ledger shadow‑write idempotency and backfill.
     - Integration: two requests that exceed `tokens.daily_cap` return 429 with RG headers, and legacy daily token guards are bypassed on RG‑governed routes.
   - **Status (v1.1)**: Done — enforced via RG `tokens.daily_cap` with ledger backfill and covered by `tldw_Server_API/tests/Resource_Governance/test_tokens_daily_cap.py` and `tldw_Server_API/tests/Resource_Governance/test_e2e_tokens_daily_cap.py`.

2. **Workflows daily caps via ledger**
   - Pick a ledger category (e.g., `category="workflows_runs"` or reuse `jobs` if generalized) and a policy field (e.g., `workflows.daily_cap` or `requests.daily_cap` scoped to workflows).
   - Replace the remaining inline “daily quota” checks in `endpoints/workflows.py` with:
     - `remaining = ledger.remaining_for_day("user", user_id, category, daily_cap)`
     - Deny when remaining <= 0, mirroring legacy 429/headers.
   - Shadow‑write each workflow run into the ledger with deterministic `op_id` based on workflow/run id.
   - Tests:
     - Resource_Governance e2e parity on `/api/v1/workflows/*` under a tiny daily cap.
   - **Status (v1.1)**: Done — enforced via `workflows_runs.daily_cap` and covered by `tldw_Server_API/tests/Resource_Governance/test_workflows_runs_daily_cap.py` and `tldw_Server_API/tests/Resource_Governance/test_e2e_workflows_daily_cap.py`.

3. **Legacy limiter retirement criteria + steps**
   - Criteria to flip a module to RG‑only:
     - Route is mapped in `route_map` and enforced by middleware.
     - Shadow mismatches (`rg_shadow_decision_mismatch_total{module=...}`) are near‑zero for ≥1 release window under representative load.
     - 429/Retry‑After and `X‑RateLimit-*` headers match legacy semantics in both memory and Redis backends.
   - Steps per module (chat, embeddings, authnz, evals, character‑chat, web‑scraping, audio, workflows):
     1) Keep legacy limiter evaluating only for shadow metrics; enforce via RG.
     2) Demote legacy limiter to a thin shim (no counters) and emit a deprecation warning on any direct use.
     3) After one stable release, remove shim + delete unused env aliases/tests.
   - **Status**: Ongoing — RG-first enforcement and parity/shadow coverage are in place; full shim removal is handled incrementally to preserve safe rollback.

## Engineering Implementation Plan (Concrete Steps)

This section turns the v1 roadmap into concrete, repo-level steps that can be tackled in small, reviewable PRs. It assumes work happens under the global `RG_ENABLED` toggle and keeps existing behavior as the default until each integration is stable.

### Milestone 1 — Core Library & Memory Backend

**Goal:** Land the core `ResourceGovernor` and in-memory backend with full tests, but no external integrations.

- Scaffolding
  - Add a new module directory `tldw_Server_API/app/core/Resource_Governance/`.
  - Create initial Python modules:
    - `__init__.py` (exporting public types and a factory).
    - `resource_governor.py` (facade and high-level API).
    - `backends/memory_backend.py` (in-memory implementation).
    - `categories/requests.py`, `categories/tokens.py`, `categories/concurrency.py`, `categories/minutes.py` (category managers).
    - `time_source.py` (monotonic `TimeSource` abstraction).
    - `schemas.py` (Pydantic-style dataclasses for `LimitSpec`, `EntityKey`, `ReservationHandle`, decision objects).
- Implementation
  - Implement `ResourceGovernor` with `check/reserve/commit/refund/renew/release/peek/reset` and `op_id` idempotency.
  - Implement token-bucket + optional sliding-window logic for `requests` and `tokens` in the memory backend.
  - Implement `ConcurrencyLimiter` for `streams`/`jobs` using per-entity counters with TTL and `renew`/`release`.
  - Implement a thin `MinutesLedger` adapter that wraps the existing audio minutes DB implementation (no schema changes).
  - Implement configuration wiring (without integrations) in a new settings module (for example, `tldw_Server_API/app/core/Resource_Governance/settings.py`) that reads `RG_*` env vars and `TLDW_TEST_MODE`.
- Tests
  - Add unit tests under `tldw_Server_API/tests/Resource_Governance/` for:
    - Token bucket and sliding-window semantics using a fake `TimeSource`.
    - Composite reservations across multiple categories with rollback on failure.
    - Idempotent `commit` and `refund` keyed by `op_id`.
    - Concurrency leases in memory (`streams`/`jobs`) including TTL expiry and `renew`.
    - Minutes ledger adapter calling through to the existing audio minutes DAL.
  - Ensure tests pass in `TLDW_TEST_MODE` with deterministic burst behavior.

### Milestone 2 — Redis Backend & Failover

**Goal:** Implement the Redis backend, lease semantics, and `RG_REDIS_FAIL_MODE` behavior.

- Implementation
  - Add `backends/redis_backend.py` implementing:
    - Lua or MULTI/EXEC operations for `requests`/`tokens` windows and multi-category reservations.
    - ZSET-based semaphore leases for `streams`/`jobs` with acquire/renew/release and TTL.
  - Implement failover behavior based on `RG_REDIS_FAIL_MODE` and per-policy `fail_mode` as defined in the PRD.
  - Wire Redis backend selection into the governor factory, controlled by `RG_BACKEND` and `RG_REDIS_URL`.
- Tests
  - Add unit/integration tests for the Redis backend, guarded by `RG_REAL_REDIS_URL` or equivalent test fixture envs.
  - Cover:
    - Sliding-window and token-bucket correctness in Redis vs memory backend.
    - Concurrency leases with TTL and GC.
    - Failover semantics for `fail_closed`, `fail_open`, and `fallback_memory` (including metrics tags).
  - Add chaos-style tests that simulate Redis outages and clock skew (skipped when Redis is unavailable).

### Milestone 3 — Policy Loader, YAML Stub & Health

**Goal:** Introduce the policy store/loader layer and a health endpoint, still without wiring any public endpoints to the governor.

- Implementation
  - Add `policy_loader.py` with:
    - File-backed loader reading `tldw_Server_API/Config_Files/resource_governor_policies.yaml`.
    - DB-backed loader using the `rg_policies` table in AuthNZ DB.
    - In-process caching with `RG_POLICY_DB_CACHE_TTL_SEC`.
  - Create the YAML stub at `tldw_Server_API/Config_Files/resource_governor_policies.yaml` with examples from “Policy DSL & Route Mapping”.
  - Implement a small DAL in the AuthNZ subsystem for `rg_policies` (Postgres and SQLite paths) using the schema in this PRD.
  - Implement optimistic concurrency on policy updates (using `version`), returning a 409 on conflict.
  - Add a health endpoint:
    - `GET /api/v1/resource-governor/health` in a new FastAPI router (for example, `tldw_Server_API/app/api/v1/endpoints/resource_governor.py`), returning `{store, snapshot_version, policy_count, updated_at}`.
- Tests
  - Add unit tests for file-based policy parsing and validation.
  - Add SQLite unit tests for the `AuthNZPolicyStore`.
  - Add Postgres-backed tests using the existing AuthNZ fixtures where available.
  - Add an integration test for the `/health` endpoint to ensure it reflects live policy snapshot data.

### Milestone 4 — Ingress Middleware & SlowAPI Façade

**Goal:** Replace ingress counting with a governor-backed façade while preserving existing public behavior and headers.

- Implementation
  - Add an ASGI middleware adapter (for example, `RGSlowAPIMiddleware` under `tldw_Server_API/app/core/Resource_Governance/middleware.py`) that:
    - Extracts `policy_id` from FastAPI route tags/decorators.
    - Derives the entity key using auth scopes or IP (per “Ingress Scoping & IP Derivation”).
    - Calls `reserve` before invoking handlers; on deny, returns 429 with `Retry-After` and `X-RateLimit-*` headers.
    - On completion, invokes `commit` / `refund` as appropriate and handles streaming renew/release.
  - Update `tldw_Server_API/app/api/v1/API_Deps/rate_limiting.py` to:
    - Keep SlowAPI decorators as config carriers only.
    - Map decorator strings / tags to `policy_id`s used by the middleware.
    - Respect the global `RG_ENABLED` flag.
- Tests
  - Add integration tests for representative routes verifying:
    - Allow/deny behavior and `Retry-After`/`X-RateLimit-*` headers.
    - IP scoping behavior with and without `RG_TRUSTED_PROXIES` / `RG_CLIENT_IP_HEADER`.
    - Backward compatibility for SlowAPI-decorated routes when RG is disabled.

### Milestone 5 — Module Integrations (MCP, Chat, Embeddings, Audio)

**Goal:** Wire the highest-impact modules to the governor behind feature flags and validate parity with legacy behavior.

- MCP
  - In `tldw_Server_API/app/core/MCP_unified/auth/rate_limiter.py`:
    - Replace internal logic with a thin façade to the governor `requests` category and `category=ingestion|read` tags.
    - Preserve the public API (`get_rate_limiter`, `RateLimitExceeded`), reading limits from policies/envs via the policy loader.
  - Add integration tests exercising MCP ingress paths with `RG_ENABLED` on/off.
- Chat
  - In `tldw_Server_API/app/core/Chat/rate_limiter.py`:
    - Replace `ConversationRateLimiter` internals with governor-backed `requests` + `tokens`.
    - Implement the reserve→commit(actuals)→refund(delta) flow using token estimates and actual provider usage.
    - Preserve `initialize_rate_limiter` signature and any public types.
  - Add tests that compare legacy vs RG behavior under shadow mode when both are enabled.
- Embeddings
  - In `tldw_Server_API/app/core/Embeddings/rate_limiter.py`:
    - Replace the current sliding-window limiter with a governor-backed `requests` category.
    - Ensure env-based configuration is mapped to `RG_*` and/or policy rules.
  - Add property tests checking that steady-load behavior matches the prior implementation within a tolerance.
- Audio
  - In `tldw_Server_API/app/core/Usage/audio_quota.py`:
    - Replace in-process/Redis counters for `streams`/`jobs` with the governor’s `streams`/`jobs` categories.
    - Keep the existing daily minutes ledger, wired through the `MinutesLedger` adapter.
  - Add tests that verify:
    - Concurrency limits for streams/jobs.
    - Unchanged daily minutes charging behavior.
- Flags & rollout
  - Integrations consult global `RG_ENABLED` and are mapped/enforced via `route_map` + policies (no per-module enable toggles).

**Status (v1.0)**:
- MCP: `tldw_Server_API/app/core/MCP_unified/auth/rate_limiter.py` consults RG when global `RG_ENABLED` is active, with legacy limiters retained as fallback-only shims.
- Chat: `tldw_Server_API/app/core/Chat/rate_limiter.py` consults RG when global `RG_ENABLED` is active; `/api/v1/chat/completions` performs endpoint-level token reserve→commit against `chat.*` policies.
- Embeddings API: `tldw_Server_API/app/core/Embeddings/rate_limiter.py` provides an RG-backed async limiter (`AsyncRateLimiter.check_rate_limit_async`) when global `RG_ENABLED` is active, with legacy sliding-window counters retained as fallback-only shims.
- Embeddings server: `tldw_Server_API/app/core/Embeddings/Embeddings_Server/Embeddings_Create.py` consults RG when global `RG_ENABLED` is active, falling back to the legacy bucket when RG is disabled or unavailable.
- Audio: `tldw_Server_API/app/core/Usage/audio_quota.py` consults RG for streams/jobs concurrency when global `RG_ENABLED` is active, while retaining the daily minutes ledger and usage DAL for billing/quotas.

**Remaining v1.1+ module integration follow-ups**:
- Ensure that, once RG parity is validated for each module, the corresponding legacy limiter paths are either:
  - Slimmed down to thin shims that purely forward to ResourceGovernor, or
  - Clearly documented as intentionally retained (for example, internal-only diagnostic helpers or offline maintenance scripts).

### Milestone 6 — Admin API, Shadow Mode & Cutover

**Goal:** Add admin policy management, observability, and a safe rollout path with shadow mode and deprecation warnings.

- Admin API
  - Implement the admin endpoints described in the PRD under a new router (for example, `tldw_Server_API/app/api/v1/endpoints/resource_governor_admin.py`):
    - `GET /api/v1/resource-governor/policies`
    - `GET /api/v1/resource-governor/policy/{policy_id}`
    - `PUT /api/v1/resource-governor/policy/{policy_id}` with optimistic concurrency on `version`.
    - `DELETE /api/v1/resource-governor/policy/{policy_id}`
  - Wire these endpoints through AuthNZ to require an `admin` role (single-user mode treated as admin).
- Shadow mode & metrics
  - Add a shadow-mode path in the major modules (MCP, Chat, Embeddings, SlowAPI ingress) that:
    - Evaluates both the legacy limiter and the governor.
    - Emits `rg_shadow_decision_mismatch_total` when decisions differ.
  - Build basic dashboards/alerts around `rg_*` metrics for drift and failover visibility.
- Deprecation & cutover
  - Implement legacy→RG env mappings and once-per-process deprecation warnings as described in “Compat Map”.
  - Plan a staged enablement:
    - Enable RG for MCP and Chat first in shadow mode, then full enforcement.
    - Move Embeddings and SlowAPI ingress next.
    - Finally enable Audio concurrency once validated.
  - Update documentation and examples to reference `RG_*` envs and policies as the canonical configuration surface.

**Status (v1.0)**:
- Policy health and basic admin introspection are available via `tldw_Server_API/app/api/v1/endpoints/resource_governor.py` (`GET /api/v1/resource-governor/health` and related endpoints) and `AuthNZPolicyAdmin` in `tldw_Server_API/app/core/Resource_Governance/policy_admin.py`, backed by the AuthNZ DB when configured.
- Shadow-mode comparison is implemented for several modules:
  - MCP unified limiter (`_maybe_enforce_with_rg_mcp` + `record_shadow_mismatch`).
  - Embeddings API (`AsyncRateLimiter.check_rate_limit_async` with shadow comparisons when `RG_SHADOW_EMBEDDINGS` is enabled).
  - Chat rate limiter (`_maybe_enforce_with_rg_chat` plus legacy limiter evaluation for side-by-side behavior).
- Admin CRUD for policies is implemented via `tldw_Server_API/app/api/v1/endpoints/resource_governor.py` (`GET/PUT/DELETE` under `/api/v1/resource-governor/*`) backed by `AuthNZPolicyAdmin`. A complete cutover (with legacy limiter removal) remains follow-up work; operators should continue to treat RG as the primary enforcer where enabled, with legacy limiters left in place as safety shims until metrics and tests demonstrate parity.

### Milestone 7 — Cleanup

**Goal:** Remove obsolete limiters once parity is proven and RG is stable.

- Remove or slim down legacy modules listed under “Deletions / Consolidation Targets”, leaving only minimal façade shims that import ResourceGovernor and raise deprecation warnings when used.
- Remove any legacy env parsing that duplicates policy/env behavior once migrations are complete.
- Simplify test suites by:
  - Removing legacy limiter-specific tests where RG covers the same behavior.
  - Keeping a small number of golden tests to guard against regressions in migration shims.

### Phase 6 / 7: Legacy Limiter Retirement Checklist

Use this checklist to track when modules move from “RG + legacy limiter” to “RG-only (legacy as thin shim or removed)”. Entries should only be marked complete once HTTP behavior, metrics, and shadow-mode comparisons show parity.

| Domain        | Primary legacy limiter/module                                           | RG controls                                      | Status (v1.0)                      | Next action for RG-only                                                                 |
|--------------|-------------------------------------------------------------------------|--------------------------------------------------|------------------------------------|----------------------------------------------------------------------------------------|
| AuthNZ       | `tldw_Server_API/app/core/AuthNZ/rate_limiter.py::RateLimiter`         | `RG_ENABLED`, `RG_AUTHNZ_POLICY_ID`              | RG + legacy (shadow/partial)       | Decide whether to route all AuthNZ rate limits through RG and slim DB/Redis logic down |
| Chat         | `tldw_Server_API/app/core/Chat/rate_limiter.py::ConversationRateLimiter` | `RG_ENABLED`, `RG_CHAT_POLICY_ID`                | RG + legacy (shadow comparisons; RG-primary default) | Continue validating parity; once stable, keep `ConversationRateLimiter` as a minimal shim only for diagnostics/tests. |
| Embeddings   | `tldw_Server_API/app/core/Embeddings/rate_limiter.py::UserRateLimiter` | `RG_ENABLED`, `RG_EMBEDDINGS_POLICY_ID`          | RG + legacy (shadow comparisons)   | Promote RG decisions to primary, keep only minimal legacy path for diagnostics if needed|
| Embeddings server | `tldw_Server_API/app/core/Embeddings/Embeddings_Server/Embeddings_Create.py::TokenBucketLimiter` | `RG_ENABLED`, `RG_EMBEDDINGS_SERVER_POLICY_ID`   | RG + legacy (fallback)             | Treat RG as authoritative, shrink TokenBucket limiter to internal shim or remove       |
| Character Chat | `tldw_Server_API/app/core/Character_Chat/character_rate_limiter.py::CharacterRateLimiter` | `RG_ENABLED`, `RG_CHARACTER_CHAT_POLICY_ID`      | RG + legacy (shadow/fallback)      | Confirm RG coverage and convert legacy limiter to a thin shim or retire it             |
| Web scraping | `tldw_Server_API/app/core/Web_Scraping/enhanced_web_scraping.py` internal limiter paths | `RG_ENABLED`, `RG_WEB_SCRAPING_POLICY_ID`        | RG wired; legacy helpers present   | Verify RG covers production paths; deprecate old per-module counters where safe        |
| Audio        | `tldw_Server_API/app/core/Usage/audio_quota.py` per-user counters (streams/jobs) | `RG_ENABLED`                                     | RG for concurrency; legacy minutes | Keep minutes ledger as designed; consider phasing out non-RG stream/job counters       |
| SlowAPI ingress | `tldw_Server_API/app/api/v1/API_Deps/rate_limiting.py` (SlowAPI decorators) | `RG_ENABLED`      | Middleware + legacy decorators     | Move remaining ingress counting to RG middleware only and leave decorators as tags     |

### Remaining adoption checklist (AuthNZ + RG integration)

- New endpoints:
  - Ensure new public/admin endpoints under `/api/v1/chat/*`, `/api/v1/embeddings*`, `/api/v1/audio/*`, `/api/v1/evaluations*`, `/api/v1/mcp/*`, `/api/v1/tools/*`, `/api/v1/workflows/*`, `/api/v1/media/*`, and related domains follow the “new endpoints checklist”: authenticate via `get_auth_principal`, authorize via `require_permissions(...)` / `require_roles(...)`, and, when latency/cost-sensitive or user-facing, decide whether they need a ResourceGovernor policy + `route_map` entry.
  - When adding RG-aware endpoints, prefer wiring them directly to governor-backed helpers (e.g., `_maybe_enforce_with_rg_chat`, embeddings RG limiter, audio concurrency governors) instead of introducing new per-module token buckets.

- Mode/profile-based behavior:
  - `tldw_Server_API/app/core/Resource_Governance/deps.py::derive_entity_key` derives user-scoped entity keys from `request.state.user_id` and API-key scopes; these values are populated by AuthNZ flows and MUST remain derived from `AuthPrincipal`, not written directly by other modules.
  - Embeddings tenant quotas (`/api/v1/embeddings/tenant/quotas`) and ingestion backpressure guards (`guard_backpressure_and_quota`) use mode/profile checks (`is_single_user_mode()` / `AUTH_MODE` / `PROFILE`) only to disable tenant-style RPS quotas in local single-user/dev scenarios; they do not bypass ResourceGovernor policies where configured.
  - Rate limiting shims in `auth_deps.check_rate_limit` / `check_auth_rate_limit` may bypass AuthNZ-level rate limits for the configured single-user API key in local/dev scenarios; RG-based ingress controls should be preferred for new rate limits and, over time, these shims can be revisited or simplified.

- Legacy limiters and RG parity:
  - Chat: continue to validate parity between `ConversationRateLimiter` and RG decisions under `RG_ENABLED=true` using `tldw_Server_API/tests/Resource_Governance/test_chat_rg_limiter_cutover.py` and chat HTTP-level tests; once mismatches are rare and headers align, `ConversationRateLimiter` can remain as a minimal diagnostics shim only.
  - Embeddings API and embeddings server: consult RG when `RG_ENABLED=true`; legacy `UserRateLimiter` and `TokenBucketLimiter` implementations remain as compatibility shims for non-RG deployments and should shrink over time.
  - Evaluations: `UserRateLimiter.check_rate_limit` consults RG first when `RG_ENABLED=true`; per-minute counters in the SQLite `user_rate_limits` / `rate_limit_tracking` tables remain as a secondary enforcement layer when RG is disabled or unavailable. Daily evaluations/tokens caps consult `ResourceDailyLedger` when available (with `daily_usage` retained for cost and backfill). Cutover behavior and RG metadata (`policy_id`, `retry_after`, `rate_limit_source`) are locked in by `test_rg_cutover_evals_authnz_character_web.py::test_evaluations_rg_denies` and HTTP-level headers/tests in `test_e2e_evals_authnz_character_headers.py`.
  - AuthNZ: the AuthNZ `RateLimiter` consults RG when `RG_ENABLED=true` and falls back to the existing DB/Redis-backed limiter when RG is disabled or fails; the legacy limiter remains in place for installations that do not enable RG and is explicitly documented here as a compatibility shim rather than a migration target for this phase.
  - Character Chat: `CharacterRateLimiter.check_rate_limit` consults RG when `RG_ENABLED=true` and raises 429 on RG denial; the internal Redis/in-memory limiter is kept as a fallback path when RG is disabled or unavailable.
  - Web Scraping: the enhanced web scraping `RateLimiter.acquire` uses RG for backoff when `RG_ENABLED=true`, but HTTP semantics for the scraping endpoints remain unchanged (no direct 429 mapping). The in-process rate limiter is retained as the primary guard, with RG modeled as an additional safety rail.
  - Audio: RG-backed concurrency for streams/jobs is controlled by global `RG_ENABLED`, while daily minutes are enforced via `ResourceDailyLedger` (with `audio_usage_daily` used only for backfill and fallback). The remaining non-RG concurrency counters are explicitly treated as legacy shims for environments that do not enable RG audio integration.

- Previously RG-free ingress routes now governed in v1.1:
  - `/api/v1/research/*` → `research.default`
  - `/api/v1/workflows/*` and `/api/v1/scheduler/workflows/*` → `workflows.default`
  - `/api/v1/prompt-studio/*` → `prompt_studio.default`
  - `/api/v1/rag/*` → `rag.default`
  - `/api/v1/media/*` → `media.default`
