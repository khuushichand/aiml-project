# Media DB V2 Sync Log Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind `get_sync_log_entries`, `delete_sync_log_entries`, and
`delete_sync_log_entries_before` onto package-owned runtime helpers so the
canonical `MediaDatabase` no longer owns that sync-log cluster through legacy
globals, while preserving the `Media_DB_v2` compat shell and keeping sync-log
behavior unchanged.

**Architecture:** Add one package runtime helper module for the three sync-log
methods, rebind the canonical class methods in `media_database_impl.py`, and
convert the legacy `Media_DB_v2` methods into live-module compat shells. Use
direct ownership/delegation regressions plus focused helper-path tests for
payload decode/fallback, parameter ordering, and delete validation before
rebinding, then verify against the existing Media DB sync-log behavior suite.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting:
   - canonical `MediaDatabase.get_sync_log_entries` is no longer legacy-owned
   - canonical `MediaDatabase.delete_sync_log_entries` is no longer
     legacy-owned
   - canonical `MediaDatabase.delete_sync_log_entries_before` is no longer
     legacy-owned
   - legacy `_LegacyMediaDatabase` methods delegate through a package helper
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'get_sync_log_entries or delete_sync_log_entries or delete_sync_log_entries_before'
```

Expected: FAIL

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_sync_log_ops.py`

**Steps:**
1. Add failing helper-path tests asserting:
   - `get_sync_log_entries(...)` decodes valid payload JSON, converts malformed
     payload JSON to `None`, and preserves `since_change_id` plus optional
     `limit` parameter ordering
   - `delete_sync_log_entries(...)` returns `0` for an empty list, rejects
     non-integer ids, and executes a placeholder-based delete through
     `transaction()` plus `_execute_with_connection(...)`
   - `delete_sync_log_entries_before(...)` rejects negative thresholds and
     executes the expected threshold delete through the transaction path
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_sync_log_ops.py
```

Expected: FAIL

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/sync_log_ops.py`

**Steps:**
1. Add package-owned helpers for the three sync-log methods
2. Preserve current:
   - ascending `change_id` ordering
   - payload JSON decode/fallback behavior
   - optional `LIMIT` behavior
   - empty-list and validation behavior for deletes
   - transaction-backed delete execution and rowcount handling
3. Re-run the Task 2 helper slice

Expected: PASS

### Task 4: Rebind Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper functions
2. Rebind the three canonical methods
3. Re-run the Task 1 regression slice

Expected: canonical ownership assertions pass, compat-shell delegation still red

### Task 5: Convert Legacy Helpers To Live-Module Compat Shells

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate the three legacy methods through `import_module(...)`
2. Keep the legacy methods present as compat shells
3. Re-run the Task 1 regression slice

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
  tldw_Server_API/tests/DB_Management/test_media_db_sync_log_ops.py \
  tldw_Server_API/tests/MediaDB2/test_sqlite_db.py \
  -k 'get_sync_log_entries or delete_sync_log_entries or delete_sync_log_entries_before or sync_log_ops'
```

2. Run Bandit on touched production files
3. Recount ownership
4. Run `git diff --check`

Expected ownership count: `148`

Actual close-out:
- ownership slice: `6 passed, 227 deselected, 6 warnings`
- helper slice: `4 passed, 6 warnings`
- broader sync-log tranche bundle: `18 passed, 261 deselected, 6 warnings`
- Bandit on touched production files: no issues
- ownership recount: `151 -> 148`
- `git diff --check`: clean
