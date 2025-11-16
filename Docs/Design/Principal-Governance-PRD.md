# Principal & Governance PRD (v0.1)

## Summary

AuthNZ today has two powerful but partially independent concepts:

- Principals: users, API keys, virtual keys, service tokens, single-user mode.
- Guardrails: rate limits, lockouts, quotas, budgets, and usage logging.

They are wired together per-feature (AuthNZ rate limiter, quotas, virtual key budgets, LLM usage logs, login lockouts, etc.), which creates duplication and drift. This PRD proposes:

1. A unified `AuthPrincipal` / `AuthContext` model that represents “who is calling” and their claims.
2. A unified governance layer that treats all guardrails as resource counters on that principal, with consistent semantics and storage.

The goal is to make all request-time AuthNZ decisions flow through a single, explicit principal object and a single governance abstraction, while remaining backwards-compatible and testable.

## Related Documents

- `Docs/Design/User-Unification-PRD.md` – single vs multi-user behavior and deployment profiles.
- `Docs/Design/User-Auth-Deps-PRD.md` – unified auth dependencies and claim-first authorization.
- `Docs/Design/Resource_Governor_PRD.md` – global, cross-module resource governance (`ResourceGovernor`).

---

## Problems & Symptoms

### 1. Fragmented Principal Representation

- Multiple ways to derive the current user and API key:
  - `User_DB_Handling.verify_jwt_and_fetch_user` and API key branches.
  - `tldw_Server_API/app/api/v1/API_Deps/auth_deps.py:get_current_user` and related helpers with their own auth/session logic.
  - `llm_budget_guard.enforce_llm_budget` resolving keys from headers and re-attaching `request.state.api_key_id` / `user_id`.
  - `UsageLoggingMiddleware` assuming `request.state.user_id` / `api_key_id`.
- Each component re-derives identity and attaches partial context to `request.state` (user id, key id, orgs/teams, scope) with defensive try/except.
- Single-user mode and multi-user mode diverge at the dependency level instead of at configuration.

**Current compatibility surface**

- Existing public dependencies (`auth_deps.get_current_user`, `User_DB_Handling.get_request_user`) are widely used across endpoints and tests.
- They:
  - Return dict- or `User`-shaped objects, not `AuthPrincipal`.
  - Write `request.state.user_id/api_key_id/org_ids/team_ids` directly instead of using `AuthContext`.
  - Contain mode-specific behavior (e.g., synthetic single-user admin, direct `SINGLE_USER_API_KEY` checks).
- These dependencies MUST be treated as the compatibility surface in v1:
  - Internally, they will be refactored to delegate to `get_auth_principal` / `AuthContext`.
  - Externally, their return shape and core HTTP semantics (401 vs 403, error detail strings) must remain stable unless explicitly versioned.

### 2. Fragmented Governance / Guardrails

- Separate yet similar guardrail systems:
  - `AuthNZ.rate_limiter.RateLimiter` (requests/minute + login lockouts, Redis + DB).
  - `AuthNZ.quotas` (`vk_jwt_counters`, `vk_api_key_counters`).
  - `AuthNZ.virtual_keys` + `llm_budget_guard` (day/month token and USD limits).
  - `AuthNZ.usage_logging_middleware` (usage_log rows).
  - Session revocation and token blacklist (session and token lifetime vs. revocation).
- All enforce variations of “increment a counter for some identifier, compare to a limit, maybe reject”, but with different:
  - Identifiers (`identifier`, `api_key_id`, `jti`, `user_id`).
  - Tables and schemas (`rate_limits`, `failed_attempts`, `account_lockouts`, `vk_*`, `llm_usage_log`, `usage_log`).
  - Windows (minute-based, day-based, month-based, rolling vs calendar).
  - Test-mode behavior and metrics.

### 3. Hard-to-Explain Behavior

- It is non-obvious which limits apply to which request:
  - A virtual API key hitting `/chat/completions` is subject to:
    - LLM budget guard (day/month tokens + USD).
    - AuthNZ request-per-minute limiter (possibly service vs user).
    - Endpoint-specific rate limiting and usage logging elsewhere in the stack.
