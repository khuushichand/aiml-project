# Media DB V2 Postgres TTS/Source-Hash Helper Rebinding Design

## Summary

Rebind `_ensure_postgres_tts_history` and `_ensure_postgres_source_hash_column`
onto package-owned schema helpers so the canonical `MediaDatabase` no longer
owns this remaining small PostgreSQL post-core ensure pair through legacy
globals, while preserving `Media_DB_v2` as a live-module compatibility shell.

## Scope

In scope:

- Add a package schema helper module for:
  - `_ensure_postgres_tts_history(...)`
  - `_ensure_postgres_source_hash_column(...)`
- Rebind canonical `MediaDatabase` methods for those two helpers
- Convert legacy `Media_DB_v2` methods into live-module compat shells
- Add direct ownership/delegation regressions
- Add focused helper-path tests asserting:
  - `tts_history` table creation still runs before the index set
  - all expected `tts_history` indexes are still emitted
  - source-hash ensure still emits the column add before the index creation

Out of scope:

- Changing `_postgres_migrate_to_v16(...)` or `_postgres_migrate_to_v20(...)`
- Changing TTS history CRUD behavior
- Changing source-hash query behavior
- Changing broader claims, collections, email-state, or RLS helpers

## Why This Slice

This is the smallest remaining Postgres post-core helper cluster. Both methods
are self-contained, already exercised indirectly by the rebounded migration-body
helpers for `v16` and `v20`, and they sit outside the wider claims/collections
domain surfaces that would expand the tranche unnecessarily.

## Risks

Low. The main invariants are statement order and keeping the current
best-effort warning-only behavior:

- `tts_history` table creation must still precede all index creation
- the six `tts_history` indexes must remain unchanged
- source-hash must still create the column before its index
- backend exceptions must remain warning-only

## Test Strategy

Add:

1. canonical ownership regressions for both methods
2. legacy compat-shell delegation regressions for both methods
3. focused helper-path tests for:
   - `_ensure_postgres_tts_history(...)` emitted SQL order
   - `_ensure_postgres_source_hash_column(...)` emitted SQL order
4. reuse existing `v16` / `v20` helper-path tests and bootstrap follow-up tests
   as broader guards

## Success Criteria

- canonical helper methods are package-owned
- legacy `Media_DB_v2` helper methods remain live-module compat shells
- focused helper-path tests pass
- existing `v16` / `v20` helper-path tests stay green
- normalized ownership count drops from `181` to `179`
