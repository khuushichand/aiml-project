# Media DB V2 Postgres Data-Tables Ensure Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind `_ensure_postgres_data_tables`,
`_ensure_postgres_columns`, and `_ensure_postgres_data_tables_columns` onto
package-owned schema helpers so the canonical `MediaDatabase` no longer owns
that PostgreSQL data-tables ensure cluster through the legacy module, while
preserving the `Media_DB_v2` compat shell and keeping the statement/backfill
ordering unchanged.

**Architecture:** Add one package schema helper module for the data-tables
ensure cluster, rebind the canonical class methods in `media_database_impl.py`,
and convert the legacy `Media_DB_v2` methods into live-module compat shells.
Verify ordering and repair behavior with focused helper tests and reuse the
existing PostgreSQL migration coverage as the broader guard.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting:
   - canonical `MediaDatabase._ensure_postgres_data_tables` is no longer
     legacy-owned
   - canonical `MediaDatabase._ensure_postgres_columns` is no longer
     legacy-owned
   - canonical `MediaDatabase._ensure_postgres_data_tables_columns` is no
     longer legacy-owned
   - legacy `_LegacyMediaDatabase` methods delegate through a package helper
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k '_ensure_postgres_data_tables or _ensure_postgres_columns or _ensure_postgres_data_tables_columns'
```

Expected: FAIL

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py`

**Steps:**
1. Add failing unit tests asserting:
   - `_ensure_postgres_data_tables(...)` runs create-table statements, then the
     late-column ensure, then non-table statements
   - `_ensure_postgres_columns(...)` only adds missing columns
   - `_ensure_postgres_data_tables_columns(...)` runs the late-column/backfill/index flow
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  -k 'postgres_data_tables_structures'
```

Expected: FAIL

### Task 3: Add Package Schema Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/schema/postgres_data_table_structures.py`

**Steps:**
1. Add package-owned helpers for the three methods
2. Preserve existing ordering and warning-only behavior
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
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py \
  -k '_ensure_postgres_data_tables or _ensure_postgres_columns or _ensure_postgres_data_tables_columns or postgres_data_tables_structures or workspace_tag'
```

2. Run Bandit on touched production files
3. Recount ownership
4. Run `git diff --check`

Expected ownership count: `181`

Actual close-out:
- ownership slice: `6 passed`
- helper slice: `3 passed`
- broader bundle: `9 passed, 1 skipped, 217 deselected, 6 warnings`
- Bandit on touched production files: no issues
- ownership recount: `184 -> 181`
- `git diff --check`: clean