- Diagnosing “why was this request rejected?” often requires tracing multiple modules and DB tables.
- Adding new guardrails risks duplicating logic.

---

## Goals

### Primary Goals

- **G1: Unified Principal Model**
  - Introduce an `AuthPrincipal` / `AuthContext` object representing the authenticated caller, populated once per request and attached to `request.state.auth`.
  - Capture identity (user, API key, service token, single-user), claims (roles, permissions), membership (orgs/teams), and credentials (token type, jti, key id).

- **G2: Unified Governance Interface**
  - Introduce a governance abstraction that can enforce:
    - Rate limits (requests/min, burst).
    - Quotas and budgets (tokens/day, USD/month).
    - Login lockouts and suspicious-activity lockouts.
  - All keyed by `AuthPrincipal` (or a principal-derived identifier) plus metric name and scope.

- **G3: Observability & Debuggability**
  - For any rejected request, make it possible to answer:
    - “Which principal?”, “Which rule?”, “Which metric/bucket?”, “Current count vs limit?”, “Which module blocked it?”
  - Provide consistent metrics and structured logs.

### Secondary Goals

- Reduce duplicate SQL and Redis usage patterns in guardrail code.
- Reduce repeated derivation of `user_id`, `api_key_id`, orgs/teams, and scope.
- Make test behavior predictable and configurable for governance (test bypass, deterministic quotas).

### Non-Goals (Initial Version)

- Replacing all non-AuthNZ limiters (e.g., chat, MCP, embeddings) immediately. Those are covered by the existing `Resource_Governor_PRD.md` and will be integrated later.
- Changing higher-level product semantics (e.g., default LLM budgets, login lockout thresholds).
- Replacing existing `usage_log` / `llm_usage_log` schemas in v1; we will adapt to them.

---

## Proposed Solution

### 1. AuthPrincipal / AuthContext

Define a single principal model that is created as early as possible in the auth pipeline and reused everywhere.

**Tentative shape**

- Identity:
  - `subject_id: str` (e.g., “user:123”, “service:workflow-engine”, “api_key:42”).
  - `user_id: Optional[int]` (numeric user id when available).
  - `api_key_id: Optional[int]`.
  - `subject_type: Literal["user","service","api_key","anonymous","single_user"]`.
  - `token_type: Optional[str]` (“access”, “refresh”, “service”, “virtual”, etc.).
  - `jti: Optional[str]`.
- Claims:
  - `roles: list[str]`.
  - `permissions: list[str]`.
  - `is_admin: bool`.
  - `tenant_id / org_ids / team_ids`.
- Request context:
  - `ip: Optional[str]`.
  - `user_agent: Optional[str]`.
  - `request_id: Optional[str]`.

Throughout this PRD:

- `AuthPrincipal` refers to the identity and claims of the caller.
- `AuthContext` refers to `AuthPrincipal` plus transient request metadata (e.g., IP, User-Agent, request id).

**Creation flow**

- Single dependency `get_auth_principal(request: Request) -> AuthPrincipal`:
  - Detects credential:
    - Single-user API key (if configured).
    - API key header (`X-API-KEY` / `Authorization: Bearer` with key).
    - JWT (access/service/virtual).
  - Validates credential via existing services:
    - `JWTService` / `SessionManager` + `TokenBlacklist`.
    - `APIKeyManager`.
  - Hydrates user data & RBAC once (existing lookup from AuthNZ DB).
  - Attaches principal to `request.state.auth` and sets `request.state.user_id`, `api_key_id`, etc. for backwards compatibility.
  - Sets content scope via `set_scope` using principal’s org/team context.

**Integration**

- Refactor:
  - `User_DB_Handling.verify_jwt_and_fetch_user`.
  - `auth_deps.get_current_user`, test-mode stubs.
  - `llm_budget_guard`, `UsageLoggingMiddleware`, and any code reading `request.state.user_id` directly.
- Add a thin `get_current_user` dependency that just returns `principal.user` (or raises 401).

#### Initialization order

