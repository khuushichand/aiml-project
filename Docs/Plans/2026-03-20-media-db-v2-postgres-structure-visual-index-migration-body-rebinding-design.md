# Media DB v2 Postgres Structure/Visual Index Migration Body Rebinding Design

Date: 2026-03-20
Branch: `codex/media-db-v2-stage1-caller-first`

## Summary

Extract PostgreSQL migration body `v21` from legacy canonical-method ownership while
preserving the `Media_DB_v2` compat shell.

This tranche is a real ownership-reduction slice for exactly one migration body:
`_postgres_migrate_to_v21`.

## Why This Slice

`_postgres_migrate_to_v21` is the next adjacent migration body after the recently
completed `v16`, `v18`, `v19`, and `v20` rebinding work. Unlike those single-helper
methods, `v21` contains inline backend-driven index creation logic for:

- `DocumentStructureIndex` / `documentstructureindex`
- `VisualDocuments` / `visualdocuments`

That makes it wider than the recent thin-delegate slices, but still bounded enough
to extract as one method without pulling broader bootstrap or domain setup into the
same task.

## In Scope

- Add a package-owned helper module for `v21`
- Rebind canonical `MediaDatabase._postgres_migrate_to_v21` in
  `media_database_impl.py`
- Keep `Media_DB_v2._postgres_migrate_to_v21` as a live-module compat shell
- Add direct ownership and delegation regressions
- Add focused helper behavior coverage for the package helper
- Add one dedicated Postgres migration-path test that proves the `v21` indexes are
  restored after downgrade

## Out of Scope

- Any changes to `migrations.py`
- Any changes to `_ensure_postgres_fts`, `_ensure_postgres_rls`,
  `_ensure_postgres_tts_history`, or other migration helpers
- Any broader bootstrap extraction
- Any changes to `v22`

## Design

### Helper Module

Add a new package-owned migration-body helper module:

- `media_db/schema/migration_bodies/postgres_structure_visual_indexes.py`

The helper will expose:

- `run_postgres_migrate_to_v21(db, conn)`

Its behavior should mirror the existing legacy method exactly:

1. Use `db.backend`
2. Use `backend.escape_identifier`
3. Detect lowercase/uppercase table names via `backend.table_exists(..., connection=conn)`
4. Create the structure index only if the structure table exists
5. Create the visual caption/tag indexes only if the visual table exists

No SQL or branching behavior should be changed in this tranche.

### Canonical Rebinding

Rebind only the canonical class method in `media_database_impl.py`:

- `MediaDatabase._postgres_migrate_to_v21 = run_postgres_migrate_to_v21`

This is what reduces normalized legacy-owned canonical-method count by 1.

### Legacy Compat Shell

Keep `Media_DB_v2._postgres_migrate_to_v21` present, but convert it into a
live-module compat shell using `import_module(...)`, following the same pattern
used for `v12`, `v13`, `v16`, `v18`, `v19`, and `v20`.

That preserves the legacy import and monkeypatch seam without leaving runtime
ownership on the legacy canonical class.

## Tests

### Direct Regressions

Add to `test_media_db_v2_regressions.py`:

- canonical `MediaDatabase._postgres_migrate_to_v21` no longer uses legacy globals
- legacy `Media_DB_v2._postgres_migrate_to_v21` delegates through the package helper

### Focused Helper Behavior

Add a unit test to `test_media_db_schema_bootstrap.py` that proves
`run_postgres_migrate_to_v21(db, conn)`:

- checks structure-table existence
- checks visual-table existence
- emits structure index SQL when the structure table exists
- emits visual caption/tag index SQL when the visual table exists

This should be a backend-stub test, not a full integration test.

### Migration-Path Guard

Add one dedicated integration test to `test_media_postgres_migrations.py`:

- downgrade schema version to `20`
- drop `idx_dsi_media_path`, `idx_visualdocs_caption`, and `idx_visualdocs_tags`
- run `db._initialize_schema()`
- assert all three indexes exist again

This is required because current broad Postgres migration coverage reaches `v20`
but does not isolate `v21`.

## Success Criteria

- `MediaDatabase._postgres_migrate_to_v21` is package-owned
- `Media_DB_v2._postgres_migrate_to_v21` remains a compat shell
- focused helper behavior test passes
- dedicated Postgres `v21` migration-path test passes
- broader Postgres support/migration/regression bundle stays green
- normalized ownership count drops by `1`

Expected ownership delta:

- `219 -> 218`

## Risks

### Case-sensitive table detection

The helper must preserve the current lowercase/uppercase table probing exactly.
If that is simplified incorrectly, the migration may skip index creation on one
of the supported naming variants.

### False-positive integration coverage

If the migration-path test does not explicitly drop the `v21` indexes first, the
test can pass without proving that `v21` restored them.

### Behavior drift

This tranche must preserve the exact SQL/index naming currently used by the
legacy method. Any cleanup of SQL formatting or identifier strategy belongs in a
later hardening slice.
