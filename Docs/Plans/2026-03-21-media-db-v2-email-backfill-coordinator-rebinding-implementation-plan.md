# Media DB V2 Email Backfill Coordinator Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind the legacy email backfill batch and worker coordinators onto a
package-owned runtime module so the canonical `MediaDatabase` no longer owns
them through legacy globals while preserving resumable checkpoint and worker
contracts.

**Architecture:** Add one runtime helper module for the two backfill
coordinators, rebind the canonical methods in `media_database_impl.py`, and
convert the legacy `Media_DB_v2` methods into live-module compat shells. Keep
tenant resolution, metadata/source derivation, state helpers, and
`upsert_email_message_graph(...)` as existing DB-instance seams for this
tranche.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting canonical ownership moved off legacy
   globals for:
   - `run_email_legacy_backfill_batch(...)`
   - `run_email_legacy_backfill_worker(...)`
2. Add failing compat-shell delegation regressions proving the legacy
   `Media_DB_v2` methods delegate through a package helper module via a live
   `import_module(...)` reference.
3. Keep `_resolve_email_tenant_id(...)`, `upsert_email_message_graph(...)`,
   and the state helper methods out of the regression surface.
4. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'run_email_legacy_backfill_batch or run_email_legacy_backfill_worker'
```

Expected: FAIL

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_email_backfill_ops.py`

**Steps:**
1. Add failing helper-path tests asserting:
   - `run_email_legacy_backfill_batch(...)` rejects invalid `batch_size`
   - `run_email_legacy_backfill_worker(...)` rejects invalid `max_batches`
   - `run_email_legacy_backfill_worker(...)` stops with
     `stop_reason="no_progress"` when the batch seam reports no forward
     progress
   - `run_email_legacy_backfill_worker(...)` aggregates `scanned`, `ingested`,
     `skipped`, and `failed` across multiple batch results before completion
2. Keep these tests narrow: prove coordinator behavior only, not the full
   message upsert graph.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_email_backfill_ops.py
```

Expected: FAIL

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/email_backfill_ops.py`

**Steps:**
1. Move `run_email_legacy_backfill_batch(...)` and
   `run_email_legacy_backfill_worker(...)` into the new runtime module.
2. Preserve current routing through these DB-instance seams:
   - `_resolve_email_tenant_id(...)`
   - `_normalize_email_backfill_key(...)`
   - `_parse_email_backfill_safe_metadata(...)`
   - `_derive_email_backfill_source_fields(...)`
   - `upsert_email_message_graph(...)`
   - `_update_email_backfill_progress(...)`
   - `get_email_legacy_backfill_state(...)`
3. Preserve current validation, stop reasons, and final-state updates.
4. Re-run the Task 2 helper slice.

Expected: PASS

### Task 4: Rebind Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper functions from `email_backfill_ops.py`.
2. Rebind the two canonical methods onto the package-owned helpers.
3. Re-run the Task 1 regression slice.

Expected: canonical ownership assertions pass, compat-shell delegation still red

### Task 5: Convert Legacy Methods To Live-Module Compat Shells

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate each of the two legacy methods through `import_module(...)`.
2. Keep the legacy methods present as compat shells.
3. Leave `_resolve_email_tenant_id(...)`, helper seams, and
   `upsert_email_message_graph(...)` untouched.
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
  tldw_Server_API/tests/DB_Management/test_media_db_email_backfill_ops.py \
  tldw_Server_API/tests/DB_Management/test_email_native_stage1.py \
  tldw_Server_API/tests/Helper_Scripts/test_helper_script_media_db_imports.py \
  -k 'run_email_legacy_backfill_batch or run_email_legacy_backfill_worker or email_legacy_backfill'
```

2. Run Bandit on touched production files
3. Recount ownership
4. Run `git diff --check`

Expected ownership count: `92`

Result: Achieved. Focused helper and ownership slices passed, the broader
backfill bundle passed, Bandit reported no issues on touched production files,
`git diff --check` was clean, and the normalized ownership count dropped from
`94` to `92`.
