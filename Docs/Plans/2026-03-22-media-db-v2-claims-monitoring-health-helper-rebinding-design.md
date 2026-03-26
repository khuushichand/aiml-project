# Media DB V2 Claims Monitoring Health Helper Rebinding Design

## Overview

This tranche removes legacy ownership of the claims monitoring health helper
pair from `Media_DB_v2` and rebinds it onto a package-owned runtime module.
The target methods are:

- `get_claims_monitoring_health(...)`
- `upsert_claims_monitoring_health(...)`

The canonical `MediaDatabase` should stop owning these methods through legacy
globals, while the legacy class keeps compat-shell methods that delegate
through a live module reference.

## Why This Slice

After monitoring settings and alert CRUD moved off the legacy shell, the
remaining monitoring surface splits into:

- legacy config CRUD and migration glue
- event delivery helpers
- the small health pair

The health pair is the cleanest next bounded slice because:

- it is only two methods
- it has active caller coverage from claims service and rebuild code
- it does not require moving broader monitoring event or migration logic

Relevant callers and guards:

- `tldw_Server_API/app/core/Claims_Extraction/claims_service.py`
- `tldw_Server_API/app/core/Claims_Extraction/claims_rebuild_service.py`
- `tldw_Server_API/tests/Claims/test_claims_rebuild_health_persistence.py`
- `tldw_Server_API/tests/Claims/test_claims_rebuild_service_failure.py`

## In Scope

- Add one package-owned runtime helper module for the two health methods
- Rebind canonical `MediaDatabase` methods in `media_database_impl.py`
- Convert the two legacy `Media_DB_v2` methods into live-module compat shells
- Add ownership/delegation regressions
- Add focused helper-path tests for insert/update/read behavior

## Out Of Scope

- monitoring config CRUD and legacy migration helpers
- monitoring alerts CRUD
- monitoring event helpers and delivery helpers
- claims analytics and scheduler helpers

## Required Behavior To Preserve

### Read Path

- `get_claims_monitoring_health(...)` must return the latest row for a user by
  `updated_at DESC`
- missing-row behavior must remain `{}`

### Upsert Path

- insert when no row exists for the user
- update the most recent existing row when one exists
- preserve the tuple/dict fallback when reading the existing row id
- return the freshly read row after both insert and update

### Field Semantics

- `queue_size` must still coerce to `int`
- all optional timestamps and failure metadata must remain pass-through values

## Risk Review

### 1. Existing-row id fallback

`upsert_claims_monitoring_health(...)` currently handles both mapping-style and
tuple-style row access when reading the existing row id. That fallback needs to
survive extraction because it is part of the helper’s current DB-compat shape.

### 2. Rebuild-service caller contract

`claims_rebuild_service` persists health via the DB seam. This tranche must not
change the method signature or write/read semantics that those callers depend
on.

## Design

### New Runtime Module

Add:

- `tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_monitoring_health_ops.py`

This module will own:

- `get_claims_monitoring_health(...)`
- `upsert_claims_monitoring_health(...)`

### Canonical Rebinding

In `media_database_impl.py`:

- import the two runtime helper functions
- assign them onto the canonical `MediaDatabase` class

### Legacy Compat Shells

In `Media_DB_v2.py`:

- keep the two methods present
- replace each body with an `import_module(...)` delegation call into
  `claims_monitoring_health_ops`

## Testing Strategy

### Direct Regressions

Extend:

- `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

Add assertions for:

- canonical ownership moved off legacy globals for both methods
- legacy compat-shell delegation through the runtime module

### Focused Helper Tests

Add:

- `tldw_Server_API/tests/DB_Management/test_media_db_claims_monitoring_health_ops.py`

Cover:

- missing-row `{}` behavior
- insert path storing a first row
- update path replacing the latest row contents while preserving single-row
  semantics

### Broader Guards

Keep:

- `tldw_Server_API/tests/Claims/test_claims_rebuild_health_persistence.py`
- `tldw_Server_API/tests/Claims/test_claims_rebuild_service_failure.py`

## Success Criteria

- canonical `MediaDatabase` no longer owns the two health methods through
  legacy globals
- legacy methods remain working compat shells
- focused helper tests pass
- caller-facing rebuild/health tests stay green
- normalized ownership count drops from `65` to `63`
