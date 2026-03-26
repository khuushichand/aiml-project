# Media DB V2 Claims Cluster Assignment Rebuild Helper Rebinding Design

## Summary

Rebind the live embeddings-clustering coordinator,
`MediaDatabase.rebuild_claim_clusters_from_assignments(...)`, onto a
package-owned runtime helper so the canonical `MediaDatabase` no longer owns
that coordinator through legacy globals. Keep the already-rebound exact-rebuild
and cluster CRUD/aggregate surfaces untouched.

## Why This Slice

- `rebuild_claim_clusters_from_assignments(...)` is the active persistence path
  used by `claims_clustering.rebuild_claim_clusters_embeddings(...)`.
- It already has meaningful caller-facing coverage in:
  - `tldw_Server_API/tests/Claims/test_claims_clustering_embeddings.py`
  - `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`
- Its dependencies are already package-owned or stable:
  - transaction handling
  - low-level execute/fetch helpers
  - cluster CRUD/read methods
- The remaining alternative surfaces are broader:
  - claims CRUD/search methods
  - bootstrap/schema coordinators
  - `rollback_to_version(...)`

## In Scope

- `rebuild_claim_clusters_from_assignments(...)`

## Out Of Scope

- `rebuild_claim_clusters_exact(...)`
- embeddings generation/loading logic
- claims CRUD/search methods
- bootstrap/schema helpers
- `rollback_to_version(...)`

## Preserved Invariants

- Existing clusters for the target user are removed before rebuild, including:
  - `claim_cluster_membership` rows
  - old `claim_clusters` rows
  - `Claims.claim_cluster_id` assignments for claims owned by the target user
- Cleanup remains scoped by effective owner identity via
  `COALESCE(CAST(m.owner_user_id AS TEXT), m.client_id) = ?`.
- New clusters still:
  - insert `cluster_version=1`
  - insert `watchlist_count=0`
  - keep `summary=NULL`
  - use the provided `canonical_claim_text`
  - keep the provided `representative_claim_id`
- Membership insertion still uses `ON CONFLICT DO NOTHING`.
- Members with missing `claim_id` are ignored.
- `claims_assigned` remains the count of valid input members queued for insert,
  not backend rowcount semantics.
- PostgreSQL `RETURNING id` handling remains intact.

## Test Strategy

Add direct regressions for:

- canonical `MediaDatabase.rebuild_claim_clusters_from_assignments` no longer
  using legacy globals
- legacy `Media_DB_v2.rebuild_claim_clusters_from_assignments` delegating
  through a live package module import

Add focused helper-path tests for:

- cleanup of stale cluster rows, membership rows, and claim assignments before
  rebuild
- malformed member rows without `claim_id` being ignored
- `claims_assigned` counting valid input members
- SQLite insert path using `lastrowid`
- PostgreSQL insert path preserving `RETURNING id`

Keep broader guards from:

- `test_claims_clustering_embeddings.py`
- `test_media_db_api_imports.py`

## Success Criteria

- normalized ownership count drops `32 -> 31`
- no behavior regressions in embeddings clustering callers
- worktree remains clean after verification
