# PRD: Admin Endpoints Final Split (Remaining `admin/__init__.py`)

- Title: Admin Endpoints Final Split
- Owner: AuthNZ and Backend Team
- Status: Implemented (Ready for Final Review/Merge)
- Target Version: v0.2.x
- Last Updated: 2026-02-08

## Summary

This PRD finalizes the admin endpoint split so `tldw_Server_API/app/api/v1/endpoints/admin/__init__.py` is an aggregator + compatibility shim, and high-churn route groups live in focused modules (`admin_rbac.py`, `admin_rate_limits.py`, `admin_data_ops.py`, `admin_ops.py`).

The objective is maintainability without API contract drift: keep all `/api/v1/admin/*` paths, auth behavior, test monkeypatch points, and response schemas stable.

## Repo Evidence and Current State

- Current thin aggregator:
  - `tldw_Server_API/app/api/v1/endpoints/admin/__init__.py` is now ~299 lines.
  - It contains router includes and compatibility helpers, with no route decorators.
- Extracted route modules:
  - `tldw_Server_API/app/api/v1/endpoints/admin/admin_rbac.py` (~1106 lines)
  - `tldw_Server_API/app/api/v1/endpoints/admin/admin_rate_limits.py` (~135 lines)
  - `tldw_Server_API/app/api/v1/endpoints/admin/admin_data_ops.py` (~293 lines)
  - `tldw_Server_API/app/api/v1/endpoints/admin/admin_ops.py` (~450 lines)
- Existing admin services reused by extracted routes:
  - `tldw_Server_API/app/services/admin_roles_permissions_service.py`
  - `tldw_Server_API/app/services/admin_data_ops_service.py`
  - `tldw_Server_API/app/services/admin_system_ops_service.py`
  - `tldw_Server_API/app/services/admin_scope_service.py`

## Problem Statement

Before this split, `admin/__init__.py` combined route handlers, auth scope logic, audit emission, direct repo calls, and system operations. This reduced readability, increased regression risk, and made unit-level testing harder.

## Goals

- Keep `admin/__init__.py` as:
  - router aggregation
  - compatibility/test shim exports
  - minimal helper wrappers only
- Move remaining endpoint groups into focused modules.
- Enforce consistent endpoint -> service layering.
- Preserve backward compatibility in:
  - paths
  - dependencies/decorators
  - schema contracts
  - import/monkeypatch test points

## Non-Goals

- No admin feature additions.
- No RBAC model redesign.
- No AuthNZ schema migration.
- No route renames or response contract changes.

## Functional Scope

### In Scope

- Remaining route extraction from `admin/__init__.py` into:
  - `admin_rbac.py`
  - `admin_rate_limits.py`
  - `admin_data_ops.py`
  - `admin_ops.py`
- Preservation of compatibility symbols in `admin/__init__.py`.

### Out of Scope

- New admin UX/API capabilities.
- Service-layer redesign beyond extraction boundaries.

## Route Ownership Map (Final)

- `admin_rbac.py`
  - `/kanban/fts/{action}`
  - role CRUD and permission assignment
  - tool permission CRUD/batch/prefix grant-revoke
  - role matrix and categories
  - user roles, overrides, effective permissions
- `admin_rate_limits.py`
  - `/roles/{role_id}/rate-limits` (upsert/clear)
  - `/users/{user_id}/rate-limits` (upsert)
- `admin_data_ops.py`
  - `/backups` list/create
  - `/backups/{backup_id}/restore`
  - `/retention-policies` list/update
- `admin_ops.py`
  - `/maintenance` get/update
  - `/feature-flags` list/upsert/delete
  - `/incidents` list/create/update/add-event/delete
  - `/llm-usage/pricing/reload`
  - `/chat/model-aliases/reload`

## Compatibility Contract

The following symbols must remain importable from `tldw_Server_API.app.api.v1.endpoints.admin`:

- `_is_postgres_backend`
- `_get_rbac_repo`
- `_ensure_sqlite_authnz_ready_if_test_mode`
- `_emit_admin_audit_event`
- `emit_budget_audit_event`
- `_enforce_admin_user_scope`
- `_is_platform_admin`
- `_require_platform_admin`
- `_get_admin_org_ids`
- `_load_bulk_user_candidates`

`admin/__init__.py` remains the stable import path for tests that monkeypatch these helpers.

## Architecture Decisions

- Keep endpoint modules thin-to-moderate and reuse existing service modules instead of duplicating business logic.
- Permit local wrapper helpers in extracted modules where needed for scope/audit behavior but forward shared behavior through:
  - `admin_scope_service`
  - root admin shim (`_emit_admin_audit_event`)
- Keep router inclusion centralized in `admin/__init__.py` to avoid route registration drift.

## Migration Plan and Status

### Phase 1: RBAC Extraction

- Status: Complete
- Result:
  - RBAC, tool permissions, user-role assignments, overrides, effective permission routes moved to `admin_rbac.py`.

### Phase 2: Rate-Limit Extraction

- Status: Complete
- Result:
  - Role/user rate-limit routes moved to `admin_rate_limits.py`.

### Phase 3: Data Ops Extraction

- Status: Complete
- Result:
  - Backup/restore/retention routes moved to `admin_data_ops.py`.

### Phase 4: System Ops Extraction

- Status: Complete
- Result:
  - Maintenance/feature-flags/incidents/cache reload routes moved to `admin_ops.py`.

### Phase 5: Final Shim Slimming

- Status: Complete
- Result:
  - `admin/__init__.py` reduced to aggregation + compatibility shims.

## Testing and Verification

### Static/Lint

- `ruff` on all affected admin endpoint modules must pass.

### Targeted Tests

- Admin smoke and role/permission matrix tests.
- Data ops and system ops tests.
- User profile admin scope/audit tests.
- AuthNZ integration RBAC admin endpoint tests.

### Compatibility Checks

- Validate old helper imports from `admin` module still resolve.
- Validate monkeypatch-based tests still pass without import path changes.
- Confirm OpenAPI route coverage for all `/api/v1/admin/*` endpoints remains intact.

## Risks and Mitigations

- Risk: Route-level auth/scope drift.
  - Mitigation: preserve decorator/dependency patterns as-is during extraction.
- Risk: Test breakage from symbol movement.
  - Mitigation: keep stable shim exports in `admin/__init__.py`.
- Risk: Circular imports when wrappers call root helpers.
  - Mitigation: use lazy imports inside helper wrappers where required.

## Acceptance Criteria

- `admin/__init__.py` contains no endpoint route handlers.
- All extracted admin routes are reachable with unchanged paths and schemas.
- Compatibility/test shim symbols remain importable from admin package root.
- Existing admin/AuthNZ tests for these routes pass.
- Service-layer usage remains explicit and consistent in extracted modules.

## Definition of Done

- Extraction complete for RBAC, rate-limits, data-ops, and ops modules.
- Lint and targeted test suites pass.
- PRD updated to implemented state (this document).
