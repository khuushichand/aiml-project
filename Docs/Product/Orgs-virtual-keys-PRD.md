
# Organizations, Teams, and Virtual Keys - PRD/Design (v1)

## Goals

- Introduce hierarchical grouping: Organizations contain Teams; Teams contain Users.
- Enable Virtual API Keys with constrained access (endpoint scope) and spend limits (tokens/cost) for LLM features.
- Integrate with existing AuthNZ, RBAC, and the LLM Usage tracking pipeline (llm_usage_log/daily).
- Keep changes additive and backward-compatible; minimize churn in existing endpoints.

## Non-Goals (v1)

- Full org/team-scoped RBAC inheritance and per-resource ACLs (future).
- Cascading side effects across org/team membership changes. Adds/removes are explicit and localized; no implicit cascades in v1.

## User Stories

- As an admin, I can create Organizations and Teams, assign users to Teams, and audit membership.
- As a user/admin, I can create a Virtual API Key tied to my account/org/team that can only access certain endpoints (e.g., chat/embeddings) and has daily/monthly budgets for tokens and/or USD costs.
- If a Virtual Key leaks, the blast radius is limited: it cannot access admin or non-allowed endpoints, and will be throttled/blocked once budgets are reached.

## Architecture Overview

- Schema additions (SQLite/Postgres):
  - `organizations`, `org_members`.
  - `teams`, `team_members` (team scoped to an org).
  - Extend `api_keys` with Virtual Key metadata:
    - `is_virtual`, `parent_key_id`, `org_id`, `team_id`.
    - Budget fields: `llm_budget_day_tokens`, `llm_budget_month_tokens`, `llm_budget_day_usd`, `llm_budget_month_usd`.
    - Access control fields: `llm_allowed_endpoints`, `llm_allowed_providers`, `llm_allowed_models` (stored as JSON strings in SQLite and Postgres for broad asyncpg compatibility; cast to JSONB as needed in Postgres code paths).

- Services:
  - `orgs_teams.py`: CRUD helpers for orgs, teams, and team membership (add/list/delete).
  - `virtual_keys.py`: helpers to read per-key limits, evaluate current usage (day/month) using `llm_usage_log` (fallback) and `llm_usage_daily` when present.

- Enforcement:
  - `LLMBudgetMiddleware` (FastAPI middleware) checks on configured LLM endpoints:
    - Reads `request.state.api_key_id` (populated in API key auth path) and looks up limits.
    - Enforces endpoint allowlist early (reject 403 if not allowed).
    - Optionally enforces provider/model allowlists if set on the key (provider from `X-LLM-Provider`, model from JSON body `model`); reject 403 if not allowed.
    - Enforces budgets (reject 402 Payment Required when exceeded).
  - Post-request logging remains unchanged (existing `log_llm_usage`). This combination blocks subsequent requests once limits are reached.

- Admin APIs (v1):
  - CRUD: organizations, teams, membership (create/list/delete; idempotent add semantics).
  - Organization membership endpoints (admin):
    - POST /api/v1/admin/orgs/{org_id}/members - add member (idempotent; returns existing membership when present)
    - GET  /api/v1/admin/orgs/{org_id}/members - list with pagination (limit/offset) and filters (role, status)
    - PATCH /api/v1/admin/orgs/{org_id}/members/{user_id} - update role (optional in v1; implemented)
    - DELETE /api/v1/admin/orgs/{org_id}/members/{user_id} - remove member (idempotent)
    - GET  /api/v1/admin/users/{user_id}/org-memberships - user-centric listing for UI convenience
  - Team membership endpoints (admin):
    - POST /api/v1/admin/teams/{team_id}/members - add member (idempotent)
    - GET  /api/v1/admin/teams/{team_id}/members - list members
    - DELETE /api/v1/admin/teams/{team_id}/members/{user_id} - remove member (idempotent)
  - Virtual key endpoints (admin):
    - POST /api/v1/admin/users/{user_id}/virtual-keys - create virtual key with limits and allowlists
    - GET  /api/v1/admin/users/{user_id}/virtual-keys - list/search

## Data Model

- organizations(id, uuid, name, slug, owner_user_id, is_active, created_at, updated_at, metadata)
- org_members(org_id, user_id, role, status, added_at)
- teams(id, org_id, name, slug, description, is_active, created_at, updated_at, metadata)
- team_members(team_id, user_id, role, status, added_at)

- api_keys (extended)
  - is_virtual INTEGER DEFAULT 0
  - parent_key_id INTEGER NULL
  - org_id INTEGER NULL
  - team_id INTEGER NULL
  - llm_budget_day_tokens INTEGER NULL
  - llm_budget_month_tokens INTEGER NULL
  - llm_budget_day_usd REAL NULL
  - llm_budget_month_usd REAL NULL
  - llm_allowed_endpoints TEXT NULL  -- JSON list of endpoint identifiers (e.g., ["chat.completions","embeddings"])
  - llm_allowed_providers TEXT NULL  -- optional JSON list
  - llm_allowed_models TEXT NULL     -- optional JSON list

Indexes: org/team membership by foreign keys; helpful composite indexes for list/filter.

