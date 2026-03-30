# Media DB V2 Data Table Internal Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind the internal data-table helper cluster onto package-owned
runtime helpers so the canonical `MediaDatabase` no longer owns
`_resolve_data_tables_owner`, `_resolve_data_table_write_client_id`,
`_get_data_table_owner_client_id`, `_soft_delete_data_table_children`, or
`_normalize_data_table_row_json` through legacy globals, while preserving
behavior and the `Media_DB_v2` compat shell.

**Architecture:** Add one package runtime helper module for the five internal
data-table helpers, rebind the canonical class methods in
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
   - canonical `MediaDatabase._resolve_data_tables_owner` is no longer
     legacy-owned
   - canonical `MediaDatabase._resolve_data_table_write_client_id` is no
     longer legacy-owned
   - canonical `MediaDatabase._get_data_table_owner_client_id` is no longer
     legacy-owned
   - canonical `MediaDatabase._soft_delete_data_table_children` is no longer
     legacy-owned
   - canonical `MediaDatabase._normalize_data_table_row_json` is no longer
     legacy-owned
   - legacy `_LegacyMediaDatabase` methods delegate through a package helper
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'resolve_data_tables_owner or resolve_data_table_write_client_id or get_data_table_owner_client_id or soft_delete_data_table_children or normalize_data_table_row_json'
```

Expected: FAIL

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_data_table_helper_ops.py`

**Steps:**
1. Add failing helper-path tests asserting:
   - `_resolve_data_tables_owner(...)` prefers explicit owner, falls back to
     non-admin request scope, and returns `None` for admin/no-scope cases
   - `_resolve_data_table_write_client_id(...)` prefers explicit owner,
     otherwise reads `client_id` from the table row, and raises the existing
     `InputError` codes for missing row or missing owner
   - `_get_data_table_owner_client_id(...)` returns the string client id or
     `None`
   - `_normalize_data_table_row_json(...)` preserves valid JSON and raises on
     invalid JSON, non-object keyed payloads, and unknown column ids
   - `_soft_delete_data_table_children(...)` updates all three child tables
     and preserves owner-filter behavior
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_data_table_helper_ops.py
```

Expected: FAIL

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/data_table_helper_ops.py`

**Steps:**
1. Add package-owned helpers for the five internal data-table methods
2. Preserve current:
   - explicit-owner precedence and request-scope fallback
   - table-owner lookup and `InputError("data_table_not_found")` /
     `InputError("data_table_owner_missing")` behavior
   - fetch-contract behavior for `_get_data_table_owner_client_id(...)`
   - row JSON parsing and unknown-column validation semantics
   - three-table child soft-delete fanout and owner-filter propagation
3. Re-run the Task 2 helper slice

Expected: PASS

### Task 4: Rebind Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper functions
2. Rebind the five canonical helper methods
3. Re-run the Task 1 regression slice

Expected: canonical ownership assertions pass, compat-shell delegation still red

### Task 5: Convert Legacy Helpers To Live-Module Compat Shells

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate the five legacy helper methods through `import_module(...)`
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
  tldw_Server_API/tests/DB_Management/test_media_db_data_table_helper_ops.py \
  tldw_Server_API/tests/DB_Management/test_data_tables_crud.py \
  tldw_Server_API/tests/DataTables/test_data_tables_api.py \
  tldw_Server_API/tests/DataTables/test_data_tables_worker.py \
  tldw_Server_API/tests/DataTables/test_data_tables_export.py \
  -k 'resolve_data_tables_owner or resolve_data_table_write_client_id or get_data_table_owner_client_id or soft_delete_data_table_children or normalize_data_table_row_json or data_table'
```

2. Run Bandit on touched production files
3. Recount ownership
4. Run `git diff --check`

Expected ownership count: `134`

Observed close-out:
- `python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py tldw_Server_API/tests/DB_Management/test_media_db_data_table_helper_ops.py tldw_Server_API/tests/DB_Management/test_data_tables_crud.py tldw_Server_API/tests/DataTables/test_data_tables_api.py tldw_Server_API/tests/DataTables/test_data_tables_worker.py tldw_Server_API/tests/DataTables/test_data_tables_export.py -k 'resolve_data_tables_owner or resolve_data_table_write_client_id or get_data_table_owner_client_id or soft_delete_data_table_children or normalize_data_table_row_json or data_table'` -> `52 passed, 245 deselected, 6 warnings`
- `python -m bandit -r tldw_Server_API/app/core/DB_Management/media_db/runtime/data_table_helper_ops.py tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py tldw_Server_API/app/core/DB_Management/Media_DB_v2.py` -> no issues identified
- `python Helper_Scripts/checks/media_db_runtime_ownership_count.py` -> `134`
- `git diff --check` -> clean
