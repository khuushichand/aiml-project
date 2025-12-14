# AuthNZ PRDs — Post‑v0.1 Tracker

This file tracks **post‑v0.1** follow-ups for the AuthNZ PRD set:

- `Docs/Product/Resource_Governor_PRD.md`
- `Docs/Product/User-Auth-Deps-PRD.md`
- `Docs/Product/User-Unification-PRD.md`

The v0.1 implementation is complete per `Docs/Product/AuthNZ-PRDs_IMPLEMENTATION_PLAN.md`. The items below are the remaining “Stage 9 / long-tail” work to fully retire legacy shims and reduce remaining tech debt safely.

---

## Stage 9A: RG Rollout Validation (Operational)

**Goal**: Prove RG parity in production-like traffic before removing legacy limiters.

- [ ] Define the “release window” used for parity (e.g., 1–2 weeks) and record it here.
- [ ] Build dashboards/alerts for:
  - `rg_shadow_decision_mismatch_total`
  - `rg_denials_total`, `rg_decisions_total`
  - Any module-specific legacy limiter metrics that still exist during rollout
- [ ] Confirm representative traffic (or load tests) exercises each governed ingress surface at least once:
  - Chat, Embeddings, MCP, Audio, AuthNZ, Evaluations, Character Chat, Web Scraping, Workflows
- [ ] Capture mismatch counts by module/route/policy_id at the end of the window and decide whether drift is acceptable.

Quick commands:
- `python -m pytest -q tldw_Server_API/tests/Resource_Governance`
- Metrics endpoint: `GET /api/v1/metrics/prometheus`

---

## Stage 9B: “No Double-Enforcement” Audit (Code)

**Goal**: When `RG_ENABLED=1`, RG is the sole enforcer and legacy paths do not double-enforce.

- [x] Global RG middleware enablement uses `RG_ENABLED` only (no legacy `RG_ENABLE_*` aliases).
- [x] Audio SlowAPI key function becomes RG-aware to prevent SlowAPI double-enforcement under RG.
- [x] MCP shadow mismatch comparisons use `peek_allowed` (no legacy consumption) and `TokenBucketRateLimiter.peek_allowed` is side-effect free.
- [x] Audit remaining RG-first modules for any legacy limiter “shadow” evaluation that writes/consumes counters in a way that could surprise operators:
  - [x] Chat: `tldw_Server_API/app/core/Chat/rate_limiter.py`
    - RG decision short-circuits legacy limiter entirely (no shadow simulation, no legacy consumption).
  - [x] Embeddings: `tldw_Server_API/app/core/Embeddings/rate_limiter.py`
    - Shadow simulation uses `UserRateLimiter.shadow_check_rate_limit` against a shadow-only queue (does not mutate the legacy enforcement queue); controlled by `RG_SHADOW_EMBEDDINGS` (default on).
  - [x] AuthNZ: `tldw_Server_API/app/core/AuthNZ/rate_limiter.py`
    - Uses `_peek_legacy_allow_without_side_effects(...)` for mismatch comparisons; RG allow/deny does not consume legacy counters.
  - [x] Evaluations: `tldw_Server_API/app/core/Evaluations/user_rate_limiter.py`
    - Under RG allow, legacy checks are best-effort diagnostics and `_record_request(...)` remains for usage/ledger shadow writes + legacy-style headers (not enforcement).
  - [x] Character Chat: `tldw_Server_API/app/core/Character_Chat/character_rate_limiter.py`
    - Shadow comparisons use Redis `ZCOUNT` / in-memory pruning only (no counter consumption); RG allow short-circuits legacy enforcement.
  - [x] Web Scraping: `tldw_Server_API/app/core/Web_Scraping/enhanced_web_scraping.py`
    - RG is treated as backoff gating; local “polite scraping” limiter still enforces per-process RPS/RPM/RPH (additive by design).

Notes:
- If a module needs stateful legacy simulation to make shadow metrics meaningful, document it explicitly and ensure it cannot reintroduce double-enforcement (it must remain “observability only”).

---

## Stage 9C: Legacy Shim Retirement (Removal)

**Goal**: Remove legacy limiters after parity is proven.

- [ ] Add once-per-process deprecation warnings when legacy limiter code paths are used (especially when `RG_ENABLED=1`).
- [ ] After the defined parity window, remove or shrink legacy limiters into thin RG-forwarding shims (or delete them where unused):
  - Remove legacy state/counters where they are no longer needed.
  - Keep only diagnostic endpoints/helpers if required, clearly documented as RG diagnostics.
- [ ] Tighten defaults for shadow flags as appropriate (currently default-on in some modules):
  - `RG_SHADOW_EMBEDDINGS`
  - `RG_SHADOW_AUTHNZ`
  - `RG_SHADOW_CHARACTER_CHAT`

---

## Stage U1: Remaining Inline DDL → Migrations/Backstops (AuthNZ Tech Debt)

