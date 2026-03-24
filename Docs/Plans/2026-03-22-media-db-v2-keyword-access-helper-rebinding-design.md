# Media DB V2 Keyword Access Helper Rebinding Design

## Summary

After the claims write tranche, the normalized legacy ownership count is `22`.
The next clean non-bootstrap seam is the keyword-access pair:

- `add_keyword(...)`
- `fetch_media_for_keywords(...)`

`add_keyword(...)` is already a thin repository wrapper, while
`fetch_media_for_keywords(...)` still owns grouped keyword-to-media query
assembly, input normalization, trash filtering, and response shaping. Taken
together they form a coherent keyword-access tranche without widening into
keyword-link mutation, media search, synced document updates, or rollback.

## Current Method Shape

`add_keyword(...)` currently owns only:

- the legacy `MediaDatabase` entrypoint signature
- a direct delegate to `KeywordsRepository.from_legacy_db(self).add(...)`

`fetch_media_for_keywords(...)` currently owns:

- list-type validation
- empty-input fast returns
- keyword normalization via strip/lowercase/deduplication
- backend-aware keyword ordering through `_keyword_order_expression(...)`
- `deleted` / `is_trash` filtering for media rows
- grouped result shaping keyed by canonical keyword text
- best-effort consistency fallback if a returned DB keyword is not already in
  the normalized input set
- `DatabaseError` wrapping around backend/query failures

## Why This Slice Is Safe

The caller surface is active but narrow:

- direct keyword write/read behavior already covered in
  [test_sqlite_db.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/MediaDB2/test_sqlite_db.py)
- grouped keyword media lookup exercised by
  [test_vector_stores_keyword_match.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/VectorStores/test_vector_stores_keyword_match.py)
- repository semantics for `add_keyword(...)` already package-owned in
  [keywords_repository.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/DB_Management/media_db/repositories/keywords_repository.py)

This slice reduces ownership without widening into:

- `search_by_safe_metadata(...)`
- `replace_data_table_contents(...)`
- `apply_synced_document_content_update(...)`
- `rollback_to_version(...)`
- bootstrap / schema / migration coordinators

## Risks To Pin

### 1. `add_keyword(...)` must preserve the repository seam

This method is already structurally simple. The rebinding must keep the live
entrypoint behavior identical by continuing to call
`KeywordsRepository.from_legacy_db(self).add(...)` with the same `conn=...`
forwarding.

Focused helper tests must pin:

- canonical `MediaDatabase.add_keyword` rebinding
- repository factory call with the legacy DB instance
- exact forwarding of `keyword` and `conn`

### 2. `fetch_media_for_keywords(...)` normalization and empty-input behavior

This method has multiple fast-return paths that are easy to regress when moved.

Focused helper tests must pin:

- `TypeError` when input is not a list
- `{}` for `[]`
- `{}` when all provided items normalize to empty strings
- deduplicated lowercase keys in the returned mapping

### 3. `fetch_media_for_keywords(...)` grouped read semantics

The main runtime value of the method is the grouped mapping shape that downstream
vector-store creation relies on.

Focused helper tests must pin:

- `deleted = 0` filtering for media rows
- `is_trash = 0` filtering when `include_trash=False`
- inclusion of trash rows when `include_trash=True`
- per-keyword grouped output preserving canonical DB keyword keys
- media item field shaping for the returned dictionaries

### 4. Ordering and consistency fallback should stay intact

The method depends on `_keyword_order_expression(...)` and appends a fallback
group if a returned DB keyword is not already in the normalized input set.
That fallback should remain intact even if it is rare in normal operation.

Focused helper tests should pin:

- `_keyword_order_expression("k.keyword")` is used
- rows for an unexpected keyword still get returned under a new key instead of
  being dropped

## Recommended Tranche

Move only:

- `add_keyword(...)`
- `fetch_media_for_keywords(...)`

Defer:

- keyword-link mutation helpers already moved elsewhere
- `search_by_safe_metadata(...)`
- `replace_data_table_contents(...)`
- `apply_synced_document_content_update(...)`
- `rollback_to_version(...)`
- bootstrap / postgres coordinator helpers

## Design

Add a package-owned runtime module:

- `tldw_Server_API/app/core/DB_Management/media_db/runtime/keyword_access_ops.py`

That module should expose:

- `add_keyword(self, keyword, conn=None)`
- `fetch_media_for_keywords(self, keywords, include_trash=False)`

Then:

- rebind the canonical methods in
  [media_database_impl.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py)
- convert the legacy methods in
  [Media_DB_v2.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/DB_Management/Media_DB_v2.py)
  into live-module compat shells

## Test Strategy

### Direct regressions

Add ownership/delegation regressions in
[test_media_db_v2_regressions.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py)
for:

- canonical `MediaDatabase` methods no longer using legacy globals
- legacy `Media_DB_v2` methods delegating through `keyword_access_ops.py`

### Focused helper coverage

Add a dedicated helper test file:

- `tldw_Server_API/tests/DB_Management/test_media_db_keyword_access_ops.py`

Pin:

- repository forwarding for `add_keyword(...)`
- type/empty-input guards for `fetch_media_for_keywords(...)`
- normalization, grouping, include-trash filtering, and fallback-key behavior

### Broader guards

Reuse caller-facing coverage from:

- [test_sqlite_db.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/MediaDB2/test_sqlite_db.py)
- [test_vector_stores_keyword_match.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/VectorStores/test_vector_stores_keyword_match.py)

## Success Criteria

- canonical keyword-access methods are package-owned
- legacy `Media_DB_v2` keyword-access methods are live-module compat shells
- helper tests pin repository forwarding plus grouped keyword-media lookup
  behavior
- broader SQLite keyword and vector-store keyword-match guards stay green
- normalized ownership count drops `22 -> 20`
