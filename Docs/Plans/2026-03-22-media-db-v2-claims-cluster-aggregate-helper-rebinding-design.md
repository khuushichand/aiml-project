# Media DB V2 Claims Cluster Aggregate Helper Rebinding Design

## Overview

This tranche removes the legacy ownership of the small claims cluster aggregate
helper layer from `Media_DB_v2` and rebinds it onto a package-owned runtime
module. The target methods are:

- `get_claim_clusters_by_ids(...)`
- `get_claim_cluster_member_counts(...)`
- `update_claim_clusters_watchlist_counts(...)`

The canonical `MediaDatabase` class should stop owning these methods through
legacy globals, while `Media_DB_v2` keeps compat-shell methods that delegate
through a live module reference.

## Why This Slice

After the monitoring-config CRUD layer moved off legacy ownership, the next
clean bounded seam is this three-method aggregate helper cluster:

- it is small and internally coherent
- it is used together in the watchlist notification path in
  `claims_service.py`
- it avoids the wider blast radius of claims cluster CRUD and rebuild methods
- it avoids the coordinator behavior in
  `migrate_legacy_claims_monitoring_alerts(...)`

The key caller seam is:

- `claims_service.py` retrieving clusters and member counts, then updating
  watchlist counts:
  - `clusters = db.get_claim_clusters_by_ids(cluster_ids)`
  - `member_counts = db.get_claim_cluster_member_counts(cluster_ids)`
  - `db.update_claim_clusters_watchlist_counts(counts)`

## In Scope

- Add one package-owned runtime helper module for the three aggregate helper
  methods
- Rebind canonical `MediaDatabase` methods in `media_database_impl.py`
- Convert the three legacy `Media_DB_v2` methods into live-module compat shells
- Add direct ownership/delegation regressions
- Add focused helper-path tests for empty-input behavior, tuple-row fallback,
  and update-count semantics

## Out Of Scope

- `migrate_legacy_claims_monitoring_alerts(...)`
- cluster CRUD and read methods such as:
  - `create_claim_cluster(...)`
  - `get_claim_cluster(...)`
  - `list_claim_clusters(...)`
  - `create_claim_cluster_link(...)`
  - `delete_claim_cluster_link(...)`
  - `list_claim_cluster_members(...)`
- cluster rebuild coordinators:
  - `rebuild_claim_clusters_exact(...)`
  - `rebuild_claim_clusters_from_assignments(...)`
- claims CRUD/search, bootstrap/schema, and rollback helpers

## Required Behavior To Preserve

### Cluster Lookup

- `get_claim_clusters_by_ids(...)` must keep:
  - returning `[]` for empty input
  - querying only `id`, `canonical_claim_text`, and `updated_at`
  - preserving `IN (...)` placeholder behavior for the provided ids
  - returning `[dict(row) for row in rows]`

### Member Counts

- `get_claim_cluster_member_counts(...)` must keep:
  - returning `{}` for empty input
  - grouping by `cluster_id`
  - preserving tuple-index row fallback (`row[0]`, `row[1]`)
  - ignoring malformed rows via the current noncritical exception path

### Watchlist Count Updates

- `update_claim_clusters_watchlist_counts(...)` must keep:
  - returning `0` for empty input
  - using `execute_many(...)`
  - coercing both count and cluster id to `int`
  - returning `len(params)` rather than backend rowcount

## Risk Review

### 1. Empty-input fast return

All three methods have empty-input fast returns. Losing those would produce
invalid `IN ()` SQL or unnecessary update calls.

### 2. Tuple-row fallback in member counts

`get_claim_cluster_member_counts(...)` currently reads tuple-style rows rather
than mapping rows. If that shifts during extraction, the watchlist path can
silently see empty member counts even though rows were returned.

### 3. Update return semantics

`update_claim_clusters_watchlist_counts(...)` returns the number of items it
attempted to write, not backend rowcount. The caller currently treats this as
best-effort helper behavior; that contract should not drift.

### 4. Do not mix with cluster rebuild logic

The rebuild methods are far wider: they delete membership rows, clear claim
cluster ids, create clusters, and repopulate membership tables. Bundling them
with this helper trio would turn a narrow aggregate-helper slice into a broad
cluster coordinator extraction.

## Design

### New Runtime Module

Add:

- `tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_cluster_aggregate_ops.py`

This module will own:

- `get_claim_clusters_by_ids(...)`
- `get_claim_cluster_member_counts(...)`
- `update_claim_clusters_watchlist_counts(...)`

### Canonical Rebinding

In `media_database_impl.py`:

- import the three runtime helper functions
- assign them onto the canonical `MediaDatabase` class

### Legacy Compat Shells

In `Media_DB_v2.py`:

- keep the three methods present
- replace each body with an `import_module(...)` delegation call into
  `claims_cluster_aggregate_ops`

## Testing Strategy

### Direct Regressions

Add or extend regressions in
`tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py` for:

- canonical ownership moved off legacy globals for all three methods
- legacy compat-shell delegation through the runtime module

### Focused Helper Tests

Add:

- `tldw_Server_API/tests/DB_Management/test_media_db_claims_cluster_aggregate_ops.py`

Focus on:

- `[] -> []` for `get_claim_clusters_by_ids(...)`
- `[] -> {}` for `get_claim_cluster_member_counts(...)`
- tuple-row fallback and malformed-row ignore behavior for member counts
- `{} -> 0` for `update_claim_clusters_watchlist_counts(...)`
- update count returning `len(params)` after `execute_many(...)`

### Broader Guards

Keep these as tranche-level caller-facing guards:

- `tldw_Server_API/tests/Claims/test_claims_watchlist_notifications.py`
- `tldw_Server_API/tests/Claims/test_claims_dashboard_analytics.py`
- `tldw_Server_API/tests/Claims/test_claims_cluster_links_and_search.py`
- `tldw_Server_API/tests/Claims/test_claims_service_override_db.py`

## Success Criteria

- canonical `MediaDatabase` no longer owns the three aggregate helper methods
  through legacy globals
- legacy `Media_DB_v2` methods remain working compat shells
- helper-path tests pass
- caller-facing claims cluster/watchlist tests stay green
- normalized ownership count drops from `47` to `44`