- Some middlewares (e.g., usage logging, budget guards) run before route dependencies are resolved.
- We will support two safe patterns:
  - A lightweight “auth bootstrap” middleware that populates `request.state.auth` once per request using `get_auth_principal`.
  - Middlewares that lazily call `get_auth_principal` themselves when they first need auth context.
- Both patterns must be idempotent and safe under repeated calls within a single request.

### 2. Unified Governance Layer for AuthNZ

Introduce an AuthNZ-scoped governance interface that uses the principal model to enforce guardrails. `AuthGovernor` is an AuthNZ-specific façade over the shared `ResourceGovernor` described in `Resource_Governor_PRD.md`, providing AuthNZ-focused metric names, defaults, and integration points while delegating common rate-limit and quota mechanics to the underlying governor.

**Tentative interface**

- `AuthGovernor.check_and_increment(principal, metric, amount=1, window=None, scope=None) -> (allowed, metadata)`
  - `metric`: e.g., `"requests"`, `"login_attempts"`, `"llm_tokens"`, `"llm_usd"`.
  - `window`: e.g., `"1m"`, `"1d"`, `"30d"`, `"calendar_day"`.
  - `scope`: optional string or tuple (e.g., endpoint path, key_id, org_id, team_id); default derived from principal + request.
  - `metadata`: includes current count, limit, bucket, retry-after, and any additional diagnostic info.

**Semantics**

- **Atomicity**:
  - Increments are atomic per `(principal, metric, window, scope)` within the backing store (single Redis command or single DB transaction).
- **Error handling**:
  - If the primary backend (e.g., Redis) fails, `AuthGovernor` falls back to the durable backend (DB) when possible.
  - If all backends fail, `AuthGovernor` logs the failure and follows a per-metric policy (defaulting to fail-open for non-security metrics; security-critical metrics may be configured to fail-closed).
- **Idempotency / deduplication**:
  - Calls are not implicitly idempotent; each invocation increments the counter.
  - Call sites that require deduplication should include an idempotency key in `scope` (or use future explicit idempotency support) so the governor can group/reuse increments if needed.

**Guardrails mapped to metrics**

- Guardrails must support per-org and per-team enforcement as first-class, not only per principal. Metrics may be keyed by principal alone, by org, by team, or by combinations (e.g., principal+org).

- Login attempts & lockouts:
  - `metric="login_attempts"`, window configurable (e.g., 15 minutes).
  - Replace custom logic in `rate_limiter.record_failed_attempt`.
- AuthNZ rate limits:
  - `metric="auth_requests"`, `window="1m"`, per principal (user or API key).
  - Exposed as `RateLimiter` facade using `AuthGovernor` under the hood.
- Virtual key budgets:
  - `metric="llm_tokens_day"`, `llm_tokens_month`, `llm_usd_day`, `llm_usd_month`.
  - Implemented via `AuthGovernor` using `llm_usage_log` as underlying store for counts.
  - Day- and month-based budgets are computed over calendar UTC days and months (midnight UTC boundaries), aligned with existing `llm_usage_log` queries.
- Additional internal metrics:
  - `metric="password_resets"`, `registration_requests`, `admin_actions`, etc. as needed.

**Storage & backends**

- Reuse existing tables for v1:
  - `llm_usage_log` for LLM tokens/usd.
  - `usage_log` for request-level metrics where appropriate.
  - `failed_attempts` / `account_lockouts` initially, then gradually unified behind the governor.
  - For v1, `llm_usage_log` serves both as the detailed accounting ledger and as the source for budget enforcement. Future versions may rely primarily on aggregated tables (e.g., `llm_usage_daily`) for enforcement while retaining `llm_usage_log` as the canonical ledger.
- Provide a simple, local in-memory cache (if needed) for hot metrics (e.g., login attempts) for test and small deployments.
- Integrate Redis (when configured) via `DatabasePool` helpers for low-latency counters, but keep DB as source of truth for budgets.
- In clustered deployments, all enforcement decisions MUST ultimately be based on shared Redis/DB state rather than in-process-only counters. In-process caches are allowed as hints, but they must not be the sole source of truth for enforcement decisions.

### 3. Unified Rejection & Logging

