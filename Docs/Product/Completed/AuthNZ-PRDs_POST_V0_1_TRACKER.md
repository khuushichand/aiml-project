# AuthNZ PRDs — Post‑v0.1 Tracker

This file tracks **post‑v0.1** follow-ups for the AuthNZ PRD set:

- `Docs/Product/Resource_Governor_PRD.md`
- `Docs/Product/User-Auth-Deps-PRD.md`
- `Docs/Product/User-Unification-PRD.md`

The v0.1 implementation is complete per `Docs/Product/AuthNZ-PRDs_IMPLEMENTATION_PLAN.md`. The items below are the remaining “Stage 9 / long-tail” work to fully retire legacy shims and reduce remaining tech debt safely.

---

## Stage 9A: RG Rollout Validation (Operational)

**Goal**: Prove RG parity in **staging/dev** traffic before removing legacy limiters.

- [x] Define the **parity window** used for validation and record it here.
  - In the absence of production, treat this as a **staging soak window** (e.g., 30–120 minutes)
    with **stable RG config** (no policy edits during the window).
- [x] Build dashboards/alerts (or a lightweight snapshot+diff report) for:
  - `rg_shadow_decision_mismatch_total`
  - `rg_denials_total`, `rg_decisions_total`
  - Any module-specific legacy limiter metrics that still exist during rollout
- [x] Confirm representative traffic (or synthetic load) exercises each RG-governed surface at least once:
  - Ingress: `chat.default`, `embeddings.default`, `audio.default`, `evals.default`, `media.default`, `workflows.default`, `rag.default`
  - Module-level: `authnz.default`, `character_chat.default`
  - Optional extras: `mcp.ingestion` (ingress) and `web_scraping.default` (outbound scraping gating) if you want to validate those too
- Staging/dev notes (common gotchas):
  - `TEST_MODE=1` / `TLDW_TEST_MODE=1` bypasses AuthNZ endpoint rate limiting deps → you will not observe `authnz.default` decisions.
  - In `AUTH_MODE=single_user`, Character Chat legacy limiter is **disabled by default**; when `RG_ENABLED=1`, RG still emits `character_chat.default` decisions (enable legacy only if you want fallback/shadow comparisons).
  - `/api/v1/chat/*` (singular) is the Chat API governed by `chat.default`; `/api/v1/chats/*` (plural) is Character Chat sessions governed by `character_chat.default`.
- [x] Capture mismatch deltas by `module/route/policy_id` at the end of the window and decide whether drift is acceptable.

### Staging parity run record (latest)

- Window (UTC): `2025-12-14 17:26:19` → `2025-12-14 17:27:09` (synthetic exercise window)
- Environment: `dev`, `dev@c3f13178`
- RG config: `RG_ENABLED=1`, `RG_POLICY_STORE=file`, `RG_BACKEND=memory`, `rg_policy_version=1`, `policies=20`
- Pass criteria (staging): `Σ increase(rg_shadow_decision_mismatch_total) == 0` and expected policy IDs observed in `rg_decisions_total` at least once
- Results:
  - Mismatches: `0`
  - Coverage (rg_decisions_total increases): `authnz.default`, `character_chat.default`, `chat.default`, `embeddings.default`, `audio.default`, `evals.default`, `media.default`, `workflows.default`, `rag.default`
  - Notes/decision: `PASS` (mismatch delta 0; coverage observed)

Quick commands:
- `python -m pytest -q tldw_Server_API/tests/Resource_Governance`
- Metrics endpoints:
  - `GET /metrics` (full service Prometheus text; includes RG series)
  - `GET /api/v1/metrics/text` (same content under the API prefix, if enabled)
  - `GET /api/v1/mcp/metrics/prometheus` (MCP-only scrape endpoint; requires `system.logs`)
- Automated exercise (recommended):
  - `python Helper_Scripts/rg_stage9a_parity_window.py exercise --api-key "$SINGLE_USER_API_KEY" --timeout 10`
