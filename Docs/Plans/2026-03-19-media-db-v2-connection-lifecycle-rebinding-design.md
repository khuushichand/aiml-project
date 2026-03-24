# Media DB V2 Connection Lifecycle Rebinding Design

**Status:** Proposed, review-corrected, and approved for tranche-A planning on 2026-03-19.

**Goal:** Rebind the lowest-risk Media DB infrastructure methods that manage transaction-scoped and persistent connection lifecycle so the canonical `MediaDatabase` stops resolving that ownership through `Media_DB_v2.py`.

## Why This Tranche Exists

The normalized ownership counter now shows `243` canonical methods whose
function globals still point at `Media_DB_v2.py`.

Recent refactor work already removed several helper clusters from that legacy
host:

- bootstrap pragma ownership
- backup helpers
- chunk helper clusters
- multiple read/query helper clusters
- document/version/keyword helper delegates

What remains on the low-risk infrastructure side is the connection and
transaction lifecycle layer.

That layer is attractive because it is:

- cohesive
- already mechanically separated from most domain behavior
- valuable to remove before larger startup/bootstrap slices

It is also risky in a very specific way: some nearby helpers look
infrastructure-like but actually widen the blast radius into constructor,
query-building, or startup behavior.

This design keeps the tranche narrow enough to be safe.

## Review Corrections Incorporated

### 1. Defer `_resolve_backend` from the first plumbing slice

