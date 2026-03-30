# Media DB V2 Claims FTS Helper Rebinding Design

## Summary

Rebind `MediaDatabase.rebuild_claims_fts(...)` onto a package-owned runtime
helper while preserving backend-specific FTS rebuild behavior for both SQLite
and PostgreSQL. The legacy `Media_DB_v2` method remains as a live-module compat
shell.

## Scope

In scope:
- `rebuild_claims_fts(...)`
- canonical rebinding in
  `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`
- legacy compat-shell delegation in
  `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- direct ownership/delegation regressions
- focused helper-path tests for SQLite and PostgreSQL behavior

Out of scope:
- `search_claims(...)`
- `upsert_claims(...)`
- `soft_delete_claims_for_media(...)`
- `rebuild_claim_clusters_from_assignments(...)`
- claims FTS trigger/schema setup

## Current Behavior

`rebuild_claims_fts(...)` is a coordinator with backend-specific branches:

- SQLite:
  - clears `claims_fts` using `delete-all`
  - recreates the FTS table if that clear fails because the table is missing
  - reinserts rows from non-deleted claims
  - returns the indexed row count from `claims_fts`
- PostgreSQL:
  - asks the backend to create the FTS table metadata/wiring
  - refreshes `claims.claims_fts_tsv`
  - returns the count of non-deleted claims
- unsupported backends raise `NotImplementedError`
- SQLite and backend errors are normalized to `DatabaseError`

## Risks

### SQLite recreate path

The SQLite branch has a recovery path for a missing `claims_fts` table. If the
helper extraction loses that branch, existing local databases can fail to
recover after FTS damage or partial bootstrap drift.

### PostgreSQL backend seam

The PostgreSQL branch must continue calling `backend.create_fts_table(...)`
before refreshing `claims_fts_tsv`. That backend seam is already covered by the
support tests and should remain untouched.

### Service override path

`claims_service.rebuild_claims_fts(...)` uses the override DB helper in SQLite
admin-override flows. This tranche must not alter that caller-facing contract.

## Proposed Design

Add a runtime module:

- `tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_fts_ops.py`

Expose:

- `rebuild_claims_fts(self) -> int`

Implementation approach:

1. Lift the current `Media_DB_v2.rebuild_claims_fts(...)` body into the runtime
   module with behavior unchanged.
2. Rebind canonical `MediaDatabase.rebuild_claims_fts` to the package helper.
3. Convert the legacy method into a live `import_module(...)` compat shell.

## Test Strategy

### Direct regressions

Add ownership/delegation regressions proving:

- canonical `MediaDatabase.rebuild_claims_fts` no longer uses legacy globals
- legacy `_LegacyMediaDatabase.rebuild_claims_fts` delegates through the live
  runtime module

### Focused helper-path tests

Add a dedicated helper test module covering:

- canonical helper rebinding plus SQLite missing-table recovery
- direct PostgreSQL helper path using a lightweight backend stub

### Broader guards

Reuse existing caller-facing/support tests:

- `tldw_Server_API/tests/DB_Management/test_media_postgres_support.py`
- `tldw_Server_API/tests/Claims/test_claims_service_override_db.py`
- `tldw_Server_API/tests/RAG/test_dual_backend_end_to_end.py`

## Success Criteria

- normalized ownership count drops `33 -> 32`
- direct ownership/delegation regressions pass
- focused helper-path tests pass
- broader caller/support bundle stays green
- Bandit reports no new findings on touched production files
