# Media DB V2 Claims Cluster Exact Rebuild Helper Rebinding Design

## Summary

Rebind the active claims cluster exact-rebuild coordinator,
`MediaDatabase.rebuild_claim_clusters_exact(...)`, onto a package-owned runtime
helper so the canonical `MediaDatabase` no longer owns that coordinator through
legacy globals. Keep the sibling
`rebuild_claim_clusters_from_assignments(...)` method out of scope for this
slice.

## Why This Slice

- `rebuild_claim_clusters_exact(...)` is the live runtime path used by
  `claims_service.rebuild_claim_clusters(...)` when the method is `exact`.
- It already has meaningful caller-facing coverage in:
  - `tldw_Server_API/tests/Claims/test_claims_watchlist_notifications.py`
  - `tldw_Server_API/tests/Claims/test_claims_dashboard_analytics.py`
  - `tldw_Server_API/tests/Claims/test_claims_service_override_db.py`
- `rebuild_claim_clusters_from_assignments(...)` is wider than it looks and has
  no direct runtime callers in this worktree, so bundling it would widen the
  tranche without protecting an active path.

## In Scope

- `rebuild_claim_clusters_exact(...)`

## Out Of Scope

- `rebuild_claim_clusters_from_assignments(...)`
- embedding-based clustering
- unrelated claims CRUD/search surfaces
- bootstrap/schema helpers

## Preserved Invariants

- `min_size` normalization still coerces invalid values to `2` and clamps to at
  least `1`.
- Existing clusters for the target user are removed before rebuild, including:
  - membership rows
  - `Claims.claim_cluster_id` assignments
  - old cluster rows
- Exact grouping still normalizes claim text with lowercase plus collapsed
  whitespace.
- Newly created exact clusters still:
  - use the first claim in the normalized group as representative
  - insert membership rows with `similarity_score=1.0`
  - reassign `Claims.claim_cluster_id`
  - bump `cluster_version` from `1` to `2`
- PostgreSQL `RETURNING id` handling remains intact.

## Test Strategy

Add direct regressions for:

- canonical `MediaDatabase.rebuild_claim_clusters_exact` no longer using legacy
  globals
- legacy `Media_DB_v2.rebuild_claim_clusters_exact` delegating through a live
  package module import

Add focused helper-path tests for:

- `min_size` normalization and exact text grouping
- clearing preexisting cluster state before rebuild
- per-cluster version bump to `2`
- PostgreSQL `RETURNING id` path

Keep broader guards from:

- `test_claims_watchlist_notifications.py`
- `test_claims_dashboard_analytics.py`
- `test_claims_service_override_db.py`

## Success Criteria

- normalized ownership count drops `34 -> 33`
- no behavior regressions in exact cluster rebuild callers
- worktree remains clean after verification
