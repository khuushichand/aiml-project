# Media DB V2 Email Backfill Coordinator Rebinding Design

## Summary

Rebind the legacy email backfill coordinator pair onto a package-owned runtime
module so the canonical `MediaDatabase` no longer owns those methods through
legacy globals. Preserve resumable checkpointing, per-row progress updates,
worker stop semantics, and the existing upsert/delete seams while explicitly
deferring tenant resolution, metadata/source derivation helpers, and the
message-graph persistence layer.

## Scope

In scope:
- `run_email_legacy_backfill_batch(...)`
- `run_email_legacy_backfill_worker(...)`
- direct ownership and compat-shell delegation regressions
- focused helper-path tests for worker stop semantics and coordinator
  validation
- reuse of broader stage-1 email-native guards for resumability and idempotence

Out of scope:
- `_resolve_email_tenant_id(...)`
- `_normalize_email_backfill_key(...)`
- `_parse_email_backfill_safe_metadata(...)`
- `_derive_email_backfill_source_fields(...)`
- `_ensure_email_backfill_state_row(...)`
- `_fetch_email_backfill_state_row(...)`
- `_update_email_backfill_progress(...)`
- `upsert_email_message_graph(...)`
- `get_email_legacy_backfill_state(...)`
- the email query/mutation/retention layers already moved out of legacy

## Why This Slice

This is the cleanest remaining bounded email cluster because the two methods
form one coordinator layer:
- one resumable batch pass that loads legacy email `Media` rows, normalizes
  state, and advances the `(tenant_id, backfill_key)` checkpoint
- one worker loop that repeatedly calls the batch coordinator until completion
  or a bounded stop condition

It is already covered by strong caller-facing tests:
- [test_email_native_stage1.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_email_native_stage1.py)
  exercises resumability, idempotence, preexisting-row skipping, and worker
  completion semantics
- [email_legacy_backfill_runner.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/Helper_Scripts/checks/email_legacy_backfill_runner.py)
  is the production runner surface for the worker entrypoint
- [test_helper_script_media_db_imports.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Helper_Scripts/test_helper_script_media_db_imports.py)
  already guards the helper script’s package-facing import contract

By contrast, `_resolve_email_tenant_id(...)` is still a shared seam across the
remaining email surface, and `upsert_email_message_graph(...)` is a much wider
write-domain method with participant, label, attachment, and FTS behavior.
Mixing either into this slice would widen a coherent coordinator move into a
broader email-domain refactor.

## Existing Risks To Preserve

### 1. Batch progress semantics must remain resumable and idempotent

`run_email_legacy_backfill_batch(...)` currently:
- resolves `(tenant_id, backfill_key)` state
- resumes from `last_media_id`
- updates backfill progress after every scanned row
- finalizes state to `completed` or `completed_with_errors` when no work
  remains

That contract must stay intact. The package helper should not inline or
restructure the state-row helpers.

### 2. Per-row ingestion must keep routing through existing seams

The batch coordinator currently relies on instance seams for:
- `_parse_email_backfill_safe_metadata(...)`
- `_derive_email_backfill_source_fields(...)`
- `_collect_email_labels(...)`
- `upsert_email_message_graph(...)`
- `_update_email_backfill_progress(...)`

Those seams should remain instance-routed. The helper move is about ownership
of the coordinators, not the underlying normalization or persistence logic.

### 3. Worker stop semantics must remain unchanged

`run_email_legacy_backfill_worker(...)` currently stops on:
- `completed`
- `max_batches`
- `no_progress`

The `no_progress` safety valve is important because it prevents an infinite
loop if a batch returns `completed=False` but scans no rows. That behavior
needs direct helper-path coverage.

### 4. Argument validation must remain narrow and explicit

The pair currently:
- rejects non-integer or non-positive `batch_size`
- rejects non-integer or non-positive `max_batches`
- normalizes `backfill_key`
- keeps `tenant_id` resolution on the DB instance

Those validation and routing rules should remain unchanged.

## Implementation Shape

Add one package runtime module:
- `tldw_Server_API/app/core/DB_Management/media_db/runtime/email_backfill_ops.py`

That module should own only:
- `run_email_legacy_backfill_batch(...)`
- `run_email_legacy_backfill_worker(...)`

Important boundary choices:
- keep `_resolve_email_tenant_id(...)` on the DB instance
- keep metadata/source-derivation helpers on the DB instance
- keep `upsert_email_message_graph(...)` on the DB instance
- keep state helper methods on the DB instance

Then:
- rebind the canonical methods in `media_database_impl.py`
- convert the legacy methods in `Media_DB_v2.py` into live-module compat shells

## Test Strategy

### Ownership / compat-shell regressions

Add direct regressions in
`tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py` for:
- canonical ownership moved off legacy globals for:
  - `run_email_legacy_backfill_batch(...)`
  - `run_email_legacy_backfill_worker(...)`
- legacy `Media_DB_v2` methods delegating through a live `import_module(...)`
  reference

Keep `_resolve_email_tenant_id(...)`, `upsert_email_message_graph(...)`, and
the state helpers out of the regression surface.

### Focused helper-path tests

Add a new helper test file covering:
- `run_email_legacy_backfill_batch(...)` rejecting invalid `batch_size`
- `run_email_legacy_backfill_worker(...)` rejecting invalid `max_batches`
- `run_email_legacy_backfill_worker(...)` stopping with `stop_reason="no_progress"`
  when the batch seam returns `completed=False` and `scanned=0`
- `run_email_legacy_backfill_worker(...)` aggregating counters correctly across
  multiple batch results before completion

These helper tests should use narrow stubs for the worker seam when possible,
not rebuild the full email graph path.

### Broader caller-facing guards

Retain and reuse:
- [test_email_native_stage1.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_email_native_stage1.py)
- [test_helper_script_media_db_imports.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Helper_Scripts/test_helper_script_media_db_imports.py)

The stage-1 suite is the compatibility guard for real backfill semantics. The
new helper tests are the primary proof of canonical rebinding.

## Success Criteria

- canonical ownership for the two in-scope methods moves off legacy globals
- both legacy methods remain present as live-module compat shells
- focused helper-path tests pass
- broader email-native backfill guards stay green
- normalized ownership count drops from `94` to `92`
