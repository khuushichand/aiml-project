# Media DB V2 Claims Monitoring Settings Helper Rebinding Design

## Summary

Rebind the legacy claims monitoring settings helper pair onto a package-owned
runtime module so the canonical `MediaDatabase` no longer owns those methods
through legacy globals. Preserve the existing claims-service and claims
monitoring API contracts for `get_claims_monitoring_settings(...)` and
`upsert_claims_monitoring_settings(...)` while explicitly deferring alerts,
events, health, analytics, and broader monitoring helpers.

## Scope

In scope:
- `get_claims_monitoring_settings(...)`
- `upsert_claims_monitoring_settings(...)`
- direct ownership and compat-shell delegation regressions
- focused helper-path tests for missing-row, insert, no-op update, and partial
  update behavior
- reuse of broader monitoring-config caller-facing guards

Out of scope:
- `list_claims_monitoring_alerts(...)`
- `get_claims_monitoring_alert(...)`
- `create_claims_monitoring_alert(...)`
- `update_claims_monitoring_alert(...)`
- monitoring events, health, analytics, and scheduler helpers
- claims-service authorization and normalization logic

## Why This Slice

This is the smallest remaining claims monitoring seam because the two methods
form one table-local config helper pair over `claims_monitoring_settings`:
- fetch the current monitoring config row for one user
- create or update that row and return the stored state

It already has meaningful caller-facing coverage in:
- [claims_service.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/Claims_Extraction/claims_service.py)
  for monitoring config defaults, validation, and update flow
- [claims.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/api/v1/endpoints/claims.py)
  for the stable monitoring-config endpoint contract
- [test_claims_monitoring_api.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_monitoring_api.py)
  for config read/write behavior through the API
- [test_claims_alerts_digest.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_alerts_digest.py)
  for downstream monitoring-config use in alert delivery

## Existing Risks To Preserve

### 1. Missing reads must stay empty-dict

`get_claims_monitoring_settings(...)` currently returns `{}` when no row exists.
The service layer depends on that empty-dict contract to decide when it should
materialize defaults.

### 2. Insert must preserve enabled defaulting

On first insert, `upsert_claims_monitoring_settings(...)` stores `enabled = 1`
when `enabled is None`. That behavior matters because the service layer relies
on DB persistence to preserve the default-enabled monitoring state.

### 3. Update must preserve no-op return behavior

When an existing row is present and no update fields are supplied,
`upsert_claims_monitoring_settings(...)` currently returns the stored row
unchanged instead of issuing an empty update. The service layer depends on that
response shape.

### 4. Update must remain partial and read-after-write

The helper currently updates only provided fields, appends `updated_at`, and
returns the stored row via `get_claims_monitoring_settings(...)`. That
read-after-write behavior should remain exact.

## Implementation Shape

Add one package runtime module:
- `tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_monitoring_settings_ops.py`

That module should own only:
- `get_claims_monitoring_settings(...)`
- `upsert_claims_monitoring_settings(...)`

Then:
- rebind the canonical methods in `media_database_impl.py`
- convert the legacy methods in `Media_DB_v2.py` into live-module compat shells

Important boundary choices:
- do not change `claims_service.py`
- do not change `claims.py`
- do not pull in alert, event, health, analytics, or scheduler helpers

## Test Strategy

### Ownership / compat-shell regressions

Add direct regressions in
`tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py` for:
- canonical ownership moved off legacy globals for both in-scope methods
- legacy `Media_DB_v2` methods delegating through a live `import_module(...)`
  reference

### Focused helper-path tests

Add a new helper test file covering:
- `get_claims_monitoring_settings(...)` returning `{}` for a missing row
- `upsert_claims_monitoring_settings(...)` insert path with default-enabled
  behavior
- `upsert_claims_monitoring_settings(...)` no-op update path returning the
  current row
- `upsert_claims_monitoring_settings(...)` partial update preserving untouched
  fields and updating supplied ones

These tests should exercise canonical `MediaDatabase` methods, not the legacy
class.

### Broader caller-facing guards

Retain and reuse:
- [test_claims_monitoring_api.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_monitoring_api.py)
- [test_claims_alerts_digest.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_alerts_digest.py)

The focused helper tests are the primary rebinding proof. The API and digest
tests are the broader compatibility guards showing the monitoring-config reads
and writes still feed caller-facing flows correctly.

## Success Criteria

- canonical ownership for the two in-scope methods moves off legacy globals
- both legacy methods remain present as live-module compat shells
- focused helper-path tests pass
- broader monitoring-config caller-facing guards stay green
- normalized ownership count drops from `72` to `70`