- Traffic smoke checklist (prints HTTP status codes):
  - `curl -sS -o /dev/null -w "mcp.status %{http_code}\\n" "$BASE/api/v1/mcp/status"`
  - `curl -sS -o /dev/null -w "audio.health %{http_code}\\n" "$BASE/api/v1/audio/transcriptions/health"`
  - `curl -sS -o /dev/null -w "chat.commands %{http_code}\\n" -H "X-API-KEY: $SINGLE_USER_API_KEY" "$BASE/api/v1/chat/commands"`
  - `curl -sS -o /dev/null -w "emb.providers %{http_code}\\n" -H "X-API-KEY: $SINGLE_USER_API_KEY" "$BASE/api/v1/embeddings/providers-config"`
  - `curl -sS -o /dev/null -w "evals.rate_limits %{http_code}\\n" -H "X-API-KEY: $SINGLE_USER_API_KEY" "$BASE/api/v1/evaluations/rate-limits"`
  - `curl -sS -o /dev/null -w "workflows.auth_check %{http_code}\\n" -H "X-API-KEY: $SINGLE_USER_API_KEY" "$BASE/api/v1/workflows/auth/check"`
  - `curl -sS -o /dev/null -w "rag.health %{http_code}\\n" "$BASE/api/v1/rag/health"`
  - `curl -sS -o /dev/null -w "auth.login(bad) %{http_code}\\n" -X POST "$BASE/api/v1/auth/login" -H "Content-Type: application/x-www-form-urlencoded" --data "username=bad&password=bad"`
- Character chat create (emits `character_chat.default` decisions when `RG_ENABLED=1`; legacy limiter is disabled by default in single-user mode):
    - `curl -sS -o /dev/null -w "chats.create %{http_code}\\n" -H "X-API-KEY: $SINGLE_USER_API_KEY" -H "Content-Type: application/json" -X POST "$BASE/api/v1/chats/" -d '{"character_id":999999,"title":"stage9a"}'`
  - Web scraping (valid JSON only; `web_scraping.default` is emitted during outbound fetch gating):
    - `curl -sS -o /dev/null -w "media.web_scrape %{http_code}\\n" -H "X-API-KEY: $SINGLE_USER_API_KEY" -H "Content-Type: application/json" -X POST "$BASE/api/v1/media/process-web-scraping" -d '{"scrape_method":"Individual URLs","url_input":"https://example.com","max_pages":1,"max_depth":1,"mode":"ephemeral"}'`
- Snapshot+diff helper:
  - `python Helper_Scripts/rg_stage9a_parity_window.py snapshot --out stage9a_before.prom`
  - `python Helper_Scripts/rg_stage9a_parity_window.py snapshot --out stage9a_after.prom`
  - `python Helper_Scripts/rg_stage9a_parity_window.py report --before stage9a_before.prom --after stage9a_after.prom`

---

## Stage 9B: “No Double-Enforcement” Audit (Code)

**Goal**: When `RG_ENABLED=1`, RG is the sole enforcer and legacy paths do not double-enforce.

- [x] Global RG middleware enablement uses `RG_ENABLED` only (no legacy `RG_ENABLE_*` aliases).
- [x] Audio ingress now relies on RG only; legacy ingress limiter path removed to prevent double-enforcement.
- [x] MCP shadow mismatch comparisons use `peek_allowed` (no legacy consumption) and `TokenBucketRateLimiter.peek_allowed` is side-effect free.
- [x] Audit remaining RG-first modules for any legacy limiter “shadow” evaluation that writes/consumes counters in a way that could surprise operators:
  - [x] Chat: `tldw_Server_API/app/core/Chat/rate_limiter.py`
    - RG decision short-circuits legacy limiter entirely (no shadow simulation, no legacy consumption).
  - [x] Embeddings: `tldw_Server_API/app/core/Embeddings/rate_limiter.py`
    - Shadow simulation uses `UserRateLimiter.shadow_check_rate_limit` against a shadow-only queue (does not mutate the legacy enforcement queue); controlled by `RG_SHADOW_EMBEDDINGS` (default off).
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

