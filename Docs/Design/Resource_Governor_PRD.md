# Resource Governance PRD (v1)

## Summary

Multiple independent rate limiters and quota mechanisms exist across the codebase with overlapping logic and inconsistent semantics (burst behavior, refunding, test bypass, metrics, persistence). This PRD proposes a unified ResourceGovernor capable of governing per-entity resource limits for requests, tokens, streams, jobs, and minutes using a shared interface and pluggable backends (in-memory and Redis) with consistent test-mode behavior, metrics tags, and refund semantics.

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

## Personas & Entities

- Persona: API user (API key/JWT user id), service client (MCP client id), conversation id (Chat), IP address (ingress fallback), system services.
- Entity key format: `scope:value` where scope ∈ {`user`, `api_key`, `client`, `ip`, `conversation`, `tenant`, `service`}.
- Effective entity: per endpoint determines which entity keys apply. Examples:
  - Chat: `user:{id}`, optionally `conversation:{id}`; tokens reserved under `tokens` and request under `requests`.
  - Audio stream: `user:{id}` governing `streams` semaphore and `minutes` ledger.
  - MCP: `client:{id}` or `user:{id}` with `requests` in categories `ingestion` or `read` via tags.

## Functional Requirements

- Core interface:
  - check(spec) → decision: Returns allow/deny with retry_after and metadata.
  - reserve(spec, op_id) → handle: Reserves resources atomically across categories (best-effort rollback on partial failures). `op_id` is an idempotency key.
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

- Policy composition semantics (strictest wins):
  - For each category, compute remaining headroom per applicable scope (global, tenant, user, conversation, etc.). Effective headroom is the minimum across scopes (strictest constraint).
  - Allow if the effective headroom ≥ requested units; otherwise deny for that category.
  - Compute per-scope `retry_after`; the category’s `retry_after` is the maximum across denying scopes. Overall `retry_after` is the maximum across denied categories.

## Configuration

- New standardized env vars (legacy aliases maintained via mapping during migration):
  - `RG_BACKEND`: `memory` | `redis`
  - `RG_REDIS_URL`: Redis URL
  - `RG_TEST_BYPASS`: `true|false` (defaults to honoring `TEST_MODE`)
  - `RG_REDIS_FAIL_MODE`: `fail_closed` | `fail_open` | `fallback_memory` (defaults to `fail_closed`). Controls behavior on Redis outages.
    - Default `fail_closed` is recommended for write paths and global-coordination categories; use `fallback_memory` only for non-critical categories where local over-admission is acceptable.
  - `RG_CLIENT_IP_HEADER`: Header to trust for client IP when behind trusted proxies (e.g., `X-Forwarded-For`, `CF-Connecting-IP`).
  - `RG_TRUSTED_PROXIES`: Comma-separated CIDRs for trusted reverse proxies; when unset, IP scope uses the direct remote address only.
  - `RG_METRICS_ENTITY_LABEL`: `true|false` (default `false`). If true, include hashed entity label in metrics; otherwise exclude to avoid high cardinality.
  - `RG_POLICY_STORE`: `file` | `db` (default `file`). In production, prefer `db` and use AuthNZ DB as SoT; in dev, `file` + env overrides.
  - `RG_POLICY_DB_CACHE_TTL_SEC`: TTL for DB policy cache (default 10s) when `RG_POLICY_STORE=db`.
  - Category defaults (fallbacks applied per module if unspecified):
    - `RG_REQUESTS_RPM_DEFAULT`, `RG_REQUESTS_BURST`
    - `RG_TOKENS_PER_MIN_DEFAULT`, `RG_TOKENS_BURST`
    - `RG_STREAMS_MAX_CONCURRENT_DEFAULT`, `RG_STREAMS_TTL_SEC`
    - `RG_JOBS_MAX_CONCURRENT_DEFAULT`
    - `RG_MINUTES_DAILY_CAP_DEFAULT` (still enforced via durable ledger)

- Back-compat mapping examples:
  - `MCP_RATE_LIMIT_*` → RequestsLimiter rules for service `mcp`.
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

- Routes attach `policy_id` via FastAPI route tags or decorators. An ASGI middleware reads the tag and consults the governor. SlowAPI decorators remain as config carriers only.
- Policy reload: file watcher or periodic TTL check; swap policies atomically. Invalid updates are rejected with clear logs.
- Per-category overrides: policy `fail_mode` may override `RG_REDIS_FAIL_MODE` for that policy/category.
- Stub location: `tldw_Server_API/Config_Files/resource_governor_policies.yaml` provides default examples and hot-reload settings.
- Source of Truth in production: policies stored in AuthNZ DB (e.g., `rg_policies`) with JSON payloads and `updated_at` timestamps.
  - Cache layer with TTL and/or change feed; hot-reload applies atomically across workers.
  - Env vars remain as development overrides; DB wins in production when present.

### Admin API (Minimal)

- Read-only snapshot:
  - `GET /api/v1/resource-governor/policy` → metadata (version, store, count); `?include=ids|full` for IDs or full payloads.
- Admin (requires `admin` role; single-user treated as admin):
  - `GET /api/v1/resource-governor/policies` → list `{id, version, updated_at}`
  - `GET /api/v1/resource-governor/policy/{policy_id}` → `{id, version, updated_at, payload}`
  - `PUT /api/v1/resource-governor/policy/{policy_id}` → upsert JSON payload; optional explicit `version` (auto-increments if omitted)
  - `DELETE /api/v1/resource-governor/policy/{policy_id}` → delete policy
- Behavior:
  - When `RG_POLICY_STORE=db`, successful writes trigger best-effort PolicyLoader refresh; file store remains read-only.
  - All responses include `{status: ok|error}` and details on errors; avoid logging PII.

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

