# Media DB V2 Postgres Sequence-Sync Helper Rebinding Design

## Summary

Rebind `_sync_postgres_sequences` onto a package-owned helper so the canonical
`MediaDatabase` no longer owns that PostgreSQL helper through legacy globals,
while preserving `Media_DB_v2` as a live-module compatibility shell and keeping
the existing `v18` migration-body helper untouched.

## Scope

In scope:

- Add a package helper module for `sync_postgres_sequences(...)`
- Rebind canonical `MediaDatabase._sync_postgres_sequences`
- Convert legacy `Media_DB_v2._sync_postgres_sequences` into a live-module
  compat shell
- Add direct ownership/delegation regressions
- Add focused helper-path tests for:
  - skipping incomplete sequence metadata rows
  - coercing invalid `MAX(...)` results to `0`
  - `setval(..., 1, false)` for empty/non-positive branches
  - `setval(..., max_id)` for positive branches
- Reuse the existing integration guard for sequence repair after bootstrap

Out of scope:

- Changing `_postgres_migrate_to_v18`
- Changing the migration registry/runner
- Changing `_update_schema_version_postgres`
- Changing backend escape or execution primitives

## Why This Slice

`_sync_postgres_sequences` is the next narrow PostgreSQL-specific helper after
`_update_schema_version_postgres`. It already has an integration guard in the
Postgres migration suite, but it is still canonical legacy-owned and lacks
direct helper-path tests for its highest-risk branches.

## Risks

Low to moderate. The helper is compact, but it contains ordered behavior that
must stay exact:

- rows missing table/column/sequence names must be skipped
- invalid `scalar` values must fall back to `0`
- empty/non-positive maxima must call `SELECT setval(%s, %s, false)` with `1`
- positive maxima must call `SELECT setval(%s, %s)` with the observed maximum
- identifier escaping must still flow through `backend.escape_identifier`

## Test Strategy

Add:

1. canonical ownership regression
2. legacy compat-shell delegation regression
3. helper-path unit tests for skip, fallback, non-positive, and positive
   branches
4. existing `test_media_postgres_sequence_sync` integration guard as the broader
   verification path

## Success Criteria

- canonical `_sync_postgres_sequences` is package-owned
- legacy `Media_DB_v2._sync_postgres_sequences` remains a live-module compat
  shell
- helper-path tests pass for all algorithm branches
- existing integration guard stays green
- normalized ownership count drops from `206` to `205`
