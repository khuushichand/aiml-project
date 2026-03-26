# Media DB V2 Claims Write Helper Rebinding Design

## Summary

After the `search_claims(...)` tranche, the normalized legacy ownership count is
`26`. The next clean adjacent claims-specific seam is the remaining write layer:

- `upsert_claims(...)`
- `update_claim(...)`
- `update_claim_review(...)`
- `soft_delete_claims_for_media(...)`

These four methods still own the direct mutation path for claims rows, review
state, and claim soft-delete cleanup. They are materially narrower than the
remaining bootstrap, keyword, safe-metadata, and rollback surfaces, and they
form a coherent write-helper tranche.

## Current Method Shape

`upsert_claims(...)` currently owns:

- empty-input fast return
- default timestamp generation
- per-row normalization for typed claim payload fields
- default extractor / extractor_version / uuid / client_id shaping
- bulk insert row assembly
- transactional `execute_many(...)`

`update_claim(...)` currently owns:

- selective field update assembly
- no-op fast return through `get_claim_with_media(...)`
- version bump / `last_modified` / `client_id` mutation
- PostgreSQL `claims_fts_tsv` refresh when `claim_text` changes
- final updated-row readback

`update_claim_review(...)` currently owns:

- optimistic-lock conflict detection via `review_version`
- review-field mutation assembly
- optional corrected-text writeback into `claim_text`
- review timestamps and review-version increment
- PostgreSQL `claims_fts_tsv` refresh on corrected text
- append-only insert into `claims_review_log`
- final updated-row readback

`soft_delete_claims_for_media(...)` currently owns:

- transactional soft-delete by `media_id`
- version / `last_modified` / `client_id` mutation
- SQLite-only best-effort `claims_fts` delete trigger emulation
- rowcount return
- sqlite-error wrapping into `DatabaseError`

## Why This Slice Is Safe

The caller surface is active and coherent:

- ingestion and rebuild flows:
  [ingestion_claims.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/Claims_Extraction/ingestion_claims.py)
  and
  [claims_rebuild_service.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/Claims_Extraction/claims_rebuild_service.py)
- claims service write paths:
  [claims_service.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/Claims_Extraction/claims_service.py)
- FTS and downstream retrieval guards:
  [test_claims_fts_triggers.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_claims_fts_triggers.py)
  and
  [test_claims_retriever.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/RAG/test_claims_retriever.py)

This slice gives real ownership reduction while staying under the already-moved
claims read/search helpers. It does not need to widen into cluster rebuild,
monitoring, bootstrap, or query logic.

## Risks To Pin

### 1. `upsert_claims(...)` defaults and bulk shaping

Despite the name, `upsert_claims(...)` is a Stage 1 bulk insert helper. A
rebinding bug can silently change default extractor values, UUID generation, or
timestamp/client identity shaping while still inserting rows.

Focused helper tests must pin:

- empty-input returns `0`
- default extractor / extractor_version / client_id shaping
- generated UUID and timestamp fallback behavior
- returned insert count equals inserted row count

### 2. `update_claim(...)` version and FTS refresh behavior

`update_claim(...)` is the narrow claim-edit path. It must preserve the
no-op fast return, version bump semantics, and PostgreSQL `claims_fts_tsv`
refresh only when `claim_text` changes.

Focused helper tests must pin:

- no-op update returns the current row through `get_claim_with_media(...)`
- real updates bump `version`, stamp `last_modified`, and write `client_id`
- PostgreSQL branch issues the `claims_fts_tsv` refresh only for text changes

### 3. `update_claim_review(...)` conflict and audit-log behavior

This is the highest-risk method in the slice. It mixes optimistic locking,
claim-text correction, review-version mutation, and audit logging.

Focused helper tests must pin:

- optimistic-lock conflicts return `{"conflict": True, "current": ...}`
- corrected-text updates also bump `version` and refresh PostgreSQL FTS
- successful review writes append to `claims_review_log`
- no-op input returns the original row without spurious updates

### 4. `soft_delete_claims_for_media(...)` SQLite FTS cleanup

SQLite still relies on the best-effort `claims_fts` delete insertion path.
Rebinding must preserve that behavior while keeping PostgreSQL free of the
SQLite cleanup branch.

Focused helper tests must pin:

- affected-row count propagation
- SQLite branch emits the `claims_fts(claims_fts, rowid, claim_text)` delete
  statement
- PostgreSQL branch skips the SQLite FTS cleanup path

## Recommended Tranche

Move only:

- `upsert_claims(...)`
- `update_claim(...)`
- `update_claim_review(...)`
- `soft_delete_claims_for_media(...)`

Defer:

- `replace_data_table_contents(...)`
- `search_by_safe_metadata(...)`
- `rollback_to_version(...)`
- bootstrap / postgres schema coordinators
- keyword helpers
- synced document update helpers

## Design

Add a package-owned runtime module:

- `tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_write_ops.py`

That module should expose:

- `upsert_claims(self, claims)`
- `update_claim(self, claim_id, *, ...)`
- `update_claim_review(self, claim_id, *, ...)`
- `soft_delete_claims_for_media(self, media_id)`

Then:

- rebind the canonical `MediaDatabase` methods in
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
- legacy `Media_DB_v2` methods delegating through `claims_write_ops.py`

### Focused helper coverage

Add a dedicated helper test file:

- `tldw_Server_API/tests/DB_Management/test_media_db_claims_write_ops.py`

Pin:

- `upsert_claims(...)` defaults and row-count behavior
- `update_claim(...)` no-op and PostgreSQL FTS-refresh behavior
- `update_claim_review(...)` conflict path, corrected-text path, and
  `claims_review_log` insertion
- `soft_delete_claims_for_media(...)` SQLite cleanup and PostgreSQL no-cleanup
  behavior

### Broader guards

Reuse caller-facing coverage from:

- [test_claims_review_api.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_review_api.py)
- [test_claims_review_metrics_api.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_review_metrics_api.py)
- [test_claims_dashboard_analytics.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_dashboard_analytics.py)
- [test_claims_fts_triggers.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_claims_fts_triggers.py)
- [test_media_add_endpoint.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/MediaIngestion_NEW/integration/test_media_add_endpoint.py)

## Success Criteria

- canonical claims write methods are package-owned
- legacy `Media_DB_v2` write methods are live-module compat shells
- focused helper tests pin write defaults, conflicts, audit-log behavior, and
  SQLite/PostgreSQL FTS side effects
- broader claims write / review / ingestion guards stay green
- normalized ownership count drops `26 -> 22`
