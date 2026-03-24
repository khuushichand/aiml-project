# Media DB V2 Execution Helper Rebinding Design

**Status:** Proposed, review-corrected, and approved for tranche planning on 2026-03-19.

**Goal:** Rebind the Media DB execution helper surface to a package-native
runtime module without breaking SQLite ephemeral cleanup, sync-trigger error
handling, PostgreSQL helper behavior, or the existing legacy monkeypatch seams
used by the regression suite.

## Why This Tranche Exists

The previous connection-lifecycle tranche moved these methods off
`Media_DB_v2.py`:

- `_get_txn_conn`
- `_set_txn_conn`
- `_get_tx_depth`
- `_set_tx_depth`
- `_inc_tx_depth`
- `_dec_tx_depth`
- `_get_persistent_conn`
- `_set_persistent_conn`
- `get_connection`
- `close_connection`
- `release_context_connection`

That reduced the normalized legacy-owned method count from `243` to `232`
without changing constructor or query-execution behavior.

The next adjacent low-risk cluster is the execution-helper layer:

- `_execute_with_connection`
- `_executemany_with_connection`
- `_fetchone_with_connection`
- `_fetchall_with_connection`
- `execute_query`
- `execute_many`

These methods are more behavior-sensitive than the previous lifecycle slice,
but they are still cohesive enough to move together if the existing seams are
preserved explicitly.

## Review Corrections Incorporated

### 1. Preserve the legacy `sqlite3.connect` patch seam

The current cleanup regression at
[test_media_db_connection_cleanup.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_connection_cleanup.py)
patches `Media_DB_v2.sqlite3.connect`.

Today, `execute_query()` and `execute_many()` read `sqlite3.connect` from the
legacy module globals in `Media_DB_v2.py`. If the extracted runtime module
imports `sqlite3` directly, those cleanup tests will stop exercising the same
branch even if behavior happens to remain similar.

This tranche therefore preserves the legacy patch seam instead of rewriting the
tests:

- the runtime execution module should route ephemeral SQLite connection
  creation through a compat helper imported from `Media_DB_v2`, or
- otherwise preserve an equivalent shell-level indirection that the current
  tests can still patch

This is ownership extraction, not a test-contract rewrite.

### 2. Keep statement-prep and parameter-normalization helpers out of scope

The following helpers sit nearby but should not move in this tranche:

- `_prepare_backend_statement`
- `_prepare_backend_many_statement`
- `_normalise_params`

They already have focused backend-utils coverage and are used by more than just
the execution helpers. The execution methods should continue calling them
through `self`, which preserves the current seams and keeps this slice narrow.

### 3. Keep query-builder helpers out of scope

These helpers also remain deferred:

- `_append_case_insensitive_like`
- `_keyword_order_expression`

They belong to the read/query-helper slice, not the execution-helper slice.

### 4. Move the execution helper surface as one cluster

Do not split `_execute_with_connection` / `_executemany_with_connection` /
`_fetchone_with_connection` / `_fetchall_with_connection` away from
`execute_query` / `execute_many`.

The broader regression surface already stubs these methods directly in several
Postgres-support tests, so splitting them would add transition churn without
reducing risk.

They move together.

### 5. Add missing focused regressions before the implementation move

Current coverage is strong for SQLite cleanup but thinner for two branches that
could regress during extraction:

- `execute_query()` re-raising sync-trigger `sqlite3.IntegrityError` unchanged
- `execute_many()` no-op and validation behavior

This tranche adds or extends narrow regressions for:

- sync-trigger passthrough in `execute_query`
- `execute_many([]) -> None`
- `execute_many(non_list)` raising the expected `TypeError` path

## In Scope

- Rebind these canonical methods into a package-native runtime module:
  - `_execute_with_connection`
  - `_executemany_with_connection`
  - `_fetchone_with_connection`
  - `_fetchall_with_connection`
  - `execute_query`
  - `execute_many`
- Preserve instance-call seams to:
  - `_prepare_backend_statement`
  - `_prepare_backend_many_statement`
  - `get_connection`
  - `_apply_sqlite_connection_pragmas`
