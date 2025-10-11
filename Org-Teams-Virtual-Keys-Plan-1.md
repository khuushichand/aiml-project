# Organizations, Teams, and Virtual Keys — PRD/Design (v1)

## Goals

- Introduce hierarchical grouping: Organizations contain Teams; Teams contain Users.
- Enable Virtual API Keys with constrained access (endpoint scope) and spend limits (tokens/cost) for LLM features.
- Integrate with existing AuthNZ, RBAC, and the LLM Usage tracking pipeline (llm_usage_log/daily).
- Keep changes additive and backward‑compatible; minimize churn in existing endpoints.

## Non‑Goals (v1)

- Full org/Team‑scoped RBAC inheritance and per‑resource ACLs (future).
- Complex pre‑request model/provider enforcement for all LLM endpoints (v1 enforces endpoint scope and budgets; provider/model allowlists are stored and can be enforced later/after usage logging).

## User Stories

- As an admin, I can create Organizations and Teams, assign users to Teams, and audit membership.
- As a user/admin, I can create a Virtual API Key tied to my account/org/team that can only access certain endpoints (e.g., chat/embeddings) and has daily/monthly budgets for tokens and/or USD costs.
- If a Virtual Key leaks, the blast radius is limited: it cannot access admin or non‑allowed endpoints, and will be throttled/blocked once budgets are reached.

## Architecture Overview

- Schema additions (SQLite/Postgres):
  - `organizations`, `org_members`.
  - `teams`, `team_members` (team scoped to an org).
  - Extend `api_keys` with Virtual Key metadata:
    - `is_virtual`, `parent_key_id`, `org_id`, `team_id`.
    - Budget fields: `llm_budget_day_tokens`, `llm_budget_month_tokens`, `llm_budget_day_usd`, `llm_budget_month_usd`.
    - Access control fields: `llm_allowed_endpoints`, `llm_allowed_providers`, `llm_allowed_models` (JSON text in SQLite; JSONB text in Postgres via initialize bootstrap).

- Services:
  - `orgs_teams.py`: CRUD helpers for orgs, teams, and membership.
  - `virtual_keys.py`: helpers to read per‑key limits, evaluate current usage (day/month) using `llm_usage_log` (fallback) and `llm_usage_daily` when present.

- Enforcement:
  - New `LLMBudgetMiddleware` (FastAPI middleware) checks on LLM endpoints:
    - Reads `request.state.api_key_id` (populated in API key auth path) and looks up limits.
    - Enforces endpoint allowlist early (reject 403 if not allowed).
    - Enforces budgets (reject 402 Payment Required when exceeded).
  - Post‑request logging remains unchanged (existing `log_llm_usage`). This combination blocks subsequent requests once limits are reached.

- Admin APIs (v1):
  - CRUD: organizations, teams, membership (simple create/list/delete).
  - Virtual key creation endpoint (admin creates a virtual key for a user with limits and endpoint scope); list/search.

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
  - POST /api/v1/admin/orgs              — create org
  - GET  /api/v1/admin/orgs              — list orgs
  - POST /api/v1/admin/orgs/{org_id}/teams — create team
  - GET  /api/v1/admin/orgs/{org_id}/teams — list teams
  - POST /api/v1/admin/teams/{team_id}/members — add member
  - DELETE /api/v1/admin/teams/{team_id}/members/{user_id} — remove member
  - POST /api/v1/admin/users/{user_id}/virtual-keys — create virtual key
  - GET  /api/v1/admin/users/{user_id}/virtual-keys — list virtual keys

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

On each request to LLM endpoints:
1) If request uses API key auth and the key is_virtual=1:
   - If llm_allowed_endpoints is set, ensure the endpoint identifier is in the allowlist; else 403.
   - Compute current usage for key_id:
       - Day: sum from `llm_usage_log` where date(ts)=UTC today and key_id matches.
       - Month: sum where ts IN current UTC month.
     Compare against configured budgets (tokens and/or USD). If any limit would be exceeded (>=), reject with 402 and clear message.

Notes:
- We use logging data as source of truth for spend/token usage; aggregation to daily table can be leveraged for monthly sums in future.
- Budgets are soft state. A request that tips over a limit will be allowed once (the tipping request), and subsequent requests will be blocked.

## Settings (new)

- `VIRTUAL_KEYS_ENABLED` (bool, default: true)
- `LLM_BUDGET_ENFORCE` (bool, default: true)
- `LLM_BUDGET_ENDPOINTS` (list[str], default: ["/api/v1/chat/completions", "/api/v1/embeddings"]) — paths to scope middleware.

## Testing Plan (v1)

- Unit tests:
  - Schema migration ensures presence of new tables/columns (SQLite).
  - APIKeyManager.create_virtual_key inserts row with flags/limits; validate selection via validate_api_key.
  - virtual_keys.is_key_over_budget: simulate llm_usage_log rows and verify threshold checks.

- Integration (follow‑up):
  - Admin endpoints for org/team CRUD and virtual key creation.
  - Middleware blocks disallowed endpoints and over‑budget keys.

## Rollout

1) Ship migrations + services + middleware (guarded by settings).
2) Add admin endpoints and minimal UI later; ensure docs describe usage and env vars.
3) Backward compatible: non‑virtual keys unaffected; JWT flows unchanged.

