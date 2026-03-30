# Media DB V2 Claims Monitoring Config Helper Rebinding Design

## Overview

This tranche removes the legacy ownership of the claims monitoring-config CRUD
layer from `Media_DB_v2` and rebinds it onto a package-owned runtime module.
The target methods are:

- `delete_claims_monitoring_configs_by_user(...)`
- `list_claims_monitoring_configs(...)`
- `create_claims_monitoring_config(...)`
- `get_claims_monitoring_config(...)`
- `update_claims_monitoring_config(...)`
- `delete_claims_monitoring_config(...)`
- `list_claims_monitoring_user_ids(...)`

The canonical `MediaDatabase` class should stop owning these methods through
legacy globals, while `Media_DB_v2` keeps compat-shell methods that delegate
through a live module reference.

## Why This Slice

After the claims review metrics helpers moved off legacy ownership, the next
clean claims-specific seam is the monitoring-config CRUD layer:

- it is a coherent internal cluster centered on the legacy
  `claims_monitoring_config` table
- it has active caller coverage in:
  - `tldw_Server_API/tests/Claims/test_claims_monitoring_api.py`
  - `tldw_Server_API/tests/Claims/test_claims_monitoring_legacy_migration.py`
  - `tldw_Server_API/tests/Claims/test_claims_alerts_scheduler.py`
- it is narrower than the remaining claims CRUD/search and clustering surface

This slice explicitly excludes the legacy migration coordinator
`migrate_legacy_claims_monitoring_alerts(...)`, which depends on both the old
config table and the already rebound alert layer.

## In Scope

- Add one package-owned runtime helper module for the seven monitoring-config
  methods
- Rebind canonical `MediaDatabase` methods in `media_database_impl.py`
- Convert the seven legacy `Media_DB_v2` methods into live-module compat
  shells
- Add direct ownership/delegation regressions
- Add focused helper-path tests for create/update/list/user-id behavior

## Out Of Scope

- `migrate_legacy_claims_monitoring_alerts(...)`
- claims monitoring alerts/settings/health/events helpers already rebound
- claims CRUD/search helpers
- claims clustering helpers
- email, bootstrap/schema, and safe-metadata search helpers

## Required Behavior To Preserve

### Config CRUD

- `delete_claims_monitoring_configs_by_user(...)` must keep deleting by
  `user_id` and committing
- `list_claims_monitoring_configs(...)` must keep:
  - selecting the same row shape
  - filtering by `user_id`
  - ordering by `id DESC`
- `create_claims_monitoring_config(...)` must keep:
  - using `self._get_current_utc_timestamp_str()` for both timestamps
  - using `RETURNING id` on PostgreSQL
  - using `cursor.lastrowid` on SQLite
  - coercing `enabled` to `1` or `0`
  - returning the refreshed row through `get_claims_monitoring_config(...)`
- `get_claims_monitoring_config(...)` must keep returning `{}` for a missing
  row
- `update_claims_monitoring_config(...)` must keep:
  - updating only fields explicitly provided
  - coercing numeric inputs through `float(...)`
  - coercing `enabled` to `1` or `0`
  - returning the current row unchanged when no fields are provided
  - always writing `updated_at` when any update occurs
- `delete_claims_monitoring_config(...)` must keep deleting by `id` and
  committing

### Monitoring User IDs

- `list_claims_monitoring_user_ids(...)` must keep unioning distinct user ids
  across `claims_monitoring_alerts` and `claims_monitoring_settings`
- it must keep the current mapping-row then tuple-row fallback
- it must keep filtering null and empty ids from the returned list

## Risk Review

### 1. Backend-specific create id retrieval

`create_claims_monitoring_config(...)` still has a backend split: PostgreSQL
uses `RETURNING id`, SQLite uses `lastrowid`. If the helper collapses those
paths incorrectly, create can succeed but return an empty object.

### 2. No-op update behavior

`update_claims_monitoring_config(...)` intentionally returns the current row
without issuing an update when no fields are provided. That behavior is easy to
lose during extraction and is observable at the API layer.

### 3. Scheduler discovery seam

`list_claims_monitoring_user_ids(...)` is part of the scheduler’s user scan
path. If the tuple-row fallback or null filtering changes, the scheduler can
silently skip users or process bad ids.

### 4. Legacy migration coupling

`migrate_legacy_claims_monitoring_alerts(...)` depends on this CRUD layer but
is a broader coordinator that also touches the alert helpers. It should remain
out of scope so this tranche stays a pure helper rebinding slice.

## Design

### New Runtime Module

Add:

- `tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_monitoring_config_ops.py`

This module will own:

- `delete_claims_monitoring_configs_by_user(...)`
- `list_claims_monitoring_configs(...)`
- `create_claims_monitoring_config(...)`
- `get_claims_monitoring_config(...)`
- `update_claims_monitoring_config(...)`
- `delete_claims_monitoring_config(...)`
- `list_claims_monitoring_user_ids(...)`

### Canonical Rebinding

In `media_database_impl.py`:

- import the seven runtime helper functions
- assign them onto the canonical `MediaDatabase` class

### Legacy Compat Shells

In `Media_DB_v2.py`:

- keep the seven methods present
- replace each body with an `import_module(...)` delegation call into
  `claims_monitoring_config_ops`

## Testing Strategy

### Direct Regressions

Add or extend regressions in
`tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py` for:

- canonical ownership moved off legacy globals for all seven methods
- legacy compat-shell delegation through the runtime module

### Focused Helper Tests

Add:

- `tldw_Server_API/tests/DB_Management/test_media_db_claims_monitoring_config_ops.py`

Focus on:

- backend-specific create id retrieval
- no-op update behavior
- update field coercion and refreshed-row return
- list ordering
- mapping-row and tuple-row fallback for `list_claims_monitoring_user_ids(...)`

### Broader Guards

Keep these as tranche-level caller-facing guards:

- `tldw_Server_API/tests/Claims/test_claims_monitoring_api.py`
- `tldw_Server_API/tests/Claims/test_claims_monitoring_legacy_migration.py`
- `tldw_Server_API/tests/Claims/test_claims_alerts_scheduler.py`

## Success Criteria

- canonical `MediaDatabase` no longer owns the seven monitoring-config methods
  through legacy globals
- legacy `Media_DB_v2` methods remain working compat shells
- helper-path tests pass
- caller-facing monitoring API, migration, and scheduler tests stay green
- normalized ownership count drops from `54` to `47`