- Preserve the legacy `sqlite3.connect` patch seam used by current cleanup
  tests.
- Add focused ownership and behavior regressions for the execution branches
  listed above.

## Out Of Scope

- `__init__`
- `_resolve_backend`
- `_ensure_sqlite_backend`
- `_prepare_backend_statement`
- `_prepare_backend_many_statement`
- `_normalise_params`
- `_append_case_insensitive_like`
- `_keyword_order_expression`
- schema initialization, migrations, and FTS setup
- caller migration
- changing the public error contract of `execute_query` or `execute_many`

## Architecture

### A. Add a package-native runtime execution module

Introduce a new module under `media_db.runtime`, for example:

- `tldw_Server_API/app/core/DB_Management/media_db/runtime/execution_ops.py`

That module becomes the canonical owner of the six methods in scope.

The implementations should stay method-shaped and continue to take `self`.

### B. Preserve current helper seams through instance methods

The moved implementations should continue to call through the existing instance
surface rather than importing lower-level helpers directly where that would
change seams.

Examples:

- `_execute_with_connection()` should still call
  `self._prepare_backend_statement(...)`
- `_executemany_with_connection()` should still call
  `self._prepare_backend_many_statement(...)`
- `_fetchone_with_connection()` and `_fetchall_with_connection()` should still
  go through `self._execute_with_connection(...)`
- `execute_query()` and `execute_many()` should still call
  `self.get_connection()` and `self._apply_sqlite_connection_pragmas(...)`

This keeps the extraction narrow and avoids dragging prep-helper ownership into
the same tranche.

### C. Preserve SQLite ephemeral behavior exactly

For SQLite, `execute_query()` and `execute_many()` currently own:

- ephemeral `sqlite3.connect(...)` creation when outside transactions and not
  using `:memory:`
- `row_factory = sqlite3.Row`
- pragma application through `_apply_sqlite_connection_pragmas`
- fetch behavior for `SELECT` and `RETURNING`
- auto-commit semantics for ephemeral connections
- cleanup via `close_sqlite_ephemeral(cur, eph)`
- error translation behavior

All of that remains identical in this tranche.

### D. Preserve PostgreSQL behavior exactly

For PostgreSQL, the moved methods must keep:

- `BackendCursorAdapter` wrapping
- `BackendDatabaseError -> DatabaseError` translation
- `commit=True` handling on an explicit connection
- helper-driven behavior used by existing Postgres-support tests

## Testing Strategy

### Ownership regressions

Extend `test_media_db_v2_regressions.py` with a parametrized ownership
regression for the six execution-helper methods, expecting their globals to
point at:

- `tldw_Server_API.app.core.DB_Management.media_db.runtime.execution_ops`

### Focused behavior regressions

Use and extend:

- [test_media_db_connection_cleanup.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_connection_cleanup.py)
  for ephemeral-close-on-error behavior
- add a regression for `sync error` passthrough in `execute_query()`
- add a regression for `execute_many([]) is None`
- add a regression for non-list `params_list` raising the wrapped `TypeError`
  path expected by the current public behavior

### Postgres helper regressions

Reuse the existing helper-driven coverage in
[test_media_postgres_support.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_postgres_support.py)
for:

- `_execute_with_connection`
- `_executemany_with_connection`
- `_fetchone_with_connection`
- `_fetchall_with_connection`
- `execute_many` helper delegation behavior

### Measurement

After implementation, rerun:

`python Helper_Scripts/checks/media_db_runtime_ownership_count.py`

The normalized count should drop by `6` for the six rebound methods in this
slice.

## Success Criteria

- The six execution-helper methods no longer resolve globals from
  `Media_DB_v2.py`.
- Existing SQLite cleanup tests still pass without changing their patch target.
- Sync-trigger integrity error passthrough remains intact.
- `execute_many()` validation/no-op behavior remains intact.
- Existing Postgres-support helper tests still pass.
- The normalized legacy-owned method count drops by `6`.
