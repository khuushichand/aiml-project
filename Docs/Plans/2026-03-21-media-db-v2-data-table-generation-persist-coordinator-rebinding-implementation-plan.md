# Media DB V2 Data Table Generation Persist Coordinator Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind the live `persist_data_table_generation(...)` coordinator onto
package-owned runtime helpers so the canonical `MediaDatabase` no longer owns
that method through legacy globals, while preserving behavior and the
`Media_DB_v2` compat shell.

**Architecture:** Add one package runtime helper module for
`persist_data_table_generation(...)`, rebind the canonical class method in
`media_database_impl.py`, and convert the legacy `Media_DB_v2` method into a
live-module compat shell. Lock the seam first with ownership/delegation
regressions and focused helper-path tests that pin owner validation, source
preservation/replacement semantics, and `generation_model` update behavior.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting:
   - canonical `persist_data_table_generation(...)` is no longer legacy-owned
   - legacy `_LegacyMediaDatabase.persist_data_table_generation(...)`
     delegates through a package helper module
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'persist_data_table_generation'
```

Expected: FAIL

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_data_table_generation_ops.py`

**Steps:**
1. Add failing helper-path tests asserting:
   - blank `owner_user_id` raises `InputError("owner_user_id is required")`
   - owner mismatch raises `InputError("data_table_owner_mismatch")`
   - `sources=None` preserves existing sources
   - `sources=[]` clears existing sources
   - `generation_model=None` preserves the existing stored model
   - successful persist returns the refreshed table row with updated metadata
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_data_table_generation_ops.py
```

Expected: FAIL

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/data_table_generation_ops.py`

**Steps:**
1. Add a package-owned runtime helper for `persist_data_table_generation(...)`
2. Preserve current:
   - owner validation and owner-mismatch behavior
   - `sources is None` versus `sources == []` semantics
   - row/column/source packing and hash generation
   - `generation_model` update behavior
   - refreshed-row return behavior
3. Re-run the Task 2 helper slice

Expected: PASS

### Task 4: Rebind Canonical Method

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper function
2. Rebind canonical `persist_data_table_generation(...)`
3. Re-run the Task 1 regression slice

Expected: canonical ownership assertion passes, compat-shell delegation still red

### Task 5: Convert Legacy Method To Live-Module Compat Shell

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate legacy `persist_data_table_generation(...)` through `import_module(...)`
2. Keep the legacy method present as a compat shell
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
  tldw_Server_API/tests/DB_Management/test_media_db_data_table_generation_ops.py \
  tldw_Server_API/tests/DB_Management/test_data_tables_crud.py \
  tldw_Server_API/tests/DataTables/test_data_tables_api.py \
  tldw_Server_API/tests/DataTables/test_data_tables_worker.py \
  -k 'persist_data_table_generation or data_table'
```

2. Run Bandit on touched production files
3. Recount ownership
4. Run `git diff --check`

Expected ownership count: `116`