- Plan: Introduce a generic `DailyLedger` abstraction to extend beyond `minutes` (e.g., `tokens_per_day`).
- Interface (concept): `add(entity, category, units, occurred_at_utc)`, `remaining(entity, category, day)`, `peek(entity, category)`, `reset(...)`.
- Storage: reuse existing DB with a generalized schema (`day_utc`, `entity`, `category`, `units`), plus indexes; migrate audio minutes to this ledger.
- Semantics: UTC-based partitioning; consistent rounding per policy; idempotent commits via `op_id`.
- Rollout: shadow existing minutes ledger first; then cut over with migration script. Target version: v1.1.

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

- In addition to the global toggle, each integration can be enabled/disabled independently during migration:
  - `RG_ENABLE_MCP`
  - `RG_ENABLE_CHAT`
  - `RG_ENABLE_SLOWAPI`
  - `RG_ENABLE_AUDIO`
  - `RG_ENABLE_EMBEDDINGS`
  - `RG_ENABLE_EVALUATIONS`
  - `RG_ENABLE_AUTHNZ`
  - `RG_ENABLE_CHARACTER_CHAT`
  - `RG_ENABLE_WEB_SCRAPING`
  - `RG_ENABLE_EMBEDDINGS_SERVER`
- Convention: any unset module flag inherits from `RG_ENABLED`.

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
  - Decorator strings remain as config carriers; actual enforcement is via RG when `RG_ENABLE_SLOWAPI=true`.

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
  - Calls RG `check/reserve` before handler; on deny, returns 429 with headers; on allow, sets `X-RateLimit-*` headers and proceeds.
  - On completion, performs `commit/refund` as applicable; handles streaming by renewing/releasing leases.
  - When `RG_ENABLE_SLOWAPI=false`, middleware is disabled and legacy SlowAPI behavior remains.

## Risks & Mitigations

- Partial failures across categories → perform deterministic order, rollback on failure, log anomalies.
- Redis outages → auto-fallback to in-memory with warning; emit `backend=fallback` metric tag.
- Behavior drift from legacy implementations → shadow mode comparisons and golden tests.
- Test flakiness with time windows → use monotonic time and deterministic burst in `TLDW_TEST_MODE`.
- Metrics cardinality → exclude `entity` from metric labels by default; optionally include hashed entity via `RG_METRICS_ENTITY_LABEL`; sample per-entity logs for diagnostics.
- Concurrency lease management → provide explicit `renew` and `release`; use per-lease IDs and TTLs; GC expired leases.
- IP scoping behind proxies → require `RG_TRUSTED_PROXIES` and `RG_CLIENT_IP_HEADER` to trust forwarded addresses; prefer auth scopes over IP when available.
- Policy composition ambiguity → define strictest-wins semantics (min headroom across applicable scopes) per category; compute `retry_after` as max across denying scopes and categories.
- Fallback-to-memory over-admission → make behavior configurable via `RG_REDIS_FAIL_MODE` (default `fail_closed`); emit metrics on failover; consider per-category overrides.
- Idempotency on retries → require `op_id` for reserve/commit/refund; operations are idempotent per `op_id` and handle.
- Minutes ledger edge cases → split usage across UTC day boundaries; define rounding rules; restrict retroactive commits or require `occurred_at`.
- Env flag drift → standardize on `TLDW_TEST_MODE`; `RG_TEST_BYPASS` only overrides governor behavior with documented precedence.

## Open Questions

- Minutes generalization: planned for v1.1 via a generic DailyLedger (see Minutes Ledger Semantics). For v1, reuse audio minutes ledger only.
- Cross-category budgets: do we want a global “cost units” budget that maps tokens/requests into a unified spend?
- Tier/source of truth: adopt AuthNZ DB as the policy SoT in production with cache + hot-reload; keep env+YAML as dev overrides.
- Multi-tenant isolation: do we introduce `tenant:{id}` as a first-class scope now?


## Acceptance Criteria

- New `ResourceGovernor` module with memory + Redis backends and the specified API.
- MCP, Chat, and SlowAPI ingress paths migrated to the unified governor with no regression in public API or tests.
- Audio streams concurrency and minutes cap enforced via the governor, with durable minutes persisted as before.
- Embeddings limiter replaced; Evaluations/AuthNZ/Character Chat/Web Scraping scheduled for follow-on.
- Consistent test-mode bypass and refund semantics demonstrated in tests.
- Metrics emitted with the standardized label set; basic dashboards updated.
- Compat map documented and implemented with deprecation warnings for legacy envs.
- Per-module feature flags available and honored during phased rollout.
- Roadmap captured: v1.1 generic DailyLedger plan documented; cross-category budget model noted for future.

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
  - Clarify policy composition (strictest-wins per category; retry_after = max across denying scopes/categories) and default algorithms (token bucket first, sliding window where appropriate).
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
  - Enforce via `check/reserve` pre-handler; `commit/refund` post-handler; support streaming renew/release.
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
  - Per-module flags (`RG_ENABLE_*`) inherit from `RG_ENABLED`.
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
  - Compat map + deprecation warnings; per-module rollout plan (enable MCP/Chat first, then Embeddings/SlowAPI, then Audio).
- Success Criteria:
  - Admin endpoints tested; dashboards populated; shadow-mode shows near-zero drift pre-cutover; staged flags allow safe rollback.
- Tests:
  - Admin API integration test for `/api/v1/resource-governor/policy` endpoints.
  - Shadow-mode drift alert test (delta metric non-zero on injected mismatch).

Post v1.0 (Planned v1.1)
- Generic `DailyLedger` for tokens-per-day and future categories; migration of audio minutes to generic ledger.
- Cross-category “cost unit” modeling for analytics and optional budgets (no enforcement changes).
- Additional providers/integrations as needed.
