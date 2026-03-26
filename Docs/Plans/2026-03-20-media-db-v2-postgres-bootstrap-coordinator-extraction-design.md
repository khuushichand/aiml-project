# Media DB V2 Postgres Bootstrap Coordinator Extraction Design

**Status:** Proposed, review-corrected, and ready for tranche planning on 2026-03-20.

**Goal:** Extract the real PostgreSQL schema bootstrap coordinator out of legacy
`Media_DB_v2` ownership without widening into migration-body or domain-helper
extraction.

## Why This Tranche Exists

The SQLite bootstrap bridge is now package-owned, but the PostgreSQL backend
bridge is still a direct pass-through in
[`schema/backends/postgres.py`](./../../tldw_Server_API/app/core/DB_Management/media_db/schema/backends/postgres.py).

At the same time, the PostgreSQL side is already partially decomposed:

- top-level dispatch is package-owned through
  [`ensure_media_schema`](./../../tldw_Server_API/app/core/DB_Management/media_db/schema/bootstrap.py)
- migration entrypoints already flow through
  [`schema/migrations.py`](./../../tldw_Server_API/app/core/DB_Management/media_db/schema/migrations.py)
- policy setup already flows through
  [`schema/features/policies.py`](./../../tldw_Server_API/app/core/DB_Management/media_db/schema/features/policies.py)

The real remaining coordinator ownership is concentrated in
[`Media_DB_v2._initialize_schema_postgres`](./../../tldw_Server_API/app/core/DB_Management/Media_DB_v2.py),
which still mixes:

- fresh-schema bootstrap
- migration dispatch
- duplicated post-bootstrap ensure work
- FTS, policy, email, data-table, claims, and sequence follow-up

That makes the next safe slice narrower than “Postgres migrations.” The right
target is the **Postgres bootstrap coordinator**.

## Review Corrections Incorporated

### 1. Do not extract migration bodies in this tranche

The migration registry and migration bodies are still live compatibility
surfaces:

- `_get_postgres_migrations()`
- `_run_postgres_migrations()`
- `_postgres_migrate_to_v*()`

Tests still bind to them directly, especially in
[`test_media_postgres_support.py`](./../../tldw_Server_API/tests/DB_Management/test_media_postgres_support.py).

This tranche keeps those surfaces intact and only changes the coordinator that
calls them.

### 2. Normalize the duplicated Postgres post-bootstrap ensure block first

`_initialize_schema_postgres()` currently duplicates a large follow-up ensure
block across the “schema already current” and “post-migration/fresh bootstrap”
paths, including:

- collections/content items
- tts history
- data tables
- source hash
- claims extensions
- email schema
- sequence sync
- policy setup

The collections/content-item part is especially wasteful because
[`_ensure_postgres_collections_tables`](./../../tldw_Server_API/app/core/DB_Management/Media_DB_v2.py)
already exists as a dedicated helper.

So the coordinator should first be normalized around a single
package-native `ensure_postgres_post_core_structures(...)` helper rather than
copying that duplication into a new module.

### 3. Preserve the bridge patch seam

The backend bridge in
[`schema/backends/postgres.py`](./../../tldw_Server_API/app/core/DB_Management/media_db/schema/backends/postgres.py)
should call a helper module through a live module reference, not through a
statically bound function import. That preserves the same low-churn monkeypatch
style we just established for SQLite.

### 4. Preserve runtime and validation invariants

This tranche must not change:

- `_CURRENT_SCHEMA_VERSION`
- runtime factory validation semantics
- `_postgres_policy_exists()` behavior
- migration reachability through existing wrapper helpers

The package coordinator should be a routing/normalization move, not a schema
behavior rewrite.

## In Scope

- package-native Postgres bootstrap coordinator
- package-native helper for the duplicated Postgres post-bootstrap ensure block
- backend bridge extraction in `schema/backends/postgres.py`
- delegating `Media_DB_v2._initialize_schema_postgres()` to the package
  coordinator
- bridge/coordinator ownership regressions and focused Postgres bootstrap tests

## Out Of Scope

- moving `_get_postgres_migrations()` out of `Media_DB_v2`
- moving `_run_postgres_migrations()` out of `Media_DB_v2`
- extracting any `_postgres_migrate_to_v*()` bodies
- claims/email/data-tables/FTS/RLS migration decomposition
- startup/runtime factory behavior changes unrelated to coordinator ownership

## Target Architecture

### A. Keep dispatch stable, replace the Postgres backend bridge

Keep:

- `ensure_media_schema(db)`
- `initialize_postgres_schema(db)` as the backend dispatch surface

Change:

- `initialize_postgres_schema(db)` should stop calling
  `db._initialize_schema_postgres()` directly
- it should instead call a package-native `bootstrap_postgres_schema(db)`

### B. Extract one package-native post-bootstrap ensure helper

Introduce a package-native helper that centralizes the duplicated coordinator
follow-up work:

- `_ensure_postgres_collections_tables(conn)`
- `_ensure_postgres_tts_history(conn)`
- `_ensure_postgres_data_tables(conn)`
- `_ensure_postgres_source_hash_column(conn)`
- `_ensure_postgres_claims_extensions(conn)`
- `_ensure_postgres_email_schema(conn)`
- `_sync_postgres_sequences(conn)`
- `ensure_postgres_policies(db, conn)`

This helper should replace the duplicated inline SQL and repeated ensure calls
inside `_initialize_schema_postgres()`.

### C. Keep migration dispatch and domain helpers as legacy leaves

The new coordinator may still temporarily call:

- `run_postgres_migrations(db, conn, current_version, target_version)`
- `apply_postgres_core_media_schema(db, conn)`
- `ensure_postgres_fts(db, conn)`
- legacy instance helpers for collections, email, claims, source hash, TTS, and
  sequence sync

That is acceptable for this tranche. The goal is coordinator ownership, not
full migration-body extraction.

## Risks

### 1. Broad Postgres test surface

Postgres bootstrap touches fresh schema creation, downgraded migration paths,
policy setup, and sequence sync. The coordinator move must therefore reuse the
existing focused test surface rather than introducing broad new integration
coverage.

### 2. Existing compatibility tests still expect legacy migration methods

Some tests intentionally assert on `_get_postgres_migrations()` and individual
legacy migration methods. The coordinator extraction must leave those entrypoints
available.

### 3. Inline collections SQL should not be copied again

If the new package coordinator simply copies the existing large inline block,
the ownership moves but the design debt remains. This tranche should normalize
around existing helper methods before extracting.

## Required Tests

- bridge ownership regressions in
  [`test_media_db_schema_bootstrap.py`](./../../tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py)
- existing migration behavior in
  [`test_media_postgres_migrations.py`](./../../tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py)
- existing support/compat behavior in
  [`test_media_postgres_support.py`](./../../tldw_Server_API/tests/DB_Management/test_media_postgres_support.py)
- runtime validation coverage in
  [`test_media_db_runtime_factory.py`](./../../tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py)

## Recommended Next Tranche

1. Add Postgres backend bridge ownership regressions.
2. Extract `ensure_postgres_post_core_structures(...)` into a package-native
   helper module using existing instance helper methods.
3. Introduce `bootstrap_postgres_schema(...)` in the same helper module.
4. Route `schema/backends/postgres.py` and
   `Media_DB_v2._initialize_schema_postgres()` through that helper.
5. Verify with the focused Postgres bootstrap/migration/runtime bundle.
