# Auth Add Tracker

Purpose: Track the multi-user AuthNZ additions for SQLite setups, per‑user API keys, and RBAC with granular controls, along with WebUI and admin API support.

Last updated: 2025-10-09

## Vision & Scope

- Multi-user support on SQLite with per-user `X-API-KEY` usage (in addition to JWT in Postgres/multi-user).
- Centralized RBAC: roles, permissions, user overrides; rate limits by role/user; usage logging + reporting.
- Admin API and WebUI for managing users, API keys, roles/permissions, and rate limits.
- Phased rollout: start soft (log-only), then enforce in critical areas.

## Current State (Phase 1 complete)

Implemented
- Schema & migrations (SQLite) + PG bootstrap
  - Tables: `roles`, `permissions`, `role_permissions`, `user_roles`, `user_permissions` (overrides),
    `rbac_role_rate_limits`, `rbac_user_rate_limits`, `usage_log`, `usage_daily`.
  - Seeded roles: `admin`, `user`, `moderator`.
  - Seeded permissions aligned with existing constants (media.*, users.*, system.*, api.*).
- RBAC helper
  - `core/AuthNZ/rbac.py` effective permission utilities (delegates to configured `UserDatabase`).
- Admin API (RBAC)
  - Roles: list/create/delete
  - Permissions: list/create
  - Role-permissions: grant/revoke
  - User-roles: list/add/remove
  - User-overrides: list/upsert/delete
  - Effective permissions: get for user
  - Rate limits: upsert per role/user
- WebUI stub
  - New Admin → Access Control tab: manage roles, permissions, assignments, overrides; view effective perms.
- API-key usage audit (optional)
  - `API_KEY_AUDIT_LOG_USAGE` setting; logs a lightweight "used" event on validation.
- Startup & tests
  - Ensures SQLite AuthNZ migrations at startup (dev/tests). New unit test for RBAC admin endpoints.
- Non-blocking rate-limit selector (logging only)
  - `auth_deps.rbac_rate_limit(resource)`: logs strictest configured limit per user/resource.
- Minimal enforcement
  - Media ingestion (`/api/v1/media/add`, `/api/v1/media/process-web-scraping`) now require `media.create`.
  - Evaluation creation logs RBAC rate-limit selection (no enforcement yet).

Key Files
- Migrations: `app/core/AuthNZ/migrations.py` (012–014)
- RBAC helper: `app/core/AuthNZ/rbac.py`
- Admin API: `app/api/v1/endpoints/admin.py`, schemas `app/api/v1/schemas/admin_rbac_schemas.py`
- WebUI: `WebUI/index.html`, `WebUI/tabs/admin_content.html`
- Settings: `app/core/AuthNZ/settings.py` (API_KEY_AUDIT_LOG_USAGE)
- API-key manager: `app/core/AuthNZ/api_key_manager.py` (usage audit)
- Rate-limit selector: `app/api/v1/API_Deps/auth_deps.py` (enforce_rbac_rate_limit + rbac_rate_limit factory)
- Media enforcement: `app/api/v1/endpoints/media.py` (PermissionChecker + RBAC limit for media.create)
- Eval logging: `app/api/v1/endpoints/evaluations_unified.py` (RBAC limit logging on create)
- Startup ensure: `app/main.py`
- Test: `tests/AuthNZ/test_rbac_admin_endpoints.py`

## Plan (Phased Rollout)

1) Schema + Admin API + Effective calculator [DONE]
2) WebUI: Access Control page (Users/Roles tabs) [DONE (stub)]
3) Enforcement (soft → hard)
   - Add `PermissionChecker` to critical endpoints (media ingest, eval runs); soft mode logs/warns.
   - Expand coverage gradually to other endpoints.
4) Rate limits + reporting
   - Switch `rbac_rate_limit(...)` to enforce limits; add usage_log writes via middleware/wrapper.
   - Summaries via `usage_daily`; add admin reporting endpoints + WebUI charts.
5) Broader enforcement & dashboards
   - Tag/annotate remaining endpoints; add dashboards for permission denials, rate-limit hits, and usage by resource.

## Next Steps (active)

- Tests
  - Add integration tests for user overrides affecting effective permissions.
  - Add smoke tests for media ingestion permission checks (403 when missing `media.create`).
- Enforcement & Logging
  - Optionally add a soft-enforce mode flag for selective gating if needed by deployments.
  - Wire `rbac_rate_limit` on additional high-traffic endpoints (readers/search) to gather data.
- Reporting
  - Add small middleware to record `usage_log` per request (guarded by config toggle), and a daily aggregator task.
- UI Enhancements
  - Add role-permission assignment UI & role comparison view; diff preview for staged changes.

## Backward Compatibility

- Single-user mode: PermissionChecker always allows; X-API-KEY remains valid.
- Multi-user SQLite: Baseline role `user` includes `media.create` so ingestion continues to work.
- Postgres: RBAC tables are bootstrapped, admin APIs work; full PG migrations remain a future improvement.

## Open Questions / Decisions

- Final permission taxonomy for Evals (e.g., `evals.create`, `evals.run`); seeded later when enforcement expands.
- Storage of per-key rate limits vs per-user/role; reconcile with global SlowAPI limits when turning on enforcement.
- Consolidate `usage_log` with Unified Audit Service or keep separate for light analytics.

## Changelog (recent)

- Added RBAC migrations + seeds (SQLite) and PG bootstrap for RBAC tables.
- Implemented RBAC admin endpoints + schemas and Access Control UI stub.
- Added RBAC helper and optional API-key usage audit.
- Annotated media ingestion endpoints with `media.create` and added RBAC limit logging for eval creation.
- Ensured SQLite migrations at startup; added initial RBAC admin tests.

