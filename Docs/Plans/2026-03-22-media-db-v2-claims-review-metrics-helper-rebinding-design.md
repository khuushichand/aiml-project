# Media DB V2 Claims Review Metrics Helper Rebinding Design

## Overview

This tranche removes the legacy ownership of the claims review metrics helper
layer from `Media_DB_v2` and rebinds it onto a package-owned runtime module.
The target methods are:

- `get_claims_review_extractor_metrics_daily(...)`
- `upsert_claims_review_extractor_metrics_daily(...)`
- `list_claims_review_extractor_metrics_daily(...)`
- `list_claims_review_user_ids(...)`

The canonical `MediaDatabase` class should stop owning these methods through
legacy globals, while `Media_DB_v2` keeps compat-shell methods that delegate
through a live module reference.

## Why This Slice

After the monitoring event helpers moved off legacy ownership, the next clean
claims-specific seam is the review-metrics cluster:

- it is a coherent four-method cluster in `Media_DB_v2`
- it sits on the active runtime path for dashboard analytics, review metrics
  API reads, and the review-metrics scheduler
- it already has caller-facing coverage in:
  - `tldw_Server_API/tests/Claims/test_claims_review_extractor_metrics_daily.py`
  - `tldw_Server_API/tests/Claims/test_claims_review_metrics_scheduler.py`
  - `tldw_Server_API/tests/Claims/test_claims_review_metrics_api.py`
  - `tldw_Server_API/tests/Claims/test_claims_dashboard_analytics.py`

This is tighter than the remaining legacy monitoring-config CRUD layer, which
widens immediately into legacy alert migration behavior.

## In Scope

- Add one package-owned runtime helper module for the four review-metrics
  methods
- Rebind canonical `MediaDatabase` methods in `media_database_impl.py`
- Convert the four legacy `Media_DB_v2` methods into live-module compat shells
- Add direct ownership/delegation regressions
- Add focused helper-path tests for the review-metrics behaviors that are easy
  to regress during extraction

## Out Of Scope

- `list_claims(...)`
- `search_claims(...)`
- `upsert_claims(...)`
- `get_claims_by_media(...)`
- `get_claims_by_uuid(...)`
- `get_claim_with_media(...)`
- `update_claim(...)`
- `update_claim_review(...)`
- `soft_delete_claims_for_media(...)`
- claims monitoring config CRUD and legacy alert migration
- claims clustering, bootstrap/schema, and search helpers

## Required Behavior To Preserve

### Get

- `get_claims_review_extractor_metrics_daily(...)` must keep normalizing
  `extractor_version=None` to `""`
- it must keep returning `{}` for a missing row
- it must keep selecting the same row shape and field set

### Upsert

- `upsert_claims_review_extractor_metrics_daily(...)` must keep:
  - normalizing `extractor_version=None` to `""`
  - using `self._get_current_utc_timestamp_str()` for write timestamps
  - inserting when no matching row exists
  - updating the existing row when a matching row exists
  - preserving the current mapping-row then tuple-row fallback when reading the
    existing row id
  - returning the refreshed row through
    `get_claims_review_extractor_metrics_daily(...)`

### List

- `list_claims_review_extractor_metrics_daily(...)` must keep:
  - filtering by `user_id`
  - optional filters for `start_date`, `end_date`, `extractor`, and
    `extractor_version`
  - coercing `limit` and `offset` to integers
  - clamping `limit` to `1..5000`
  - clamping `offset` to `>= 0`
  - ordering by `report_date DESC, id DESC`

### Review User IDs

- `list_claims_review_user_ids(...)` must keep returning `[]` for non-Postgres
  backends
- for Postgres it must keep selecting distinct review-log owner ids through the
  `claims -> media` join
- it must keep preserving the current mapping-row then tuple-row fallback and
  filtering null/empty ids from the result

## Risk Review

### 1. Version normalization drift

The metrics read/write layer intentionally normalizes `extractor_version=None`
to `""`. The scheduler, dashboard analytics path, and API reads all depend on
that behavior matching across get, upsert, and list.

### 2. Existing-row id fallback

`upsert_claims_review_extractor_metrics_daily(...)` uses a mapping-row then
tuple-row fallback when reading the existing metrics row id. If that fallback
is lost, helper tests may still pass on one backend shape while the other
breaks.

### 3. Postgres-only scheduler discovery seam

`list_claims_review_user_ids(...)` is the scheduler’s Postgres discovery seam.
It is a small helper, but if it changes semantics the scheduler can silently
skip users or process the wrong scope.

## Design

### New Runtime Module

Add:

- `tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_review_metrics_ops.py`

This module will own:

- `get_claims_review_extractor_metrics_daily(...)`
- `upsert_claims_review_extractor_metrics_daily(...)`
- `list_claims_review_extractor_metrics_daily(...)`
- `list_claims_review_user_ids(...)`

### Canonical Rebinding

In `media_database_impl.py`:

- import the four runtime helper functions
- assign them onto the canonical `MediaDatabase` class

### Legacy Compat Shells

In `Media_DB_v2.py`:

- keep the four methods present
- replace each body with an `import_module(...)` delegation call into
  `claims_review_metrics_ops`

## Testing Strategy

### Direct Regressions

Add/extend regressions in
`tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py` for:

- canonical ownership moved off legacy globals for all four methods
- legacy compat-shell delegation through the runtime module

### Focused Helper Tests

Add:

- `tldw_Server_API/tests/DB_Management/test_media_db_claims_review_metrics_ops.py`

Focus on:

- `extractor_version=None` normalization to `""`
- insert/update read-after-write behavior
- list limit/offset coercion and clamp behavior
- non-Postgres `list_claims_review_user_ids(...) -> []`
- Postgres-style tuple fallback for `list_claims_review_user_ids(...)`

### Broader Guards

Keep these as tranche-level caller-facing guards:

- `tldw_Server_API/tests/Claims/test_claims_review_extractor_metrics_daily.py`
- `tldw_Server_API/tests/Claims/test_claims_review_metrics_scheduler.py`
- `tldw_Server_API/tests/Claims/test_claims_review_metrics_api.py`
- `tldw_Server_API/tests/Claims/test_claims_dashboard_analytics.py`

## Success Criteria

- canonical `MediaDatabase` no longer owns the four review-metrics methods
  through legacy globals
- legacy `Media_DB_v2` methods remain working compat shells
- helper-path tests pass
- caller-facing claims review metrics tests stay green
- normalized ownership count drops from `58` to `54`
