# Media DB V2 Claims Search Read Helper Rebinding Design

## Summary

After the `list_claims(...)` tranche, the normalized legacy ownership count is
`27`. The next clean claims-specific seam is `Media_DB_v2.search_claims(...)`.
This method is still canonical legacy-owned, but it is materially narrower than
the remaining claims write surface.

`search_claims(...)` is a single read coordinator that chooses the SQLite or
PostgreSQL search path, applies scope and ownership filters, and optionally
falls back to a `LIKE` search when FTS returns no rows. It should move as a
one-method slice, not be bundled with `upsert_claims(...)`,
`update_claim(...)`, `update_claim_review(...)`, or
`soft_delete_claims_for_media(...)`.

## Current Method Shape

`search_claims(...)` currently owns:

- whitespace trimming and empty-query early return
- `limit` coercion and lower-bound normalization
- scope resolution via `get_scope()`
- SQLite FTS search with best-effort `claims_fts` rebuild
- PostgreSQL FTS search using `FTSQueryTranslator.normalize_query(...)`
- optional `owner_user_id` filtering
- non-admin personal/team/org visibility filtering
- optional fallback to `LIKE` / `ILIKE`
- backend-specific result shaping, including `relevance_score`

That makes it a real coordinator, but still a bounded one.

## Why This Slice Is Safe

The caller surface is active and coherent:

- claims API search path:
  [claims_service.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/Claims_Extraction/claims_service.py)
- workflow adapter search path:
  [crud.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/Workflows/adapters/knowledge/crud.py)
- RAG claims retrieval path:
  [database_retrievers.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/RAG/rag_service/database_retrievers.py)

Those callers all depend on the same signature and read behavior, so a
package-owned rebinding gives real ownership reduction without widening into
claim writes or review state.

## Risks To Pin

### 1. SQLite FTS rebuild and fallback behavior

The SQLite branch defensively rebuilds `claims_fts` before running a `MATCH`
query. A rebinding bug can silently break search results even though the method
still returns a list.

The focused helper tests must pin:

- empty or whitespace-only query returns `[]`
- invalid `limit` falls back to `20`
- SQLite FTS returns rows when indexed content exists
- `fallback_to_like=False` suppresses `LIKE` fallback
- `fallback_to_like=True` returns rows when FTS returns none but `LIKE` matches

### 2. Scope visibility and ownership filters

The highest-risk branch is the non-admin scope filter. It dynamically expands
personal/team/org visibility predicates and composes them with
`owner_user_id`.

The helper tests must include at least one non-admin scope case proving that
rows outside the active scope are excluded from search results.

### 3. PostgreSQL tsquery path

The PostgreSQL branch depends on normalized `to_tsquery(...)` input and a
backend-specific SQL shape. This is too important to leave covered only by the
broader dual-backend suites.

The helper coverage should pin:

- `FTSQueryTranslator.normalize_query(...)` output is used
- the PostgreSQL branch passes the normalized tsquery twice
- the fallback branch switches to `ILIKE`

A backend stub is sufficient here; the tranche does not need to widen into
PostgreSQL migration or schema setup.

### 4. Caller-compat seams

The workflow adapter calls `media_db.search_claims(query=..., limit=...,
offset=...)`, even though the current method does not accept `offset`. That
path is currently mediated by a test double rather than the real implementation,
so this tranche must preserve the real canonical signature exactly and avoid
changing callers.

The claims API and RAG paths depend on `query`, `limit`, `fallback_to_like`,
and `owner_user_id`.

## Recommended Tranche

Move only:

- `search_claims(...)`

Defer:

- `upsert_claims(...)`
- `update_claim(...)`
- `update_claim_review(...)`
- `soft_delete_claims_for_media(...)`
- `replace_data_table_contents(...)`
- `search_by_safe_metadata(...)`
- `rollback_to_version(...)`
- the remaining bootstrap/postgres helpers

## Design

Add a package-owned runtime module:

- `tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_search_ops.py`

That module should expose:

- `search_claims(self, query, *, limit=20, fallback_to_like=True,
  owner_user_id=None)`

Then:

- rebind canonical `MediaDatabase.search_claims` in
  [media_database_impl.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py)
- convert legacy `Media_DB_v2.search_claims(...)` in
  [Media_DB_v2.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/DB_Management/Media_DB_v2.py)
  into a live-module compat shell

## Test Strategy

### Direct regressions

Add ownership/delegation regressions in
[test_media_db_v2_regressions.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py)
for:

- canonical `MediaDatabase.search_claims` no longer using legacy globals
- legacy `Media_DB_v2.search_claims(...)` delegating through the runtime module

### Focused helper coverage

Add a dedicated helper test file:

- `tldw_Server_API/tests/DB_Management/test_media_db_claims_search_ops.py`

Pin:

- canonical rebinding to the new runtime helper
- empty-query and invalid-limit normalization
- SQLite FTS success path
- `fallback_to_like=False` no-fallback behavior
- `fallback_to_like=True` fallback behavior
- non-admin scope exclusion
- PostgreSQL stub branch using normalized tsquery and `ILIKE` fallback

### Broader guards

Reuse existing caller-facing coverage from:

- [test_claims_cluster_links_and_search.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_cluster_links_and_search.py)
- [test_claims_retriever.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/RAG/test_claims_retriever.py)
- [test_dual_backend_end_to_end.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/RAG/test_dual_backend_end_to_end.py)

## Success Criteria

- canonical `MediaDatabase.search_claims(...)` is package-owned
- legacy `Media_DB_v2.search_claims(...)` is a live-module compat shell
- focused helper tests pin FTS, fallback, scope, and PostgreSQL-branch behavior
- broader claims API / RAG caller guards stay green
- normalized ownership count drops `27 -> 26`
