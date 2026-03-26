# Media DB V2 Email Sync Backfill State Helper Rebinding Design

## Summary

Rebind the email sync-state and backfill-state helper layer onto a package-owned
runtime module so the canonical `MediaDatabase` no longer owns those methods
through legacy globals. Preserve the existing instance-method contracts used by
the connectors worker and email API, while explicitly deferring tenant
resolution and the batch/worker coordinators that sit above this state layer.

## Scope

In scope:
- `_resolve_email_sync_source_row_id(...)`
- `_fetch_email_sync_state_row(...)`
- `get_email_sync_state(...)`
- `mark_email_sync_run_started(...)`
- `mark_email_sync_run_succeeded(...)`
- `mark_email_sync_run_failed(...)`
- `_fetch_email_backfill_state_row(...)`
- `_ensure_email_backfill_state_row(...)`
- `get_email_legacy_backfill_state(...)`
- `_update_email_backfill_progress(...)`
- direct ownership and compat-shell delegation regressions
- focused helper-path tests for sync-state and backfill-state semantics
- reuse of broader email-native and connector-facing guards

Out of scope:
- `_resolve_email_tenant_id(...)`
- `run_email_legacy_backfill_batch(...)`
- `run_email_legacy_backfill_worker(...)`
- `upsert_email_message_graph(...)`
- `apply_email_label_delta(...)`
- `reconcile_email_message_state(...)`
- `search_email_messages(...)`
- `get_email_message_detail(...)`
- `enforce_email_retention_policy(...)`
- `hard_delete_email_tenant_data(...)`

## Why This Slice

This is the cleanest remaining non-claims, non-bootstrap cluster because the
methods form one coherent state-management layer:
- sync-source lookup and sync-state persistence
- backfill-state lookup and progress persistence
- public reader/writer entrypoints already used by worker and API callers

It is also well covered already:
- [test_email_native_stage1.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_email_native_stage1.py)
  exercises sync-state roundtrips and backfill resumability
- [test_policy_and_connectors.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/External_Sources/test_policy_and_connectors.py)
  pins the connectors worker’s `get_email_sync_state(...)` and
  `mark_email_sync_run_*` contracts
- [email.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/api/v1/endpoints/email.py)
  still consumes `get_email_sync_state(...)` through the DB instance seam

By contrast, `_resolve_email_tenant_id(...)` is shared across nearly the entire
remaining email domain, and `run_email_legacy_backfill_batch(...)` /
`run_email_legacy_backfill_worker(...)` are coordinator methods rather than
state helpers. Pulling either into this slice would widen the blast radius.

## Existing Risks To Preserve

### 1. Worker-facing sync-state methods must preserve their instance contracts

The connectors worker only checks for and calls instance methods:
- `get_email_sync_state(...)`
- `mark_email_sync_run_started(...)`
- `mark_email_sync_run_succeeded(...)`
- `mark_email_sync_run_failed(...)`

This tranche must preserve those names, signatures, and return shapes while
moving canonical ownership off legacy globals.

### 2. `get_email_sync_state(...)` must remain a read-only lookup when the source is absent

The method currently resolves a source row without creating it and returns
`None` when no source exists. That behavior is part of the worker/API contract
and must not change.

### 3. Sync-state retry and cursor semantics must stay intact

The current behavior is:
- `mark_email_sync_run_started(...)` creates or updates a state row and clears
  errors while preserving a normalized cursor
- `mark_email_sync_run_failed(...)` increments `retry_backoff_count`
- `mark_email_sync_run_succeeded(...)` resets retries, clears error state, and
  preserves the prior cursor when a new cursor is not supplied

Those semantics are already covered in
[test_email_native_stage1.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_email_native_stage1.py#L134)
and must remain unchanged.

### 4. Backfill-state progress updates must preserve counters and conditional `last_error`

`_update_email_backfill_progress(...)` increments multiple counters and only
overwrites `last_error` when a non-empty error string is supplied. That is the
highest-risk internal behavior in this helper cluster and needs a focused test
of its own.

### 5. Backfill coordinators stay legacy-owned in this tranche

`run_email_legacy_backfill_batch(...)` and `run_email_legacy_backfill_worker(...)`
should keep calling the rebound helper methods through the DB instance. This
slice is only moving the state layer underneath them.

## Test Strategy

### Ownership / compat-shell regressions

Add direct regressions in
`tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py` for:
- canonical ownership moved off legacy globals for the 10 in-scope methods
- legacy `Media_DB_v2` methods delegating through a live `import_module(...)`
  reference

Keep the delegation checks especially explicit for the four worker-facing
public methods and the two backfill-state public entrypoints.

### Focused helper-path tests

Add a new helper test file for the runtime module covering:
- `_resolve_email_sync_source_row_id(...)` returning `None` when
  `create_if_missing=False` and the source row is absent, then creating and
  returning an id when `create_if_missing=True`
- sync-state start/fail/succeed roundtrip semantics, including retry reset and
  cursor preservation
- `_update_email_backfill_progress(...)` incrementing counters correctly and
  only replacing `last_error` when a non-empty error is provided
- `get_email_legacy_backfill_state(...)` returning normalized state rows after
  helper-driven updates

### Broader caller-facing guards

Retain and reuse:
- [test_email_native_stage1.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_email_native_stage1.py)
- [test_policy_and_connectors.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/External_Sources/test_policy_and_connectors.py)
- [test_email_search_endpoint.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/MediaIngestion_NEW/integration/test_email_search_endpoint.py)

The endpoint and worker tests are compatibility guards, not the primary proof
of canonical rebinding.

## Implementation Shape

Add one package runtime module, likely:
- `tldw_Server_API/app/core/DB_Management/media_db/runtime/email_state_ops.py`

It should own the 10 in-scope methods only.

Behavior requirements:
- do not change `_resolve_email_tenant_id(...)`
- keep sync-state and backfill-state SQL/return semantics identical
- keep batch/worker methods in `Media_DB_v2.py` unchanged except that they will
  now call rebound helpers through the DB instance

Then:
- rebind the canonical methods in `media_database_impl.py`
- convert the legacy methods in `Media_DB_v2.py` into live-module compat shells

## Success Criteria

- canonical ownership for the 10 in-scope methods moves off legacy globals
- all legacy methods remain present as live-module compat shells
- focused helper-path tests pass
- broader email-native and connectors-worker guards stay green
- normalized ownership count drops from `114` to `104`
