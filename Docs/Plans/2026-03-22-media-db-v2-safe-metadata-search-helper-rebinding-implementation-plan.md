# Media DB V2 Safe Metadata Search Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind `search_by_safe_metadata(...)` onto a package-owned runtime
helper while preserving identifier-join behavior, standard media constraints,
grouped counting, sorting, and paging semantics.

**Architecture:** Add a `safe_metadata_search_ops.py` runtime helper for the
single in-scope query builder, rebind the canonical `MediaDatabase` method in
`media_database_impl.py`, and convert the legacy `Media_DB_v2` method into a
live-module compat shell. Keep rollback and bootstrap/init coordinators out of
scope.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add a failing canonical regression asserting
   `MediaDatabase.search_by_safe_metadata(...)` no longer resolves globals from
   `Media_DB_v2`.
2. Add a failing compat-shell delegation regression proving the legacy
   `Media_DB_v2.search_by_safe_metadata(...)` delegates through
   `safe_metadata_search_ops.py` via a live `import_module(...)` reference.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_safe_metadata_search python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'search_by_safe_metadata'
```

Result: `2 passed, 495 deselected, 6 warnings`

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_safe_metadata_search_ops.py`

**Steps:**
1. Add a failing helper-path test asserting canonical rebinding to the package
   helper module.
2. Add focused helper tests covering:
   - identifier-filter join behavior
   - JSON fallback behavior for non-identifier fields
   - grouped vs ungrouped count/result query shapes
   - zero-result fast return
   - sorting and limit/offset parameter placement
   - wrapped `DatabaseError` behavior on query failure
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_safe_metadata_search python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_safe_metadata_search_ops.py
```

Result: `5 passed, 6 warnings`

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/safe_metadata_search_ops.py`

**Steps:**
1. Move the `search_by_safe_metadata(...)` body into the new runtime module.
2. Preserve:
   - identifier-join vs JSON fallback behavior
   - keyword/date/text/media-type constraints
   - grouped counting and result-query behavior
   - sorting before pagination
   - read-only `DatabaseError` wrapping
3. Re-run the Task 2 helper slice.

Result: helper runtime added and helper-path slice passed

### Task 4: Rebind The Canonical Method

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import `search_by_safe_metadata(...)` from `safe_metadata_search_ops.py`.
2. Rebind canonical `MediaDatabase.search_by_safe_metadata`.
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
PYTHONPYCACHEPREFIX=/tmp/pycache_safe_metadata_search python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_safe_metadata_search_ops.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/MediaDB2/test_sqlite_db.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/MediaDB2/test_safe_metadata_endpoints.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/MediaDB2/test_metadata_endpoints_more.py \
  -k 'search_by_safe_metadata or metadata_search or by_identifier'
```

2. Run Bandit on touched production files.
3. Recount ownership.
4. Run `git diff --check`.

Expected ownership count: `17`

**Verification Results**
- Pytest tranche bundle: `15 passed, 539 deselected, 6 warnings`
- Bandit on touched production files: `0` results, `0` errors
- Normalized ownership count: `18 -> 17`
- `git diff --check`: clean
