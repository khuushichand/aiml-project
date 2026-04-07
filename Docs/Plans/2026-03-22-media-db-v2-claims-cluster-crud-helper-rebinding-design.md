# Media DB V2 Claims Cluster CRUD Helper Rebinding Design

## Summary

Rebind the legacy claims cluster CRUD/link/member layer onto a package-owned
runtime module so the canonical `MediaDatabase` no longer owns these methods
through legacy globals while preserving claims cluster API, watchlist, and
embedding-clustering behavior.

## Scope

In scope:
- `list_claim_clusters(...)`
- `get_claim_cluster(...)`
- `get_claim_cluster_link(...)`
- `list_claim_cluster_links(...)`
- `create_claim_cluster_link(...)`
- `delete_claim_cluster_link(...)`
- `list_claim_cluster_members(...)`
- `create_claim_cluster(...)`
- `add_claim_to_cluster(...)`

Out of scope:
- `rebuild_claim_clusters_exact(...)`
- `rebuild_claim_clusters_from_assignments(...)`
- claims aggregate helpers already rebound
- claims CRUD/search/review helpers
- monitoring helpers
- bootstrap/schema helpers

## Why This Slice

This is now the cleanest remaining active claims domain seam. The methods are
used together by the claims clusters API and by cluster-link/member caller
paths, but they are still narrower than the rebuild coordinators and much
narrower than claims CRUD/search.

## Risks To Preserve

1. `list_claim_cluster_members(...)` visibility filtering:
   - `get_scope()` fallback behavior
   - personal/team/org filtering
   - empty-scope behavior collapsing to `(0 = 1)`
2. `create_claim_cluster(...)` backend-specific id retrieval:
   - PostgreSQL `RETURNING id`
   - SQLite `lastrowid`
3. `add_claim_to_cluster(...)` transaction semantics:
   - membership insert
   - claim `claim_cluster_id` update
   - cluster version/update timestamp bump
4. Link semantics:
   - `create_claim_cluster_link(...)` remains idempotent under conflict
   - `delete_claim_cluster_link(...)` preserves rowcount fallback
5. Filter normalization:
   - list/link/member limit/offset clamping
   - direction normalization in `list_claim_cluster_links(...)`

## Test Strategy

Direct regressions:
- canonical methods no longer use legacy globals
- legacy `Media_DB_v2` methods delegate through live package-module imports

Focused helper tests:
- create/get/list cluster behavior and filter preservation
- link create/get/list/delete behavior including direction handling
- member list visibility filtering via helper-module `get_scope` monkeypatch
- `add_claim_to_cluster(...)` preserving membership, claim assignment, and
  cluster version bump

Broader guards:
- `tldw_Server_API/tests/Claims/test_claims_cluster_links_and_search.py`
- `tldw_Server_API/tests/Claims/test_claims_clusters_api.py`
- `tldw_Server_API/tests/Claims/test_claims_clustering_embeddings.py`
- `tldw_Server_API/tests/Claims/test_claim_cluster_upsert_idempotency.py`
- `tldw_Server_API/tests/Claims/test_claims_watchlist_notifications.py`

## Success Criteria

- normalized ownership count drops from `43` to `34`
- claims cluster API and link/member caller paths remain green
- rebuild coordinators remain untouched