Although `_resolve_backend` sits near the connection methods, it is not just
plumbing. [Media_DB_v2.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/DB_Management/Media_DB_v2.py#L1317) calls it directly from `__init__`.

Rebinding `_resolve_backend` would therefore change object construction while
`__init__` itself remains legacy-owned. That makes it a constructor/bootstrap
change, not a simple lifecycle-ownership change.

This tranche keeps `_resolve_backend` out of scope.

### 2. Treat `execute_query` and `execute_many` as a separate behavior-sensitive slice

`execute_query` and `execute_many` look like connection plumbing, but they
also own:

- SQLite ephemeral connection lifecycle
- auto-commit behavior
- `DatabaseError` translation
- sync-trigger integrity error handling
- use of `_apply_sqlite_connection_pragmas`
- use of `self.get_connection()` and statement-prep seams

That is too much behavior to hide inside the first lifecycle move.

This tranche keeps `execute_query`, `execute_many`, `_execute_with_connection`,
`_executemany_with_connection`, `_fetchone_with_connection`, and
`_fetchall_with_connection` out of scope and reserves them for tranche-B.

### 3. Defer query-builder helpers to a later read/query slice

The following methods are still legacy-owned, but they are not connection
lifecycle methods:

- `_prepare_backend_statement`
- `_prepare_backend_many_statement`
- `_normalise_params`
- `_append_case_insensitive_like`
- `_keyword_order_expression`

They already have standalone backend-utils coverage and are used by broader
query surfaces such as search helpers. Moving them now would mix the lifecycle
slice with a read/query-helper slice.

They remain out of scope.

### 4. Preserve shell and instance seams already used by tests

The current regression suite does not heavily patch the lifecycle methods
themselves, but it does exercise their behavior through:

- PostgreSQL persistent connection reuse
- connection return behavior
- lifecycle cleanup paths
- class-level ownership assertions in `test_media_db_v2_regressions.py`

This tranche must preserve current instance-call behavior:

- `get_connection()` still consults transaction-local and persistent
  connection state the same way
- `close_connection()` and `release_context_connection()` still go through the
  pool-return path
- transaction-depth helpers remain simple wrappers around the existing
  `ContextVar` storage on `self`

The change is ownership, not semantics.

## In Scope

- Rebind these canonical `MediaDatabase` methods into a new package-native
  runtime module:
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
- Add ownership regression coverage proving those methods no longer resolve
  globals from `Media_DB_v2`.
- Verify behavior with the existing Postgres scope/persistent-connection tests
  and any targeted lifecycle regressions needed for this move.

## Out Of Scope

- `__init__`
- `_resolve_backend`
- `_ensure_sqlite_backend`
- `_prepare_backend_statement`
- `_prepare_backend_many_statement`
- `_normalise_params`
- `_append_case_insensitive_like`
- `_keyword_order_expression`
- `_execute_with_connection`
- `_executemany_with_connection`
- `_fetchone_with_connection`
- `_fetchall_with_connection`
- `execute_query`
- `execute_many`
- schema initialization, migrations, and FTS setup
- any caller migration work

## Method Cluster

The connection-lifecycle tranche is intentionally limited to two subgroups.

### A. Transaction-local state helpers

These methods are simple wrappers over the existing context-local storage on
the `MediaDatabase` instance:

- `_get_txn_conn`
- `_set_txn_conn`
- `_get_tx_depth`
- `_set_tx_depth`
- `_inc_tx_depth`
- `_dec_tx_depth`

They are the cleanest low-risk ownership move because they do not reach into
backend bootstrap or query construction logic.

### B. Persistent connection lifecycle helpers

These methods manage PostgreSQL persistent connection reuse and pool return
semantics outside explicit transactions:

- `_get_persistent_conn`
- `_set_persistent_conn`
- `get_connection`
- `close_connection`
- `release_context_connection`

They do interact with the backend pool and `apply_scope`, so they are more
behavior-sensitive than the transaction-depth helpers, but still isolated
enough to move as one coherent slice.

## Architecture

### A. Add a package-native runtime module for connection lifecycle

Introduce a dedicated runtime module under `media_db.runtime`, for example:

- `tldw_Server_API/app/core/DB_Management/media_db/runtime/connection_lifecycle.py`

It should export the tranche-A methods listed above.

The implementations should remain method-shaped functions taking `self`, just
like the earlier runtime wrapper modules.

### B. Rebind the canonical class in `media_database_impl.py`

`media_database_impl.py` should import the tranche-A runtime functions and
rebind the canonical class:

- `MediaDatabase._get_txn_conn = _get_txn_conn`
- `MediaDatabase._set_txn_conn = _set_txn_conn`
- ...
- `MediaDatabase.release_context_connection = release_context_connection`

That keeps the class identity unchanged while moving ownership away from
`Media_DB_v2.py`.

### C. Preserve existing semantics exactly

The runtime-owned methods should preserve:

- `ContextVar` usage on `self._txn_conn_var`, `self._tx_depth_var`, and
  `self._persistent_conn_var`
- SQLite memory-DB special handling in `get_connection`
- PostgreSQL persistent connection reuse
- `backend.apply_scope()` execution inside `get_connection`
- no-op behavior when closing inside a transaction
- pool-return semantics for `close_connection()` and
  `release_context_connection()`

This tranche should not introduce new abstractions or backend branches.

## Testing Strategy

### Ownership regressions

Extend `test_media_db_v2_regressions.py` with a targeted ownership assertion
covering the tranche-A methods and expecting their globals to point at:

- `tldw_Server_API.app.core.DB_Management.media_db.runtime.connection_lifecycle`

### Behavior regressions

Use existing focused tests as the main behavior guardrails:

- [test_media_db_connection_cleanup.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_connection_cleanup.py)
  for persistent-connection and cleanup semantics that touch `get_connection`
- any existing Postgres scope reuse tests that already validate
  `backend.apply_scope()` and persistent connection reuse

If a narrow gap appears, add only the smallest regression needed for:

- pool-return behavior on `close_connection()`
- no-op close behavior inside a transaction
- `release_context_connection()` remaining Postgres-only

### Measurement

After implementation, rerun:

`python Helper_Scripts/checks/media_db_runtime_ownership_count.py`

and confirm the normalized count drops by exactly the number of rebound
methods in this tranche.

## Success Criteria

- The tranche-A methods above no longer resolve globals from `Media_DB_v2.py`.
- Existing lifecycle semantics are unchanged.
- Constructor/bootstrap behavior is unchanged because `_resolve_backend` and
  `__init__` remain untouched.
- Query-builder and execution behavior are unchanged because those methods are
  deferred.
- The normalized legacy-owned method count drops by the tranche-A method count.
