# Media DB V2 Safe Metadata Search Helper Rebinding Design

## Summary

After the synced-document update tranche, the normalized legacy ownership count
is `18`. The cleanest remaining non-bootstrap singleton is
`search_by_safe_metadata(...)`.

This method is a read-only query builder used by the metadata-search and
identifier lookup endpoints. It owns its own SQL assembly, identifier-join
switching, standard media filters, paging, and sorting. That makes it a real
helper extraction, but still narrow enough for a bounded single-method slice.

## Current Method Shape

`search_by_safe_metadata(...)` currently owns:

- page/offset calculation
- base `DocumentVersions` / `Media` clause assembly
- optional `DocumentVersionIdentifiers` join for identifier fields
- identifier-field predicate generation (`doi`, `pmid`, `pmcid`, `arxiv_id`,
  `s2_paper_id`)
- JSON-text fallback predicates against `dv.safe_metadata`
- match-all vs match-any filter grouping
- `text_query`, `media_types`, keyword, and date-range constraints
- total-count query generation
- grouped vs ungrouped result query generation
- sort-mode selection and limit/offset application
- read-only exception wrapping to `DatabaseError`

## Why This Slice Is Safe

This method is active, but the boundary is still narrow:

- it is read-only
- it uses `execute_query(...)` instead of transaction/mutation seams
- its only live callers are listing/identifier endpoints plus direct SQLite tests
- it does not cross into sync, versioning, rollback, or bootstrap coordination

That makes it safer than the broader remaining surfaces:

- `rollback_to_version(...)`
- `initialize_db(...)`
- `_initialize_schema*` / postgres bootstrap helpers

## Risks To Pin

### 1. Identifier fields must still trigger the identifiers join

The method special-cases `doi`, `pmid`, `pmcid`, `arxiv_id`, and
`s2_paper_id` through `DocumentVersionIdentifiers`. Rebinding must preserve:

- conditional `LEFT JOIN DocumentVersionIdentifiers dvi ON dvi.dv_id = dv.id`
- field-specific predicate generation on `dvi.<field>`
- continued JSON-text fallback for non-identifier fields

### 2. Standard media constraints must remain attached to the metadata query

The endpoints currently rely on this helper to combine metadata filters with:

- free-text matching against title / safe-metadata text
- media-type filtering
- `must_have_keywords` and `must_not_have_keywords`
- `date_start` / `date_end`

The existing SQLite and endpoint tests already pin these constraints, so the
helper extraction must keep that combined-query behavior unchanged.

### 3. Sorting must happen before pagination

The current tests already prove `title_asc` sorting before page slicing. That
is one of the easiest regressions if the query is rearranged during extraction.

### 4. Grouped count/results semantics must not drift

When `group_by_media=True`, count uses `COUNT(DISTINCT m.id)` and the result
query groups by `m.id`. When false, count uses `COUNT(*)` and results are not
grouped. This needs direct coverage in the helper tests because it is the
public behavioral split of the method.

## Recommended Tranche

Move only:

- `search_by_safe_metadata(...)`

Defer:

- `rollback_to_version(...)`
- `initialize_db(...)`
- `_initialize_schema*` / postgres bootstrap coordinators

## Design

Add one package-owned runtime module:

- `tldw_Server_API/app/core/DB_Management/media_db/runtime/safe_metadata_search_ops.py`

It should expose:

- `search_by_safe_metadata(...)`

Then:

- rebind canonical `MediaDatabase.search_by_safe_metadata` in
  [media_database_impl.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py)
- convert the legacy method in
  [Media_DB_v2.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/DB_Management/Media_DB_v2.py)
  into a live-module compat shell

This tranche should not touch the listing endpoints or identifier normalization
logic beyond preserving the existing helper contract.

## Test Strategy

### Direct regressions

Add ownership/delegation regressions in
[test_media_db_v2_regressions.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py)
for:

- canonical `MediaDatabase.search_by_safe_metadata(...)` no longer using legacy
  globals
- legacy `Media_DB_v2.search_by_safe_metadata(...)` delegating through
  `safe_metadata_search_ops.py`

### Focused helper coverage

Add:

- `tldw_Server_API/tests/DB_Management/test_media_db_safe_metadata_search_ops.py`

Pin:

- canonical helper rebinding
- identifier-filter join behavior
- JSON fallback behavior for non-identifier fields
- grouped vs ungrouped count/result query shapes
- early zero-result fast return
- sorting and pagination parameter placement
- read-only error wrapping to `DatabaseError`

### Broader caller-facing guards

Reuse existing coverage:

- [test_sqlite_db.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/MediaDB2/test_sqlite_db.py)
- [test_safe_metadata_endpoints.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/MediaDB2/test_safe_metadata_endpoints.py)
- [test_metadata_endpoints_more.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/MediaDB2/test_metadata_endpoints_more.py)

## Success Criteria

- canonical ownership for `search_by_safe_metadata(...)` moves off legacy
  globals
- legacy method remains a live-module compat shell
- helper-path tests pass for join selection, query shape, and zero-result
  behavior
- broader endpoint and SQLite guards stay green
- normalized ownership count drops `18 -> 17`
