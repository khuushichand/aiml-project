# Media DB V2 Claims Analytics Export Helper Rebinding Design

## Summary

Rebind the legacy claims analytics export helper cluster onto a package-owned
runtime module so the canonical `MediaDatabase` no longer owns those methods
through legacy globals. Preserve the existing claims-service and API contract
for create, get, list, count, and retention cleanup while explicitly deferring
claims notifications, monitoring, review, and cluster logic.

## Scope

In scope:
- `create_claims_analytics_export(...)`
- `get_claims_analytics_export(...)`
- `list_claims_analytics_exports(...)`
- `count_claims_analytics_exports(...)`
- `cleanup_claims_analytics_exports(...)`
- direct ownership and compat-shell delegation regressions
- focused helper-path tests for read-after-write, filter parity, and retention
  semantics
- reuse of broader claims analytics endpoint and service guards

Out of scope:
- claims notifications methods
- claims monitoring methods
- claims review methods
- claims cluster methods
- `search_claims(...)`
- `get_claims_by_uuid(...)`, `get_claims_by_media(...)`, and broader claims
  CRUD/search surfaces

## Why This Slice

This is the cleanest remaining first claims-domain slice because the five
methods form a coherent storage helper layer around one table:
- create a persisted export row
- fetch an export row by `export_id` with optional user scoping
- list export summaries with status/format filters
- count export summaries with the same filters
- delete old export rows for one user by retention window

It already has caller-facing coverage in:
- [test_claims_analytics_exports_cleanup.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_analytics_exports_cleanup.py)
  for cleanup/list/count semantics
- [test_claims_dashboard_analytics.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_dashboard_analytics.py)
  for service and API-level export flows

By contrast, notifications carry delivery-state and downstream caller behavior,
monitoring is a much larger config/event/health domain, and review/cluster
methods are materially broader than this table-local helper cluster.

## Existing Risks To Preserve

### 1. Create must preserve read-after-write semantics

`create_claims_analytics_export(...)` currently inserts the row and immediately
returns `get_claims_analytics_export(...)`. That contract matters because the
claims service reads `status` and `created_at` from the returned row after
creating an export.

### 2. Get must preserve optional user scoping and payload fields

`get_claims_analytics_export(...)` currently:
- always filters by `export_id`
- optionally filters by `user_id`
- returns the payload-bearing fields used by the download path:
  `payload_json`, `payload_csv`, `status`, and `format`

The helper move must not narrow the returned field set or drop the optional
`user_id` condition.

### 3. List/count filter parity must remain exact

`list_claims_analytics_exports(...)` and `count_claims_analytics_exports(...)`
share the same `user_id`, `status`, and `format` filter behavior. That parity
is what allows the claims service to return a consistent `exports` list and
`total`.

### 4. Cleanup must preserve tolerant retention handling

`cleanup_claims_analytics_exports(...)` currently:
- returns `0` for non-numeric or non-positive `retention_hours`
- computes a UTC cutoff string
- clamps the returned delete count to a non-negative integer

That tolerant behavior should remain unchanged.

## Implementation Shape

Add one package runtime module:
- `tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_analytics_export_ops.py`

That module should own only:
- `create_claims_analytics_export(...)`
- `get_claims_analytics_export(...)`
- `list_claims_analytics_exports(...)`
- `count_claims_analytics_exports(...)`
- `cleanup_claims_analytics_exports(...)`

Then:
- rebind the canonical methods in `media_database_impl.py`
- convert the legacy methods in `Media_DB_v2.py` into live-module compat shells

Important boundary choices:
- do not change `claims_service.py`
- do not change the API endpoints
- do not pull any notifications, monitoring, review, or cluster helpers into
  this tranche

## Test Strategy

### Ownership / compat-shell regressions

Add direct regressions in
`tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py` for:
- canonical ownership moved off legacy globals for all five in-scope methods
- legacy `Media_DB_v2` methods delegating through a live `import_module(...)`
  reference

### Focused helper-path tests

Add a new helper test file covering:
- `create_claims_analytics_export(...)` returning the freshly readable row
- `get_claims_analytics_export(...)` honoring the optional `user_id` filter
- `list_claims_analytics_exports(...)` and `count_claims_analytics_exports(...)`
  staying in filter parity for `status` and `format`
- `cleanup_claims_analytics_exports(...)` returning `0` for invalid or
  non-positive `retention_hours`

These tests should stay narrow and hit the canonical `MediaDatabase` methods,
not the legacy class.

### Broader caller-facing guards

Retain and reuse:
- [test_claims_analytics_exports_cleanup.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_analytics_exports_cleanup.py)
- [test_claims_dashboard_analytics.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_dashboard_analytics.py)

The focused helper tests are the primary rebinding proof. The claims dashboard
suite is the broader compatibility guard for the service/API contract.

## Success Criteria

- canonical ownership for the five in-scope methods moves off legacy globals
- all five legacy methods remain present as live-module compat shells
- focused helper-path tests pass
- broader claims analytics caller-facing guards stay green
- normalized ownership count drops from `90` to `85`
