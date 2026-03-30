# Media DB V2 Media Lifecycle Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind `soft_delete_media`, `share_media`, `unshare_media`,
`get_media_visibility`, `mark_as_trash`, and `restore_from_trash` onto
package-owned runtime helpers so the canonical `MediaDatabase` no longer owns
that media lifecycle cluster through legacy globals, while preserving the
`Media_DB_v2` compat shell and keeping lifecycle behavior unchanged.

**Architecture:** Add one package runtime helper module for the six lifecycle
methods, rebind the canonical class methods in `media_database_impl.py`, and
convert the legacy `Media_DB_v2` methods into live-module compat shells. Use
direct ownership/delegation regressions plus focused helper-path tests for
soft-delete cascade behavior, visibility transitions, and trash/restore sync
behavior before rebinding, then verify against the existing lifecycle and
caller-facing integration tests.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Not Started

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting:
   - canonical `MediaDatabase.soft_delete_media` is no longer legacy-owned
   - canonical `MediaDatabase.share_media` is no longer legacy-owned
   - canonical `MediaDatabase.unshare_media` is no longer legacy-owned
   - canonical `MediaDatabase.get_media_visibility` is no longer legacy-owned
   - canonical `MediaDatabase.mark_as_trash` is no longer legacy-owned
   - canonical `MediaDatabase.restore_from_trash` is no longer legacy-owned
   - legacy `_LegacyMediaDatabase` methods delegate through a package helper
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'soft_delete_media or share_media or unshare_media or get_media_visibility or mark_as_trash or restore_from_trash'
```

Expected: FAIL

### Task 2: Add Helper-Path Red Tests

**Status**: Not Started

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_media_lifecycle_ops.py`

**Steps:**
1. Add failing helper-path tests asserting:
   - `soft_delete_media(..., cascade=True)` still unlinks keywords, soft-deletes
     child rows, and calls `_delete_fts_media(...)` through the instance seam
   - `share_media(...)` rejects invalid scope combinations and writes expected
     visibility/org/team values
   - `unshare_media(...)` routes through the share path to restore `personal`
     visibility
   - `get_media_visibility(...)` returns the expected payload and `None` when
     the media row is absent
   - `mark_as_trash(...)` and `restore_from_trash(...)` preserve transaction
     and sync-update behavior
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_media_lifecycle_ops.py
```

Expected: FAIL

### Task 3: Add Package Runtime Helper Module

**Status**: Not Started

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/media_lifecycle_ops.py`

**Steps:**
1. Add package-owned helpers for the six lifecycle methods
2. Preserve current:
   - keyword unlinking and child-row cascade behavior
   - `_delete_fts_media(...)` instance-seam usage
   - post-commit vector invalidation behavior in `soft_delete_media(...)`
   - visibility validation and update payload behavior
   - trash/restore sync event behavior
   - `unshare_media(...)` as a thin wrapper over the share path
3. Re-run the Task 2 helper slice

Expected: PASS

### Task 4: Rebind Canonical Methods

**Status**: Not Started

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper functions
2. Rebind the six canonical lifecycle methods
3. Re-run the Task 1 regression slice

Expected: canonical ownership assertions pass, compat-shell delegation still red

### Task 5: Convert Legacy Helpers To Live-Module Compat Shells

**Status**: Not Started

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate the six legacy methods through `import_module(...)`
2. Keep the legacy methods present as compat shells
3. Re-run the Task 1 regression slice

Expected: PASS

### Task 6: Verify The Tranche

**Status**: Not Started

**Files:**
- Reuse modified files only

**Steps:**
1. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  tldw_Server_API/tests/DB_Management/test_media_db_media_lifecycle_ops.py \
  tldw_Server_API/tests/MediaDB2/test_sqlite_db.py \
  tldw_Server_API/tests/DB_Management/test_email_native_stage1.py \
  tldw_Server_API/tests/DB_Management/test_db_manager_wrappers.py \
  tldw_Server_API/tests/External_Sources/test_sync_coordinator.py \
  -k 'soft_delete_media or share_media or unshare_media or get_media_visibility or mark_as_trash or restore_from_trash or media_lifecycle_ops'
```

2. Run Bandit on touched production files
3. Recount ownership
4. Run `git diff --check`

Expected ownership count: `139`
