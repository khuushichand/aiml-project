# PRD: Admin Endpoints Final Split (Remaining __init__.py)

- Title: Admin Endpoints Final Split
- Owner: AuthNZ and Backend Team
- Status: Draft
- Target Version: v0.2.x
- Last Updated: 2026-02-08

## Summary

Admin endpoint splitting is mostly complete, but `endpoints/admin/__init__.py` is still a large mixed-responsibility module. This PRD defines the final extraction so `__init__.py` becomes an aggregator + compatibility shim while RBAC/data-ops/system routes move to focused modules.

## Current State (Repo Evidence)

- Admin now uses package modules:
  - `admin_user.py`, `admin_orgs.py`, `admin_byok.py`, `admin_tools.py`, `admin_usage.py`, etc.
- Remaining monolith:
  - `tldw_Server_API/app/api/v1/endpoints/admin/__init__.py` (~2044 lines).
  - Contains ~50 route handlers (RBAC, overrides/rate-limits, backups/retention, maintenance/flags/incidents, cache reload hooks).
- Important compatibility shims currently in `__init__.py`:
  - `_is_postgres_backend`
  - `_enforce_admin_user_scope`
  - `_get_admin_org_ids`
  - `_load_bulk_user_candidates`
  - `emit_budget_audit_event`
- Existing services that should be reused (not bypassed):
  - `admin_roles_permissions_service.py`
  - `admin_data_ops_service.py`
  - `admin_system_ops_service.py`
  - `admin_scope_service.py`

## Problem Statement

`admin/__init__.py` still contains high-complexity direct endpoint logic mixed with helper shims and service orchestration. This creates inconsistency with already-split admin modules and increases maintenance risk for RBAC/system features.

## Goals

- Reduce `admin/__init__.py` to aggregator + compatibility shims.
- Extract remaining route groups into dedicated endpoint modules.
- Increase service-layer usage consistency.
- Preserve all current route paths, auth behavior, and response contracts.
- Preserve test shim import/patch stability.

## Non-Goals

- No route path changes.
- No RBAC policy model redesign.
- No AuthNZ schema changes.
- No behavior changes to admin authorization semantics.

## Scope

### In Scope

- Extract remaining route handlers from `admin/__init__.py` into new endpoint modules.
- Keep helper compatibility symbols available from `admin` package path.

### Out of Scope

- New admin product features.
- Service architecture redesign beyond routing consistency and helper movement.

## Target Module Map

Add modules under `tldw_Server_API/app/api/v1/endpoints/admin/` for what still lives in `__init__.py`:

- `admin_rbac.py`
  - roles, permissions, matrix, effective permissions
  - user role assignment/removal
  - overrides
- `admin_rate_limits.py`
  - role/user rate limit endpoints
- `admin_data_ops.py`
  - backups
  - restore
  - retention policies
- `admin_ops.py`
  - maintenance mode
  - feature flags
  - incidents
  - pricing/model alias cache refresh endpoints

After extraction, `admin/__init__.py` should:
- define root router and include all admin subrouters
- retain compatibility helper exports only
- avoid implementing large endpoint handlers directly

## Compatibility Requirements

- Preserve all current `/api/v1/admin/*` routes and payload contracts.
- Preserve helper shim symbols for tests and imports:
  - `_is_postgres_backend`
  - `_enforce_admin_user_scope`
  - `_get_admin_org_ids`
  - `_load_bulk_user_candidates`
  - `emit_budget_audit_event`
- Maintain existing dependency configuration (`require_roles`, rate limits, principal resolution).

## Migration Plan

### Phase 1: RBAC Route Extraction

- Move RBAC and permission routes from `__init__.py` into `admin_rbac.py`.
- Keep shared helper calls through `admin_scope_service` and existing admin services.

### Phase 2: Rate-Limit Route Extraction

- Move user/role rate limit routes into `admin_rate_limits.py`.
- Keep request/response models unchanged.

### Phase 3: Data Ops Extraction

- Move backup/restore/retention routes into `admin_data_ops.py`.
- Keep service layer call sites (`admin_data_ops_service`).

### Phase 4: System Ops Extraction

- Move maintenance/flags/incidents/cache refresh routes into `admin_ops.py`.
- Keep `admin_system_ops_service` as the primary business logic layer.

### Phase 5: Final Shim Slimming

- Leave `__init__.py` as include-router glue + compatibility exports.
- Remove duplicated endpoint logic from `__init__.py`.

## Testing Strategy

- Run existing admin endpoint test suites unchanged.
- Add focused tests for each new module file where coverage is thin.
- Add compatibility tests for shim symbols imported from admin package root.
- Validate no path-level route regressions via OpenAPI route checks.

## Risks and Mitigations

- Risk: route registration/order conflicts during extraction.
  - Mitigation: migrate one route group at a time and verify OpenAPI diff.
- Risk: test failures due to shim movement.
  - Mitigation: preserve shim names in `admin/__init__.py` until all tests are stable.
- Risk: accidental auth behavior drift.
  - Mitigation: keep dependency decorators and service calls unchanged during route moves.

## Success Metrics

- `admin/__init__.py` reduced from ~2044 lines to a thin aggregator/shim.
- Remaining admin concerns are split into cohesive files.
- Existing admin tests and API contracts remain stable.

## Acceptance Criteria

- All current admin routes still available and behaviorally unchanged.
- Compatibility shim symbols remain importable from admin package root.
- `admin/__init__.py` no longer holds large endpoint bodies.
- Service layer usage is consistent and explicit in extracted modules.