- [x] Add once-per-process deprecation warnings when legacy limiter code paths are used (especially when `RG_ENABLED=1`).
- [x] After the defined parity window, remove or shrink legacy limiters into thin RG-forwarding shims (or delete them where unused):
  - Remove legacy state/counters where they are no longer needed.
  - Keep only diagnostic endpoints/helpers if required, clearly documented as RG diagnostics.
- [x] Tighten defaults for shadow flags as appropriate (previously default-on in some modules; default-off is preferred):
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
- [x] For each, decide: migrate into `AuthNZ/migrations.py`, `AuthNZ/pg_migrations_extra.py`, or a dedicated repo `ensure_schema()` helper.
  - [x] Rate limiter schema → `AuthnzRateLimitsRepo.ensure_schema()` (RateLimiter no longer embeds DDL; covered by existing unit tests).
  - [x] Token blacklist schema → `AuthnzTokenBlacklistRepo.ensure_schema()` (TokenBlacklist delegates; covered by existing unit tests).
  - [x] Single-user RBAC seed DDL → `ensure_single_user_rbac_seed_if_needed()` now relies on `ensure_authnz_schema_ready_once()` (SQLite) + `ensure_authnz_core_tables_pg()` (Postgres); only SQLite `:memory:` keeps a minimal backstop DDL.
  - [x] API keys schema → authoritative in `AuthNZ/migrations.py` (SQLite) + `AuthNZ/pg_migrations_extra.py` (Postgres); `AuthnzApiKeysRepo.ensure_tables()` is a thin wrapper.
- [x] Add/extend SQLite + Postgres tests for any migrated schema/init behavior.
  - [x] SQLite RBAC seed: `tldw_Server_API/tests/AuthNZ/unit/test_single_user_rbac_seed_sqlite.py`
  - [x] SQLite API keys virtual fields: `tldw_Server_API/tests/AuthNZ/unit/test_authnz_migrations_api_keys.py`
  - [x] Postgres API keys ensure helper: `tldw_Server_API/tests/AuthNZ/unit/test_pg_migrations_api_keys.py`

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
  - `AuthnzApiKeysRepo.ensure_tables()` – thin wrapper: delegates Postgres schema ensure to `ensure_api_keys_tables_pg()` and asserts SQLite tables exist (migrations remain authoritative).

---

## Stage U2: Remaining `is_single_user_mode()` Uses (Auth/Guardrail vs UX)

**Goal**: Keep `AUTH_MODE` / `is_single_user_mode()` out of auth/guardrail decisions where claims/profile flags should apply.

- [x] Re-audit callsites and classify each as **coordination/UX** vs **auth/guardrail**:
  - `rg -n "is_single_user_mode\\(" tldw_Server_API/app`
- [x] For any auth/guardrail callsites, design a claim-first alternative (principal + profile/feature flags) and add tests before flipping defaults.
  - Rate-limit bypass now uses `is_single_user_principal(principal)` (claim-first; fixed-id fallback only when `AUTH_MODE=single_user`).

### Current callsite classification (snapshot)

- **Coordination/UX**
  - `tldw_Server_API/app/main.py:1040` – ChaChaNotes warm-up scheduling for single-user default user.
  - `tldw_Server_API/app/main.py:1872` – startup banner + “show API key” behavior.
  - `tldw_Server_API/app/main.py:3031` – legacy lifespan startup banner helper.
  - `tldw_Server_API/app/main.py`: startup banners and UX hints for auth mode (quickstart endpoint).

- **Auth/guardrail**
  - (none) — remaining uses are coordination/UX or compatibility-only.

- **Compatibility / feature-gated helper**
  - `tldw_Server_API/app/api/v1/API_Deps/auth_deps.py:1031` – org-policy synthetic `org_id=1` fallback uses principal-first logic by default; legacy mode/profile branch only when `ORG_POLICY_SINGLE_USER_PRINCIPAL` is explicitly disabled.
