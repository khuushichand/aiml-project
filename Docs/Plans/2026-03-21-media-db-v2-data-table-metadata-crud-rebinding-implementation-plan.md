# Media DB V2 Data Table Metadata CRUD Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind the bounded data-table metadata CRUD layer onto package-owned
runtime helpers so the canonical `MediaDatabase` no longer owns
`create_data_table`, `get_data_table`, `get_data_table_by_uuid`,
`list_data_tables`, `count_data_tables`, `update_data_table`, or
`soft_delete_data_table` through legacy globals, while preserving behavior and
the `Media_DB_v2` compat shell.

**Architecture:** Add one package runtime helper module for the seven
metadata CRUD methods, rebind the canonical class methods in
`media_database_impl.py`, and convert the legacy `Media_DB_v2` methods into
live-module compat shells. Lock the seam first with direct
ownership/delegation regressions and focused helper-path tests, then verify
against the existing data-table CRUD, API, worker, and export suites.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting:
   - canonical `create_data_table` is no longer legacy-owned
   - canonical `get_data_table` is no longer legacy-owned
   - canonical `get_data_table_by_uuid` is no longer legacy-owned
   - canonical `list_data_tables` is no longer legacy-owned
   - canonical `count_data_tables` is no longer legacy-owned
   - canonical `update_data_table` is no longer legacy-owned
   - canonical `soft_delete_data_table` is no longer legacy-owned
   - legacy `_LegacyMediaDatabase` methods delegate through a package helper
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'create_data_table or get_data_table or get_data_table_by_uuid or list_data_tables or count_data_tables or update_data_table or soft_delete_data_table'
```

Expected: FAIL

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_data_table_metadata_ops.py`

**Steps:**
1. Add failing helper-path tests asserting:
   - `create_data_table(...)` rejects invalid string `column_hints`
   - `update_data_table(...)` rejects invalid string `column_hints`
   - `get_data_table_by_uuid("")` returns `None`
   - `list_data_tables(...)` and `count_data_tables(...)` preserve filter
     parity for owner/status/search/workspace/include_deleted
   - `soft_delete_data_table(...)` only calls
     `_soft_delete_data_table_children(...)` when the parent update rowcount is
     nonzero
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_data_table_metadata_ops.py
```

Expected: FAIL

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/data_table_metadata_ops.py`

**Steps:**
1. Add package-owned runtime helpers for the seven metadata CRUD methods
2. Preserve current:
   - `column_hints` validation/serialization behavior
   - owner-filter and admin behavior
   - list/count filter parity
   - `soft_delete_data_table(...)` transaction and child-cascade gating
3. Re-run the Task 2 helper slice

Expected: PASS

### Task 4: Rebind Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper functions
2. Rebind the seven canonical methods
3. Re-run the Task 1 regression slice

Expected: canonical ownership assertions pass, compat-shell delegation still red

### Task 5: Convert Legacy Methods To Live-Module Compat Shells

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate the seven legacy methods through `import_module(...)`
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
  tldw_Server_API/tests/DB_Management/test_media_db_data_table_metadata_ops.py \
  tldw_Server_API/tests/DB_Management/test_data_tables_crud.py \
  tldw_Server_API/tests/DataTables/test_data_tables_api.py \
  tldw_Server_API/tests/DataTables/test_data_tables_worker.py \
  tldw_Server_API/tests/DataTables/test_data_tables_export.py \
  -k 'create_data_table or get_data_table or get_data_table_by_uuid or list_data_tables or count_data_tables or update_data_table or soft_delete_data_table or data_table'
```

2. Run Bandit on touched production files
3. Recount ownership
4. Run `git diff --check`

Expected ownership count: `127`
