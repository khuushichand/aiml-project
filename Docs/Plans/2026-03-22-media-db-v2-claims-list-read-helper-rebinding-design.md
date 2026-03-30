# Media DB V2 Claims List Read Helper Rebinding Design

## Summary

After the direct-claims-read tranche, the normalized legacy ownership count is
`28`. The next clean claims-specific seam is `Media_DB_v2.list_claims(...)`.
This method is still canonical legacy-owned, but it is materially narrower than
the remaining claims write/search surface.

The method is a single read coordinator that assembles SQL filters and applies
shared visibility scoping. It should move as a one-method slice, not be bundled
with `search_claims(...)`, `upsert_claims(...)`, `update_claim(...)`,
`update_claim_review(...)`, or `soft_delete_claims_for_media(...)`.

## Current Method Shape

`list_claims(...)` currently owns:

- `limit` / `offset` coercion and clamping
- `include_deleted` gating
- optional SQL filters for:
  - `media_id`
  - `owner_user_id`
  - `org_id`
  - `team_id`
  - `review_status`
  - `reviewer_id`
  - `review_group`
  - `claim_cluster_id`
- scope-aware visibility filtering via `get_scope()`
- row ordering by `media_id`, `chunk_index`, and `id`

That makes it a real coordinator, but still a bounded one.

## Why This Slice Is Safe

The caller surface is active and coherent:

- admin/API list path:
  [claims.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/api/v1/endpoints/claims.py)
  and
  [claims_service.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/Claims_Extraction/claims_service.py)
- clustering pagination path:
  [claims_clustering.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/Claims_Extraction/claims_clustering.py)
- workflow adapter list path:
  [crud.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/Workflows/adapters/knowledge/crud.py)

Those callers all depend on the same method signature and read behavior, so a
package-owned rebinding gives real ownership reduction without widening into
write or search semantics.

## Risks To Pin

### 1. Filter composition

This method builds its `WHERE` clause incrementally. A rebinding bug can easily
drop one of the optional filters while still returning valid rows.

The focused helper tests must pin:

- `include_deleted=False` excludes soft-deleted claims
- `review_status`, `reviewer_id`, `review_group`, and `claim_cluster_id`
  filters each narrow results correctly
- `owner_user_id` still matches
  `COALESCE(CAST(m.owner_user_id AS TEXT), m.client_id)`

### 2. Scope visibility

The highest-risk branch is the non-admin scope filter. It depends on `get_scope`
and expands personal/team/org visibility clauses dynamically. Existing caller
tests do not pin this branch directly.

The helper tests must include at least one non-admin scope case proving that
rows outside the active scope are excluded.

### 3. Limit/offset normalization

The clustering and workflow paths both depend on the method accepting direct
`limit` / `offset` arguments. The method also has fallback logic for invalid
values and clamps the valid range.

The helper tests should pin:

- invalid values fall back to `limit=100`, `offset=0`
- negative offsets clamp to `0`
- ordering remains `media_id ASC, chunk_index ASC, id ASC`

### 4. Caller-compat seams

The workflow adapter path calls `media_db.list_claims(limit=..., offset=...)`
without any of the claims-specific filters. The clustering path calls
`list_claims(owner_user_id=..., include_deleted=False, limit=..., offset=...)`.

The tranche should preserve the public signature exactly and keep the legacy
method as a live-module compat shell.

## Recommended Tranche

Move only:

- `list_claims(...)`

Defer:

- `search_claims(...)`
- `upsert_claims(...)`
- `update_claim(...)`
- `update_claim_review(...)`
- `soft_delete_claims_for_media(...)`
- the broader bootstrap/postgres helpers still remaining elsewhere

## Design

Add a package-owned runtime module:

- `tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_list_ops.py`

That module should expose:

- `list_claims(self, *, media_id=None, owner_user_id=None, org_id=None,
  team_id=None, review_status=None, reviewer_id=None, review_group=None,
  claim_cluster_id=None, limit=100, offset=0, include_deleted=False)`

Then:

- rebind canonical `MediaDatabase.list_claims` in
  [media_database_impl.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py)
- convert legacy `Media_DB_v2.list_claims(...)` in
  [Media_DB_v2.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/DB_Management/Media_DB_v2.py)
  into a live-module compat shell

## Test Strategy

### Direct regressions

Add ownership/delegation regressions in
[test_media_db_v2_regressions.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py)
for:

- canonical `MediaDatabase.list_claims` no longer using legacy globals
- legacy `Media_DB_v2.list_claims(...)` delegating through the runtime module

### Focused helper coverage

Add a dedicated helper test file:

- `tldw_Server_API/tests/DB_Management/test_media_db_claims_list_ops.py`

Pin:

- canonical rebinding to the new runtime helper
- invalid/clamped pagination behavior
- deleted filtering and ordering
- `owner_user_id` filter
- review filters and cluster filter
- non-admin scope exclusion

### Broader guards

Reuse existing caller-facing coverage from:

- [test_claims_items_api.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_items_api.py)
- [test_claims_clustering_embeddings.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_clustering_embeddings.py)
- [test_knowledge_adapters.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Workflows/adapters/test_knowledge_adapters.py)

## Success Criteria

- canonical `MediaDatabase.list_claims(...)` is package-owned
- legacy `Media_DB_v2.list_claims(...)` is a live-module compat shell
- focused helper tests pin the filter, scope, and pagination behavior
- broader API/clustering/workflow caller guards stay green
- normalized ownership count drops `28 -> 27`
