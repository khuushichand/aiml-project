# Media DB V2 SQLite Claims Extension Helper Rebinding Design

## Goal

Rebind `_ensure_sqlite_claims_extensions()` off `Media_DB_v2` so the canonical
`MediaDatabase` no longer owns this SQLite claims-extension repair helper
through the legacy module, while preserving the legacy compat shell and keeping
the helper behavior unchanged.

## Scope

In scope:
- `_ensure_sqlite_claims_extensions()`
- canonical rebinding in `media_database_impl.py`
- live-module compat shell in `Media_DB_v2.py`
- focused ownership/delegation regressions
- focused helper-path tests
- existing SQLite post-core bootstrap ordering guard

Out of scope:
- claims CRUD/query methods
- PostgreSQL claims helpers
- higher-level bootstrap coordinators
- claims monitoring APIs beyond the helper’s table/column/index repair work

## Current State

The remaining normalized legacy-owned canonical-method count is `185`.

This helper currently owns three bounded SQLite repair paths:
- bootstrap the full claims schema with `_CLAIMS_TABLE_SQL` when `Claims` does
  not exist
- patch missing review/cluster columns onto `Claims` when the table exists
- repair `claims_monitoring_events.delivered_at` and its delivery index

## Target Design

Add one package-owned schema module:
- `tldw_Server_API/app/core/DB_Management/media_db/schema/sqlite_claims_extensions.py`

It should own:
- `ensure_sqlite_claims_extensions(db, conn) -> None`

Then:
- rebind the canonical method in `media_database_impl.py`
- keep the legacy method in `Media_DB_v2.py` as a live-module compat shell

## Behavior Invariants

`ensure_sqlite_claims_extensions()` must preserve:
- initial `sqlite_master` probe for `Claims`
- immediate `_CLAIMS_TABLE_SQL` bootstrap and early return when `Claims` is
  absent
- `PRAGMA table_info(Claims)` introspection before column repair
- exact missing-column gating for:
  - `review_status`
  - `reviewer_id`
  - `review_group`
  - `reviewed_at`
  - `review_notes`
  - `review_version`
  - `review_reason_code`
  - `claim_cluster_id`
- re-run of `_CLAIMS_TABLE_SQL` after column repair
- `claims_monitoring_events.delivered_at` repair plus
  `idx_claims_monitoring_events_delivered`
- warning-only behavior on SQLite errors

## Tests

Add three layers of coverage:

1. Ownership and compat-shell regressions in
   `test_media_db_v2_regressions.py`
   - canonical `_ensure_sqlite_claims_extensions` is no longer legacy-owned
   - legacy method delegates through a live package module reference

2. Helper-path tests in `test_media_db_schema_bootstrap.py`
   - missing `Claims` table path executes `_CLAIMS_TABLE_SQL` and returns
   - existing `Claims` table path emits missing extension-column SQL, replays
     `_CLAIMS_TABLE_SQL`, and repairs `delivered_at` plus its index

3. Existing SQLite post-core ordering guard
   - `test_ensure_sqlite_post_core_structures_runs_followup_ensures`

## Success Criteria

- canonical `_ensure_sqlite_claims_extensions` is package-owned
- legacy `Media_DB_v2` method remains a callable compat shell
- focused helper tests pass
- existing SQLite post-core ordering guard stays green
- normalized ownership count drops `185 -> 184`