- When any guardrail denies a request:
  - Attach a structured detail payload with:
    - `principal_id`, `metric`, `limit`, `current`, `window`, `scope`.
  - Log a consistent event with principal tags and metric.
  - Optionally feed into the existing security alerting pipeline (`AuthNZ.alerting`).
  - When logging `principal_id`, use a non-PII stable identifier (e.g., hashed `user_id/api_key_id` or a surrogate id), and honor existing `PII_REDACT_LOGS` / `USAGE_LOG_DISABLE_META` settings.
- Prometheus metrics emitted by `AuthGovernor` should use an `auth_gov_*` prefix to avoid collisions and to make governance metrics easy to discover.
- The JSON structure of HTTP 402 responses for budget/guardrail failures (including top-level `error`, `message`, and `details` fields) is part of the public API surface. Once shipped, it should be treated as stable, or deliberately versioned (e.g., via a top-level `version` field) when changes are necessary.

---

## Scope

### In-Scope (v1)

- New `AuthPrincipal` model and `get_auth_principal` dependency.
- New `AuthGovernor` abstraction, backed by:
  - Existing `llm_usage_log` and virtual key limits.
  - Existing login attempts and lockout tables (`failed_attempts`, `account_lockouts`).
- Refactors:
  - `llm_budget_guard` to consume `AuthPrincipal` and `AuthGovernor`.
  - AuthNZ login lockout logic to use `AuthGovernor`.
  - `UsageLoggingMiddleware` to record principal identity consistently, but keep current schema.

### Out of Scope (v1)

- Full migration of all module-specific limiters to the governance layer (handled by separate Resource_Governor PRD).
- Schema changes to `usage_log` / `llm_usage_log`.
- Changes to external APIs or error codes beyond structured details for guardrail failures.

---

## Risks & Mitigations

- **Risk: Backwards incompatibility for tests pushing directly on `request.state.user_id`.**
  - Mitigation: Keep `request.state.user_id/api_key_id/org_ids/team_ids` in sync with `AuthPrincipal` for at least one major version; deprecate over time.

- **Risk: Increased latency on hot code paths.**
  - Mitigation: Cache principal per request (single creation), use local caches for high-frequency guardrails, and rely on existing indices/Redis usage.

- **Risk: Complexity of partial rollout.**
  - Mitigation: Feature flags / settings to opt specific features into the new governance path (e.g., `AUTH_GOVERNOR_ENABLE_LLM_BUDGETS`, `AUTH_GOVERNOR_ENABLE_LOGIN_LOCKOUTS`).

---

## Milestones & Phasing

### Phase 1: Principal Skeleton (AuthContext)

- Define `AuthPrincipal` dataclass and `get_auth_principal` dependency.
- Refactor `User_DB_Handling` and `auth_deps` to use it internally but keep existing public dependencies.
- Add small integration tests for:
  - Single-user mode.
  - Multi-user JWT flow.
  - API key auth (user and virtual).

### Phase 2: LLM Budgets via AuthGovernor

- Implement minimal `AuthGovernor` with metrics for LLM budgets using existing `llm_usage_log` and virtual key columns.
- Refactor `llm_budget_guard` to consume `AuthPrincipal` and `AuthGovernor`.
- Add tests:
  - Over-budget virtual key returns 402 with structured detail.
  - Budget counts align with `llm_usage_log`.

### Phase 3: Login Lockouts via AuthGovernor

- Migrate login attempt tracking and lockouts to `AuthGovernor`.
- Keep legacy tables but access them only through the governance layer.
- Add tests for lockout threshold behavior in both SQLite and Postgres.

### Phase 4: Consolidation & Clean-up

- Audit guardrail code paths inside AuthNZ and:
  - Remove duplicated logic replaced by `AuthPrincipal` + `AuthGovernor`.
  - Update docs (AuthNZ README, API integration guide) to describe principals and governance.

---

## Open Questions

- Should `AuthPrincipal` be persisted in logs as a structured JSON blob, or just via a stable principal id?
- How much of the existing `Resource_Governor_PRD` should be reused for AuthNZ vs. kept as a separate higher-level module?
- Should limits be configured primarily via `config.txt` / `.env` or via admin API tables with per-org overrides?