**Goal**: Keep AuthNZ backend behavior identical while shrinking inline DDL/dialect branching.

- [x] Inventory remaining inline `CREATE TABLE IF NOT EXISTS` outside the migrations/backstops:
  - `tldw_Server_API/app/core/AuthNZ/initialize.py`
  - `tldw_Server_API/app/core/AuthNZ/rate_limiter.py`
  - `tldw_Server_API/app/core/AuthNZ/token_blacklist.py`
  - `tldw_Server_API/app/core/AuthNZ/repos/api_keys_repo.py`
- [ ] For each, decide: migrate into `AuthNZ/migrations.py`, `AuthNZ/pg_migrations_extra.py`, or a dedicated repo `ensure_schema()` helper.
  - [x] Rate limiter schema → `AuthnzRateLimitsRepo.ensure_schema()` (RateLimiter no longer embeds DDL; covered by existing unit tests).
  - [x] Token blacklist schema → `AuthnzTokenBlacklistRepo.ensure_schema()` (TokenBlacklist delegates; covered by existing unit tests).
  - [x] Single-user RBAC seed DDL → `ensure_single_user_rbac_seed_if_needed()` now relies on `ensure_authnz_schema_ready_once()` (SQLite) + `ensure_authnz_core_tables_pg()` (Postgres); only SQLite `:memory:` keeps a minimal backstop DDL.
  - [ ] API keys schema → decide whether `AuthnzApiKeysRepo.ensure_tables()` remains a long-lived backstop or is reduced once migrations are authoritative.
- [ ] Add/extend SQLite + Postgres tests for any migrated schema/init behavior.
  - [x] SQLite RBAC seed: `tldw_Server_API/tests/AuthNZ/unit/test_single_user_rbac_seed_sqlite.py`

Quick commands:
- `rg -n "CREATE TABLE IF NOT EXISTS" tldw_Server_API/app/core/AuthNZ`

### DDL inventory (snapshot)

- `tldw_Server_API/app/core/AuthNZ/repos/rate_limits_repo.py`
  - `AuthnzRateLimitsRepo.ensure_schema()` – idempotent schema backstop for AuthNZ rate-limit tables (SQLite + Postgres).
- `tldw_Server_API/app/core/AuthNZ/initialize.py`
  - `ensure_single_user_rbac_seed_if_needed()` – no longer creates RBAC tables for Postgres / file-backed SQLite; delegates schema ensure to `ensure_authnz_schema_ready_once()` + `ensure_authnz_core_tables_pg()`. SQLite `:memory:` retains minimal RBAC table creation as a backstop.
- `tldw_Server_API/app/core/AuthNZ/repos/token_blacklist_repo.py`
  - `AuthnzTokenBlacklistRepo.ensure_schema()` – idempotent schema backstop for the AuthNZ token blacklist table (SQLite + Postgres), including SQLite column harmonization.
- `tldw_Server_API/app/core/AuthNZ/repos/api_keys_repo.py`
  - `AuthnzApiKeysRepo.ensure_tables()` – creates `api_keys` and `api_key_audit_log`, plus a large set of idempotent `ALTER TABLE` additions and indexes.

---

## Stage U2: Remaining `is_single_user_mode()` Uses (Auth/Guardrail vs UX)

**Goal**: Keep `AUTH_MODE` / `is_single_user_mode()` out of auth/guardrail decisions where claims/profile flags should apply.

- [x] Re-audit callsites and classify each as **coordination/UX** vs **auth/guardrail**:
  - `rg -n "is_single_user_mode\\(" tldw_Server_API/app`
- [ ] For any auth/guardrail callsites, design a claim-first alternative (principal + profile/feature flags) and add tests before flipping defaults.

### Current callsite classification (snapshot)

- **Coordination/UX**
  - `tldw_Server_API/app/main.py:1036` – ChaChaNotes warm-up scheduling for single-user default user.
  - `tldw_Server_API/app/main.py:1868` – startup banner + “show API key” behavior.
  - `tldw_Server_API/app/main.py:3027` – legacy lifespan startup banner helper.
  - `tldw_Server_API/app/main.py:3351` – `/webui/config.json` mode hint + API key injection (non-prod).

- **Auth/guardrail (explicit carve-out)**
  - `tldw_Server_API/app/api/v1/API_Deps/auth_deps.py:1232` – admin bypass of global IP rate limits in **canonical** single-user mode (`AUTH_MODE=single_user`).
  - `tldw_Server_API/app/api/v1/API_Deps/auth_deps.py:1296` – admin bypass of auth-endpoint IP rate limits in **canonical** single-user mode.

- **Compatibility / feature-gated helper**
  - `tldw_Server_API/app/api/v1/API_Deps/auth_deps.py:1031` – org-policy synthetic `org_id=1` fallback uses principal-first logic by default; legacy mode/profile branch only when `ORG_POLICY_SINGLE_USER_PRINCIPAL` is explicitly disabled.
