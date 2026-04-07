# Media DB V2 Data Table Content Replace Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind `replace_data_table_contents(...)` onto a package-owned runtime
helper while preserving owner validation, child replacement semantics,
transaction-bound writes, and source-preservation behavior.

**Architecture:** Add a `data_table_replace_ops.py` runtime helper owning the
single in-scope coordinator, rebind the canonical `MediaDatabase` method in
`media_database_impl.py`, and convert the legacy `Media_DB_v2` method into a
live-module compat shell. Keep generation persistence, search, rollback, and
bootstrap coordinators out of scope.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing canonical regressions asserting
   `MediaDatabase.replace_data_table_contents(...)` no longer resolves its
   globals from `Media_DB_v2`.
2. Add a failing compat-shell delegation regression proving the legacy
   `Media_DB_v2.replace_data_table_contents(...)` delegates through
   `data_table_replace_ops.py` via a live `import_module(...)` reference.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_data_table_replace python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'replace_data_table_contents'
```

Expected: FAIL

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_data_table_replace_ops.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_data_tables_crud.py`

**Steps:**
1. Add a failing helper-path test asserting canonical rebinding to the package
   helper module.
2. Add focused helper tests covering:
   - blank owner rejection
   - missing columns rejection
   - `rows is None` rejection
   - owner mismatch rejection
   - generated ids / row hashes and transaction-bound replacement calls
3. Add one real SQLite CRUD test proving content replacement:
   - replaces active columns and rows
   - leaves prior columns and rows soft-deleted
   - preserves existing sources
4. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_data_table_replace python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_data_table_replace_ops.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_data_tables_crud.py \
  -k 'replace_data_table_contents'
```

Expected: FAIL

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/data_table_replace_ops.py`

**Steps:**
1. Move the `replace_data_table_contents(...)` body into the new runtime
   module.
2. Preserve:
   - explicit owner requirement
   - row/column packing and generated ids / hashes
   - transaction-bound soft-delete plus `execute_many(...)` reinserts
   - no mutation of sources or table metadata
3. Re-run the Task 2 helper slice.

Expected: helper slice still red only for canonical binding

### Task 4: Rebind The Canonical Method

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import `replace_data_table_contents(...)` from `data_table_replace_ops.py`.
2. Rebind canonical `MediaDatabase.replace_data_table_contents`.
3. Re-run the Task 1 regression slice.

Expected: canonical ownership assertion passes, compat-shell delegation still red

### Task 5: Convert The Legacy Method To A Live-Module Compat Shell

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Replace the legacy method body with a live-module compat shell delegating
   through `import_module(...)`.
2. Preserve the public signature exactly.
3. Re-run the Task 1 regression slice.

Expected: PASS

### Task 6: Verify The Tranche

**Status**: Complete

**Files:**
- Reuse modified files only

**Steps:**
1. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_data_table_replace python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_data_table_replace_ops.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_data_tables_crud.py \
  -k 'replace_data_table_contents'
```

2. Run Bandit on touched production files.
3. Recount ownership.
4. Run `git diff --check`.

Expected ownership count: `19`

**Verification Results**:
- Focused ownership slice: `2 passed, 491 deselected, 6 warnings`
- Focused helper/CRUD slice: `7 passed, 6 deselected, 6 warnings`
- Tranche pytest bundle: `9 passed, 497 deselected, 6 warnings`
- Bandit on touched production files: `0` results, `0` errors
- Normalized ownership count: `20 -> 19`
- `git diff --check`: clean
