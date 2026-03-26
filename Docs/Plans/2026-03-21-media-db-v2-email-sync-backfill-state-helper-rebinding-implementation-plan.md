# Media DB V2 Email Sync Backfill State Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind the email sync-state and backfill-state helper layer onto a
package-owned runtime module so the canonical `MediaDatabase` no longer owns
those methods through legacy globals, while preserving worker-facing and
API-facing email-state contracts.

**Architecture:** Add one runtime helper module for the email sync/backfill
state layer, rebind the canonical methods in `media_database_impl.py`, and
convert the legacy `Media_DB_v2` methods into live-module compat shells. Keep
`_resolve_email_tenant_id(...)` and the backfill batch/worker coordinators
legacy-owned for this tranche, and lock the state semantics first with focused
helper tests plus caller-facing worker/API guards.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting canonical ownership moved off legacy
   globals for:
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
2. Add failing compat-shell delegation regressions proving the legacy
   `Media_DB_v2` methods delegate through a package helper module via a live
   `import_module(...)` reference.
3. Keep `_resolve_email_tenant_id(...)` and the batch/worker coordinators out
   of the regression surface for this tranche.
4. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'email_sync_state or email_backfill_state or resolve_email_sync_source_row_id or update_email_backfill_progress'
```

Expected: FAIL

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_email_state_ops.py`

**Steps:**
1. Add failing helper-path tests asserting:
   - `_resolve_email_sync_source_row_id(...)` returns `None` when the source is
     absent and `create_if_missing=False`
   - `_resolve_email_sync_source_row_id(...)` creates and returns a source row
     id when `create_if_missing=True`
   - `mark_email_sync_run_started(...)`, `mark_email_sync_run_failed(...)`, and
     `mark_email_sync_run_succeeded(...)` preserve the current retry/cursor
     semantics
   - `_update_email_backfill_progress(...)` increments counters and only
     replaces `last_error` when a non-empty error is provided
   - `get_email_legacy_backfill_state(...)` returns normalized state after
     helper-driven updates
2. Keep these tests narrow: prove sync/backfill state helper behavior only, not
   the higher-level batch/worker coordinators.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_email_state_ops.py
```

Expected: FAIL

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/email_state_ops.py`

**Steps:**
1. Move the 10 in-scope sync-state/backfill-state helper bodies into the new
   runtime module.
2. Preserve existing SQL, return shapes, and retry/cursor/error semantics.
3. Keep `_resolve_email_tenant_id(...)` calls routed through the DB instance.
4. Do not modify `run_email_legacy_backfill_batch(...)` or
   `run_email_legacy_backfill_worker(...)` in this task.
5. Re-run the Task 2 helper slice.

Expected: PASS

### Task 4: Rebind Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper functions from `email_state_ops.py`.
2. Rebind the 10 canonical methods onto the package-owned helpers.
3. Re-run the Task 1 regression slice.

Expected: canonical ownership assertions pass, compat-shell delegation still red

### Task 5: Convert Legacy Methods To Live-Module Compat Shells

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate each of the 10 legacy methods through `import_module(...)`.
2. Keep the legacy methods present as compat shells.
3. Leave `_resolve_email_tenant_id(...)`,
   `run_email_legacy_backfill_batch(...)`, and
   `run_email_legacy_backfill_worker(...)` untouched.
4. Re-run the Task 1 regression slice.

Expected: PASS

### Task 6: Verify The Tranche

**Status**: Complete

**Files:**
- Reuse modified files only

**Steps:**
1. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  tldw_Server_API/tests/DB_Management/test_media_db_email_state_ops.py \
  tldw_Server_API/tests/DB_Management/test_email_native_stage1.py \
  tldw_Server_API/tests/External_Sources/test_policy_and_connectors.py \
  tldw_Server_API/tests/MediaIngestion_NEW/integration/test_email_search_endpoint.py \
  -k 'email_sync_state or email_backfill_state or resolve_email_sync_source_row_id or update_email_backfill_progress or legacy_backfill or connectors'
```

2. Run Bandit on touched production files
3. Recount ownership
4. Run `git diff --check`

Expected ownership count: `104`