---

## Success Criteria

- All AuthNZ guardrail decisions (LLM budgets, login lockouts, AuthNZ-level rate limits) can be attributed to a single `AuthPrincipal` and `metric`.
- New features needing guardrails can integrate by:
  - Calling `get_auth_principal`.
  - Calling `AuthGovernor.check_and_increment` with a new metric.
- Measurable reduction in:
  - Lines of code in `llm_budget_guard`, `quotas`, and AuthNZ rate limiter.
  - Number of code sites manually reading/writing `request.state.user_id/api_key_id/org_ids/team_ids`.

## Implementation Plan

### Stage 1: Principal Skeleton (AuthContext)
**Goal**: Introduce `AuthPrincipal` and `get_auth_principal` and have AuthNZ core use it internally without changing external behavior.

**Success Criteria**:
- `AuthPrincipal` is created exactly once per request on authenticated routes.
- `request.state.auth` is populated and mirrored into `request.state.user_id` / `api_key_id` for compatibility.
- Existing auth flows (single-user API key, multi-user JWT, API keys) pass tests unchanged, and public dependencies (`auth_deps.get_current_user`, `User_DB_Handling.get_request_user`) continue to work by internally calling `get_auth_principal`.

**Tests**:
- Unit tests for `get_auth_principal` covering:
  - Single-user API key.
  - Multi-user JWT (access + refresh).
  - User-bound API key and virtual key.
- Integration tests asserting `request.state.auth` and `request.state.user_id/api_key_id` are set for representative endpoints.

**Status**: Not Started

### Stage 2: LLM Budgets via AuthGovernor
**Goal**: Route virtual-key LLM budget enforcement through `AuthGovernor` using `AuthPrincipal` and existing `llm_usage_log` data.

**Success Criteria**:
- `llm_budget_guard` consults `AuthGovernor` rather than directly querying usage/budgets.
- Budget exceed decisions include metric, window, and principal details in the HTTP 402 response.
- No regression in budget enforcement semantics for day/month token and USD limits.

**Tests**:
- Unit tests for `AuthGovernor` budget metrics (tokens/day, tokens/month, usd/day, usd/month).
- API-level tests:
  - Under-budget key succeeds and increments usage.
  - Over-budget key receives 402 with structured detail.
- Regression tests ensuring non-virtual keys are unaffected.

**Status**: Not Started

### Stage 3: Login Lockouts via AuthGovernor
**Goal**: Replace bespoke login attempt and lockout logic in AuthNZ rate limiter with `AuthGovernor` metrics.

**Success Criteria**:
- Failed login attempts increment a `login_attempts` metric for the relevant principal or identifier.
- Lockout decisions use a single configuration path and produce consistent lockout metadata.
- Existing lockout thresholds and timings behave as before for both SQLite and Postgres backends.

**Tests**:
- Unit tests for `AuthGovernor` login-attempt metrics and threshold crossing.
- Integration tests for login endpoints:
  - Repeated failures lead to lockout and a clear response payload.
  - Successful login after lockout expiry works.

**Status**: Not Started

### Stage 4: Consolidation & Clean-up
**Goal**: Remove duplicated guardrail logic and ensure all AuthNZ guardrails use `AuthPrincipal` + `AuthGovernor`.

**Success Criteria**:
- No direct reads/writes of `failed_attempts`, `account_lockouts`, or virtual-key counters outside the governance layer.
- `llm_budget_guard`, login lockouts, and AuthNZ-level rate limits all go through `AuthGovernor`.
- AuthNZ README and API integration docs describe principals and governance clearly.
- `UsageLoggingMiddleware` derives `user_id` / `api_key_id` (and related context) from `AuthPrincipal` rather than ad-hoc state where possible.

**Tests**:
- Static/code-level checks (or targeted tests) to ensure no remaining direct SQL manipulation of guardrail tables outside repositories/governor.
- End-to-end tests for representative guarded routes (auth, chat, embeddings) verifying combined behavior.

**Status**: Not Started
