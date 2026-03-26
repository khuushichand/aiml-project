# Media DB V2 Scope Resolution Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind `_resolve_scope_ids(...)` onto a package-owned runtime helper
while preserving default fallback, request-scope overrides, and `_scope_cache`
writeback.

**Architecture:** Add a `scope_resolution_ops.py` runtime helper for the single
in-scope helper, rebind the canonical `MediaDatabase` method in
`media_database_impl.py`, and convert the legacy `Media_DB_v2` method into a
live-module compat shell. Keep bootstrap/init and rollback coordinators out of
scope.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add a failing canonical regression asserting
   `MediaDatabase._resolve_scope_ids(...)` no longer resolves globals from
   `Media_DB_v2`.
2. Add a failing compat-shell delegation regression proving the legacy
   `Media_DB_v2._resolve_scope_ids(...)` delegates through
   `scope_resolution_ops.py` via a live `import_module(...)` reference.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_scope_resolution python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k '_resolve_scope_ids'
```

Result: `2 passed, 497 deselected, 6 warnings`

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_scope_resolution_ops.py`

**Steps:**
1. Add a failing helper-path test asserting canonical rebinding to the package
   helper module.
2. Add focused helper tests covering:
   - default-only fallback behavior
   - request-scope override behavior
   - partial-scope fallback behavior
   - non-fatal `get_scope()` exception fallback
   - `_scope_cache` writeback
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_scope_resolution python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_scope_resolution_ops.py
```

Result: `6 passed, 6 warnings`

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/scope_resolution_ops.py`

**Steps:**
1. Move the `_resolve_scope_ids(...)` body into the new runtime module.
2. Preserve:
   - `get_scope()` lookup fallback
   - default org/team fallback behavior
   - partial override behavior
   - `_scope_cache` writeback
3. Re-run the Task 2 helper slice.

Result: helper runtime added and helper-path slice passed

### Task 4: Rebind The Canonical Method

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import `_resolve_scope_ids(...)` from `scope_resolution_ops.py`.
2. Rebind canonical `MediaDatabase._resolve_scope_ids`.
3. Re-run the Task 1 regression slice.

Result: canonical ownership assertion passed

### Task 5: Convert The Legacy Method To A Live-Module Compat Shell

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Replace the legacy method body with a live-module compat shell delegating
   through `import_module(...)`.
2. Preserve the public signature exactly.
3. Re-run the Task 1 regression slice.

Result: compat-shell delegation slice passed

### Task 6: Verify The Tranche

**Status**: Complete

**Files:**
- Reuse modified files only

**Steps:**
1. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_scope_resolution python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_scope_resolution_ops.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_request_scope_isolation.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_sync_utils.py \
  -k '_resolve_scope_ids or scope'
```

2. Run Bandit on touched production files.
3. Recount ownership.
4. Run `git diff --check`.

Expected ownership count: `16`

**Verification Results**
- Pytest tranche bundle: `20 passed, 506 deselected, 6 warnings`
- Bandit on touched production files: `0` results, `0` errors
- Normalized ownership count: `17 -> 16`
- `git diff --check`: clean
