# Media DB V2 Data Table Child-Content Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind the bounded data-table child-content layer onto package-owned
runtime helpers so the canonical `MediaDatabase` no longer owns the child
summary/read/write/delete methods through legacy globals.

**Architecture:** Add one package runtime helper module for the 10 child-content
methods, rebind the canonical class methods in `media_database_impl.py`, and
convert the legacy `Media_DB_v2` methods into live-module compat shells.
Preserve owner-gating, row validation, list ordering, and summary-count
behavior. Defer `replace_data_table_contents(...)` and
`persist_data_table_generation(...)`.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting canonical ownership moved off legacy for:
   - `get_data_table_counts`
   - `insert_data_table_columns`
   - `list_data_table_columns`
   - `soft_delete_data_table_columns`
   - `insert_data_table_rows`
   - `list_data_table_rows`
   - `soft_delete_data_table_rows`
   - `insert_data_table_sources`
   - `list_data_table_sources`
   - `soft_delete_data_table_sources`
2. Add failing regressions asserting the legacy `_LegacyMediaDatabase` methods
   delegate through a package helper module.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'get_data_table_counts or insert_data_table_columns or list_data_table_columns or soft_delete_data_table_columns or insert_data_table_rows or list_data_table_rows or soft_delete_data_table_rows or insert_data_table_sources or list_data_table_sources or soft_delete_data_table_sources'
```

Expected: FAIL

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_data_table_child_ops.py`

**Steps:**
1. Add failing helper-path tests asserting:
   - `get_data_table_counts(...)` aggregates column/source counts correctly
   - insert methods return `0` when explicit owner-gating fails
   - `insert_data_table_rows(...)` raises `data_table_columns_required` when
     key validation is enabled and no columns exist
   - `list_data_table_rows(...)` preserves limit/offset normalization and query
     ordering
   - the three soft-delete child methods return rowcount from the update cursor
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_data_table_child_ops.py
```

Expected: FAIL

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/data_table_child_ops.py`

**Steps:**
1. Add package-owned runtime helpers for the 10 child-content methods.
2. Preserve current:
   - owner-gating and write-client resolution
   - row validation through `_normalize_data_table_row_json(...)`
   - list ordering and limit/offset coercion
   - child summary aggregation behavior
3. Re-run the Task 2 helper slice.

Expected: PASS

### Task 4: Rebind Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper functions.
2. Rebind the 10 canonical methods.
3. Re-run the Task 1 regression slice.

Expected: canonical ownership assertions pass, compat-shell delegation still red

### Task 5: Convert Legacy Methods To Live-Module Compat Shells

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate the 10 legacy methods through `import_module(...)`.
2. Keep the legacy methods present as compat shells.
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
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  tldw_Server_API/tests/DB_Management/test_media_db_data_table_child_ops.py \
  tldw_Server_API/tests/DB_Management/test_data_tables_crud.py \
  tldw_Server_API/tests/DataTables/test_data_tables_api.py \
  tldw_Server_API/tests/DataTables/test_data_tables_worker.py \
  tldw_Server_API/tests/DataTables/test_data_tables_export.py \
  -k 'get_data_table_counts or insert_data_table_columns or list_data_table_columns or soft_delete_data_table_columns or insert_data_table_rows or list_data_table_rows or soft_delete_data_table_rows or insert_data_table_sources or list_data_table_sources or soft_delete_data_table_sources or data_table'
```

2. Run Bandit on touched production files.
3. Recount ownership.
4. Run `git diff --check`.

Expected ownership count: `117`