## API Surface (v1)

- Admin
  - POST /api/v1/admin/orgs              - create org
  - GET  /api/v1/admin/orgs              - list orgs
  - POST /api/v1/admin/orgs/{org_id}/teams - create team
  - GET  /api/v1/admin/orgs/{org_id}/teams - list teams
  - POST /api/v1/admin/teams/{team_id}/members - add member
  - DELETE /api/v1/admin/teams/{team_id}/members/{user_id} - remove member
  - POST /api/v1/admin/orgs/{org_id}/members - add org member (idempotent)
  - GET  /api/v1/admin/orgs/{org_id}/members - list org members (limit/offset, role, status)
  - PATCH /api/v1/admin/orgs/{org_id}/members/{user_id} - update role
  - DELETE /api/v1/admin/orgs/{org_id}/members/{user_id} - remove org member (idempotent)
  - POST /api/v1/admin/users/{user_id}/virtual-keys - create virtual key
  - GET  /api/v1/admin/users/{user_id}/virtual-keys - list virtual keys
  - GET  /api/v1/admin/users/{user_id}/org-memberships - list org memberships

Payload for create virtual key (subset):
```
{
  "name": "temp-lab-chat",
  "description": "Ephemeral key for lab UI",
  "expires_in_days": 30,
  "org_id": 1,
  "team_id": 5,
  "allowed_endpoints": ["chat.completions","embeddings"],
  "budget_day_tokens": 100_000,
  "budget_month_tokens": 2_000_000,
  "budget_day_usd": 5.00,
  "budget_month_usd": 100.00
}
```

## Enforcement Logic

On each request to configured LLM endpoints (defaults: `/api/v1/chat/completions`, `/api/v1/embeddings`):
1) If request uses API key auth and the key is_virtual=1:
   - If llm_allowed_endpoints is set, ensure the endpoint identifier is in the allowlist; else 403.
   - If llm_allowed_providers is set, ensure `X-LLM-Provider` is in allowlist; else 403.
   - If llm_allowed_models is set, ensure request JSON `model` is in allowlist; else 403.
   - Compute current usage for key_id:
       - Day: sum from `llm_usage_log` where date(ts)=UTC today and key_id matches.
       - Month: sum where ts IN current UTC month.
     Compare against configured budgets (tokens and/or USD). If any limit would be exceeded (>=), reject with 402 and clear message.

Notes:
- We use logging data as source of truth for spend/token usage; aggregation to daily table can be leveraged for monthly sums in future.
- Budgets are soft state. A request that tips over a limit will be allowed once (the tipping request), and subsequent requests will be blocked.
 - Error codes: 403 for disallowed endpoint/provider/model; 402 for budget exceeded.
 - Membership operations are idempotent. No cascading deletes or implicit role propagation in v1.
 - Audit logging is best-effort on membership changes (add/remove/update). Uses get_audit_service_for_user when a real user context exists; failures never block.

## Settings (new)

- `VIRTUAL_KEYS_ENABLED` (bool, default: true)
- `LLM_BUDGET_ENFORCE` (bool, default: true)
- `LLM_BUDGET_ENDPOINTS` (list[str], default: ["/api/v1/chat/completions", "/api/v1/embeddings"]) - paths to scope middleware. `allowed_endpoints` values map to identifiers used internally (e.g., `chat.completions`, `embeddings`).

## Testing Plan (v1)

- Unit tests:
  - Schema migration ensures presence of new tables/columns (SQLite).
  - APIKeyManager.create_virtual_key inserts row with flags/limits; validate selection via validate_api_key.
  - virtual_keys.is_key_over_budget: simulate llm_usage_log rows and verify threshold checks.

- Integration:
  - Admin endpoints for org/team CRUD; org membership (POST/GET/PATCH/DELETE + user-centric listing); team membership (POST/GET/DELETE); virtual key creation/list. Pagination and filter behaviour now covered for both SQLite and Postgres paths.
  - Middleware blocks disallowed providers/models when allowlists are set (403). Endpoint allowlists explicitly reject `/api/v1/embeddings` for chat-only keys. Edge cases covered:
    - Missing X-LLM-Provider header with a provider allowlist (allowed unless header present and disallowed).
    - Non-JSON bodies or invalid JSON (skip model enforcement; should not trigger 403/402).
  - Middleware returns 402 after budgets are exceeded for virtual keys (SQLite + Postgres). Both token- and USD-based ceilings validated.
  - Real audit tests via reusable real_audit_service fixture and @pytest.mark.real_audit for team/org membership add/remove/role update across SQLite and Postgres.
  - Postgres test suite uses a dedicated fixture (test_db_pool) so app endpoints and services share the same DSN and clean schema per test.

## Rollout

1) Ship migrations + services + middleware (guarded by settings).
2) Admin endpoints delivered in v1 (including org membership routes and DELETE team member); UI can follow; docs updated here and in README quick references.
3) Backward compatible: non-virtual keys unaffected; JWT flows unchanged.

## Status

- v1 implementation complete. Follow-ups:
  - Explore org/team RBAC propagation strategies in v2.
