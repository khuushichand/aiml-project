# Media DB V2 Claims Monitoring Alert Helper Rebinding Design

## Overview

This tranche removes the legacy ownership of the live claims monitoring alert
CRUD layer from `Media_DB_v2` and rebinds it onto a package-owned runtime
module. The target methods are:

- `list_claims_monitoring_alerts(...)`
- `get_claims_monitoring_alert(...)`
- `create_claims_monitoring_alert(...)`
- `update_claims_monitoring_alert(...)`
- `delete_claims_monitoring_alert(...)`

The canonical `MediaDatabase` class should stop owning these methods through
legacy globals, while `Media_DB_v2` keeps compat-shell methods that delegate
through a live module reference.

## Why This Slice

After the claims monitoring settings pair moved off legacy ownership, the next
clean claims-specific seam is the alert CRUD layer:

- it is a coherent five-method cluster in `Media_DB_v2`
- it is still actively used by the claims service and API
- it already has caller-facing coverage in:
  - `tldw_Server_API/tests/Claims/test_claims_monitoring_api.py`
  - `tldw_Server_API/tests/Claims/test_claims_alerts_digest.py`
  - `tldw_Server_API/tests/Claims/test_claims_monitoring_legacy_migration.py`

This is better leverage than the remaining legacy config CRUD helpers, which
are now mostly migration support rather than the primary live API path.

## In Scope

- Add one package-owned runtime helper module for the five alert CRUD methods
- Rebind canonical `MediaDatabase` methods in `media_database_impl.py`
- Convert the five legacy `Media_DB_v2` methods into live-module compat shells
- Add direct ownership/delegation regressions
- Add focused helper-path tests for the alert CRUD behaviors that are easy to
  regress during extraction

## Out Of Scope

- `delete_claims_monitoring_configs_by_user(...)`
- `list_claims_monitoring_configs(...)`
- `create_claims_monitoring_config(...)`
- `get_claims_monitoring_config(...)`
- `update_claims_monitoring_config(...)`
- `delete_claims_monitoring_config(...)`
- `migrate_legacy_claims_monitoring_alerts(...)`
- claims monitoring events, health, analytics, and scheduler helpers

## Required Behavior To Preserve

### List/Get

- `list_claims_monitoring_alerts(...)` must keep returning rows ordered by
  `id DESC`
- `get_claims_monitoring_alert(...)` must keep returning `{}` for a missing row

### Create

- the normal insert path must keep returning the created row via
  `get_claims_monitoring_alert(...)`
- the legacy migration path with explicit `alert_id` must preserve that id
- PostgreSQL sequence repair via `setval(...)` must remain in place for the
  explicit-id path, because legacy migration depends on that behavior

### Update

- no-op updates must keep returning the current row unchanged
- partial updates must keep preserving untouched fields
- supplied fields must keep coercing to the existing string/float/int storage
  behavior

### Delete

- deletion remains a hard delete by id

## Risk Review

### 1. Explicit `alert_id` migration path

`create_claims_monitoring_alert(...)` is not a generic CRUD insert only. It has
an explicit-id path used by `migrate_legacy_claims_monitoring_alerts(...)`. If
that path loses id preservation or PostgreSQL sequence repair, the legacy
migration contract breaks.

### 2. Migration helper still legacy-owned

`migrate_legacy_claims_monitoring_alerts(...)` will remain legacy-owned in this
slice, but it calls the rebound alert CRUD methods through `self`. That is
acceptable, provided the alert CRUD semantics remain unchanged.

### 3. Service/API callers rely on normalized downstream behavior

The claims service performs authorization and JSON/channel normalization above
the DB layer. This tranche must not move or reinterpret that logic. It should
only preserve the current DB-layer storage semantics.

## Design

### New Runtime Module

Add:

- `tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_monitoring_alert_ops.py`

This module will own:

- `list_claims_monitoring_alerts(...)`
- `get_claims_monitoring_alert(...)`
- `create_claims_monitoring_alert(...)`
- `update_claims_monitoring_alert(...)`
- `delete_claims_monitoring_alert(...)`

### Canonical Rebinding

In `media_database_impl.py`:

- import the five runtime helper functions
- assign them onto the canonical `MediaDatabase` class

### Legacy Compat Shells

In `Media_DB_v2.py`:

- keep the five methods present
- replace each body with an `import_module(...)` delegation call into
  `claims_monitoring_alert_ops`

## Testing Strategy

### Direct Regressions

Add/extend regressions in
`tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py` for:

- canonical ownership moved off legacy globals for all five methods
- legacy compat-shell delegation through the runtime module

### Focused Helper Tests

Add:

- `tldw_Server_API/tests/DB_Management/test_media_db_claims_monitoring_alert_ops.py`

Focus on:

- list ordering
- missing-row `{}` behavior
- create explicit-id path preserving `alert_id`
- update no-op and partial-update behavior
- delete removing the row

### Broader Guards

Keep these as tranche-level caller-facing guards:

- `tldw_Server_API/tests/Claims/test_claims_monitoring_api.py`
- `tldw_Server_API/tests/Claims/test_claims_alerts_digest.py`
- `tldw_Server_API/tests/Claims/test_claims_monitoring_legacy_migration.py`

## Success Criteria

- canonical `MediaDatabase` no longer owns the five alert CRUD methods through
  legacy globals
- legacy `Media_DB_v2` methods remain working compat shells
- helper-path tests pass
- caller-facing claims monitoring tests stay green
- normalized ownership count drops from `70` to `65`
