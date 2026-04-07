# Media DB V2 Bootstrap Lifecycle Helper Rebinding Design

**Date:** 2026-03-22
**Status:** Proposed
**Target Area:** `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
**Target Ownership Count:** `4 -> 1`

## Objective

Move the final bootstrap lifecycle trio off the legacy `Media_DB_v2` module:

- `__init__(...)`
- `_ensure_sqlite_backend(...)`
- `initialize_db(...)`

This leaves `rollback_to_version(...)` as the only remaining legacy-owned
method so it can be handled as an isolated final mutation tranche.

## Why This Slice

After the core-media schema tranche, the remaining legacy-owned surface is:

- `__init__(...)`
- `_ensure_sqlite_backend(...)`
- `initialize_db(...)`
- `rollback_to_version(...)`

`rollback_to_version(...)` is still a live high-blast-radius mutation
coordinator with API, DB-manager, FTS, document-version, and sync-log effects.
It should remain isolated.

The other three methods form one coherent bootstrap lifecycle slice:

1. `__init__(...)` constructs the DB object, resolves backend/runtime state,
   creates in-memory SQLite persistence when needed, and calls
   `_initialize_schema()`.
2. `initialize_db(...)` is the public compatibility wrapper still used across a
   broad caller surface and by `managed_media_database(...)`.
3. `_ensure_sqlite_backend(...)` is now effectively a compatibility no-op and
   belongs with the bootstrap lifecycle surface, not with rollback.

Crucially, the constructor no longer depends on remaining legacy-owned helpers:

- `_resolve_backend(...)` is already package-owned
- `_initialize_schema(...)` is already package-owned
- `close_connection(...)` is already package-owned
- `_apply_sqlite_connection_pragmas(...)` is already package-owned

That makes this trio the clean next ownership cut.

## Current State

### `__init__(...)`

The legacy constructor currently owns:

1. input validation for `db_path` and `client_id`
2. memory/file path normalization
3. parent-directory creation for file DBs
4. backend resolution and backend-type initialization
5. transaction/persistent-connection contextvar setup
6. persistent SQLite in-memory connection creation plus pragma application
7. `_media_insert_lock` and `_scope_cache` initialization
8. initialization failure cleanup via `close_connection()`
9. wrapping bootstrap failures into `DatabaseError`

### `initialize_db(...)`

This is an active compatibility wrapper:

1. re-runs `_initialize_schema()`
2. wraps failures into `DatabaseError`
3. returns `self`

It is used heavily by tests and through `media_db/api.py` lifecycle helpers.

### `_ensure_sqlite_backend(...)`

This method is now intentionally trivial:

1. if the backend is not SQLite, return
2. otherwise no-op

It still matters because it remains a canonical method inherited from the
legacy module.

## Proposed Design

Add one package-owned runtime helper module:

- `tldw_Server_API/app/core/DB_Management/media_db/runtime/bootstrap_lifecycle_ops.py`

It should own:

- `initialize_media_database(...)` for constructor logic
- `initialize_db(...)` for the compatibility wrapper
- `_ensure_sqlite_backend(...)` for the no-op compatibility seam

Then:

1. rebind canonical `MediaDatabase.__init__`,
   `MediaDatabase.initialize_db`, and
   `MediaDatabase._ensure_sqlite_backend` in
   `media_db/media_database_impl.py`
2. convert the legacy methods in `Media_DB_v2.py` into live-module compat
   shells that delegate through `import_module(...)`

No changes should be made to:

- `media_db/api.py`
- `media_db/runtime/validation.py`
- rollback logic

## Invariants To Preserve

### Constructor invariants

`__init__(...)` must preserve:

1. empty-string `db_path` rejection
2. `client_id` validation
3. `is_memory_db`, `db_path`, and `db_path_str` normalization
4. parent-directory creation for file-backed DBs
5. backend resolution via package-owned `_resolve_backend(...)`
6. creation of a persistent SQLite in-memory connection when appropriate
7. calling `_apply_sqlite_connection_pragmas(...)` on that persistent
   connection
8. initialization of `_txn_conn_var`, `_tx_depth_var`, `_persistent_conn_var`,
   `_media_insert_lock`, and `_scope_cache`
9. exactly one `_initialize_schema()` call
10. failure cleanup via `close_connection()` before re-raising
11. wrapping bootstrap failures into `DatabaseError`

### Compatibility-wrapper invariants

`initialize_db(...)` must preserve:

1. idempotent `_initialize_schema()` revalidation
2. `DatabaseError` wrapping semantics
3. `return self`

### SQLite-backend helper invariant

`_ensure_sqlite_backend(...)` must remain a harmless compatibility no-op for
SQLite and non-SQLite backends.

## Explicit Deferrals

Out of scope for this tranche:

- `rollback_to_version(...)`

That final method should remain a dedicated follow-up tranche because it is an
active mutation coordinator with caller-facing API coverage.

## Test Strategy

### New focused tests

Add a dedicated helper-path file:

- `tldw_Server_API/tests/DB_Management/test_media_db_bootstrap_lifecycle_ops.py`

Pin:

1. canonical rebinding for `__init__`, `initialize_db`, and
   `_ensure_sqlite_backend`
2. explicit-backend constructor path still calls `_initialize_schema()` once
3. in-memory SQLite constructor still creates a persistent connection and
   routes through `_apply_sqlite_connection_pragmas(...)`
4. constructor failure still calls `close_connection()` before raising
5. `initialize_db(...)` still returns `self` and re-wraps errors
6. `_ensure_sqlite_backend(...)` still returns harmlessly for both backend
   modes

### Ownership/delegation regressions

Extend:

- `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

Pin:

1. canonical methods no longer resolve globals from `Media_DB_v2`
2. legacy methods delegate through live-module imports to
   `bootstrap_lifecycle_ops.py`

### Broader guards

Keep broader caller compatibility green through:

- `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`
- `tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py`

## Risks

### Risk 1: Constructor lifecycle drift

Moving `__init__(...)` is riskier than the prior thin-wrapper slices because it
owns object creation, backend resolution, in-memory connection setup, and
failure cleanup.

Mitigation:

- direct helper-path tests for explicit backend, memory SQLite, and failure
  cleanup

### Risk 2: Breaking managed lifecycle callers

`initialize_db(...)` participates in the `managed_media_database(...)` contract
and broad test setup code.

Mitigation:

- direct helper test for `return self` and error wrapping
- broader import/API guard slice

### Risk 3: Widening into rollback

It would be easy to treat “final four methods” as one last cleanup tranche, but
that would mix object lifecycle with an active mutation coordinator.

Mitigation:

- keep `rollback_to_version(...)` explicitly out of scope

## Success Criteria

1. Canonical ownership for `__init__(...)`, `initialize_db(...)`, and
   `_ensure_sqlite_backend(...)` moves into
   `runtime/bootstrap_lifecycle_ops.py`
2. Legacy methods become compat shells only
3. Focused helper tests and ownership regressions pass
4. Lifecycle caller guards stay green
5. Normalized ownership count drops from `4` to `1`
